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

from app.data.stretches import (
    LADDER_NAMES, LADDER_NOTE, routine_for, scheme_for_seconds,
)
from app.data.programs import (
    ASSIST_BANDS, Block, CONDITIONING, DAILY, DEFAULT_FOCUS, HAMSTRING_END_RANGE,
    MODE_ORDER, MODES, POSTEROLATERAL_REST, PRACTICE, PROGRAMS,
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
                # Two forms. The UTC instant for anything that needs to
                # compute, and a preformatted local string for display: the
                # request already carries the offset, so the server can do the
                # conversion rather than depending on how a given browser
                # parses an ISO string. Safari in particular is strict about
                # ones without seconds.
                "logged_at": naive.isoformat(timespec="seconds") + "Z",
                "logged_at_local": (naive - timedelta(minutes=tz_offset))
                    .strftime("%-d %b, %-I:%M %p").replace("AM", "am").replace("PM", "pm"),
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
# One day, not two. A symptom two days old was still holding a session back on
# a day the person felt fine, and training every day makes that the difference
# between one gentle session and three. It is a rolling 24 hours from now
# rather than "logged today", so a morning log stops counting tomorrow morning.
SYMPTOM_WINDOW_DAYS = 1   # older than this and it is history, not today

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
GRADUATE_SESSIONS = 3     # sessions finished at the ceiling before stepping up
REST_WEEKDAY = 6          # Sunday, in Python's Monday-is-0 numbering
DELOAD_EVERY_WEEKS = 6    # a planned easy week, counted from the first session
# A week may carry about a third more work than the week before it. Every
# other safeguard in here watches one exercise at a time — the stall rule, the
# back-off, the deload — and none of them can see the session as a whole. That
# is the gap a mobility routine went through when it went from one logged set
# a day to thirty-six in four days.
# Measured as the last seven days against the average week of the last
# twenty-eight — the acute-to-chronic comparison — rather than this week
# against last week. Week against week is far too jumpy at the start: someone
# whose previous week held one session has a baseline of nothing, every
# subsequent week looks like a threefold increase, and the rule fires
# permanently and says to cut more sets than the session contains.
RAMP_LIMIT = 1.3
RAMP_MIN_BASELINE = 60    # a chronic week below this is not yet a baseline
RAMP_MAX_TRIM = 0.35      # never cut more than this much of a session
NEW_PER_SESSION = 2       # unfamiliar movements to meet on any one day
# Clear days after a back-outer knee report before anything comes back, and
# then one more movement returns every few days rather than all of them at
# once. A tendon that hurts in the morning and feels fine once warm has not
# recovered — it has warmed up, which is a property of tendons and the reason
# people re-injure them the day they feel better.
# One clear day, at the owner's call, after a morning score of nought and a
# session that went well. Three was my number and a conventional one rather
# than a measured one, and the staging below is the half of this that matters:
# the movements still come back one at a time, so a flare can still be traced
# to whichever one caused it.
SETTLE_DAYS = 1
RETURN_EVERY_DAYS = 3
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


class History:
    """Every logged set for one person, read once and kept.

    Each rule below used to fetch this for itself — the last sets for an
    exercise, whether it has stalled, whether it has topped out, how much work
    the week holds, what has ever been done at all. Every one of those ran a
    query across the whole of somebody's history, and most were called once per
    exercise inside the block loop. Drawing a single session took a hundred and
    fourteen statements and five seconds.

    It is the same data every time, so it is read once. This is less code than
    the version that was slow, not more.
    """

    def __init__(self, db, user_id):
        self.rows = (
            db.query(SetLog, WorkoutSession)
            .join(WorkoutSession, SetLog.session_id == WorkoutSession.session_id)
            .filter(SetLog.user_id == user_id).all()
        )
        self.by_exercise, self.by_session = {}, {}
        for st, s in self.rows:
            self.by_exercise.setdefault(st.exercise_id, []).append((st, s))
            self.by_session.setdefault(st.session_id, []).append(st)

    def for_exercise(self, exercise_id):
        return self.by_exercise.get(exercise_id, [])

    def ever_logged(self):
        return set(self.by_exercise)

    def sets_of(self, session):
        """A session's sets without going back for them.

        session.sets is a lazy relationship, so reading it inside a loop over
        sessions is one query per session — which was the whole of what
        remained after the per-exercise queries went.
        """
        return self.by_session.get(session.session_id, [])


def _last_sets(hist, exercise_id):
    """Sets from the most recent session that included this exercise, and when.

    The date matters because a skipped exercise keeps its old baseline. Without
    it the prescription would say "every set hit 10 — one more" about a session
    three weeks ago as though it were the last one.
    """
    dated = [(st, s) for st, s in hist.for_exercise(exercise_id) if s.date_time]
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
# The way up when there is no weight to add. A tube puller has six tubes and
# that is that, so an exercise finished at the top of its range is finished
# full stop — the only progression left is a harder version of the movement,
# and one limb at a time roughly doubles the load without touching the kit.
#
# One-way on purpose. Stalling on the harder version is handled the way any
# stall is, by dropping the target; sending it back down to the two-armed
# version would re-meet the graduation test on the very next session and
# oscillate between the two forever.
PROGRESSIONS = {
    "tube seated row": ("Tube Single Arm Row", "reps", 6, 12),
    "tube lat pulldown": ("Tube Single Arm Lat Pulldown", "reps", 6, 12),
}

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
    "tube seated row": ("Dumbbell Row", "load", 8, 12),
    "tube single arm row": ("Dumbbell Row", "load", 8, 12),
    "tube face pull": ("Band Pull Apart", "reps", 12, 20),
    # Not the same exercise, and the only honest one available: the tube loads
    # the lift, this one only asks you to hold the top of it. Better a weaker
    # version of the right movement than a strong version of a different one.
    "band hip flexion": ("Active Straight-Leg Raise Hold", "iso", 8, 15),
    # Tube lat pulldown is deliberately absent. Nothing here pulls vertically
    # without a bar overhead, and that is the reason it earned a place.
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


def _substitute(hist, name, by_name):
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
        if _stalled(hist, ex.exercise_id, scheme):
            continue          # no point moving onto something already stuck
        return Block(sub_name, scheme, 3, low, high), ex
    return None


def _topped_out(hist, exercise_id, scheme, high) -> bool:
    """Has this been finished at the top of its range often enough to move on?

    The mirror of _stalled, and the case its docstring sets aside: someone
    sitting at the top of a rep range and succeeding. For a loadable exercise
    that is not interesting, because the answer is more weight. For a fixed
    resistance there is no more weight, so it is the whole signal.

    Every set has to reach the ceiling, not just the best one. A top set at the
    ceiling with the rest trailing is someone who can hit the number once,
    which is the opposite of ready for a harder version.
    """
    field = {"iso": "hold_seconds", "reps": "reps", "load": "reps"}.get(scheme)
    if field is None or not high:
        return False

    by_session = {}
    for st, s in hist.for_exercise(exercise_id):
        if s.date_time:
            by_session.setdefault(s.date_time, []).append(st)
    if len(by_session) < GRADUATE_SESSIONS:
        return False

    for when in sorted(by_session, reverse=True)[:GRADUATE_SESSIONS]:
        vals = [getattr(x, field) or 0 for x in by_session[when]]
        if not vals or min(vals) < high:
            return False
    return True


def _stalled(hist, exercise_id, scheme) -> bool:
    """Has this exercise been stuck at the same failed target for a while?

    Repeating a target the person cannot complete is not a training plan, it is
    a loop. Three attempts at the identical figure without meeting it means the
    target is too hard, not that they need to try harder.

    "Identical" matters: a figure that is merely unchanged would also describe
    someone sitting at the top of a rep range and succeeding, who should not be
    dropped back. So a stall needs the last attempt to have actually fallen
    short as well.
    """
    by_session = {}
    for st, s in hist.for_exercise(exercise_id):
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


def symptom_region(name):
    """Which part of the knee a symptom names, if it names one.

    The side has been read off the label since sides were added; the region
    never was, so "knee pain - left lateral" and "knee pain - left medial"
    drove exactly the same response. They do not want the same response: the
    back-outer corner is tendon territory, loaded by deep bend and lunging,
    and easing the volume of a lunge leaves it a lunge.
    """
    low = (name or "").lower()
    for region in ("posterolateral", "posterior", "lateral", "medial", "anterior"):
        if region in low:
            return "lateral" if region == "posterolateral" else region
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
            "region": symptom_region(name),
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


def knee_state(db, user_id, word="soreness", keywords=None, tz_offset=0,
               hist=None) -> dict:
    """Whether to back off, hold, or progress, and why."""
    # A symptom logged elsewhere in the app outranks anything the training
    # log knows: it is a report of how the body is today, and it applies even
    # before the first session is logged.
    sets_of = hist.sets_of if hist is not None else (lambda s: s.sets)
    sessions = (
        db.query(WorkoutSession)
        .filter(WorkoutSession.user_id == user_id)
        .order_by(WorkoutSession.date_time.desc())
        .limit(5)
        .all()
    )

    # Worked out before anything can return, and carried on every branch.
    #
    # It used to be computed only on the path where nothing was wrong, and
    # every other branch hardcoded None — a logged symptom, a sore morning
    # score, painful sets. The morning-score box is hidden unless this names a
    # session, so the prompt vanished precisely when something hurt, which is
    # when the score matters most. Someone whose knee had settled could not
    # record that it had settled, because they had reported it hurting.
    worked = next((s for s in sessions if sets_of(s)), None)
    awaiting = (worked.session_id
                if worked is not None and worked.next_day_knee is None else None)

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
            "awaiting_next_day": awaiting,
            "from_symptom_log": True,
            "affected_side": flagged["side"],
            "instability": flagged["instability"],
            "symptom_kind": flagged["kind"],
            "region": flagged.get("region"),
        }

    sets_of = hist.sets_of if hist is not None else (lambda s: s.sets)
    if not sessions:
        return {"action": "progress", "reason": "No sessions logged yet.",
                "awaiting_next_day": None}

    # The most recent session that actually carries pain data, not simply the
    # most recent session. A session started and abandoned, or a tai chi
    # session logged with no sets, would otherwise mask the last real one and
    # silently switch the back-off rule off.
    last = next(
        (s for s in sessions if any(x.pain is not None for x in sets_of(s))),
        None,
    )
    pains = [x.pain for x in sets_of(last) if x.pain is not None] if last else []
    mean_pain = round(sum(pains) / len(pains), 1) if pains else None

    scored = next((s for s in sessions if s.next_day_knee is not None), None)

    if scored is not None and scored.next_day_knee >= NEXT_DAY_BACKOFF:
        return {
            "action": "back_off",
            "reason": (f"{word.capitalize()} was {scored.next_day_knee}/10 the day "
                       f"after your last scored session. Load comes down a step "
                       f"and volume is cut."),
            "awaiting_next_day": awaiting,
        }
    if mean_pain is not None and mean_pain >= SET_PAIN_BACKOFF:
        return {"action": "back_off",
                "reason": f"Mean pain in the last session was {mean_pain}/10.",
                "awaiting_next_day": awaiting}
    if mean_pain is not None and mean_pain >= SET_PAIN_HOLD:
        return {"action": "hold",
                "reason": f"Mean pain {mean_pain}/10 last session — repeat it "
                          f"rather than adding load.",
                "awaiting_next_day": awaiting}

    # Not a reason to back off, but the score is the input to the rule, so ask
    # for it — only where there was actually a session worth scoring.
    #
    # "Worth scoring" is a different question from "carries pain data", and
    # conflating the two deadlocked the programme. Pain is an optional field,
    # so someone who never fills it in has no pain-bearing session; the ask
    # never appears, because the box that carries it is hidden until this is
    # set; no next-day score is ever recorded; and leaving a phase requires
    # those scores. The result is a programme that progresses on the silent
    # assumption that nothing hurts and cannot advance a phase however well it
    # goes. Any session with sets in it is worth a morning-after score.
    return {"action": "progress",
            "reason": f"No lingering {word} — progressing.",
            "awaiting_next_day": awaiting}


# A session counts towards leaving a phase only if it covered a fair part of
# the day. Otherwise six sessions of one exercise each would unlock loaded
# squatting without the tolerance for the phase before it ever being shown.
def _substantial(session, strength_names, names_by_id=None, sets=None) -> bool:
    # names_by_id when the caller already has it. Reading st.exercise lazily
    # fires one query per set — for someone with a few hundred logged sets
    # that was most of the queries behind drawing a session, to answer a
    # question the caller could already answer from memory.
    rows = session.sets if sets is None else sets
    if names_by_id is not None:
        covered = {names_by_id[st.exercise_id].strip().lower()
                   for st in rows if st.exercise_id in names_by_id}
    else:
        covered = {st.exercise.exercise_name.strip().lower()
                   for st in rows if st.exercise is not None}
    return len(covered & strength_names) >= MIN_EXERCISES_FOR_CREDIT


def current_phase(db, user_id, focus=None, hist=None) -> dict:
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
    names_by_id = {e.exercise_id: e.exercise_name for e in
                   db.query(Exercise).filter(Exercise.user_id == user_id).all()}
    sessions = [s for s in all_strength
                if _substantial(s, strength_names, names_by_id,
                                hist.sets_of(s) if hist is not None else None)]
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


def _band_for(ex, block, weight, bands, last_sets):
    """Which band to offer, for any exercise that uses one.

    Held exercises use a band too and had no way to record it, so a Spanish
    squat never said which one held it up. Where the band assists, the default
    is the stiffest owned rather than the lightest — a band that cannot hold
    the lean is not a starting point, it is a failed set-up.
    """
    if ex.equipment != "band" or not bands:
        return None
    used = [s.band_kg for s in last_sets if s.band_kg is not None]
    if used:
        return max(used)
    if (ex.exercise_name or "").strip().lower() in ASSIST_BANDS:
        return bands[-1]
    return weight if weight is not None else bands[0]


def _repeat_floor(low, achieved):
    """The lowest a target may be set once there is a performance to go on.

    block.low is where someone with no history starts. Applied as a hard
    minimum it overrides the branches whose whole job is to repeat or ease
    off: three sets of 3, 3 and 2 against a range of 5-12 came back as
    "repeat 5 before adding", which is not a repeat, is more than was managed,
    and is a harder target handed out for a worse session. Below the range,
    what was actually done is the honest floor.
    """
    return low if not achieved else min(low, achieved)


def _prescribe(block, ex, last_sets, action, loads, last_done=None,
               stalled=False, from_assessment=False, bands=None):
    """Turn one template block plus history into a concrete instruction."""
    sets = block.sets
    detail, why = "", ""
    target, weight = None, None
    # Set when a stall has nowhere left to go: the caller then looks for an
    # easier version of the movement.
    exhausted = False

    if action in ("back_off", "deload"):
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
        # A walk has a dose, and "practise it" does not carry one. The low and
        # high of a conditioning block are minutes rather than reps.
        if (ex.category or "") == "conditioning":
            detail = (f"{block.low}-{block.high} min" if block.high
                      else "Get it done")
            why = ("Judge it by breath, not by pulse — a beta-blocker holds "
                   "the heart rate down however hard you are working.")
        else:
            detail = "Practise it"
            why = "Tick it off — logged so the knee load is on the record."
        target = None

    elif block.scheme == "iso":
        holds = [(s.hold_seconds or 0) for s in last_sets]
        top, weakest = (max(holds), min(holds)) if holds else (0, 0)
        if action in ("back_off", "deload"):
            target = max(_repeat_floor(block.low, top), int(top * 0.8) or block.low)
            why = ("Planned easy week — targets and sets come down together."
                   if action == "deload" else "Held back while the knee settles.")
        elif action == "hold" or not top:
            target = max(_repeat_floor(block.low, top), top or block.low)
            why = "Repeat last time's hold." if top else "Starting point."
        elif from_assessment:
            target = max(_repeat_floor(block.low, top), min(int(top * ASSESSMENT_FACTOR), block.high))
            why = (f"From your assessment: one max effort of {top}s. Working "
                   f"sets start at {target}s, about three quarters of it, "
                   f"because three sets at your limit is not a working level.")
        elif not complete:
            target = max(_repeat_floor(block.low, top), min(top, block.high))
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
            target = max(_repeat_floor(block.low, top), min(top, block.high))
            why = f"Last set dropped to {weakest}s — repeat {target}s before going longer."
        else:
            target = min(block.high, top + 5)
            why = f"Every set held {top}s — up 5s."
        detail = f"{sets} x {target}s hold"

    elif block.scheme == "reps":
        counts = [(s.reps or 0) for s in last_sets]
        top, weakest = (max(counts), min(counts)) if counts else (0, 0)
        # A banded exercise progresses on the band once the reps are maxed.
        # Only where the band resists. Where it holds you up, a stiffer one is
        # easier, so stepping up would be a regression dressed as progress.
        assists = (ex.exercise_name or "").strip().lower() in ASSIST_BANDS
        banded = bool(bands) and ex.equipment == "band" and not assists
        used_bands = [s.band_kg for s in last_sets if s.band_kg is not None]
        last_band = max(used_bands) if used_bands else (bands[0] if banded else None)
        rpes_r = [s.rpe for s in last_sets if s.rpe is not None]
        easy_enough = all(r <= RPE_CEILING for r in rpes_r) if rpes_r else True
        if banded and weight is None:
            weight = last_band
        if action in ("back_off", "deload"):
            target = max(_repeat_floor(block.low, top), int(top * 0.8) or block.low)
            why = ("Planned easy week — targets and sets come down together."
                   if action == "deload" else "Volume cut while the knee settles.")
        elif action == "hold" or not top:
            target = max(_repeat_floor(block.low, top), min(top or block.low, block.high))
            why = "Repeat last time." if top else "Starting point."
        elif from_assessment:
            target = max(_repeat_floor(block.low, top), min(int(top * ASSESSMENT_FACTOR), block.high))
            why = (f"From your assessment: one max effort of {top}. Working "
                   f"sets start at {target}, about three quarters of it, "
                   f"because three sets at your limit is not a working level.")
        elif not complete:
            target = max(_repeat_floor(block.low, top), min(top, block.high))
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
            target = max(_repeat_floor(block.low, top), min(top, block.high))
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

        if action in ("back_off", "deload"):
            weight = _next_load(last_w, loads, up=False)
            target = block.low
            why = ("Planned easy week — targets and sets come down together."
                   if action == "deload" else "Load down a step while the knee settles.")
        elif last_w is None:
            weight = loads[1] if len(loads) > 1 else (loads[0] if loads else None)
            target = block.low
            why = "First time — start light and see how it feels tomorrow."
        elif action == "hold":
            weight, target = last_w, max(_repeat_floor(block.low, top_reps), last_reps)
            why = "Same load again."
        elif from_assessment:
            # The assessed load was already chosen as a submaximal set, so the
            # load stands and the reps start at the bottom of the range.
            weight, target = last_w, block.low
            why = (f"From your assessment: {top_reps} reps at {last_w}kg. Starting "
                   f"at {target} reps across {sets} sets at that load.")
        elif not complete:
            weight, target = last_w, max(_repeat_floor(block.low, top_reps), top_reps)
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
            weight, target = last_w, max(_repeat_floor(block.low, top_reps), top_reps)
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
            # Per dumbbell, said out loud. The number is the weight of one
            # assembled dumbbell including its bar, and on a two-dumbbell
            # exercise "@ 5kg" reads just as easily as the pair — which is
            # twice the load and a question worth not having to ask.
            detail += f" @ {weight}kg per dumbbell"

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
        "target_band": _band_for(ex, block, weight, bands, last_sets),
        "per_side": bool(ex.is_unilateral),
        "exhausted": exhausted,
    }


def _local_date(dt, tz_offset):
    if dt is None:
        return None
    naive = dt.replace(tzinfo=None) if dt.tzinfo else dt
    return (naive - timedelta(minutes=tz_offset)).date()


def strength_spacing(profile) -> str:
    """"alternate" (a day between strength sessions) or "daily".

    Alternating is the default because it is the safer assumption, not because
    daily is wrong: with a rotation that moves the emphasis each day, training
    every day gives each area a couple of days off and is perfectly ordinary.
    """
    if profile and profile.equipment_json:
        try:
            data = json.loads(profile.equipment_json)
            if data.get("strength_spacing") in ("alternate", "daily"):
                return data["strength_spacing"]
        except (ValueError, TypeError, AttributeError):
            pass
    return "alternate"


def choose_kind(db, user_id, tz_offset) -> dict:
    """Strength today, or practice and the knee minimum?

    Muscle needs roughly a day between hard sessions, so strength days are kept
    apart: if one was done today or yesterday, today is a practice day. Over a
    week that settles into three or four strength sessions, which is where the
    evidence for a 3-day week sits — and it means every muscle is trained
    two or three times a week rather than once, as it would be on a split.
    """
    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()

    # Checked before spacing. A rest day is a fixed point in the week, and
    # "training every day" is a statement about the other six — otherwise the
    # setting quietly overrules the rest day every time.
    if today.weekday() == REST_WEEKDAY:
        return {"kind": "rest",
                "why": "Rest day. Your own practice only — no strength work "
                       "and no knee minimum. A programme that can only ever "
                       "add is how a good week turns into a sore one."}

    profile = db.query(TrainingProfile).filter(
        TrainingProfile.user_id == user_id).first()
    if strength_spacing(profile) == "daily":
        return {"kind": "strength",
                "why": "Training every day, with the emphasis rotating so each "
                       "area still gets a couple of days between sessions."}

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


def recent_easy_days(db, user_id, tz_offset=0, days=7):
    """Local dates in the window whose logs would have forced an easier session.

    A gentle day is not a rest day, which is why this reports rather than
    decides. Being ill is a load of its own, so a week spent under a migraine
    has arguably earned the rest more than a week of good training — but a
    week where the training was cut short for reasons that have since passed
    is a week with capacity left in it, and only the person can say which of
    those they are living in.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    names = {s.symptom_id: (s.symptom_name or "").lower()
             for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()}
    hits = set()
    for log in db.query(SymptomLog).filter(SymptomLog.user_id == user_id).all():
        if not log.date_time or log.symptom_id not in names:
            continue
        naive = (log.date_time.replace(tzinfo=None)
                 if log.date_time.tzinfo else log.date_time)
        if naive < cutoff:
            continue
        name = names[log.symptom_id]
        level = log.symptom_intensity or 0
        for key, levels in SESSION_LIMITS.items():
            if key in name and level in levels:
                hits.add(_local_date(log.date_time, tz_offset))
    return sorted(hits)


def _sets_between(hist, start, end, tz_offset):
    """Sets logged with a session date in [start, end]."""
    return sum(1 for _, s in hist.rows
               if s.date_time and start <= _local_date(s.date_time, tz_offset) <= end)


def _days_since_flare(db, user_id, regions, tz_offset):
    """Days since the last report naming one of these knee regions.

    Deliberately not the 24-hour window the rest of the symptom machinery
    uses. That window answers "is it sore today", which for a tendon is the
    wrong question: it is sore in the morning and fine by lunchtime whatever
    its actual state, so an on-off switch tied to today's log hands back the
    aggravating movements on the first morning somebody feels well.
    """
    ids = {s.symptom_id: (s.symptom_name or "").lower()
           for s in db.query(Symptom).filter(Symptom.user_id == user_id).all()}
    ids = {k: v for k, v in ids.items()
           if "knee" in v and symptom_region(v) in regions}
    if not ids:
        return None
    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
    seen = [_local_date(l.date_time, tz_offset)
            for l in db.query(SymptomLog).filter(
                SymptomLog.user_id == user_id,
                SymptomLog.symptom_id.in_(ids.keys())).all() if l.date_time]
    return (today - max(seen)).days if seen else None


def deload_week(db, user_id, tz_offset=0):
    """Whether this is a planned easy week, and which one.

    Counted in whole weeks from the first session logged, so it lands on the
    same weekday every time and can be seen coming. The engine already knew
    how to ease off, but only ever as a reaction — to a stall, a sore knee, a
    symptom. Nothing made it ease off while things were going well, which is
    exactly when a programme accumulates the fatigue it later blames on a
    single bad session.
    """
    dates = [_local_date(s.date_time, tz_offset)
             for s in db.query(WorkoutSession).filter(
                 WorkoutSession.user_id == user_id).all()
             if s.date_time]
    if not dates:
        return None
    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
    week = (today - min(dates)).days // 7
    if week and (week + 1) % DELOAD_EVERY_WEEKS == 0:
        return {"week": week + 1, "every": DELOAD_EVERY_WEEKS}
    return None


def _expand_mobility(db, user_id, blocks, templates, by_id, by_name,
                     knee, limits, prog, tz_offset):
    """Turn each mobility placeholder into the stretches it stands for.

    A second pass rather than part of the block loop, because a stretch is
    chosen from what the whole session trained and the warm-up slot is built
    before any of it exists.
    """
    # ── The stretch routine ────────────────────────────────────────────────
    # A second pass, because a stretch has to know what the whole session
    # trained and the "before" slot is built before any of it exists. Done
    # inline it could only ever match the exercises that happened to come
    # earlier in the list.
    by_target = {}
    for item in blocks:
        if item.get("group") == "practice":
            continue
        ex = by_id.get(item["exercise_id"])
        if ex is None or not ex.target:
            continue
        by_target.setdefault(ex.target, []).append(item["exercise"])

    # Whether to pin the kick ladder on. Derived from what is in the session
    # rather than from a setting, so it follows the person who actually kicks
    # without asking everybody else to turn it off.
    # From the templates, not from what survived. Whether someone is chasing
    # kick height is a fact about their training, and reading it off the
    # blocks meant a day that limited the kung fu out also decided they were
    # no longer a kicker — so the ladder disappeared on exactly the days the
    # exertion gate below was there to judge.
    kicks = any(
        any(w in block.name.lower() for w in ("side kick", "kung fu"))
        for block, _, _ in templates
    )
    expanded = []
    for item in blocks:
        ex = by_id.get(item["exercise_id"])
        # A practice item only. "Stretches" is a placeholder standing for a
        # routine; a mobility exercise that lands in a strength slot is just
        # that exercise. Keyed on the category alone, a session with no bands
        # substituted Band Hip Flexion for the Active Straight-Leg Raise Hold —
        # a stretch — and the strength slot then expanded into a second copy of
        # the entire stretch routine.
        if (ex is None or ex.category != "mobility"
                or item.get("group") != "practice"):
            expanded.append(item)
            continue
        slot = item.get("slot") or "after"
        routine = routine_for(
            slot, by_target,
            # The ladder is goal work — unassisted holds at end range, which
            # is moderate effort however calm it looks. On a gentle day the
            # stretches should only be restorative, so it comes out. Stated
            # rather than left to fall out of the martial practice being
            # limited out, which is what happened to be true today and would
            # stop being true the moment someone else took this up.
            kicks=kicks and (limits or {}).get("max_exertion", 3) >= 2,
            allow_floor=(limits or {}).get("allow_floor", True),
            # Only when the sore joint is one these stretches would load. A
            # sore shoulder is no reason to drop the quad stretch.
            sore_knee=(knee["action"] in ("back_off", "hold")
                       and "knee" in (prog.get("soreness_targets") or ("knee",))),
            # Every completed session, not just the strength ones. Keyed on
            # strength sessions, a stretch of practice days would hand out the
            # same ladder every time, so whichever kick came up first would be
            # the only one ever trained.
            rotation=db.query(WorkoutSession).filter(
                WorkoutSession.user_id == user_id).count(),
        )

        # One step per stretch, shaped like any other exercise, so the runner
        # counts a hold down and logs it the way it does a wall sit. A single
        # item with a list inside it needed its own controls and could not be
        # timed, which is the one thing a hold actually wants.
        steps = []
        for s in routine:
            sx = by_name.get(s["name"].strip().lower())
            if sx is None:
                continue
            # The kick ladder is loaded end-range hamstring work, which is the
            # last thing an irritated hamstring tendon wants. It is goal work
            # and can wait a fortnight.
            if (knee.get("region") in ("lateral", "posterior")
                    and knee["action"] in ("back_off", "hold")
                    and s["name"].strip().lower() in HAMSTRING_END_RANGE):
                continue
            scheme = scheme_for_seconds(s["seconds"])
            rounds = s.get("sets", 1)
            if scheme == "iso":
                detail = (f"{rounds} x {s['seconds']}s hold" if rounds > 1
                          else f"{s['seconds']}s hold")
                if s["per_side"]:
                    detail += " each side"
            else:
                detail = "Work through it" + (" each side" if s["per_side"] else "")
            steps.append({
                "exercise_id": sx.exercise_id, "exercise": sx.exercise_name,
                "target": sx.target, "equipment": sx.equipment,
                "scheme": scheme, "prescription": detail, "why": s["why"],
                "form_cues": s["cues"], "video_url": s["video_url"] or sx.video_url,
                "sets": rounds,
                "target_reps": None,
                "target_seconds": s["seconds"] or None,
                "target_weight": None, "target_band": None,
                "per_side": s["per_side"],
                "group": "mobility", "slot": slot,
            })

        if steps:
            if slot == "after" and any(s["name"] in LADDER_NAMES for s in routine):
                steps[-1]["routine_note"] = LADDER_NOTE
            expanded.extend(steps)
        else:
            # Nothing in the library to point at yet, so the routine stays a
            # list inside the one item. Better a named list that cannot be
            # timed than dropping the stretches out of the session entirely.
            item["routine"] = routine
            item["routine_note"] = LADDER_NOTE if kicks and slot == "after" else None
            expanded.append(item)
    return expanded


def _prescribe_blocks(db, user_id, hist, templates, by_name, by_id, prog,
                      knee, limits, loads, bands, available, deload,
                      flare_days, return_budget, blocks, missing, resting):
    """Turn each template into an instruction, or explain why it is not there.

    This is where an exercise meets everything that might change it: kit that
    is not to hand, a stall, a ceiling reached, a sore side, a day's limits, a
    knee being rested. One pass, one exercise at a time.

    Fills blocks, and reports what fell out and why.
    """
    returned = 0                      # rested movements handed back so far
    dropped, limited, used_ids = [], [], set()
    for block, group, slot in templates:
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
        # After the sore-area narrowing, not before it. A planned easy week is
        # about accumulated fatigue rather than one joint, so it applies to
        # everything — narrowed to the sore targets it would be a deload of
        # whichever body part happened to hurt.
        if deload and action == "progress":
            action = "deload"

        # Balancing on a knee that gives way is the specific risk, so standing
        # single-leg work comes out rather than being trimmed. Note this is
        # needs_balance rather than is_unilateral: a lying quad set is done one
        # leg at a time and involves no balance at all.
        if knee.get("instability") and sore_area and ex.needs_balance:
            dropped.append(ex.exercise_name)
            continue

        # Back-outer knee pain stands movements down rather than shrinking
        # them. A shallower lunge is still a lunge, and the structures that
        # hurt there are loaded by the pattern rather than by the volume.
        #
        # Counted from the last report rather than from today's, and handed
        # back a movement at a time: everything returning together on the
        # first good morning is how the same tendon gets irritated twice.
        if ((ex.exercise_name or "").strip().lower()
                in (POSTEROLATERAL_REST | HAMSTRING_END_RANGE)
                and flare_days is not None
                and returned >= return_budget):
            resting.append(ex.exercise_name)
            continue
        if ((ex.exercise_name or "").strip().lower()
                in (POSTEROLATERAL_REST | HAMSTRING_END_RANGE)
                and flare_days is not None):
            returned += 1

        # Only the sore side eases off. Detraining the good leg because the
        # other one hurts loses training for nothing, and the log already
        # records which side each set was done on.
        affected = knee.get("affected_side") if sore_area else None

        prior, when, from_test = _last_sets(hist, ex.exercise_id)

        # Stepping up happens before the prescription rather than after it, so
        # everything downstream — the sore-side split, the limits check, the
        # duplicate guard — sees the exercise actually being done. Patched on
        # afterwards it would prescribe one exercise and describe another.
        graduated = None
        step_up = PROGRESSIONS.get(block.name.strip().lower())
        if step_up and _topped_out(hist, ex.exercise_id, block.scheme, block.high):
            up_ex = by_name.get(step_up[0].strip().lower())
            if up_ex is not None and (available is None or up_ex.equipment in available):
                graduated = ex.exercise_name
                block = Block(step_up[0], step_up[1], block.sets, step_up[2], step_up[3])
                ex = up_ex
                prior, when, from_test = _last_sets(hist, ex.exercise_id)

        item = _prescribe(
            block, ex, prior, action, loads, last_done=when,
            stalled=_stalled(hist, ex.exercise_id, block.scheme),
            from_assessment=from_test, bands=bands,
        )

        # For a unilateral exercise with one sore side, work out what the good
        # side should do by prescribing it again as though nothing hurt.
        if affected and ex.is_unilateral and action in ("back_off", "hold"):
            healthy = _prescribe(
                block, ex, prior, "progress", loads, last_done=when,
                stalled=_stalled(hist, ex.exercise_id, block.scheme),
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

        if graduated:
            item["progressed_from"] = graduated
            # Said once, until the new version has actually been done. The
            # same rule the equipment swap uses: a change worth announcing is
            # not worth repeating every session forever.
            item["notice"] = (
                f"{graduated} has been finishing every set at the top of its "
                f"range for {GRADUATE_SESSIONS} sessions, and the tubes do not "
                f"go heavier — so it steps up to {ex.exercise_name}. One arm at "
                f"a time is roughly double the load, which is why the reps "
                f"start lower."
            ) if when is None else None

        if item.pop("exhausted", False):
            swap = _substitute(hist, block.name, by_name)
            if swap is None:
                # Nothing to move to, so say what is happening rather than
                # repeating a target that has already failed three times.
                item["why"] += (" No easier version of this is in your library — "
                                "swap it for something you can complete.")
            else:
                sub_block, sub_ex = swap
                sub_prior, sub_when, sub_test = _last_sets(hist, sub_ex.exercise_id)
                item = _prescribe(
                    sub_block, sub_ex, sub_prior, action, loads,
                    last_done=sub_when,
                    stalled=_stalled(hist, sub_ex.exercise_id, sub_block.scheme),
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
        item["slot"] = slot
        if swapped_from and item["exercise"] != swapped_from:
            item["equipment_substitute"] = swapped_from
            item["why"] = (f"Standing in for {swapped_from}, which needs kit you "
                           f"have not marked as available. {item['why']}")
        blocks.append(item)

    return dropped, limited

def _add_rehab_isometric(hist, blocks, by_name, resting, limits, loads, bands):
    """Put back something the sore knee tolerates where the lunging came out."""
    # Standing movements down leaves a gap, and a gap is not rehabilitation.
    # An isometric hold is what an irritated tendon tolerates, and often eases
    # within the hold itself, so it goes in where the lunging came out.
    if resting and not any(b["exercise"] == "Hamstring Isometric" for b in blocks):
        iso_ex = by_name.get("hamstring isometric")
        if iso_ex is not None and _within_limits(iso_ex, limits):
            iso_prior, iso_when, iso_test = _last_sets(hist, iso_ex.exercise_id)
            item = _prescribe(Block("Hamstring Isometric", "iso", 3, 20, 45),
                              iso_ex, iso_prior, "progress", loads,
                              last_done=iso_when, stalled=False,
                              from_assessment=iso_test, bands=bands)
            item.pop("exhausted", None)
            item["group"] = "strength"
            item["slot"] = None
            item["why"] = ("Loading the tendon in the way it tolerates while "
                           "the bending patterns are out. " + item["why"])
            blocks.append(item)



def _build_notes(prog, profile, decision, knee, limits, deload, flare_days,
                 missing, dropped, limited, resting, trimmed, held_back,
                 floor_reached, acute, chronic, easy_days):
    """Everything the session wants to say for itself, in one place.

    Assembling these inside build_session meant the explanation for a decision
    sat two hundred lines from the decision, and the order they appear in was
    whatever order the code happened to run.
    """
    notes = []
    if trimmed:
        notes.append(f"Trimmed {len(trimmed)} stretch(es): this week would "
                     f"otherwise reach {acute} sets against a usual week of "
                     f"{chronic:.0f}. Volume rising faster than tissue adapts "
                     f"is how a tendon gets sore with no single exercise "
                     f"being too hard.")
    elif floor_reached:
        notes.append(f"This week is running well above your usual "
                     f"({acute} sets against {chronic:.0f}) and there is not "
                     f"much stretching left to cut. Worth doing less of "
                     f"something today by choice rather than by injury.")
    if held_back:
        notes.append("Held back for another day: " + ", ".join(sorted(set(held_back)))
                     + f". No more than {NEW_PER_SESSION} unfamiliar movements "
                       f"in a session — meeting several at once is how you end "
                       f"up unable to tell which one disagreed with you.")
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

    if resting:
        when = ("today" if flare_days == 0
                else f"{flare_days} day{'s' if flare_days != 1 else ''} ago")
        notes.insert(0, "Resting the back-outer corner of the knee: "
                     + ", ".join(sorted(set(resting)))
                     + f" are out. You last reported it {when}, and these come "
                       f"back one at a time from day {SETTLE_DAYS} rather than "
                       f"all together. A tendon that hurts in the morning and "
                       f"frees up once you are warm has warmed up, not healed — "
                       f"that is what tendons do, and it is why the good "
                       f"morning is the dangerous one. Hip abduction work "
                       f"stays in throughout: the knee falling inward is the "
                       f"cause underneath this, not a symptom of it.")
    if dropped:
        notes.append("Left out because nothing you have can stand in for "
                     + ", ".join(sorted(set(dropped)))
                     + " — better a gap than something that trains a different "
                       "thing.")
    if decision["kind"] == "rest":
        easy = easy_days
        if len(easy) >= 2:
            notes.append(
                f"You logged something that eased the session back on "
                f"{len(easy)} of the last 7 days. That is a reason to take "
                f"this day, not to skip it — being unwell is a load of its "
                f"own, not a rest from one. But if those days have passed and "
                f"you feel good, a strength session is a reasonable call, and "
                f"the button above will give you one."
            )
    if deload:
        notes.insert(0, f"Week {deload['week']} — a planned easy week, one in "
                        f"every {deload['every']}. Targets and sets come down "
                        f"across the board so the next block starts fresh. "
                        f"Nothing is wrong: this is what stops something going "
                        f"wrong.")
    if knee["awaiting_next_day"]:
        notes.append(f"Score the {prog['soreness']} you felt the morning after "
                     f"your last session — it is what decides whether load "
                     f"goes up.")

    return notes


def _apply_pacing(hist, blocks, by_id, tz_offset):
    """Trim the session against how much has been done lately, and how new it is.

    Split out of build_session, which had grown to thirteen concerns and six
    hundred lines. These two rules are the only ones that look at the session
    as a whole rather than at one exercise, which is why they belong together
    and apart.

    Returns what it did so the notes can say it.
    """
    # ── How much, and how new ────────────────────────────────────────────
    # Two limits on the session as a whole, which nothing else here applies.
    # Volume injuries do not come from any one exercise being too hard; they
    # come from the total going up faster than tissue adapts, and from meeting
    # several unfamiliar movements at once. Both happened at the same time and
    # cost a tendon.
    today_local = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()
    planned = sum(b["sets"] * (2 if b["per_side"] else 1) for b in blocks)
    recent = _sets_between(hist, today_local - timedelta(days=6),
                           today_local - timedelta(days=1), tz_offset)
    chronic = _sets_between(hist, today_local - timedelta(days=27),
                            today_local - timedelta(days=1), tz_offset) / 4.0
    acute = recent + planned
    trimmed, floor_reached = [], False
    if chronic >= RAMP_MIN_BASELINE and acute > chronic * RAMP_LIMIT:
        budget = chronic * RAMP_LIMIT
        keep_at_least = planned * (1 - RAMP_MAX_TRIM)
        # Trim the stretching first: it is the least of the training and the
        # most of the count, and cutting strength work to make room for holds
        # would be the wrong way round. Never gut the session, though — a rule
        # that can delete most of a day is worse than the ramp it prevents.
        while recent + planned > budget and planned > keep_at_least:
            nxt = next((i for i in range(len(blocks) - 1, -1, -1)
                        if blocks[i]["group"] == "mobility"), None)
            if nxt is None:
                break
            trimmed.append(blocks[nxt]["exercise"])
            planned -= blocks[nxt]["sets"] * (2 if blocks[nxt]["per_side"] else 1)
            blocks.pop(nxt)
        floor_reached = recent + planned > budget

    # Unfamiliar movements, rationed. Four of these arrived together on the
    # day before the flare, two of them the patterns that caused it.
    #
    # Only once there is an established routine to introduce them into. A first
    # session is entirely unfamiliar by definition, and gated on novelty alone
    # this rationed a beginner down to two exercises and then, on a day that
    # limits had already thinned, down to none at all. The same baseline the
    # ramp rule waits for is the right one to wait for here.
    held_back = []
    if chronic >= RAMP_MIN_BASELINE:
        known = hist.ever_logged()
        met = 0
        for i in range(len(blocks) - 1, -1, -1):
            if blocks[i]["exercise_id"] in known:
                continue
            # Only demanding loaded work is rationed. Meeting three unfamiliar
            # loading patterns in one session is what hurt a tendon; learning a
            # pelvic floor lift, a new stretch or a walk is not, and counting
            # those held back most of a session — pelvic floor work included —
            # for anyone whose programme had just changed. Which, given how
            # often this one has changed, was nearly everyone.
            row = by_id.get(blocks[i]["exercise_id"])
            if blocks[i].get("group") != "strength" or (row and (row.exertion or 2) < 2):
                continue
            met += 1
            # Never empty the session to enforce a pacing rule.
            if met > NEW_PER_SESSION and len(blocks) > 1:
                held_back.append(blocks[i]["exercise"])
                blocks.pop(i)

    return trimmed, held_back, floor_reached, acute, chronic


def upcoming(db, user_id, days=14, tz_offset=0):
    """What the next fortnight is shaped like, so it can be planned around.

    A projection rather than a promise. It assumes every day gets trained and
    nothing is logged that changes the shape — a headache, a sore knee or a
    skipped day all move the rotation, because the rotation counts sessions
    rather than dates. It says so rather than implying a certainty it does not
    have.

    Built from the same rules build_session uses: the rest weekday, the A/B/C
    order, the day a deload falls on. Rewriting them here is how a planner ends
    up disagreeing with the programme it is planning.
    """
    focus = user_focus(db, user_id)
    prog = program(focus)
    # Read once and handed on, for the same reason build_session does it:
    # current_phase walks the sessions and reads the sets of each, which is a
    # query apiece without it.
    phase = current_phase(db, user_id, focus, History(db, user_id))
    spacing = strength_spacing(db.query(TrainingProfile).filter(
        TrainingProfile.user_id == user_id).first())
    today = (datetime.utcnow() - timedelta(minutes=tz_offset)).date()

    first = min((_local_date(s.date_time, tz_offset)
                 for s in db.query(WorkoutSession).filter(
                     WorkoutSession.user_id == user_id).all() if s.date_time),
                default=None)

    done = phase["sessions_done"]
    out = []
    for offset in range(days):
        when = today + timedelta(days=offset)
        row = {"date": when.isoformat(), "weekday": when.strftime("%a"),
               "today": offset == 0}

        if when.weekday() == REST_WEEKDAY:
            row.update(kind="rest", day=None,
                       theme="Rest day — a walk, practice and stretching")
        elif spacing != "daily" and offset and out and out[-1]["kind"] == "strength":
            # Alternating spacing puts a practice day after each strength day.
            row.update(kind="practice", day=None, theme="Practice and maintenance")
        else:
            letter = DAY_ORDER[done % len(DAY_ORDER)]
            done += 1
            row.update(kind="strength", day=letter,
                       theme=prog["phases"][phase["phase"]]["themes"][letter])

        cond = CONDITIONING.get(when.weekday(), [])
        row["aerobic"] = (f"{cond[0].name} — {cond[0].low}-{cond[0].high} min"
                          if cond else None)

        week = ((when - first).days // 7 + 1) if first else 0
        row["deload"] = bool(week and week % DELOAD_EVERY_WEEKS == 0)
        out.append(row)

    return {"days": out, "phase": phase["phase"], "phase_label": phase["label"],
            "focus": focus,
            "caveat": "A projection, not a promise. The rotation counts "
                      "sessions rather than dates, so a rest, a skipped day or "
                      "anything logged that changes a session shifts "
                      "everything after it."}


def build_session(db, user_id, day=None, tz_offset=0, kind=None,
                  mode=None) -> dict:
    """The whole prescription for the next session."""
    focus = user_focus(db, user_id)
    prog = program(focus)
    hist = History(db, user_id)
    phase = current_phase(db, user_id, focus, hist)
    knee = knee_state(db, user_id, prog["soreness"],
                      prog.get("symptom_keywords"), tz_offset, hist)
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
        middle += [(b, "pelvic") for b in DAILY]
        theme = prog["phases"][phase["phase"]]["themes"][day]
    elif decision["kind"] == "rest":
        # Nothing in the middle at all — not even the knee minimum, which is
        # there to fill the gap between strength days and on this one is the
        # gap. What remains is the practice you would do anyway, and the
        # stretching, which costs nothing to recover from and answers to
        # frequency rather than to load.
        # A walk is not a rest from anything, and the rest day is the one with
        # room for it.
        middle = [(b, "pelvic") for b in DAILY]
        theme = "Rest day — a walk, practice and stretching"
    else:
        # Between strength days the knees still get their work; the muscle gets
        # its recovery day. It sits where the strength work would have been.
        middle = [(b, "maintenance") for b in prog["maintenance"]]
        middle += [(b, "pelvic") for b in DAILY]
        theme = "Practice and maintenance"

    # The walk belongs to the date rather than to the session, so it lands the
    # same way on a strength day, a practice day and a rest day.
    weekday = (datetime.utcnow() - timedelta(minutes=tz_offset)).date().weekday()
    middle += [(b, "conditioning") for b in CONDITIONING.get(weekday, [])]

    blocks, missing, resting = [], [], []
    # The slot travels with the block. Practice bookends a session at both
    # ends and the group alone cannot tell them apart, which matters once
    # something attached to a practice item depends on whether the session has
    # happened yet.
    templates = [(b, "practice", "before") for b in practice["before"]]
    templates += [(b, g, None) for b, g in middle]
    templates += [(b, "practice", "after") for b in practice["after"]]

    # What the log suggests, which is not the same as what is happening. The
    # suggestion is the default; a mode passed in is the user overruling it,
    # and they know whether the triptan worked.
    deload = (deload_week(db, user_id, tz_offset)
              if decision["kind"] == "strength" else None)

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

    # How far through the settling period the back-outer knee is, if at all.
    flare_days = _days_since_flare(db, user_id, ("lateral", "posterior"), tz_offset)
    if flare_days is None or flare_days > SETTLE_DAYS + RETURN_EVERY_DAYS * 6:
        flare_days, return_budget = None, 99
    elif flare_days < SETTLE_DAYS:
        return_budget = 0
    else:
        return_budget = 1 + (flare_days - SETTLE_DAYS) // RETURN_EVERY_DAYS
    by_id = {e.exercise_id: e for e in by_name.values()}
    dropped, limited = _prescribe_blocks(
        db, user_id, hist, templates, by_name, by_id, prog, knee, limits,
        loads, bands, available, deload, flare_days, return_budget,
        blocks, missing, resting)

    blocks = _expand_mobility(db, user_id, blocks, templates, by_id, by_name,
                              knee, limits, prog, tz_offset)


    trimmed, held_back, floor_reached, acute, chronic = _apply_pacing(
        hist, blocks, by_id, tz_offset)

    _add_rehab_isometric(hist, blocks, by_name, resting, limits, loads, bands)

    notes = _build_notes(
        prog, profile, decision, knee, limits, deload, flare_days, missing,
        dropped, limited, resting, trimmed, held_back, floor_reached, acute,
        chronic, recent_easy_days(db, user_id, tz_offset)
        if decision["kind"] == "rest" else [])

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
            {k: suggested[k] for k in
             ("symptom", "level_word", "logged_at", "logged_at_local", "note")}
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
