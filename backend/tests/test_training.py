"""What the training engine must keep doing.

Each of these is a bug that actually happened. The comment on a test says
which one, because a test whose reason is forgotten gets deleted the first
time it is inconvenient.

    ./.venv/bin/python tests/test_training.py
"""
import itertools
import json
from datetime import datetime, timedelta, timezone
import os
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import Clock, KNEE_SYMPTOMS, at, fresh, log_symptom   # noqa: E402

import app.analysis.training_program as tp                          # noqa: E402
from app.data import programs as P                                  # noqa: E402
from app.data import stretches as S                                 # noqa: E402
from app.data.exercise_library import EFFORT, LIBRARY               # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    if condition:
        print(f"  pass  {name}")
    else:
        FAILURES.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def build(db, uid, **kw):
    with mock.patch.object(tp, "datetime", Clock):
        return tp.build_session(db, uid, tz_offset=0, **kw)


# ──────────────────────────────────────────────────────────────────────────
def test_catalogue_is_consistent():
    """Names drift apart when the same thing is written down twice."""
    names = {r[0].strip().lower(): r for r in LIBRARY}
    missing = []
    for focus, prog in P.PROGRAMS.items():
        for ph, spec in prog["phases"].items():
            for day, blocks in spec["days"].items():
                for b in blocks:
                    if b.name.strip().lower() not in names:
                        missing.append(f"{focus} p{ph}{day}: {b.name}")
    for group in (P.CONDITIONING.values(), [P.DAILY]):
        for blocks in group:
            for b in blocks:
                if b.name.strip().lower() not in names:
                    missing.append(f"conditioning/daily: {b.name}")
    check("every prescribed exercise exists in the library", not missing, str(missing[:3]))

    # The effort table lived in a migration script and the seed never saw it,
    # so new accounts lost floor_based and did floor work on a headache day.
    unset = [r[0] for r in LIBRARY if r[0] not in EFFORT]
    check("every exercise has an effort value", not unset, str(unset[:5]))
    bad_keys = [k for k in EFFORT if k.strip().lower() not in names]
    check("no effort key fails to match a library name", not bad_keys, str(bad_keys[:5]))

    wrong = []
    for focus, prog in P.PROGRAMS.items():
        for ph, spec in prog["phases"].items():
            for day, blocks in spec["days"].items():
                for b in blocks:
                    row = names.get(b.name.strip().lower())
                    if not row:
                        continue
                    if b.scheme == "iso" and not row[5]:
                        wrong.append(f"{b.name} iso but not isometric")
                    if b.scheme in ("reps", "load") and row[5]:
                        wrong.append(f"{b.name} {b.scheme} but isometric")
                    if b.low > b.high:
                        wrong.append(f"{b.name} low>high")
    check("scheme matches the exercise it names", not wrong, str(wrong[:3]))


def test_session_invariants():
    """The matrix that keeps finding things: modes, days, symptoms, kit."""
    db, uid, byn, sy = fresh()
    at(31)
    bad = []
    n = 0
    for symptom, level in [(None, 0), ("Headache", 2), ("Fatigue", 3),
                           ("Knee pain - left lateral", 2),
                           ("Knee swelling - left", 1), ("Knee giving way - left", 1)]:
        log_symptom(db, uid, sy.get(symptom), level)
        for mode, day, kind in itertools.product(
                ("full", "reduced", "gentle"), ("A", "B", "C"), ("strength", "practice")):
            n += 1
            tag = f"{symptom or 'none'}/{mode}/{day}/{kind}"
            try:
                r = build(db, uid, day=day, mode=mode, kind=kind)
            except Exception as exc:                        # noqa: BLE001
                bad.append(f"{tag} raised {type(exc).__name__}: {exc}")
                continue
            json.dumps(r, default=str)
            if not r["blocks"]:
                bad.append(f"{tag} empty")
            ids = [b["exercise_id"] for b in r["blocks"]]
            if len(ids) != len(set(ids)):
                bad.append(f"{tag} duplicate exercise")
            # Pelvic floor is daily; the novelty cap used to ration it away.
            if not any(b["group"] == "pelvic" for b in r["blocks"]):
                bad.append(f"{tag} no pelvic floor")
            limits = r.get("limits")
            for b in r["blocks"]:
                row = byn.get(b["exercise"])
                if limits and row:
                    if (row.exertion or 2) > limits["max_exertion"]:
                        bad.append(f"{tag} {b['exercise']} over the exertion ceiling")
                    if row.floor_based and not limits["allow_floor"]:
                        bad.append(f"{tag} {b['exercise']} floor work on a no-floor day")
                if b["scheme"] == "iso" and not b.get("target_seconds"):
                    bad.append(f"{tag} {b['exercise']} iso with no seconds")
                if b["scheme"] in ("reps", "load") and not b.get("target_reps"):
                    bad.append(f"{tag} {b['exercise']} with no rep target")
    check(f"{n} sessions build and hold their invariants", not bad, str(sorted(set(bad))[:3]))
    db.close()


def test_rest_day_is_a_rest_day():
    db, uid, byn, sy = fresh()
    at(34)                                   # 5 July 2026 is a Sunday
    r = build(db, uid)
    check("Sunday is a rest day", r["kind"] == "rest", r["kind"])
    check("rest day carries no strength or maintenance work",
          not [b for b in r["blocks"] if b["group"] in ("strength", "maintenance")],
          str([b["exercise"] for b in r["blocks"] if b["group"] in ("strength", "maintenance")]))
    # Stretches are chosen by matching the day's exercises; a rest day trains
    # nothing, so nothing matched and the routine came out empty.
    check("rest day still gets its stretches",
          any(b["group"] == "mobility" for b in r["blocks"]))
    # The walk moved to Monday, Wednesday and Friday, so Sunday is now rest
    # rather than rest-with-a-walk. Asserted rather than deleted, because a
    # silent reappearance would be a regression either way.
    check("rest day has no aerobic session of its own",
          not any(b["group"] == "conditioning" for b in r["blocks"]))
    db.close()


def test_walks_land_on_the_calendar():
    """Keyed by weekday, not by the A/B/C rotation, so they can be planned.

    The rotation counts sessions, so keyed to it a walk drifts against the
    week and the fortnight view cannot be trusted to plan around.
    """
    db, uid, byn, sy = fresh()
    seen = {}
    for offset in range(28, 35):                  # a full Monday-to-Sunday week
        when = at(offset)
        with mock.patch.object(tp, "datetime", Clock):
            a = tp.aerobic_today(db, uid, 0)
        seen[when.weekday()] = a["exercise"] if a else None
        # And it is no longer a step inside the session — it is done at
        # another time of day, so it is logged on its own.
        r = build(db, uid, kind=None if when.weekday() == 6 else "strength")
        if any(b["group"] == "conditioning" for b in r["blocks"]):
            check("the walk is not a block in the session", False,
                  f"weekday {when.weekday()}")
    check("a walk on Monday and Wednesday",
          seen.get(0) == "Brisk Walk" and seen.get(2) == "Brisk Walk",
          f"Mon {seen.get(0)}, Wed {seen.get(2)}")
    check("the long walk on Friday", seen.get(4) == "Long Walk", str(seen.get(4)))
    check("nothing on Tuesday, Thursday, Saturday or Sunday",
          all(not seen.get(d) for d in (1, 3, 5, 6)),
          str({d: seen.get(d) for d in (1, 3, 5, 6) if seen.get(d)}))
    check("the walk is logged separately from the session", True)
    db.close()


def test_morning_prompt_survives_every_branch():
    """It used to vanish whenever anything hurt, which is when it matters."""
    db, uid, byn, sy = fresh(history_days=6, broad_history=False, score=None)
    at(7)
    for label, symptom, level in [("nothing logged", None, 0),
                                  ("knee pain", "Knee pain - left lateral", 2),
                                  ("headache", "Headache", 2)]:
        log_symptom(db, uid, sy.get(symptom), level)
        r = build(db, uid, kind="strength")
        check(f"morning-score prompt shows with {label}",
              r["knee"]["awaiting_next_day"] is not None)
    db.close()


def test_posterolateral_rest_and_graded_return():
    db, uid, byn, sy = fresh()
    at(31)
    log_symptom(db, uid, sy["Knee pain - left lateral"], 2)
    r = build(db, uid, day="C", kind="strength", mode="full")
    out = P.POSTEROLATERAL_REST | P.HAMSTRING_END_RANGE
    present = {b["exercise"].strip().lower() for b in r["blocks"]}
    check("aggravating patterns are stood down", not (present & out),
          str(sorted(present & out)))
    check("a hamstring isometric goes in where they came out",
          any(b["exercise"] == "Hamstring Isometric" for b in r["blocks"]))

    # They used to all come back at once on the first morning nothing was
    # logged, which is how the same tendon gets irritated twice.
    counts = []
    for offset in (0, 3, 6, 9):
        at(31 + offset)
        r = build(db, uid, day="C", kind="strength", mode="full")
        counts.append(len({b["exercise"].strip().lower() for b in r["blocks"]} & out))
    check("rested movements return gradually, not together",
          counts == sorted(counts) and counts[0] == 0 and counts[-1] > counts[0],
          f"per-session counts {counts}")
    db.close()


def test_pacing_rules_do_not_gut_a_session():
    """The novelty cap counted stretches and pelvic floor work and left three
    blocks out of nine for anyone whose programme had just changed."""
    db, uid, byn, sy = fresh(broad_history=False)
    at(31)
    r = build(db, uid, day="A", kind="strength", mode="full")
    check("a narrow history does not ration the session away",
          len(r["blocks"]) >= 8, f"{len(r['blocks'])} blocks")
    check("pelvic floor survives the pacing rules",
          any(b["group"] == "pelvic" for b in r["blocks"]))
    held = [n for n in r["notes"] if "Held back" in n]
    if held:
        check("only demanding work is held back",
              "Stretch" not in held[0] and "Pelvic" not in held[0], held[0][:90])

    # The volume rule reports; it does not cut. Stretching was the only thing
    # it could ever cut, so an overshoot from anywhere else — strength work
    # returning after an injury, most obviously — was paid for by deleting
    # holds. And a routine measured against a four-week average that predates
    # it looks like a spike every day for a fortnight.
    check("the volume rule never removes stretches",
          not [n for n in r["notes"] if "Trimmed" in n],
          str([n for n in r["notes"] if "Trimmed" in n])[:90])
    db.close()


def test_the_stretch_routine_survives_a_busy_week():
    """It had gone to nothing: ten of thirteen holds cut, three days running."""
    db, uid, byn, sy = fresh()
    at(31)
    for day in ("A", "B", "C"):
        r = build(db, uid, day=day, kind="strength", mode="full")
        after = [b for b in r["blocks"] if b.get("slot") == "after"]
        check(f"day {day} keeps a post-session routine", len(after) >= 5,
              f"only {len(after)} stretches")
    db.close()


def test_progression_is_paced_without_asking_how_it_felt():
    """The brakes were all wired to a signal that was never given.

    `easy` read an RPE and defaulted to True when none was logged, and across
    3,353 logged sets not one carried one — so the check that was meant to hold
    a load back passed on every session the programme ever prescribed. A
    beginner does not yet know what their limit feels like, and someone who
    trusts the screen pushes to whatever it asks, so asking was never a brake.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import (CONSOLIDATE_SESSIONS,
                                               MIN_DAYS_AT_LOAD, _prescribe)

    block = Block("Box Squat", "load", 3, 8, 12)
    ex = SimpleNamespace(exercise_name="Box Squat", category="strength",
                         target="knee", equipment="dumbbell", is_hold=False,
                         is_unilateral=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    loads = [2.5, 5.0, 6.0, 7.5]

    def sets_at(w, reps, rpe=None, n=3):
        return [SimpleNamespace(weight_kg=w, reps=reps, rpe=rpe, band_kg=None)
                for _ in range(n)]

    def pace(at_load_days, reps_hist, loads_hist, at_reps):
        return {"sessions_at_load": len(loads_hist), "days_at_load": at_load_days,
                "days_since_rep_step": 3, "sessions_at_reps": at_reps,
                "top_reps": reps_hist[-1], "reps_by_session": reps_hist,
                "loads_by_session": loads_hist}

    # One session at the top of the range used to be enough to add weight.
    once = _prescribe(block, ex, sets_at(5.0, 12), "progress", loads,
                      pace=pace(30, [11, 12], [5.0, 5.0], 1))
    check("one session at the top does not add load",
          once["target_weight"] == 5.0, str(once["target_weight"]))
    check("it repeats the top instead", once["target_reps"] == 12,
          str(once["target_reps"]))

    twice = _prescribe(block, ex, sets_at(5.0, 12), "progress", loads,
                       pace=pace(30, [12, 12], [5.0, 5.0], 2))
    check(f"{CONSOLIDATE_SESSIONS} sessions at the top does",
          twice["target_weight"] == 6.0, str(twice["target_weight"]))
    check("and the reps start again at the bottom",
          twice["target_reps"] == block.low, str(twice["target_reps"]))

    # Time under the load matters on its own. Muscle adapts faster than tendon,
    # which is how a programme that feels fine produces an overuse injury.
    soon = _prescribe(block, ex, sets_at(5.0, 12), "progress", loads,
                      pace=pace(MIN_DAYS_AT_LOAD - 1, [12, 12], [5.0, 5.0], 2))
    check("a load held for under a fortnight is not stepped up",
          soon["target_weight"] == 5.0, str(soon["target_weight"]))

    # A logged RPE can still stop a step. It can no longer cause one.
    heavy = _prescribe(block, ex, sets_at(5.0, 12, rpe=9), "progress", loads,
                       pace=pace(30, [12, 12], [5.0, 5.0], 2))
    check("a hard session still blocks the step",
          heavy["target_weight"] == 5.0, str(heavy["target_weight"]))


def test_the_whole_programme_cannot_step_up_at_once():
    """Seven doublings landed between the 3rd and the 10th of November.

    Every one was a legitimate step for the exercise it belonged to, and the
    load on every session doubled in eight days. No rule that looks at one
    exercise at a time can see that, and the ramp limit could not either: it
    counted sets, and the set count went down while the work went up.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import (LOAD_STEPS_PER_WEEK, _prescribe,
                                               _ready_for_more_load)

    pace = {"sessions_at_load": 5, "days_at_load": 30, "days_since_rep_step": 3,
            "sessions_at_reps": 2, "top_reps": 12, "best_recent_load": 5.0,
            "reps_by_session": [12, 12], "loads_by_session": [5.0, 5.0]}
    ok, _ = _ready_for_more_load(pace, 12, False, proposed=6.0, budget=1)
    check("a step goes ahead while the week has room", ok)
    spent, why = _ready_for_more_load(pace, 12, False, proposed=6.0, budget=0)
    check("and is held once the week is spent", not spent)
    check("saying so in the prescription",
          "already gone up this week" in why, why)

    block = Block("Box Squat", "load", 3, 8, 12)
    ex = SimpleNamespace(exercise_name="Box Squat", category="strength",
                         target="knee", equipment="dumbbell", is_hold=False,
                         is_unilateral=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    prior = [SimpleNamespace(weight_kg=5.0, reps=12, rpe=None, band_kg=None)
             for _ in range(3)]
    held = _prescribe(block, ex, prior, "progress", [2.5, 5.0, 6.0],
                      pace=pace, step_budget=0)
    check("so the load stays where it is", held["target_weight"] == 5.0,
          str(held["target_weight"]))
    moved = _prescribe(block, ex, prior, "progress", [2.5, 5.0, 6.0],
                       pace=pace, step_budget=LOAD_STEPS_PER_WEEK)
    check("and moves when the budget allows", moved["target_weight"] == 6.0,
          str(moved["target_weight"]))


def test_the_ramp_can_see_a_load_increase():
    """It counted sets. Over the fortnight the loads doubled, the set count
    fell 12% while the mechanical work rose 62%, so the one guard meant to
    catch a ramp watched the volume going down."""
    from types import SimpleNamespace
    from app.analysis.training_program import _set_work, _planned_work

    light = SimpleNamespace(weight_kg=2.5, band_kg=None, reps=10, hold_seconds=None)
    heavy = SimpleNamespace(weight_kg=5.0, band_kg=None, reps=10, hold_seconds=None)
    check("twice the weight is twice the work",
          _set_work(heavy) == 2 * _set_work(light),
          f"{_set_work(heavy)} vs {_set_work(light)}")

    more = SimpleNamespace(weight_kg=2.5, band_kg=None, reps=20, hold_seconds=None)
    check("and so is twice the reps", _set_work(more) == 2 * _set_work(light))

    # Bodyweight is a load of one, not of nothing, or an unloaded set would
    # count for nothing at all and the stretching would vanish from the ramp.
    body = SimpleNamespace(weight_kg=None, band_kg=None, reps=10, hold_seconds=None)
    check("bodyweight work still counts", _set_work(body) == 10, str(_set_work(body)))
    hold = SimpleNamespace(weight_kg=None, band_kg=None, reps=None, hold_seconds=60)
    check("and so does a hold", _set_work(hold) > 0, str(_set_work(hold)))

    # A planned session is scored the same way, against the same baseline.
    plan = {"exercise_id": 1, "target_weight": 5.0, "target_reps": 10,
            "target_band": None, "target_seconds": None}
    check("a planned heavier session scores above its baseline",
          _planned_work(plan, {1: 25.0}) == 2.0,
          str(_planned_work(plan, {1: 25.0})))
    check("and an unknown exercise does not divide by nothing",
          _planned_work(plan, {}) == 1.0)


def test_a_load_already_carried_is_re_earned_not_rediscovered():
    """Otherwise the six-weekly deload eats the programme.

    Pacing every load step the same way meant a deload to 2.5kg took thirty
    days to climb back to the 5kg it had just come off — on a forty-two day
    deload cycle, most of the programme's life spent recovering from its own
    easy weeks. Coming back off a layoff is different: the number is familiar
    but the tissue is not, so that still takes the long road.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    block = Block("Box Squat", "load", 3, 8, 12)
    ex = SimpleNamespace(exercise_name="Box Squat", category="strength",
                         target="knee", equipment="dumbbell", is_hold=False,
                         is_unilateral=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    loads = [2.5, 5.0, 6.0]
    prior = [SimpleNamespace(weight_kg=2.5, reps=12, rpe=None, band_kg=None)
             for _ in range(3)]
    # Twelve days at 2.5kg after a deload, having been at 5kg before it.
    after_deload = {"sessions_at_load": 5, "days_at_load": 12,
                    "days_since_rep_step": 3, "sessions_at_reps": 2,
                    "top_reps": 12, "best_recent_load": 5.0,
                    "reps_by_session": [11, 12], "loads_by_session": [2.5, 2.5]}
    back = _prescribe(block, ex, prior, "progress", loads, pace=after_deload)
    check("a load worked recently is picked back up",
          back["target_weight"] == 5.0, str(back["target_weight"]))

    # The same shape, except nothing heavier has been carried in the window.
    layoff = dict(after_deload, best_recent_load=2.5)
    slow = _prescribe(block, ex, prior, "progress", loads, pace=layoff)
    check("but coming back off a layoff takes the long road",
          slow["target_weight"] == 2.5, str(slow["target_weight"]))


def test_a_big_jump_in_load_lands_at_lower_volume():
    """The plates cannot make a small step at the light end: 2.5kg to 5kg is
    the whole load again. The sets carry what the plates cannot."""
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    block = Block("Goblet Squat", "load", 4, 6, 10)
    ex = SimpleNamespace(exercise_name="Goblet Squat", category="strength",
                         target="knee", equipment="dumbbell", is_hold=False,
                         is_unilateral=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    prior = [SimpleNamespace(weight_kg=2.5, reps=10, rpe=None, band_kg=None)
             for _ in range(4)]
    p = {"sessions_at_load": 2, "days_at_load": 30, "days_since_rep_step": 3,
         "sessions_at_reps": 2, "top_reps": 10,
         "reps_by_session": [10, 10], "loads_by_session": [2.5, 2.5]}
    doubled = _prescribe(block, ex, prior, "progress", [2.5, 5.0, 6.0], pace=p)
    check("the load doubles because nothing sits between the two",
          doubled["target_weight"] == 5.0, str(doubled["target_weight"]))
    check("so the first session at it drops a set",
          doubled["sets"] == block.sets - 1,
          f"{doubled['sets']} of {block.sets}")

    # A step small enough to be ordinary keeps its volume. On this plate set
    # that is the exception rather than the rule: of the eight steps the plates
    # can make, only 11->12kg and 13.5->14.5kg come in under the threshold.
    # Every other one is a 20-100% jump, which is why the sets have to give.
    prior11 = [SimpleNamespace(weight_kg=11.0, reps=10, rpe=None, band_kg=None)
               for _ in range(4)]
    p11 = dict(p, reps_by_session=[10, 10], loads_by_session=[11.0, 11.0])
    small = _prescribe(block, ex, prior11, "progress", [5.0, 11.0, 12.0], pace=p11)
    check("a 9% step keeps its full volume", small["sets"] == block.sets,
          f"{small['sets']} of {block.sets}")


def test_reps_do_not_climb_every_single_session():
    """Adding a rep each time looks gentle and compounds into the fastest ramp
    the rotation allows — every session harder than the last, indefinitely."""
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    block = Block("Dumbbell Row", "load", 3, 8, 12)
    ex = SimpleNamespace(exercise_name="Dumbbell Row", category="strength",
                         target="upper", equipment="dumbbell", is_hold=False,
                         is_unilateral=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    prior = [SimpleNamespace(weight_kg=5.0, reps=9, rpe=None, band_kg=None)
             for _ in range(3)]
    first = {"sessions_at_load": 3, "days_at_load": 10, "days_since_rep_step": 3,
             "sessions_at_reps": 1, "top_reps": 9,
             "reps_by_session": [8, 9], "loads_by_session": [5.0, 5.0]}
    held = _prescribe(block, ex, prior, "progress", [2.5, 5.0], pace=first)
    check("a rep count is repeated before it goes up",
          held["target_reps"] == 9, str(held["target_reps"]))

    second = dict(first, sessions_at_reps=2, reps_by_session=[9, 9])
    up = _prescribe(block, ex, prior, "progress", [2.5, 5.0], pace=second)
    check("and then it goes up", up["target_reps"] == 10, str(up["target_reps"]))

    # Counted in sessions, not days: a fortnight off must not buy a step up.
    layoff = dict(first, days_since_rep_step=21, sessions_at_reps=1)
    back = _prescribe(block, ex, prior, "progress", [2.5, 5.0], pace=layoff)
    check("a layoff does not unlock one either",
          back["target_reps"] == 9, str(back["target_reps"]))


def test_a_load_has_to_weigh_something():
    """Weights stopped coming back after a layoff, and sat at 0kg instead.

    With no bar weight recorded the empty bar came out as 0kg and sat at the
    bottom of the load ladder as a rung. A deload step from the lightest real
    load landed there, and every branch that repeats or holds a load then
    repeated 0kg exactly — so "repeat it before adding load" waited forever
    for a complete session at a load that is not an exercise.
    """
    from types import SimpleNamespace
    from app.analysis.training_program import achievable_loads, _next_load

    profile = SimpleNamespace(
        dumbbell_bar_kg=0.0,
        equipment_json='{"plates": {"3.0": 8, "2.5": 4, "1.25": 4}}')
    loads = achievable_loads(profile)
    check("nothing on the ladder weighs nothing", all(w > 0 for w in loads),
          str(loads[:4]))
    check("the lightest is the lightest real load", loads[0] == 2.5, str(loads[:3]))

    check("a step down from the bottom stays on the bottom",
          _next_load(loads[0], loads, up=False) == loads[0])
    check("and a load logged at zero climbs back on",
          _next_load(0.0, loads, up=True) == 2.5)
    check("a first load is the lightest, not the one above it",
          _next_load(None, loads, up=True) == 2.5)


def test_a_load_logged_at_zero_does_not_pin_the_next_one():
    """The half that heals what was already recorded.

    Four sessions went in at 0kg before the ladder was fixed. Read back as a
    load, "repeat it before adding load" repeats zero; read as the lightest
    thing that can actually be held, the weights carry on from before the
    layoff.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    block = Block("Romanian Deadlift", "load", 4, 6, 10)
    ex = SimpleNamespace(exercise_name="Romanian Deadlift", category="strength",
                         target="posterior", equipment="dumbbell",
                         is_unilateral=False, is_hold=False, exercise_id=1,
                         form_cues=None, video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    loads = [2.5, 5.0, 7.5]
    zeros = [SimpleNamespace(weight_kg=0.0, reps=6, rpe=6) for _ in range(3)]

    got = _prescribe(block, ex, zeros, "progress", loads)
    check("an incomplete session at 0kg is not repeated at 0kg",
          got["target_weight"] == 2.5, str(got["target_weight"]))

    held = _prescribe(block, ex, zeros, "hold", loads)
    check("and holding does not hold it there either",
          held["target_weight"] == 2.5, str(held["target_weight"]))

    real = [SimpleNamespace(weight_kg=5.0, reps=6, rpe=6) for _ in range(4)]
    kept = _prescribe(block, ex, real, "hold", loads)
    check("a real load is left alone", kept["target_weight"] == 5.0,
          str(kept["target_weight"]))


def test_an_easy_week_never_asks_for_more_sets():
    """A one-set practice item came back as two on a deload week.

    The set cut floors at two so a three-set block eases to two rather than
    all the way to one. On a block that only ever had one set, that floor was
    a raise: tai chi, which is one round, was prescribed twice over for the
    whole of an easy week. Logged as two rounds on four consecutive days
    before it was spotted, so the easy week was the heaviest practice week.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    ex = SimpleNamespace(exercise_name="Tai Chi Exercises", category="martial",
                         target="whole", equipment="none", is_unilateral=False,
                         is_hold=False, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    one = Block("Tai Chi Exercises", "check", 1, 0, 0)

    for action in ("deload", "back_off"):
        got = _prescribe(one, ex, [], action, [])
        check(f"one set stays one set on a {action}", got["sets"] == 1,
              str(got["sets"]))

    # The floor itself still has to work, or a three-set block would ease to
    # one and the easy week would be a week off.
    three = Block("Goblet Squat", "load", 3, 6, 10)
    sq = SimpleNamespace(exercise_name="Goblet Squat", category="strength",
                         target="quad", equipment="dumbbell", is_unilateral=False,
                         is_hold=False, exercise_id=2, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    eased = _prescribe(three, sq, [], "deload", [2.5, 5.0])
    check("three sets still ease to two", eased["sets"] == 2, str(eased["sets"]))

    two = Block("Side Kick", "reps", 2, 10, 20)
    held = _prescribe(two, ex, [], "deload", [])
    check("and two sets hold at two", held["sets"] == 2, str(held["sets"]))


def _limits(db, uid):
    """session_limits with the test clock in place, as build() does it."""
    with mock.patch.object(tp, "datetime", Clock):
        return tp.session_limits(db, uid)


def test_nausea_and_a_stiff_neck_reshape_the_session():
    """The symptoms that actually derail training here had no way in.

    Only headache and fatigue steered a session. Nausea and neck pain were
    logged, visible in the symptom history, and changed nothing — so easing
    off for them was something done by hand and then not recorded anywhere
    the programme could see.

    A neck is the one that rules out a pattern rather than a level of effort,
    which is why it stands movements down instead of lowering the ceiling.
    """
    from app.data.programs import NECK_REST, SESSION_LIMITS

    check("nausea reshapes a session", "nausea" in SESSION_LIMITS)
    check("and so does a neck", "neck" in SESSION_LIMITS)

    db, uid, byn, sy = fresh()

    # A stiff neck at its mildest: the overhead work goes, the session stays.
    log_symptom(db, uid, sy.get("Neck pain"), 1)
    lim = _limits(db, uid)
    check("a mild neck leaves the effort ceiling alone",
          lim["max_exertion"] == 3, str(lim["max_exertion"]))
    check("but stands the overhead work down",
          "dumbbell shoulder press" in lim["rest_names"])

    r = build(db, uid, day="B")
    names = {b["exercise"] for b in r["blocks"]}
    check("so the shoulder press is not in the session",
          "Dumbbell Shoulder Press" not in names)
    check("and the rest of the day still is", len(names) > 5, str(len(names)))
    check("the note says what came out",
          any("Dumbbell Shoulder Press" in n for n in r["notes"]), str(r["notes"]))

    # A bicep curl has nothing to do with a neck, and dropping the whole
    # "upper" target to spare one would have taken it with it.
    check("work that does not touch the neck is left alone",
          "bicep curl" not in NECK_REST)

    # Nausea takes the headache shape: it is getting down to the floor and
    # back up that provokes it, so the floor closes rather than just the
    # effort ceiling coming down.
    log_symptom(db, uid, sy.get("Nausea"), 2)
    lim = _limits(db, uid)
    check("nausea at moderate closes the floor", lim["allow_floor"] is False)
    check("and holds the effort down", lim["max_exertion"] == 1,
          str(lim["max_exertion"]))
    db.close()


def test_a_stricter_symptom_does_not_hand_back_the_overhead_work():
    """Strictest-wins would have thrown the neck rule away.

    Only one limit entry is carried, chosen as the strictest on effort. A
    headache logged beside a sore neck is stricter on effort and would have
    won outright — taking its own rules and silently restoring the overhead
    work the neck had stood down. The two are not comparable, so the
    stand-downs are collected from everything that matched.
    """
    from app.models.table_class import SymptomLog

    db, uid, byn, sy = fresh()
    for name, level in (("Neck pain", 1), ("Headache", 2)):
        db.add(SymptomLog(user_id=uid, symptom_id=sy.get(name),
                          date_time=Clock._now - timedelta(hours=3),
                          symptom_intensity=level))
    db.flush()

    lim = _limits(db, uid)
    check("the headache wins on effort, as the stricter of the two",
          lim["max_exertion"] == 1, str(lim["max_exertion"]))
    check("and the neck keeps its stand-down anyway",
          "dumbbell shoulder press" in (lim.get("rest_names") or ()),
          str(sorted(lim.get("rest_names") or ())))
    db.close()


def test_the_morning_score_asks_about_the_whole_body():
    """It asked about the knee for 58 sessions and never once fired.

    Fifty-four of those came back 0, the highest ever was 2, and the back-off
    threshold is 4. Repointed at the whole body it can finally mean something
    — but a back-off from a whole-body answer has to reach the whole body,
    while a logged knee symptom must still ease off the legs and leave the
    press-ups alone. Those pulled in opposite directions through one setting.
    """
    from app.data.programs import PROGRAMS

    prog = PROGRAMS["knee"]
    check("the question is no longer about the knee",
          "knee" not in prog["soreness_prompt"].lower(),
          prog["soreness_prompt"])
    check("and the word for it is not either", prog["soreness"] != "knee",
          prog["soreness"])
    # Kept, because a logged knee symptom still needs them.
    check("the knee targets are still there for a knee symptom",
          prog["soreness_targets"] == {"knee", "hip", "calf", "posterior"},
          str(prog["soreness_targets"]))

    from app.models.table_class import WorkoutSession

    db, uid, byn, sy = fresh()
    at(31)

    # A whole-body score high enough to back off reaches the upper body too.
    for s in db.query(WorkoutSession).filter(WorkoutSession.user_id == uid).all():
        s.next_day_knee = None
    scored = (db.query(WorkoutSession)
              .filter(WorkoutSession.user_id == uid)
              .order_by(WorkoutSession.date_time.desc()).first())
    scored.next_day_knee = 6
    db.flush()

    r = build(db, uid, day="B")
    check("the score backs off at all", r["knee"]["action"] == "back_off",
          r["knee"]["reason"])
    # Whichever upper-body and core work the phase happens to contain: the
    # point is that a whole-body answer is not trimmed back to the legs.
    legs = {"knee", "hip", "calf", "posterior"}
    off_target = [b for b in r["blocks"]
                  if b["group"] == "strength" and b.get("target") not in legs]
    check("the day has work outside the legs to test with", off_target,
          str([b["exercise"] for b in r["blocks"] if b["group"] == "strength"]))
    check("and the back-off reaches it", off_target and all(
        "settle" in b["why"] or "down a step" in b["why"] for b in off_target),
        str([(b["exercise"], b["why"][:40]) for b in off_target]))

    # The same score, had it come from a logged knee symptom instead, must
    # still leave that work alone — that is what the targets are for.
    log_symptom(db, uid, sy.get("Knee pain - left lateral"), 2)
    r2 = build(db, uid, day="B")
    check("a knee symptom still narrows to the legs",
          r2["knee"].get("from_symptom_log") is True, r2["knee"]["reason"])
    spared = [b for b in r2["blocks"]
              if b["group"] == "strength" and b.get("target") not in legs]
    check("so the work outside the legs is not eased off",
          spared and not any("settle" in b["why"] for b in spared),
          str([(b["exercise"], b["why"][:40]) for b in spared]))
    db.close()


def test_an_easy_week_steps_down_once_and_holds():
    """The easy week was cutting itself every session instead of once.

    Each eased target was a fraction of the session before it, and inside a
    run of eased sessions the session before is itself eased. Side Kick went
    20, 16, 12, 10 across four days of one deload week; pelvic floor holds
    went 10s, 8s, 6s. A week meant to be one step down, held, took half the
    programme with it.

    The reference is now the best of the recent window, which the easing does
    not move, so the step is the same size on the last day as on the first.
    """
    from types import SimpleNamespace
    from app.data.programs import Block
    from app.analysis.training_program import _prescribe

    def follow(block, ex, scheme_field, start, pace, rounds=5):
        """Prescribe, do exactly what it says, prescribe again."""
        done, seen = start, []
        for _ in range(rounds):
            prior = [SimpleNamespace(reps=None, hold_seconds=None, weight_kg=None,
                                     band_kg=None, rpe=None) for _ in range(4)]
            for st in prior:
                setattr(st, scheme_field, done)
            got = _prescribe(block, ex, prior, "deload", [2.5, 5.0, 7.5], pace=pace)
            done = got["target_reps"] if scheme_field == "reps" else got["target_seconds"]
            seen.append(done)
        return seen

    kick = SimpleNamespace(exercise_name="Side Kick", category="martial",
                           target="hip", equipment="none", is_unilateral=True,
                           is_hold=False, exercise_id=1, form_cues=None,
                           video_url=None, needs_balance=False,
                           hold_seconds=None, notes=None)
    reps = follow(Block("Side Kick", "reps", 2, 10, 20), kick, "reps", 20,
                  {"working_reps": 20})
    check("reps step down once and stay", len(set(reps)) == 1, str(reps))
    check("and the step is a real one", reps[0] < 20, str(reps))

    # The ratchet it replaces, so the test fails if the reference is dropped.
    old = follow(Block("Side Kick", "reps", 2, 10, 20), kick, "reps", 20, {})
    check("without a working level it would still sink", len(set(old)) > 1, str(old))

    plank = SimpleNamespace(exercise_name="Side Plank", category="strength",
                            target="core", equipment="none", is_unilateral=False,
                            is_hold=True, exercise_id=2, form_cues=None,
                            video_url=None, needs_balance=False,
                            hold_seconds=None, notes=None)
    holds = follow(Block("Side Plank", "iso", 3, 20, 60), plank, "hold_seconds",
                   60, {"working_hold": 60})
    check("holds step down once and stay", len(set(holds)) == 1, str(holds))
    check("and that step is a real one", holds[0] < 60, str(holds))

    # Load steps down a rung from the working load, not from wherever the last
    # session landed, so a body part trained twice in the week drops once.
    sq = SimpleNamespace(exercise_name="Goblet Squat", category="strength",
                         target="quad", equipment="dumbbell", is_unilateral=False,
                         is_hold=False, exercise_id=3, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    block = Block("Goblet Squat", "load", 3, 6, 10)
    loads = [2.5, 5.0, 7.5]
    at = 7.5
    seen = []
    for _ in range(4):
        prior = [SimpleNamespace(weight_kg=at, reps=6, rpe=None, band_kg=None,
                                 hold_seconds=None) for _ in range(3)]
        got = _prescribe(block, sq, prior, "deload", loads,
                         pace={"working_load": 7.5})
        at = got["target_weight"]
        seen.append(at)
    check("load steps down one rung and holds", len(set(seen)) == 1, str(seen))
    check("and it is one rung, not two", seen[0] == 5.0, str(seen))


def test_pelvic_floor_is_a_daily_dose_not_a_progression():
    """It ratcheted itself down: 10s, then 8s, then 6s.

    The deload target was computed from the session before, so inside one easy
    week each session eased off from the already-eased figure. Pelvic floor
    work carries no load to recover from in the first place — the guidance is
    frequency, a full-length hold every day — so it should not have been in
    the easy week at all. It holds its dose now, and does not climb either.
    """
    from types import SimpleNamespace
    from app.data.programs import Block, DAILY
    from app.analysis.training_program import _prescribe

    block = DAILY[0]
    check("the daily block is the pelvic floor work",
          block.name == "Pelvic Floor Training", block.name)

    ex = SimpleNamespace(exercise_name="Pelvic Floor Training", category="strength",
                         target="core", equipment="none", is_unilateral=False,
                         is_hold=True, exercise_id=1, form_cues=None,
                         video_url=None, needs_balance=False,
                         hold_seconds=None, notes=None)
    full = [SimpleNamespace(hold_seconds=10, reps=None, rpe=None, weight_kg=None,
                            band_kg=None) for _ in range(block.sets)]

    for action in ("deload", "back_off", "progress", "hold"):
        got = _prescribe(block, ex, full, action, [], fixed_dose=True)
        check(f"{action}: the hold stays at {block.high}s",
              got["target_seconds"] == block.high, str(got["target_seconds"]))
        check(f"{action}: and all {block.sets} sets stay",
              got["sets"] == block.sets, str(got["sets"]))

    # The ratchet: fed its own cut-down history it has to come back, not sink
    # further. This is the case that produced 6s from 10s in two sessions.
    cut = [SimpleNamespace(hold_seconds=6, reps=None, rpe=None, weight_kg=None,
                           band_kg=None) for _ in range(2)]
    back = _prescribe(block, ex, cut, "deload", [], fixed_dose=True)
    check("a cut-down history does not cut it again",
          back["target_seconds"] == block.high, str(back["target_seconds"]))

    # Without the flag it is an ordinary isometric, which is what every other
    # hold in the programme still needs to be.
    ordinary = _prescribe(Block("Side Plank", "iso", 3, 20, 60), ex,
                          [SimpleNamespace(hold_seconds=30, reps=None, rpe=None,
                                           weight_kg=None, band_kg=None)
                           for _ in range(3)], "deload", [])
    check("an ordinary hold still eases off on a deload",
          ordinary["target_seconds"] < 30, str(ordinary["target_seconds"]))


def test_the_kick_prep_survives_a_practice_day():
    """It went missing on a Saturday, which is almost entirely kicking.

    The prep was sorted to the front of the warm-up rather than pinned into
    it, and sorting cannot reinstate what the target filter has already
    dropped. On a practice day the pelvic floor work is the only block with a
    target, and its lone "core" was enough to switch that filter on.
    """
    from app.data.stretches import routine_for, KICK_PREP

    practice_only = {"core": ["Pelvic Floor Training"]}
    got = [s["name"] for s in routine_for("before", practice_only, kicks=True)]
    check("the leg swings are prescribed on a practice-only day",
          all(n in got for n in KICK_PREP), str(got))

    strength = {"knee": ["Box Squat"], "hip": ["Standing Hip Abduction"],
                "core": ["Dead Bug"]}
    day = [s["name"] for s in routine_for("before", strength, kicks=True)]
    check("and still on a strength day", all(n in day for n in KICK_PREP), str(day))
    check("without lengthening the warm-up", len(day) <= 5, f"{len(day)} stretches")

    quiet = [s["name"] for s in routine_for("before", practice_only, kicks=False)]
    check("someone who does not kick is not given them",
          not any(n in quiet for n in KICK_PREP), str(quiet))


def test_an_interrupted_session_can_be_picked_up():
    """The browser held the only record that a session was open.

    So a reload during one lost it: the runner came back empty, a second
    session was created beside the first, and the sets already logged were
    stranded. It has happened here at least once.
    """
    import app.api.routes.training as routes
    from app.models.table_class import User, WorkoutSession
    db, uid, byn, sy = fresh(history_days=3, broad_history=False)
    user = db.query(User).first()
    check("nothing open to begin with",
          routes.open_session(db=db, current_user=user)["session"] is None)

    started = routes.create_session(routes.SessionCreate(session_type="strength"),
                                    db=db, current_user=user)
    sid = started["session_id"]
    for n in (1, 2):
        routes.add_set(sid, routes.SetCreate(
            exercise_id=byn["Push Up"].exercise_id, set_number=n, reps=8),
            db=db, current_user=user)
    found = routes.open_session(db=db, current_user=user)["session"]
    check("a reload recovers the open session and its sets",
          found is not None and found["session_id"] == sid and len(found["sets"]) == 2)

    routes.finish_session(sid, routes.SessionFinish(session_type="strength"),
                          db=db, current_user=user)
    check("a finished session is not offered again",
          routes.open_session(db=db, current_user=user)["session"] is None)

    # Finishing a resumed assessment must not turn it into ordinary training.
    # The browser holds "this is an assessment" in a variable, so a reload
    # loses it and finishing would reclassify the session — throwing away the
    # measurements that eight exercises are prescribed from.
    a = routes.create_session(routes.SessionCreate(session_type="assessment"),
                              db=db, current_user=user)
    routes.add_set(a["session_id"], routes.SetCreate(
        exercise_id=byn["Push Up"].exercise_id, set_number=1, reps=12),
        db=db, current_user=user)
    routes.finish_session(a["session_id"],
                          routes.SessionFinish(session_type="strength"),
                          db=db, current_user=user)
    kept = db.query(WorkoutSession).filter(
        WorkoutSession.session_id == a["session_id"]).first()
    check("an assessment cannot be reclassified by finishing it",
          kept.session_type == "assessment", kept.session_type)
    row = db.query(WorkoutSession).filter(WorkoutSession.session_id == sid).first()
    check("finishing stamps the session closed", row.finished_at is not None)

    # One abandoned days ago is not the session you are in the middle of.
    db.add(WorkoutSession(user_id=uid, session_type="strength",
                          date_time=datetime.now(timezone.utc) - timedelta(hours=30)))
    db.commit()
    check("a long-abandoned session is not offered",
          routes.open_session(db=db, current_user=user)["session"] is None)

    # The walk is logged in one shot; there is nothing to resume.
    db.add(WorkoutSession(user_id=uid, session_type="aerobic",
                          date_time=datetime.now(timezone.utc)))
    db.commit()
    check("an aerobic session is never offered for resume",
          routes.open_session(db=db, current_user=user)["session"] is None)
    db.close()


def test_beginner_is_not_limited():
    """A first session is entirely unfamiliar; rationing it leaves nothing."""
    db, uid, byn, sy = fresh(history_days=0)
    at(1)
    for mode in ("full", "reduced", "gentle"):
        r = build(db, uid, day="A", kind="strength", mode=mode)
        check(f"beginner session is not trimmed or held back ({mode})",
              not [n for n in r["notes"] if "Held back" in n or "Trimmed" in n]
              and bool(r["blocks"]))
    db.close()


def test_stretch_routine_is_not_prescribed_twice():
    """Without bands, Band Hip Flexion substitutes to a stretch — and the
    expansion then treated that strength slot as a second routine."""
    db, uid, byn, sy = fresh(kit=("dumbbell",))
    at(31)
    r = build(db, uid, day="A", kind="strength", mode="full")
    names = [b["exercise"] for b in r["blocks"]]
    check("no exercise appears twice without bands",
          len(names) == len(set(names)),
          str([n for n in names if names.count(n) > 1][:3]))
    db.close()


def test_repeat_never_asks_for_more_than_was_managed():
    """3, 3, 2 against a range of 5-12 came back as 'repeat 5 before adding'."""
    from types import SimpleNamespace
    from app.data.programs import Block
    ex = SimpleNamespace(exercise_id=1, exercise_name="Push Up", target="upper",
                         equipment="bodyweight", is_unilateral=False,
                         form_cues=None, video_url=None, category="strength")
    prev = [SimpleNamespace(reps=r, weight_kg=None, band_kg=None,
                            hold_seconds=None, rpe=None) for r in (3, 3, 2)]
    item = tp._prescribe(Block("Push Up", "reps", 3, 5, 12), ex, prev,
                         "progress", [], bands=[])
    check("a worse session never earns a harder target",
          item["target_reps"] <= 3, f"asked for {item['target_reps']} after a best of 3")



# ──────────────────────────────────────────────────────────────────────────
# Golden snapshot
#
# Recorded before build_session was split apart, so the refactor can be
# checked against what the engine actually said rather than against whether it
# still runs. Re-record deliberately, and only when the output is meant to
# change: ./.venv/bin/python tests/test_training.py --record
# ──────────────────────────────────────────────────────────────────────────

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden.json")

FIELDS = ("exercise", "prescription", "scheme", "sets", "target_reps",
          "target_seconds", "target_weight", "target_band", "per_side", "group",
          "slot", "why", "notice")


def _snapshot():
    out = {}
    db, uid, byn, sy = fresh()
    for symptom, level in [(None, 0), ("Headache", 2),
                           ("Knee pain - left lateral", 2)]:
        log_symptom(db, uid, sy.get(symptom), level)
        # 28 is a Monday, 31 a Thursday, 34 a Sunday — a walk day, an ordinary
        # day and the rest day. The snapshot covered only the last two, so
        # moving the walks out of the session changed nothing it could see.
        for offset, mode, day, kind in itertools.product(
                (28, 31, 34), ("full", "gentle"), ("A", "B", "C"), ("strength", "practice")):
            at(offset)
            r = build(db, uid, day=day, mode=mode, kind=kind)
            key = f"{symptom or 'none'}|d{offset}|{mode}|{day}|{kind}"
            out[key] = {
                "kind": r["kind"], "theme": r["theme"], "phase": r["phase"]["phase"],
                "knee": {k: r["knee"].get(k) for k in
                         ("action", "region", "affected_side", "awaiting_next_day")},
                "notes": r["notes"],
                "blocks": [{f: b.get(f) for f in FIELDS} for b in r["blocks"]],
            }
    db.close()
    return out


def test_golden_snapshot():
    now = _snapshot()
    if not os.path.exists(GOLDEN):
        check("golden snapshot exists", False, "run with --record first")
        return
    was = json.load(open(GOLDEN, encoding="utf-8"))
    diffs = []
    for key in sorted(set(was) | set(now)):
        if key not in was:
            diffs.append(f"new case {key}")
        elif key not in now:
            diffs.append(f"missing case {key}")
        elif was[key] != now[key]:
            a, b = was[key], now[key]
            for field in a:
                if a[field] != b.get(field):
                    diffs.append(f"{key}: {field} changed")
    check(f"{len(now)} recorded sessions unchanged", not diffs, str(diffs[:5]))

if __name__ == "__main__":
    if "--record" in sys.argv:
        json.dump(_snapshot(), open(GOLDEN, "w", encoding="utf-8"), indent=1)
        print(f"recorded {GOLDEN}")
        sys.exit(0)
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(f"\n{fn.__name__}")
        fn()
    print("\n" + ("=" * 60))
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("all checks passed")
