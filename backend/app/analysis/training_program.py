"""Rules that decide what to train today.

Deterministic on purpose. The knee back-off below is the safety mechanism of
this whole feature, and a rule that reads the last session's next-day score and
refuses to add load is a guarantee; the same instruction in a prompt is a
suggestion. The AI layer explains and answers questions, it does not pick loads.

Three phases, knee-led:

  1. Settle    isometrics and controlled range. No loaded squatting. This is
               where pain that flares on squats is usually best tolerated, and
               isometrics often ease it within the set.
  2. Load      eccentric step-downs and light loaded work added.
  3. Build     heavier, deeper, closer to what tramping and telemark demand.

Advancing needs both time in the phase and quiet knees, so a good week cannot
promote someone whose knees are complaining.
"""
import json
import logging
from collections import namedtuple
from datetime import datetime, timedelta

from app.models.table_class import Exercise, SetLog, TrainingProfile, WorkoutSession

logger = logging.getLogger(__name__)

# scheme: iso (hold seconds) | reps (bodyweight reps) | load (double progression)
Block = namedtuple("Block", "name scheme sets low high")

PHASES = {
    1: {
        "label": "Settle",
        "aim": "Calm the knees down and build tolerance without loaded squatting.",
        "themes": {'A': 'Knee tolerance and core', 'B': 'Hips, posterior chain and shins', 'C': 'Knee control, core and arms'},
        "days": {
            "A": [
                Block("Spanish Squat", "iso", 3, 20, 45),
                Block("Terminal Knee Extension", "reps", 3, 10, 15),
                Block("Standing Hip Abduction", "reps", 3, 10, 15),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Plank", "iso", 3, 20, 45),
            ],
            "B": [
                Block("Single Leg Glute Bridge", "reps", 3, 8, 15),
                Block("Lateral Band Walk", "reps", 3, 10, 15),
                Block("Tibialis Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 20, 40),
                Block("Push Up", "reps", 3, 5, 12),
            ],
            "C": [
                Block("Wall Sit", "iso", 3, 20, 45),
                Block("Terminal Knee Extension", "reps", 3, 10, 15),
                Block("Standing Hip Abduction", "reps", 3, 10, 15),
                Block("Sit Up", "reps", 3, 8, 15),
                Block("Tricep Dip", "reps", 3, 5, 12),
            ],
        },
    },
    2: {
        "label": "Load",
        "aim": "Introduce eccentric control and light external load.",
        "themes": {'A': 'Squat and push', 'B': 'Hinge and pull', 'C': 'Single-leg control and shoulders'},
        "days": {
            "A": [
                Block("Spanish Squat", "iso", 2, 30, 45),
                Block("Goblet Squat", "load", 3, 8, 12),
                Block("Standing Hip Abduction", "reps", 3, 12, 15),
                Block("Push Up", "reps", 3, 8, 15),
                Block("Plank", "iso", 3, 30, 60),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 3, 8, 12),
                Block("Single Leg Glute Bridge", "reps", 3, 10, 15),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 30, 45),
            ],
            "C": [
                Block("Lateral Step Down", "reps", 3, 5, 10),
                Block("Split Squat", "load", 3, 6, 10),
                Block("Tibialis Raise", "reps", 3, 15, 20),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Sit Up", "reps", 3, 10, 20),
            ],
        },
    },
    3: {
        "label": "Build",
        "aim": "Heavier and deeper, towards downhill and telemark demands.",
        "themes": {'A': 'Squat and push', 'B': 'Hinge and pull', 'C': 'Single-leg control and shoulders'},
        "days": {
            "A": [
                Block("Goblet Squat", "load", 4, 6, 10),
                Block("Split Squat", "load", 3, 8, 12),
                Block("Standing Hip Abduction", "reps", 3, 12, 20),
                Block("Dumbbell Floor Press", "load", 3, 8, 12),
                Block("Plank", "iso", 3, 45, 75),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 4, 6, 10),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Single Leg Glute Bridge", "reps", 3, 12, 20),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 40, 60),
            ],
            "C": [
                Block("Lateral Step Down", "reps", 3, 8, 12),
                Block("Anterior Step Down", "reps", 3, 8, 12),
                Block("Box Squat", "load", 3, 8, 12),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Bicep Curl", "load", 2, 10, 15),
            ],
        },
    },
}

DAY_ORDER = ["A", "B", "C"]

# The existing practice, appended to every day. "check" means there is nothing
# to count — it either happened or it did not — which still records that the
# knees were loaded that day.
TAI_CHI_FORM = "__TAI_CHI_FORM__"          # resolved to 42 or 37 at build time
TAI_CHI_FORMS = ["Tai Chi Form 42", "Tai Chi Form 37"]

# Knee work on the days between strength sessions. Tendon and quad tolerance
# responds to frequent low-load exposure far better than to one hard session a
# week, which is the single strongest argument against a body-part split here:
# on a split, the knees would be trained once every seven days.
KNEE_MINIMUM = [
    Block("Terminal Knee Extension", "reps", 2, 10, 15),
    Block("Spanish Squat", "iso", 2, 20, 45),
]

# The session runs in the order it is actually trained: tai chi opens, the
# strength work sits in the middle, and the pattern and kicks close it out.
PRACTICE_BEFORE = [
    Block("Tai Chi Exercises", "check", 1, 0, 0),
    Block(TAI_CHI_FORM, "check", 1, 0, 0),
    Block("Tai Chi Sword", "check", 1, 0, 0),
]

PRACTICE_AFTER = [
    Block("Stretches", "check", 1, 0, 0),
    Block("Kung Fu Pattern", "check", 1, 0, 0),
    Block("Side Kick", "reps", 2, 10, 20),
]


def next_tai_chi_form(db, user_id) -> str:
    """The form that is due, since the two alternate and are easy to lose track of.

    Whichever was done most recently, the other one is next.
    """
    rows = (
        db.query(SetLog, WorkoutSession, Exercise)
        .join(WorkoutSession, SetLog.session_id == WorkoutSession.session_id)
        .join(Exercise, SetLog.exercise_id == Exercise.exercise_id)
        .filter(SetLog.user_id == user_id)
        .all()
    )
    # Ordered by session time then by set id, so two forms logged in the same
    # session fall back to the order they were entered. Comparing the names
    # instead would tie-break alphabetically, which has nothing to do with
    # which was practised last.
    seen = [
        (s.date_time, st.set_id, e.exercise_name)
        for st, s, e in rows
        if s.date_time and e.exercise_name in TAI_CHI_FORMS
    ]
    if not seen:
        return TAI_CHI_FORMS[0]
    last = max(seen)[2]
    return TAI_CHI_FORMS[1] if last == TAI_CHI_FORMS[0] else TAI_CHI_FORMS[0]

# The baseline session. Deliberately submaximal: a true 1RM is the highest-risk
# thing that could be prescribed and the exact stimulus that flares this knee,
# and a rep test gives the same programming information without it.
ASSESSMENT = [
    ("Spanish Squat", "Hold until form breaks or pain rises above 3/10. Stop at 60s.",
     "Sets the starting hold."),
    ("Wall Sit", "Same, at a depth that stays comfortable. Stop at 60s.",
     "Confirms the pain-free knee angle."),
    ("Terminal Knee Extension", "One set of up to 20 slow reps per leg, lightest band.",
     "Checks the band is light enough."),
    ("Lateral Step Down", "Lowest step you own. Reps until the knee dives inward.",
     "Finds the step height to start from."),
    ("Single Leg Glute Bridge", "Max controlled reps per side, stop 2 short of failure.",
     "Baseline for hip strength, which controls knee tracking."),
    ("Goblet Squat", "One dumbbell, a load you could do about 12 times. Stop 2 reps "
                     "short. Record the load and reps.", "Estimates the working load."),
    ("Push Up", "Max reps, stopping 2 short of failure.", "Baseline upper body."),
    ("Plank", "Hold until form breaks. Stop at 90s.", "Baseline core."),
]

# ── Knee back-off ────────────────────────────────────────────────────────────
# Pain during a set and pain the next morning are different measurements. The
# second is the one that matters: a session can feel fine and still be too much.
NEXT_DAY_BACKOFF = 4      # >= this in the last scored session -> back off
SET_PAIN_BACKOFF = 4      # >= this mean pain during the last session -> back off
SET_PAIN_HOLD = 3         # >= this -> hold progression rather than back off
RPE_CEILING = 8           # progress load only if the last sets were <= this
RECENT_SCORES = 5         # how many recent next-day scores decide a phase
MIN_EXERCISES_FOR_CREDIT = 3   # exercises needed for a session to count
STALL_SESSIONS = 3        # identical failed attempts before backing the target off
STALL_FACTOR = 0.75       # how far back a stalled target drops
# A stalled target has to be allowed below the prescribed range, or the range's
# own floor blocks the reduction and the loop survives the fix. These are the
# absolute floors; at them, the exercise itself is the problem.
REPS_FLOOR = 5
SECONDS_FLOOR = 10


def achievable_loads(profile) -> list[float]:
    """Every dumbbell weight that can actually be built from the plates owned.

    Plates split evenly across two bars and load symmetrically, so they are
    consumed in pairs — which is what makes the usable steps 2.5kg rather than
    1.25kg. Prescribing a load the user cannot assemble is worse than useless.
    """
    bar = (profile.dumbbell_bar_kg if profile and profile.dumbbell_bar_kg else 0.0)

    plates = {3.0: 8, 2.5: 4, 1.25: 4}          # the kit as ordered
    if profile and profile.equipment_json:
        try:
            data = json.loads(profile.equipment_json)
            if isinstance(data.get("plates"), dict) and data["plates"]:
                plates = {float(k): int(v) for k, v in data["plates"].items()}
        except (ValueError, TypeError, AttributeError):
            logger.warning("equipment_json unreadable; using the default kit")

    # Half the plates per dumbbell, and each side of one dumbbell needs a pair.
    pairs = []
    for weight, count in plates.items():
        pairs += [weight * 2] * (count // 2 // 2)

    totals = {0.0}
    for p in pairs:
        totals |= {t + p for t in totals}
    return sorted(round(bar + t, 2) for t in totals)


def _next_load(current, loads, up=True):
    """The next buildable load above or below the current one."""
    if not loads:
        return current
    if current is None:
        return loads[1] if len(loads) > 1 else loads[0]
    if up:
        higher = [w for w in loads if w > current + 1e-6]
        return higher[0] if higher else current
    lower = [w for w in loads if w < current - 1e-6]
    return lower[-1] if lower else loads[0]


def _last_sets(db, user_id, exercise_id):
    """Sets from the most recent session that included this exercise, and when.

    The date matters because a skipped exercise keeps its old baseline. Without
    it the prescription would say "every set hit 10 — one more" about a session
    three weeks ago as though it were the last one.
    """
    rows = (
        db.query(SetLog, WorkoutSession)
        .join(WorkoutSession, SetLog.session_id == WorkoutSession.session_id)
        .filter(SetLog.user_id == user_id, SetLog.exercise_id == exercise_id)
        .all()
    )
    dated = [(st, s) for st, s in rows if s.date_time]
    if not dated:
        return [], None
    latest = max(s.date_time for _, s in dated)
    return [st for st, s in dated if s.date_time == latest], latest


# Easier versions of the same movement, hardest first. Only used once a stall
# has already survived a deload, so this is the last resort rather than the
# first response — and only where the swap is genuinely the same pattern made
# easier, not simply a different exercise.
#
# Each entry carries its own scheme and range: a squat regressed to a wall sit
# is timed rather than counted, and "8 to 12" of it would be meaningless.
REGRESSIONS = {
    "goblet squat": [("Box Squat", "load", 8, 12),
                     ("Wide Leg Squat", "reps", 8, 15),
                     ("Spanish Squat", "iso", 20, 45)],
    "box squat": [("Wide Leg Squat", "reps", 8, 15),
                  ("Spanish Squat", "iso", 20, 45)],
    "wide leg squat": [("Spanish Squat", "iso", 20, 45),
                       ("Wall Sit", "iso", 20, 45)],
    "split squat": [("Lunge", "reps", 6, 12),
                    ("Wide Leg Squat", "reps", 8, 15)],
    "lunge": [("Wide Leg Squat", "reps", 8, 15)],
    "single leg squat": [("Split Squat", "load", 6, 10),
                         ("Wide Leg Squat", "reps", 8, 15)],
    "anterior step down": [("Lateral Step Down", "reps", 5, 10),
                           ("Spanish Squat", "iso", 20, 45)],
    "lateral step down": [("Spanish Squat", "iso", 20, 45)],
    "spanish squat": [("Wall Sit", "iso", 20, 45)],
    "push up": [("Incline Push Up", "reps", 5, 12)],
    "romanian deadlift": [("Single Leg Glute Bridge", "reps", 8, 15)],
    "tricep dip": [("Incline Push Up", "reps", 5, 12)],
}


def _substitute(db, user_id, name, by_name):
    """The easiest-first alternative the user actually owns and is not stuck on.

    Returns (Block, Exercise) or None. Nothing is substituted for an exercise
    with no ladder, or when the whole ladder is missing from their library —
    silently swapping in something they have never seen would be worse than
    saying nothing.
    """
    for sub_name, scheme, low, high in REGRESSIONS.get(name.strip().lower(), []):
        ex = by_name.get(sub_name.strip().lower())
        if ex is None:
            continue
        if _stalled(db, user_id, ex.exercise_id, scheme):
            continue          # no point moving onto something already stuck
        return Block(sub_name, scheme, 3, low, high), ex
    return None


def _stalled(db, user_id, exercise_id, scheme) -> bool:
    """Has this exercise been stuck at the same failed target for a while?

    Repeating a target the person cannot complete is not a training plan, it is
    a loop. Three attempts at the identical figure without meeting it means the
    target is too hard, not that they need to try harder.

    "Identical" matters: a figure that is merely unchanged would also describe
    someone sitting at the top of a rep range and succeeding, who should not be
    dropped back. So a stall needs the last attempt to have actually fallen
    short as well.
    """
    rows = (
        db.query(SetLog, WorkoutSession)
        .join(WorkoutSession, SetLog.session_id == WorkoutSession.session_id)
        .filter(SetLog.user_id == user_id, SetLog.exercise_id == exercise_id)
        .all()
    )
    by_session = {}
    for st, s in rows:
        if s.date_time:
            by_session.setdefault(s.date_time, []).append(st)
    if len(by_session) < STALL_SESSIONS:
        return False

    field = {"iso": "hold_seconds", "reps": "reps", "load": "reps"}.get(scheme)
    if field is None:
        return False

    signatures, recent = [], sorted(by_session, reverse=True)[:STALL_SESSIONS]
    for when in recent:
        sets = by_session[when]
        vals = [getattr(x, field) or 0 for x in sets]
        top = max(vals) if vals else 0
        if scheme == "load":
            weights = [x.weight_kg for x in sets if x.weight_kg is not None]
            signatures.append((max(weights) if weights else 0, top))
        else:
            signatures.append(top)

    if len(set(signatures)) != 1:
        return False

    # The most recent attempt must have fallen short, or this is someone
    # holding steady at the top of a range on purpose.
    latest = by_session[recent[0]]
    vals = [getattr(x, field) or 0 for x in latest]
    return bool(vals) and min(vals) < max(vals)


def knee_state(db, user_id) -> dict:
    """Whether to back off, hold, or progress, and why."""
    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id)
        .order_by(WorkoutSession.date_time.desc())
        .limit(5)
        .all()
    )
    if not sessions:
        return {"action": "progress", "reason": "No sessions logged yet.",
                "awaiting_next_day": None}

    # The most recent session that actually carries pain data, not simply the
    # most recent session. A session started and abandoned, or a tai chi
    # session logged with no sets, would otherwise mask the last real one and
    # silently switch the back-off rule off.
    last = next(
        (s for s in sessions if any(x.pain is not None for x in s.sets)),
        None,
    )
    pains = [x.pain for x in last.sets if x.pain is not None] if last else []
    mean_pain = round(sum(pains) / len(pains), 1) if pains else None

    scored = next((s for s in sessions if s.next_day_knee is not None), None)

    if scored is not None and scored.next_day_knee >= NEXT_DAY_BACKOFF:
        return {
            "action": "back_off",
            "reason": (f"Knee was {scored.next_day_knee}/10 the day after your last "
                       f"scored session. Load comes down a step and volume is cut."),
            "awaiting_next_day": None,
        }
    if mean_pain is not None and mean_pain >= SET_PAIN_BACKOFF:
        return {"action": "back_off",
                "reason": f"Mean pain in the last session was {mean_pain}/10.",
                "awaiting_next_day": None}
    if mean_pain is not None and mean_pain >= SET_PAIN_HOLD:
        return {"action": "hold",
                "reason": f"Mean pain {mean_pain}/10 last session — repeat it "
                          f"rather than adding load.",
                "awaiting_next_day": None}

    # Not a reason to back off, but the score is the input to the rule, so ask
    # for it — only where there was actually a session worth scoring.
    awaiting = last.session_id if last is not None and last.next_day_knee is None else None
    return {"action": "progress",
            "reason": "Knees quiet — progressing.",
            "awaiting_next_day": awaiting}


# A session counts towards leaving a phase only if it covered a fair part of
# the day. Otherwise six sessions of one exercise each would unlock loaded
# squatting without the tolerance for the phase before it ever being shown.
def _substantial(session, strength_names) -> bool:
    covered = {
        st.exercise.exercise_name.strip().lower()
        for st in session.sets
        if st.exercise is not None
    } & strength_names
    return len(covered) >= MIN_EXERCISES_FOR_CREDIT


def current_phase(db, user_id) -> dict:
    """Which phase, and what still has to happen to leave it."""
    all_strength = [
        s for s in db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id).all()
        if s.session_type == "strength"
    ]

    # Names from every phase, because a session was logged under whichever
    # phase applied at the time.
    strength_names = {
        b.name.strip().lower()
        for spec in PHASES.values()
        for day in spec["days"].values()
        for b in day
    }
    sessions = [s for s in all_strength if _substantial(s, strength_names)]
    partial = len(all_strength) - len(sessions)
    done = len(sessions)

    # Recent scores only. Judging on the whole history would let one bad day
    # months ago block progress permanently, which is not what a single flare
    # means — but the window is wide enough that a pattern still shows.
    scores = [
        s.next_day_knee
        for s in sorted(sessions, key=lambda x: x.date_time or 0, reverse=True)
        if s.next_day_knee is not None
    ][:RECENT_SCORES]
    quiet = all(v <= 3 for v in scores) if scores else False
    # Never promote on an unproven record: some next-day scores must exist.
    enough_evidence = len(scores) >= 3

    if done >= 6 and quiet and enough_evidence:
        if done >= 14:
            phase = 3
        else:
            phase = 2
    else:
        phase = 1

    if phase == 1:
        def plural(n, word):
            return f"{n} more {word}" + ("" if n == 1 else "s")

        need = []
        if done < 6:
            need.append(plural(6 - done, "strength session"))
        if not enough_evidence:
            need.append(plural(3 - len(scores), "next-day knee score"))
        if scores and not quiet:
            need.append("next-day knee at 3/10 or below")
        to_advance = " and ".join(need) or "next-day knee scores staying low"
        if partial:
            to_advance += (f" ({partial} session{'' if partial == 1 else 's'} too "
                           f"short to count — {MIN_EXERCISES_FOR_CREDIT}+ exercises "
                           f"needed)")
    elif phase == 2:
        remaining = max(0, 14 - done)
        to_advance = (f"{remaining} more strength session"
                      f"{'' if remaining == 1 else 's'} with knees quiet")
    else:
        to_advance = "already at the top phase"

    return {"phase": phase, "label": PHASES[phase]["label"],
            "aim": PHASES[phase]["aim"], "sessions_done": done,
            "partial_sessions": partial,
            "to_advance": to_advance}


def _prescribe(block, ex, last_sets, action, loads, last_done=None,
               stalled=False):
    """Turn one template block plus history into a concrete instruction."""
    sets = block.sets
    detail, why = "", ""
    target, weight = None, None
    # Set when a stall has nowhere left to go: the caller then looks for an
    # easier version of the movement.
    exhausted = False

    if action == "back_off":
        sets = max(2, block.sets - 1)

    # What was actually completed last time. Two rules apply throughout:
    #
    #   - the weakest set counts, not the best one. Progressing off the
    #     freshest set while the last one was fading is how a programme runs
    #     away from the person following it.
    #   - the sets have to have been finished. Managing one set of three and
    #     being asked for more next time punishes logging honestly, which is
    #     the one thing this whole system depends on.
    #
    # The load scheme already worked this way; the others did not.
    expected = block.sets * (2 if ex.is_unilateral else 1)
    complete = len(last_sets) >= expected
    short = f"Only {len(last_sets)} of {expected} sets last time"

    if block.scheme == "check":
        detail = "Practise it"
        why = "Tick it off — logged so the knee load is on the record."
        target = None

    elif block.scheme == "iso":
        holds = [(s.hold_seconds or 0) for s in last_sets]
        top, weakest = (max(holds), min(holds)) if holds else (0, 0)
        if action == "back_off":
            target = max(block.low, int(top * 0.8) or block.low)
            why = "Held back while the knee settles."
        elif action == "hold" or not top:
            target = max(block.low, top or block.low)
            why = "Repeat last time's hold." if top else "Starting point."
        elif not complete:
            target = max(block.low, min(top, block.high))
            why = f"{short} — repeat it before going longer."
        elif stalled:
            target = max(SECONDS_FLOOR, int(top * STALL_FACTOR))
            if target >= top:
                exhausted = True
                why = f"Stuck at {top}s for {STALL_SESSIONS} sessions."
            else:
                why = (f"Stuck at {top}s for {STALL_SESSIONS} sessions without "
                       f"finishing it — dropping to {target}s to build back up.")
        elif weakest < top:
            # Worked at `top` and one set fell short of it, so the prescription
            # was not completed. Repeat it rather than asking for more.
            target = max(block.low, min(top, block.high))
            why = f"Last set dropped to {weakest}s — repeat {target}s before going longer."
        else:
            target = min(block.high, top + 5)
            why = f"Every set held {top}s — up 5s."
        detail = f"{sets} x {target}s hold"

    elif block.scheme == "reps":
        counts = [(s.reps or 0) for s in last_sets]
        top, weakest = (max(counts), min(counts)) if counts else (0, 0)
        if action == "back_off":
            target = max(block.low, int(top * 0.8) or block.low)
            why = "Volume cut while the knee settles."
        elif action == "hold" or not top:
            target = max(block.low, min(top or block.low, block.high))
            why = "Repeat last time." if top else "Starting point."
        elif not complete:
            target = max(block.low, min(top, block.high))
            why = f"{short} — repeat it before adding reps."
        elif stalled:
            target = max(REPS_FLOOR, int(top * STALL_FACTOR))
            if target >= top:
                exhausted = True
                why = f"Stuck at {top} for {STALL_SESSIONS} sessions."
            else:
                why = (f"Stuck at {top} for {STALL_SESSIONS} sessions without "
                       f"finishing it — dropping to {target} to build back up.")
        elif weakest < top:
            target = max(block.low, min(top, block.high))
            why = f"Last set dropped to {weakest} — repeat {target} before adding."
        elif top >= block.high:
            target = block.high
            why = f"Every set at {block.high} — hold there and slow the tempo."
        else:
            target = min(block.high, top + 1)
            why = f"Every set hit {top} — one more."
        detail = f"{sets} x {target} reps"
        if ex.is_unilateral:
            detail += " each side"

    else:  # load
        prev = [s for s in last_sets if s.weight_kg is not None]
        last_w = max((s.weight_kg for s in prev), default=None)
        counts = [(s.reps or 0) for s in prev]
        top_reps = max(counts) if counts else 0
        last_reps = min(counts) if counts else 0
        rpes = [s.rpe for s in prev if s.rpe is not None]
        easy = all(r <= RPE_CEILING for r in rpes) if rpes else True

        if action == "back_off":
            weight = _next_load(last_w, loads, up=False)
            target = block.low
            why = "Load down a step while the knee settles."
        elif last_w is None:
            weight = loads[1] if len(loads) > 1 else (loads[0] if loads else None)
            target = block.low
            why = "First time — start light and see how it feels tomorrow."
        elif action == "hold":
            weight, target = last_w, max(block.low, last_reps)
            why = "Same load again."
        elif not complete:
            weight, target = last_w, max(block.low, top_reps)
            why = f"{short} — repeat it before adding load."
        elif stalled:
            weight = _next_load(last_w, loads, up=False)
            target = block.low
            if weight == last_w:
                exhausted = True
                why = f"Stuck at {last_w}kg for {STALL_SESSIONS} sessions."
            else:
                why = (f"Stuck at {last_w}kg for {STALL_SESSIONS} sessions without "
                       f"finishing it — back to {weight}kg to build up again.")
        elif last_reps < top_reps:
            weight, target = last_w, max(block.low, top_reps)
            why = f"Last set dropped to {last_reps} — repeat {target} at {last_w}kg."
        elif last_reps >= block.high and easy:
            weight = _next_load(last_w, loads, up=True)
            target = block.low
            why = (f"Every set hit {block.high} at {last_w}kg, so load goes up and "
                   f"reps reset to {block.low}.")
        else:
            weight, target = last_w, min(block.high, top_reps + 1)
            if target <= top_reps:
                # Already at the top of the range, held back by effort rather
                # than by reps, so say that instead of "one more rep".
                hardest = max(rpes) if rpes else None
                why = (f"{top_reps} reps at {last_w}kg but RPE {hardest} — repeat "
                       f"before adding load." if hardest
                       else f"Repeat {top_reps} at {last_w}kg.")
            else:
                why = f"One more rep at {last_w}kg before adding weight."
        detail = f"{sets} x {target} reps"
        if ex.is_unilateral:
            detail += " each side"
        if weight is not None:
            detail += f" @ {weight}kg"

    # A skipped exercise keeps the baseline from whenever it was last done, so
    # the reasoning should say when that was rather than implying "last time".
    if last_done is not None and block.scheme != "check":
        naive = last_done.replace(tzinfo=None) if last_done.tzinfo else last_done
        days = (datetime.utcnow() - naive).days
        if days >= 8:
            why = f"{why} Last done {days} days ago."

    return {
        "exercise_id": ex.exercise_id,
        "exercise": ex.exercise_name,
        "target": ex.target,
        "equipment": ex.equipment,
        "scheme": block.scheme,
        "prescription": detail,
        "why": why,
        "form_cues": ex.form_cues,
        "video_url": ex.video_url,
        # Structured as well as prose: the session runner counts against these
        # rather than parsing the sentence above, which would break the moment
        # the wording changed.
        "sets": sets,
        "target_reps": target if block.scheme in ("reps", "load") else None,
        "target_seconds": target if block.scheme == "iso" else None,
        "target_weight": weight if block.scheme == "load" else None,
        "per_side": bool(ex.is_unilateral),
        "exhausted": exhausted,
    }


def _local_date(dt, tz_offset):
    if dt is None:
        return None
    naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
    return (naive - timedelta(minutes=tz_offset)).date()


def choose_kind(db, user_id, tz_offset) -> dict:
    """Strength today, or practice and the knee minimum?

    Muscle needs roughly a day between hard sessions, so strength days are kept
    apart: if one was done today or yesterday, today is a practice day. Over a
    week that settles into three or four strength sessions, which is where the
    evidence for a 3-day week sits — and it means every muscle is trained
    two or three times a week rather than once, as it would be on a split.
    """
    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()

    last = None
    for s in db.query(WorkoutSession).filter(WorkoutSession.user_id == user_id).all():
        if s.session_type != "strength" or not s.date_time:
            continue
        d = _local_date(s.date_time, tz_offset)
        if last is None or d > last:
            last = d

    if last is None:
        return {"kind": "strength", "why": "No strength session logged yet — start here."}
    gap = (today - last).days
    if gap >= 2:
        return {"kind": "strength",
                "why": f"Last strength session was {gap} days ago."}
    return {
        "kind": "practice",
        "why": ("Strength was "
                + ("today" if gap == 0 else "yesterday")
                + " — today is practice plus the knee minimum, so the muscle "
                  "gets its recovery day while the knees still get their work."),
    }


def build_session(db, user_id, day=None, tz_offset=0, kind=None) -> dict:
    """The whole prescription for the next session."""
    phase = current_phase(db, user_id)
    knee = knee_state(db, user_id)
    profile = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == user_id).first()
    loads = achievable_loads(profile)

    # Rotate A/B/C by how many strength sessions have been done, so the next
    # one is simply the next in the cycle. Anything that is not a real day
    # falls back to that rather than raising: a caller passing something odd
    # should get a sensible session, not a 500.
    if day not in DAY_ORDER:
        day = DAY_ORDER[phase["sessions_done"] % len(DAY_ORDER)]

    by_name = {
        e.exercise_name.strip().lower(): e
        for e in db.query(Exercise).filter(
            Exercise.user_id == user_id, Exercise.is_archived.is_(False)).all()
    }

    decision = {"kind": kind, "why": "Chosen explicitly."} if kind in ("strength", "practice") \
        else choose_kind(db, user_id, tz_offset)

    due_form = next_tai_chi_form(db, user_id)

    def resolve(block):
        """Templates name the form indirectly, because which one is due depends
        on what was done last rather than on the plan."""
        if block.name == TAI_CHI_FORM:
            return block._replace(name=due_form)
        return block

    if decision["kind"] == "strength":
        middle = [(b, "strength") for b in PHASES[phase["phase"]]["days"][day]]
        theme = PHASES[phase["phase"]]["themes"][day]
    else:
        # Between strength days the knees still get their work; the muscle gets
        # its recovery day. It sits where the strength work would have been.
        middle = [(b, "knee") for b in KNEE_MINIMUM]
        theme = "Practice and knee maintenance"

    blocks, missing = [], []
    templates = [(resolve(b), "practice") for b in PRACTICE_BEFORE]
    templates += middle
    templates += [(resolve(b), "practice") for b in PRACTICE_AFTER]

    for block, group in templates:
        ex = by_name.get(block.name.strip().lower())
        if ex is None:
            missing.append(block.name)
            continue
        prior, when = _last_sets(db, user_id, ex.exercise_id)
        item = _prescribe(
            block, ex, prior, knee["action"], loads, last_done=when,
            stalled=_stalled(db, user_id, ex.exercise_id, block.scheme),
        )

        if item.pop("exhausted", False):
            swap = _substitute(db, user_id, block.name, by_name)
            if swap is None:
                # Nothing to move to, so say what is happening rather than
                # repeating a target that has already failed three times.
                item["why"] += (" No easier version of this is in your library — "
                                "swap it for something you can complete.")
            else:
                sub_block, sub_ex = swap
                sub_prior, sub_when = _last_sets(db, user_id, sub_ex.exercise_id)
                item = _prescribe(
                    sub_block, sub_ex, sub_prior, knee["action"], loads,
                    last_done=sub_when,
                    stalled=_stalled(db, user_id, sub_ex.exercise_id, sub_block.scheme),
                )
                item.pop("exhausted", None)
                item["substituted_from"] = ex.exercise_name
                # Flagged until it has actually been done, so the change is
                # announced once rather than nagging forever.
                fresh = sub_when is None or (when is not None and sub_when < when)
                item["notice"] = (
                    f"{ex.exercise_name} has stalled three sessions running, so it "
                    f"has been swapped for {sub_ex.exercise_name} — the same "
                    f"movement, made easier. It will build back up from here."
                ) if fresh else None
                item["why"] = (f"Replacing {ex.exercise_name}. " + item["why"]).strip()

        item.pop("exhausted", None)
        item["group"] = group
        blocks.append(item)

    notes = []
    if not profile or not profile.dumbbell_bar_kg:
        notes.append("Weigh a bare dumbbell bar and save it in your profile — "
                     "every load below assumes the bar is included.")
    if missing:
        notes.append("Not in your library yet: " + ", ".join(missing)
                     + ". Load the starter library to add them.")
    if knee["awaiting_next_day"]:
        notes.append("Score how your knee felt the morning after your last "
                     "session — it is what decides whether load goes up.")

    return {
        "day": day,
        "phase": phase,
        "knee": knee,
        "blocks": blocks,
        "notes": notes,
        "achievable_loads": loads,
        "tai_chi_form_due": due_form,
        "kind": decision["kind"],
        "kind_why": decision["why"],
        "theme": theme,
    }
