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
import re
from collections import namedtuple
from datetime import datetime, timedelta

from app.data.programs import (
    Block, DEFAULT_FOCUS, MODE_ORDER, MODES, PRACTICE, PROGRAMS,
    SESSION_LIMITS,
)
from app.models.table_class import (
    Exercise, PracticeItem, SetLog, Symptom, SymptomLog, TrainingProfile,
    WorkoutSession,
)

logger = logging.getLogger(__name__)

def session_limits(db, user_id, tz_offset=0) -> dict | None:
    """What today's symptoms rule out, as opposed to how much they rule down.

    Returns the strictest limit any recent symptom imposes, or None. Strictest
    rather than most recent: two things logged the same morning should not let
    the milder one decide what the session may contain.
    """
    cutoff = datetime.utcnow() - timedelta(days=1)
    strictest = None
    rows = (
        db.query(SymptomLog, Symptom)
        .join(Symptom, SymptomLog.symptom_id == Symptom.symptom_id)
        .filter(SymptomLog.user_id == user_id)
        .all()
    )
    for log, sym in rows:
        if not log.date_time or not sym.symptom_name:
            continue
        naive = log.date_time.replace(tzinfo=None) if log.date_time.tzinfo else log.date_time
        if naive < cutoff:
            continue
        low = sym.symptom_name.lower()
        for token, levels in SESSION_LIMITS.items():
            if token not in low:
                continue
            rule = levels.get(log.symptom_intensity or 0)
            if rule is None:
                continue
            entry = {
                **rule,
                "symptom": sym.symptom_name,
                "level": log.symptom_intensity,
                "level_word": {1: "mild", 2: "moderate", 3: "severe"}.get(
                    log.symptom_intensity, str(log.symptom_intensity)),
                # Marked as UTC. Without the Z, new Date() in the browser
                # reads it as local time, so a log made at 09:07 NZST — stored
                # as 21:07 UTC the day before — was shown as 21:07, half a day
                # and a date out.
                "logged_at": naive.isoformat(timespec="minutes") + "Z",
                # A name for the shape of the day, so the session can be
                # described in one word before it is read in full.
                "mode": "gentle" if rule["max_exertion"] <= 1 else "reduced",
            }
            if strictest is None or (entry["max_exertion"], entry["allow_floor"]) < \
                    (strictest["max_exertion"], strictest["allow_floor"]):
                strictest = entry
    return strictest


def user_focus(db, user_id) -> str:
    """Which programme this user follows. Unknown values fall back to default."""
    p = db.query(TrainingProfile).filter(TrainingProfile.user_id == user_id).first()
    focus = getattr(p, "focus", None) or DEFAULT_FOCUS
    return focus if focus in PROGRAMS else DEFAULT_FOCUS


def unlocked_programs(profile) -> set:
    """Private programmes this account may use.

    Kept on the profile rather than keyed to a name or id in the source: the
    repository is not the place to record who somebody is, and a list means
    unlocking a second person needs no code change.
    """
    unlocked = set()
    if profile is not None and profile.equipment_json:
        try:
            data = json.loads(profile.equipment_json)
            if isinstance(data.get("programs"), list):
                unlocked = {str(x) for x in data["programs"]}
        except (ValueError, TypeError):
            pass
    # Whatever is already selected stays selectable, so nobody can switch away
    # from a programme and then find they cannot switch back.
    current = getattr(profile, "focus", None)
    if current:
        unlocked.add(current)
    return unlocked


def visible_programs(profile) -> dict:
    unlocked = unlocked_programs(profile)
    return {
        key: spec for key, spec in PROGRAMS.items()
        if not spec.get("private") or key in unlocked
    }


def program(focus: str) -> dict:
    return PROGRAMS.get(focus, PROGRAMS[DEFAULT_FOCUS])


DAY_ORDER = ["A", "B", "C"]

# The existing practice, appended to every day. "check" means there is nothing
# to count — it either happened or it did not — which still records that the
# knees were loaded that day.
def due_of_pair(db, user_id, first_id, second_id):
    """Of two exercises done in turn, whichever was not done last.

    Ordered by session time then by set id, so two logged in the same session
    fall back to the order they were entered — comparing anything else would
    tie-break on something unrelated to which came last.
    """
    rows = (
        db.query(SetLog, WorkoutSession)
        .join(WorkoutSession, SetLog.session_id == WorkoutSession.session_id)
        .filter(SetLog.user_id == user_id,
                SetLog.exercise_id.in_([first_id, second_id]))
        .all()
    )
    seen = [(s.date_time, st.set_id, st.exercise_id)
            for st, s in rows if s.date_time]
    if not seen:
        return first_id
    last = max(seen)[2]
    return second_id if last == first_id else first_id


# ── Knee back-off ────────────────────────────────────────────────────────────
# Pain during a set and pain the next morning are different measurements. The
# second is the one that matters: a session can feel fine and still be too much.
NEXT_DAY_BACKOFF = 4      # >= this in the last scored session -> back off
SET_PAIN_BACKOFF = 4      # >= this mean pain during the last session -> back off
SET_PAIN_HOLD = 3         # >= this -> hold progression rather than back off
# Symptom logs are on a 0-3 scale: none, mild, moderate, severe. Moderate or
# worse holds training back; mild repeats rather than progresses.
SYMPTOM_WINDOW_DAYS = 2   # older than this and it is history, not today

# Not all reports of the same score mean the same thing, so the threshold
# depends on what was reported. Swelling is a joint saying it is inflamed and
# is a firmer stop than pain of the same score. Giving way is instability, and
# the thing to avoid is balancing on that leg rather than volume in general.
# Stiffness is usually the mildest and often eases with movement.
#
# Matched on the symptom name, longest first, so "giving way" is not read as
# generic pain. Anything unrecognised is treated as pain.
SYMPTOM_RULES = [
    ("swelling",   {"back_off": 1, "hold": 1, "instability": False}),
    ("giving way", {"back_off": 1, "hold": 1, "instability": True}),
    ("stiffness",  {"back_off": 3, "hold": 2, "instability": False}),
]
SYMPTOM_DEFAULT = {"back_off": 2, "hold": 1, "instability": False}
RPE_CEILING = 8           # progress load only if the last sets were <= this
RECENT_SCORES = 5         # how many recent next-day scores decide a phase
MIN_EXERCISES_FOR_CREDIT = 3   # exercises needed for a session to count
STALL_SESSIONS = 3        # identical failed attempts before backing the target off
STALL_FACTOR = 0.75       # how far back a stalled target drops
# A single max effort is not a working set. Three sets at the number you could
# just about reach once is the exact mistake that leaving reps in reserve
# exists to avoid, so the assessment is scaled down to a level that repeats.
ASSESSMENT_FACTOR = 0.75
# A stalled target has to be allowed below the prescribed range, or the range's
# own floor blocks the reduction and the loop survives the fix. These are the
# absolute floors; at them, the exercise itself is the problem.
# Plates assumed when a user has not recorded their own.
DEFAULT_PLATES = {3.0: 8, 2.5: 4, 1.25: 4}

REPS_FLOOR = 5
SECONDS_FLOOR = 10


def achievable_loads(profile) -> list[float]:
    """Every dumbbell weight that can actually be built from the plates owned.

    Plates split evenly across two bars and load symmetrically, so they are
    consumed in pairs — which is what makes the usable steps 2.5kg rather than
    1.25kg. Prescribing a load the user cannot assemble is worse than useless.
    """
    bar = profile.dumbbell_bar_kg if profile and profile.dumbbell_bar_kg is not None else 0.0

    # A common starter set, used only when nothing has been recorded. It was
    # one particular person's kit, which was fine while there was one user and
    # wrong the moment there were more: someone else's dumbbells would have
    # been assumed to be these.
    plates = dict(DEFAULT_PLATES)
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


def achievable_bands(profile) -> list[float]:
    """Band resistances owned, lightest first.

    Band exercises had only reps to progress on, so topping out a rep range
    left the engine with nowhere to go but the stall-and-deload path — when
    the actual answer is the same reps against the next band.
    """
    if profile and profile.equipment_json:
        try:
            data = json.loads(profile.equipment_json)
            if isinstance(data.get("bands"), list) and data["bands"]:
                return sorted({float(b) for b in data["bands"]})
        except (ValueError, TypeError, AttributeError):
            logger.warning("equipment_json unreadable; no band sizes")
    return []


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
        return [], None, False
    latest = max(s.date_time for _, s in dated)
    sets = [st for st, s in dated if s.date_time == latest]
    was_assessment = any(s.session_type == "assessment"
                         for _, s in dated if s.date_time == latest)
    return sets, latest, was_assessment


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
    # Rungs, not a cliff: a step down that cannot be done drops to the same
    # movement with a hand on support, then to holding the position, then to
    # the two-legged isometric.
    "anterior step down": [("Lateral Step Down", "reps", 5, 10),
                           ("Supported Single Leg Squat", "reps", 5, 12),
                           ("Single Leg Balance", "iso", 10, 30),
                           ("Spanish Squat", "iso", 20, 45)],
    "lateral step down": [("Supported Single Leg Squat", "reps", 5, 12),
                          ("Single Leg Balance", "iso", 10, 30),
                          ("Spanish Squat", "iso", 20, 45)],
    "supported single leg squat": [("Single Leg Balance", "iso", 10, 30),
                                   ("Spanish Squat", "iso", 20, 45)],
    "single leg balance": [("Spanish Squat", "iso", 20, 45)],
    "spanish squat": [("Wall Sit", "iso", 20, 45)],
    "push up": [("Incline Push Up", "reps", 5, 12)],
    "romanian deadlift": [("Single Leg Glute Bridge", "reps", 8, 15)],
    "tricep dip": [("Incline Push Up", "reps", 5, 12)],
}


# Stand-ins for kit that is not there yet. Unlike REGRESSIONS
# these are not easier, just equipment-free: the same movement done another way.
# Anything with no honest bodyweight equivalent is left out rather than replaced
# with something unrelated — a session missing its rows is more use than one
# that pretends a plank is a row.
TRAVEL_SUBSTITUTES = {
    "goblet squat": ("Wide Leg Squat", "reps", 8, 15),
    "box squat": ("Wide Leg Squat", "reps", 8, 15),
    "split squat": ("Lunge", "reps", 6, 12),
    "single leg squat": ("Lunge", "reps", 6, 12),
    "romanian deadlift": ("Single Leg Glute Bridge", "reps", 8, 15),
    "spanish squat": ("Wall Sit", "iso", 20, 45),
    "terminal knee extension": ("Quad Set", "iso", 10, 30),
    "standing hip abduction": ("Side Lying Hip Abduction", "reps", 10, 20),
    "clamshell": ("Clamshell", "reps", 10, 20),
    "lateral band walk": ("Side Lying Hip Abduction", "reps", 10, 20),
    "dumbbell shoulder press": ("Pike Push Up", "reps", 5, 12),
    "dumbbell floor press": ("Push Up", "reps", 8, 15),
    "band pull apart": ("Prone Y Raise", "reps", 8, 15),
    "standing calf raise": ("Standing Calf Raise", "reps", 12, 20),
}

# Needs nothing, so it is never something to own: "bodyweight" is a floor and
# "none" is the martial practice.
ALWAYS_AVAILABLE = {"bodyweight", "none"}


def available_equipment(profile) -> set | None:
    """What the user has. None means no restriction — assume everything.

    Kit arrives in instalments, so this is a list rather than a home/away flag:
    dumbbells one week and bands the next is the normal case, not an edge one.
    """
    if profile is None or not profile.equipment_json:
        return None
    try:
        data = json.loads(profile.equipment_json)
    except (ValueError, TypeError):
        logger.warning("equipment_json unreadable; assuming everything is to hand")
        return None
    owned = data.get("available")
    if not isinstance(owned, list):
        return None
    return {str(x) for x in owned} | ALWAYS_AVAILABLE


def _within_limits(ex, limits) -> bool:
    """Whether an exercise is allowed by today's limits at all."""
    if not limits:
        return True
    if (ex.exertion or 2) > limits["max_exertion"]:
        return False
    return not (ex.floor_based and not limits["allow_floor"])


def _equipment_swap(name, equipment, by_name, available):
    """Replace an exercise needing kit that is not there. None means drop it."""
    if available is None or equipment in available:
        return "keep"
    spec = TRAVEL_SUBSTITUTES.get(name.strip().lower())
    if spec is None:
        return None
    sub_name, scheme, low, high = spec
    ex = by_name.get(sub_name.strip().lower())
    if ex is None or ex.equipment not in available:
        return None
    return Block(sub_name, scheme, 3, low, high), ex


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


def classify_symptom(name: str) -> dict:
    """How firmly a report of this kind should be treated."""
    low = (name or "").lower()
    for token, rule in SYMPTOM_RULES:
        if token in low:
            return {**rule, "kind": token}
    return {**SYMPTOM_DEFAULT, "kind": "pain"}


def symptom_side(name: str):
    """Which side a symptom names, if it names one.

    Word boundaries matter: "lateral" contains no side, but a careless
    substring check for "left" would not fire on it while one for "right"
    would never fire at all. Matched as whole words for that reason.
    """
    words = re.findall(r"[a-z]+", (name or "").lower())
    if "right" in words:
        return "right"
    if "left" in words:
        return "left"
    return None


def recent_symptom(db, user_id, keywords, tz_offset=0):
    """The most significant matching report from the last couple of days.

    Not simply the highest score: swelling at mild outranks stiffness at
    moderate, because the thresholds differ by what was reported. So each
    candidate is resolved to the action it would cause, and the strongest
    action wins, with intensity breaking ties.

    Only the recent window counts. A sore knee last week that has not recurred
    is history, and holding training back on it forever would make the log
    something people avoid using.
    """
    if not keywords:
        return None
    names = {
        s.symptom_id: s.symptom_name
        for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()
        if s.symptom_name and any(k in s.symptom_name.lower() for k in keywords)
    }
    if not names:
        return None

    cutoff = datetime.utcnow() - timedelta(days=SYMPTOM_WINDOW_DAYS)
    rank = {"back_off": 2, "hold": 1, None: 0}
    best = None
    for log in (db.query(SymptomLog)
                .filter(SymptomLog.user_id == user_id,
                        SymptomLog.symptom_id.in_(names.keys()))
                .all()):
        if not log.date_time:
            continue
        naive = log.date_time.replace(tzinfo=None) if log.date_time.tzinfo else log.date_time
        if naive < cutoff:
            continue

        name = names[log.symptom_id]
        level = log.symptom_intensity or 0
        rule = classify_symptom(name)
        if level >= rule["back_off"]:
            action = "back_off"
        elif level >= rule["hold"]:
            action = "hold"
        else:
            continue

        report = {
            "name": name, "level": level, "when": naive, "action": action,
            "kind": rule["kind"], "instability": rule["instability"],
            "side": symptom_side(name),
        }
        # Ties broken towards instability: giving way changes what you do
        # rather than how much of it, so a report that removes single-leg work
        # outranks one that only trims volume at the same score.
        key = (rank[action], int(rule["instability"]), level)
        if best is None or key > (rank[best["action"]],
                                  int(best["instability"]), best["level"]):
            best = report
    return best


def knee_state(db, user_id, word="soreness", keywords=None, tz_offset=0) -> dict:
    """Whether to back off, hold, or progress, and why."""
    # A symptom logged elsewhere in the app outranks anything the training
    # log knows: it is a report of how the body is today, and it applies even
    # before the first session is logged.
    flagged = recent_symptom(db, user_id, keywords or [], tz_offset)
    if flagged:
        level = {1: "mild", 2: "moderate", 3: "severe"}.get(flagged["level"],
                                                            str(flagged["level"]))
        when = flagged["when"].strftime("%-d %b")
        if flagged["action"] == "back_off":
            reason = (f"You logged {flagged['name']} as {level} on {when}. "
                      f"Load comes down a step and volume is cut until it settles.")
            if flagged["kind"] == "swelling":
                reason += " Swelling is a firmer stop than pain of the same score."
            if flagged["instability"]:
                reason += (" Balancing on that leg is the thing to avoid, so "
                           "single-leg work on it is out of today's session.")
        else:
            reason = (f"You logged {flagged['name']} as {level} on {when} — "
                      f"repeating rather than adding.")
        return {
            "action": flagged["action"],
            "reason": reason,
            "awaiting_next_day": None,
            "from_symptom_log": True,
            "affected_side": flagged["side"],
            "instability": flagged["instability"],
            "symptom_kind": flagged["kind"],
        }

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
            "reason": (f"{word.capitalize()} was {scored.next_day_knee}/10 the day "
                       f"after your last scored session. Load comes down a step "
                       f"and volume is cut."),
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
            "reason": f"No lingering {word} — progressing.",
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


def current_phase(db, user_id, focus=None) -> dict:
    """Which phase, and what still has to happen to leave it."""
    phases = program(focus or user_focus(db, user_id))["phases"]
    all_strength = [
        s for s in db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id).all()
        if s.session_type == "strength"
    ]

    # Names from every phase, because a session was logged under whichever
    # phase applied at the time.
    strength_names = {
        b.name.strip().lower()
        for prog in PROGRAMS.values()
        for spec in prog["phases"].values()
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
            need.append(plural(3 - len(scores), "next-day score"))
        if scores and not quiet:
            need.append("next-day knee at 3/10 or below")
        to_advance = " and ".join(need) or "next-day scores staying low"
        if partial:
            to_advance += (f" ({partial} session{'' if partial == 1 else 's'} too "
                           f"short to count — {MIN_EXERCISES_FOR_CREDIT}+ exercises "
                           f"needed)")
    elif phase == 2:
        remaining = max(0, 14 - done)
        to_advance = (f"{remaining} more strength session"
                      f"{'' if remaining == 1 else 's'} without lingering soreness")
    else:
        to_advance = "already at the top phase"

    return {"phase": phase, "label": phases[phase]["label"],
            "aim": phases[phase]["aim"], "sessions_done": done,
            "partial_sessions": partial,
            "to_advance": to_advance}


def _prescribe(block, ex, last_sets, action, loads, last_done=None,
               stalled=False, from_assessment=False, bands=None):
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
        elif from_assessment:
            target = max(block.low, min(int(top * ASSESSMENT_FACTOR), block.high))
            why = (f"From your assessment: one max effort of {top}s. Working "
                   f"sets start at {target}s, about three quarters of it, "
                   f"because three sets at your limit is not a working level.")
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
        # A banded exercise progresses on the band once the reps are maxed.
        banded = bool(bands) and ex.equipment == "band"
        used_bands = [s.band_kg for s in last_sets if s.band_kg is not None]
        last_band = max(used_bands) if used_bands else (bands[0] if banded else None)
        rpes_r = [s.rpe for s in last_sets if s.rpe is not None]
        easy_enough = all(r <= RPE_CEILING for r in rpes_r) if rpes_r else True
        if banded and weight is None:
            weight = last_band
        if action == "back_off":
            target = max(block.low, int(top * 0.8) or block.low)
            why = "Volume cut while the knee settles."
        elif action == "hold" or not top:
            target = max(block.low, min(top or block.low, block.high))
            why = "Repeat last time." if top else "Starting point."
        elif from_assessment:
            target = max(block.low, min(int(top * ASSESSMENT_FACTOR), block.high))
            why = (f"From your assessment: one max effort of {top}. Working "
                   f"sets start at {target}, about three quarters of it, "
                   f"because three sets at your limit is not a working level.")
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
        elif banded and top >= block.high and easy_enough:
            # The band is this exercise's load. Topping out the reps is the
            # signal to move up one and start the range again, exactly as
            # adding a plate would.
            weight = _next_load(last_band, bands, up=True)
            if weight is not None and last_band is not None and weight > last_band:
                target = block.low
                why = (f"Every set hit {block.high} on the {last_band}kg band, "
                       f"so it goes up to {weight}kg and reps reset to {block.low}.")
            else:
                target = block.high
                why = (f"Every set at {block.high} on your heaviest band — hold "
                       f"there and slow the tempo.")
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
        elif from_assessment:
            # The assessed load was already chosen as a submaximal set, so the
            # load stands and the reps start at the bottom of the range.
            weight, target = last_w, block.low
            why = (f"From your assessment: {top_reps} reps at {last_w}kg. Starting "
                   f"at {target} reps across {sets} sets at that load.")
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
        "target_band": weight if block.scheme == "reps" and ex.equipment == "band" else None,
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


def build_session(db, user_id, day=None, tz_offset=0, kind=None,
                  mode=None) -> dict:
    """The whole prescription for the next session."""
    focus = user_focus(db, user_id)
    prog = program(focus)
    phase = current_phase(db, user_id, focus)
    knee = knee_state(db, user_id, prog["soreness"],
                      prog.get("symptom_keywords"), tz_offset)
    profile = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == user_id).first()
    loads = achievable_loads(profile)
    bands = achievable_bands(profile)
    available = available_equipment(profile)

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

    # A user's own routine wins. The programme default is a starting point for
    # someone who has not built one, not something to append over the top.
    rows = db.query(PracticeItem).filter(PracticeItem.user_id == user_id).all()
    due_form = None
    if rows:
        practice = {"before": [], "after": []}
        for item in sorted(rows, key=lambda i: (i.position, i.practice_item_id)):
            ex_row = item.exercise
            if ex_row is None:
                continue
            name = ex_row.exercise_name
            if item.alternates_with_id and item.alternate is not None:
                due_id = due_of_pair(db, user_id, item.exercise_id,
                                     item.alternates_with_id)
                name = (ex_row.exercise_name if due_id == item.exercise_id
                        else item.alternate.exercise_name)
                due_form = name
            practice.setdefault(item.slot, []).append(
                Block(name, item.scheme, item.sets, item.low, item.high)
            )
    else:
        practice = PRACTICE.get(focus, PRACTICE[DEFAULT_FOCUS])

    if decision["kind"] == "strength":
        middle = [(b, "strength") for b in prog["phases"][phase["phase"]]["days"][day]]
        theme = prog["phases"][phase["phase"]]["themes"][day]
    else:
        # Between strength days the knees still get their work; the muscle gets
        # its recovery day. It sits where the strength work would have been.
        middle = [(b, "maintenance") for b in prog["maintenance"]]
        theme = "Practice and maintenance"

    blocks, missing = [], []
    templates = [(b, "practice") for b in practice["before"]]
    templates += middle
    templates += [(b, "practice") for b in practice["after"]]

    # What the log suggests, which is not the same as what is happening. The
    # suggestion is the default; a mode passed in is the user overruling it,
    # and they know whether the triptan worked.
    suggested = session_limits(db, user_id, tz_offset)
    suggested_mode = (suggested or {}).get("mode", "full")

    if mode in MODES and mode != suggested_mode:
        chosen = dict(MODES[mode])
        if suggested:
            chosen["note"] = (
                f"{MODES[mode]['note']} You chose this over the suggested "
                f"{MODES[suggested_mode]['label'].lower()} after logging "
                f"{suggested['symptom'].lower()} as {suggested['level_word']}."
            )
            chosen["symptom"] = suggested["symptom"]
            chosen["level_word"] = suggested["level_word"]
            chosen["logged_at"] = suggested["logged_at"]
        chosen["mode"] = mode
        chosen["overridden"] = True
        limits = None if mode == "full" else chosen
    else:
        limits = suggested

    by_id = {e.exercise_id: e for e in by_name.values()}
    dropped, limited, used_ids = [], [], set()
    for block, group in templates:
        ex = by_name.get(block.name.strip().lower())
        if ex is None:
            missing.append(block.name)
            continue

        swapped_from = None
        swap = _equipment_swap(block.name, ex.equipment, by_name, available)
        if swap is None:
            # No equivalent using what is to hand. Leaving it out is more use
            # than substituting something that trains a different thing.
            dropped.append(ex.exercise_name)
            continue
        if swap != "keep":
            swapped_from = block.name
            block, ex = swap

        # After any substitution, not just on the swap path: a swap can
        # land on an exercise the day already contains, and whichever of the two
        # comes first claims the slot. Prescribing it twice would be wrong
        # either way round.
        if ex.exercise_id in used_ids:
            if swapped_from:
                dropped.append(swapped_from)
            continue

        # A back-off applies to what is actually sore. Cutting the volume of
        # everything because one joint hurts loses training for no reason, and
        # "volume cut while the knee settles" on a row reads as nonsense.
        targets = prog.get("soreness_targets")
        action = knee["action"]
        sore_area = targets is None or (ex.target or "") in targets
        if action in ("back_off", "hold") and not sore_area:
            action = "progress"

        # Balancing on a knee that gives way is the specific risk, so standing
        # single-leg work comes out rather than being trimmed. Note this is
        # needs_balance rather than is_unilateral: a lying quad set is done one
        # leg at a time and involves no balance at all.
        if knee.get("instability") and sore_area and ex.needs_balance:
            dropped.append(ex.exercise_name)
            continue

        # Only the sore side eases off. Detraining the good leg because the
        # other one hurts loses training for nothing, and the log already
        # records which side each set was done on.
        affected = knee.get("affected_side") if sore_area else None

        prior, when, from_test = _last_sets(db, user_id, ex.exercise_id)
        item = _prescribe(
            block, ex, prior, action, loads, last_done=when,
            stalled=_stalled(db, user_id, ex.exercise_id, block.scheme),
            from_assessment=from_test, bands=bands,
        )

        # For a unilateral exercise with one sore side, work out what the good
        # side should do by prescribing it again as though nothing hurt.
        if affected and ex.is_unilateral and action in ("back_off", "hold"):
            healthy = _prescribe(
                block, ex, prior, "progress", loads, last_done=when,
                stalled=_stalled(db, user_id, ex.exercise_id, block.scheme),
                from_assessment=from_test, bands=bands,
            )
            other = "left" if affected == "right" else "right"
            # "each side" is what the bilateral wording says; once the two
            # sides are prescribed separately it contradicts itself.
            strip = lambda s: s.replace(" each side", "")
            item["side_targets"] = {
                affected: {"reps": item["target_reps"], "seconds": item["target_seconds"],
                           "sets": item["sets"]},
                other: {"reps": healthy["target_reps"], "seconds": healthy["target_seconds"],
                        "sets": healthy["sets"]},
            }
            item["affected_side"] = affected
            item["prescription"] = (f"{other}: {strip(healthy['prescription'])} · "
                                    f"{affected}: {strip(item['prescription'])}")
            item["why"] = (f"Only the {affected} side eases off. {item['why']}")

        if item.pop("exhausted", False):
            swap = _substitute(db, user_id, block.name, by_name)
            if swap is None:
                # Nothing to move to, so say what is happening rather than
                # repeating a target that has already failed three times.
                item["why"] += (" No easier version of this is in your library — "
                                "swap it for something you can complete.")
            else:
                sub_block, sub_ex = swap
                sub_prior, sub_when, sub_test = _last_sets(db, user_id, sub_ex.exercise_id)
                item = _prescribe(
                    sub_block, sub_ex, sub_prior, action, loads,
                    last_done=sub_when,
                    stalled=_stalled(db, user_id, sub_ex.exercise_id, sub_block.scheme),
                    from_assessment=sub_test, bands=bands,
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

        # After the swaps, not before them. A limit rules an exercise out
        # rather than trimming it — on a migraine day the problem is bending
        # down and exerting, and a lighter set still involves both. Checking
        # the templated exercise instead let a substitute through: terminal
        # knee extension is upright and gentle, but with no bands it becomes
        # the quad set, which is done on the floor.
        final_ex = by_id.get(item["exercise_id"], ex)
        if not _within_limits(final_ex, limits):
            limited.append(final_ex.exercise_name)
            continue

        item.pop("exhausted", None)
        used_ids.add(item["exercise_id"])
        item["group"] = group
        if swapped_from and item["exercise"] != swapped_from:
            item["equipment_substitute"] = swapped_from
            item["why"] = (f"Standing in for {swapped_from}, which needs kit you "
                           f"have not marked as available. {item['why']}")
        blocks.append(item)

    notes = []
    # `is None`, not falsiness: a plastic bar that genuinely weighs nothing is
    # recorded as 0.0, and asking someone to go and weigh what they just told
    # you is how a prompt gets ignored.
    if profile is None or profile.dumbbell_bar_kg is None:
        notes.append("Weigh a bare dumbbell bar and save it in your profile — "
                     "every load below assumes the bar is included.")
    if missing:
        notes.append("Not in your library yet: " + ", ".join(missing)
                     + ". Load the starter library to add them.")
    if limits:
        note = limits["note"]
        if limited:
            note += (" Out today: " + ", ".join(sorted(set(limited))) + ".")
        notes.insert(0, note)
    if knee.get("instability") and dropped:
        notes.append("Single-leg work is out while the knee is giving way: "
                     + ", ".join(sorted(set(dropped)))
                     + ". Two-legged work carries on at reduced volume.")
        dropped = []
    if dropped:
        notes.append("Left out because nothing you have can stand in for "
                     + ", ".join(sorted(set(dropped)))
                     + " — better a gap than something that trains a different "
                       "thing.")
    if knee["awaiting_next_day"]:
        notes.append(f"Score the {prog['soreness']} you felt the morning after "
                     f"your last session — it is what decides whether load "
                     f"goes up.")

    return {
        "day": day,
        "phase": phase,
        "knee": knee,
        "blocks": blocks,
        "notes": notes,
        "achievable_loads": loads,
        "bands": bands,
        "tai_chi_form_due": due_form,
        "available_equipment": sorted(available) if available else None,
        "limits": limits,
        "mode": (limits or {}).get("mode", "full"),
        "suggested_mode": suggested_mode,
        # Shown whichever mode is running, so the reason is never lost.
        "suggested_because": (
            {k: suggested[k] for k in ("symptom", "level_word", "logged_at", "note")}
            if suggested else None
        ),
        "modes": [{"key": m, "label": MODES[m]["label"]} for m in MODE_ORDER],
        "focus": focus,
        "focus_label": prog["label"],
        "soreness_word": prog["soreness"],
        "soreness_prompt": prog["soreness_prompt"],
        "kind": decision["kind"],
        "kind_why": decision["why"],
        "theme": theme,
    }
