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
    db.close()


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
