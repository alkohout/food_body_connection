"""The training programmes themselves, separate from the engine that runs them.

The engine — progression, stalls, deloads, equipment substitution, the
back-off rule — is about managing load and knows nothing about anybody's
goals. What differs between people is which exercises, in what order, and
what the baseline tests are. That lives here.

Two programmes for now. "general" is the default and suits someone who wants
to keep or build overall strength. "knee" front-loads knee tolerance work and
is for someone whose knees are the limiting factor.

Adding a third means adding an entry to PROGRAMS; the engine needs no changes.
"""
from collections import namedtuple

# scheme: iso (hold seconds) | reps (bodyweight reps) | load (double
# progression) | check (nothing to count, it either happened or it did not)
Block = namedtuple("Block", "name scheme sets low high")


# ──────────────────────────────────────────────────────────────────────────
# General
# ──────────────────────────────────────────────────────────────────────────

GENERAL_PHASES = {
    1: {
        "label": "Groundwork",
        "aim": "Learn the patterns and build tolerance before adding load.",
        "themes": {"A": "Squat and push", "B": "Hinge and pull",
                   "C": "Single-leg and core"},
        "days": {
            "A": [
                Block("Wide Leg Squat", "reps", 3, 8, 15),
                Block("Push Up", "reps", 3, 5, 12),
                Block("Glute Bridge", "reps", 3, 10, 20),
                Block("Plank", "iso", 3, 20, 45),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
            ],
            "B": [
                Block("Single Leg Glute Bridge", "reps", 3, 8, 15),
                Block("Prone Y Raise", "reps", 3, 8, 15),
                Block("Bird Dog", "reps", 3, 6, 12),
                Block("Side Plank", "iso", 3, 20, 40),
                Block("Tibialis Raise", "reps", 3, 12, 20),
            ],
            "C": [
                Block("Lunge", "reps", 3, 6, 12),
                Block("Incline Push Up", "reps", 3, 8, 15),
                Block("Side Lying Hip Abduction", "reps", 3, 10, 20),
                Block("Dead Bug", "reps", 3, 6, 12),
                Block("Sit Up", "reps", 3, 8, 15),
            ],
        },
    },
    2: {
        "label": "Build",
        "aim": "Add external load to patterns you can already do well.",
        "themes": {"A": "Squat and push", "B": "Hinge and pull",
                   "C": "Single-leg and core"},
        "days": {
            "A": [
                Block("Goblet Squat", "load", 3, 8, 12),
                Block("Push Up", "reps", 3, 8, 15),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Plank", "iso", 3, 30, 60),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 3, 8, 12),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Glute Bridge", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 30, 45),
                Block("Tibialis Raise", "reps", 3, 15, 20),
            ],
            "C": [
                Block("Split Squat", "load", 3, 6, 10),
                Block("Dumbbell Floor Press", "load", 3, 8, 12),
                Block("Side Lying Hip Abduction", "reps", 3, 12, 20),
                Block("Dead Bug", "reps", 3, 8, 15),
                Block("Bicep Curl", "load", 2, 10, 15),
            ],
        },
    },
    3: {
        "label": "Strength",
        "aim": "Heavier work across the same three patterns.",
        "themes": {"A": "Squat and push", "B": "Hinge and pull",
                   "C": "Single-leg and core"},
        "days": {
            "A": [
                Block("Goblet Squat", "load", 4, 6, 10),
                Block("Dumbbell Floor Press", "load", 3, 8, 12),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Plank", "iso", 3, 45, 75),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 4, 6, 10),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Split Squat", "load", 3, 8, 12),
                Block("Side Plank", "iso", 3, 40, 60),
                Block("Bird Dog", "reps", 3, 8, 12),
            ],
            "C": [
                Block("Box Squat", "load", 3, 8, 12),
                Block("Push Up", "reps", 3, 10, 20),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Side Lying Hip Abduction", "reps", 3, 12, 20),
                Block("Bicep Curl", "load", 2, 10, 15),
            ],
        },
    },
}

GENERAL_MAINTENANCE = [
    Block("Glute Bridge", "reps", 2, 10, 20),
    Block("Plank", "iso", 2, 20, 45),
]

# Submaximal throughout. A one-rep max is the highest-risk thing a programme
# can ask of someone new to lifting, and a rep test gives the same information.
GENERAL_ASSESSMENT = [
    ("Wide Leg Squat", "Max controlled reps, stopping 2 short of failure. Stop at 25.",
     "Sets the starting point for squatting."),
    ("Push Up", "Max reps, stopping 2 short of failure. Drop to your knees rather "
                "than letting the hips sag.", "Baseline for pushing."),
    ("Prone Y Raise", "Max controlled reps, stopping 2 short. Stop at 20.",
     "Baseline for the upper back."),
    ("Single Leg Glute Bridge", "Max controlled reps per side, stopping 2 short.",
     "Baseline for hips and hamstrings."),
    ("Plank", "Hold until form breaks. Stop at 90s.", "Baseline for the core."),
    ("Side Plank", "Hold until the hips drop. Stop at 60s.",
     "Baseline for the sides, which most people are weaker at."),
    ("Wall Sit", "Hold at a comfortable depth. Stop at 60s.",
     "Shows how much your legs tolerate before load is added."),
    ("Standing Calf Raise", "Max controlled reps. Stop at 30.", "Baseline for calves."),
]


# ──────────────────────────────────────────────────────────────────────────
# Knee stability
# ──────────────────────────────────────────────────────────────────────────

KNEE_PHASES = {
    1: {
        "label": "Settle",
        "aim": "Calm the knees down and build tolerance without loaded squatting, "
               "while covering the rest of the body with what needs no equipment.",
        "themes": {"A": "Knees, push and core",
                   "B": "Hips, pull and shins",
                   "C": "Single-leg control and pull"},
        "days": {
            # Six rather than five: knee work is the priority but it is not a
            # whole session, and pushing without pulling is how shoulders end
            # up rounded. Everything here needs bodyweight or a light band.
            "A": [
                Block("Spanish Squat", "iso", 3, 20, 45),
                Block("Terminal Knee Extension", "reps", 3, 10, 15),
                Block("Standing Hip Abduction", "reps", 3, 10, 15),
                Block("Push Up", "reps", 3, 5, 12),
                Block("Prone Y Raise", "reps", 3, 8, 15),
                Block("Plank", "iso", 3, 20, 45),
            ],
            "B": [
                Block("Single Leg Glute Bridge", "reps", 3, 8, 15),
                Block("Lateral Band Walk", "reps", 3, 10, 15),
                Block("Band Pull Apart", "reps", 3, 10, 20),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Tibialis Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 20, 40),
            ],
            # Single-leg control, starting well below a step down. Terminal
            # knee extension is already on day A, so this slot goes to the
            # movement that actually needs building.
            "C": [
                Block("Wall Sit", "iso", 3, 20, 45),
                Block("Single Leg Balance", "iso", 3, 10, 30),
                Block("Supported Single Leg Squat", "reps", 3, 5, 12),
                Block("Clamshell", "reps", 3, 10, 20),
                Block("Prone Y Raise", "reps", 3, 8, 15),
                Block("Sit Up", "reps", 3, 8, 15),
            ],
        },
    },
    2: {
        "label": "Load",
        "aim": "Eccentric control and light external load, with pulling matched "
               "to the pushing.",
        "themes": {"A": "Squat, pull and core",
                   "B": "Hinge, press and calves",
                   "C": "Single-leg control, press and pull"},
        "days": {
            "A": [
                Block("Spanish Squat", "iso", 2, 30, 45),
                Block("Goblet Squat", "load", 3, 8, 12),
                Block("Standing Hip Abduction", "reps", 3, 12, 15),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Push Up", "reps", 3, 8, 15),
                Block("Plank", "iso", 3, 30, 60),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 3, 8, 12),
                Block("Single Leg Glute Bridge", "reps", 3, 10, 15),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Band Pull Apart", "reps", 3, 12, 20),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 30, 45),
            ],
            "C": [
                Block("Lateral Step Down", "reps", 3, 5, 10),
                Block("Split Squat", "load", 3, 6, 10),
                Block("Dumbbell Floor Press", "load", 3, 8, 12),
                Block("Prone Y Raise", "reps", 3, 10, 15),
                Block("Tibialis Raise", "reps", 3, 15, 20),
                Block("Dead Bug", "reps", 3, 8, 15),
            ],
        },
    },
    3: {
        "label": "Build",
        "aim": "Heavier and deeper, towards downhill and telemark demands, on a "
               "balanced full-body base.",
        "themes": {"A": "Squat, press and pull",
                   "B": "Hinge, pull and press",
                   "C": "Step-downs, squat and pull"},
        "days": {
            "A": [
                Block("Goblet Squat", "load", 4, 6, 10),
                Block("Split Squat", "load", 3, 8, 12),
                Block("Standing Hip Abduction", "reps", 3, 12, 20),
                Block("Dumbbell Floor Press", "load", 3, 8, 12),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Plank", "iso", 3, 45, 75),
            ],
            "B": [
                Block("Romanian Deadlift", "load", 4, 6, 10),
                Block("Dumbbell Row", "load", 3, 8, 12),
                Block("Dumbbell Shoulder Press", "load", 3, 8, 12),
                Block("Single Leg Glute Bridge", "reps", 3, 12, 20),
                Block("Standing Calf Raise", "reps", 3, 12, 20),
                Block("Side Plank", "iso", 3, 40, 60),
            ],
            "C": [
                Block("Lateral Step Down", "reps", 3, 8, 12),
                Block("Anterior Step Down", "reps", 3, 8, 12),
                Block("Box Squat", "load", 3, 8, 12),
                Block("Band Pull Apart", "reps", 3, 15, 25),
                Block("Bicep Curl", "load", 2, 10, 15),
                Block("Dead Bug", "reps", 3, 10, 20),
            ],
        },
    },
}

KNEE_MAINTENANCE = [
    Block("Terminal Knee Extension", "reps", 2, 10, 15),
    Block("Spanish Squat", "iso", 2, 20, 45),
]

KNEE_ASSESSMENT = [
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


# ──────────────────────────────────────────────────────────────────────────

PROGRAMS = {
    "general": {
        "label": "General strength",
        "blurb": "Balanced full-body work for keeping or building overall strength.",
        "phases": GENERAL_PHASES,
        "maintenance": GENERAL_MAINTENANCE,
        "assessment": GENERAL_ASSESSMENT,
        # The word for the morning-after score. Same measurement either way;
        # asking someone without knee trouble to rate their knee would get a
        # meaningless number back.
        "soreness": "soreness",
        "soreness_prompt": "Any lingering soreness this morning?",
        # Symptom-log names that should hold training back. Matched as
        # substrings, case-insensitively, against what the user actually
        # tracks — the point of one database is that logging a sore knee in
        # the morning reaches the afternoon's session.
        "symptom_keywords": ["joint pain", "muscle pain", "body ache"],
        # Which body areas a back-off applies to. None means all of them:
        # general soreness is usually everywhere.
        "soreness_targets": None,
    },
    "knee": {
        "label": "Knee stability",
        "blurb": "Knee tolerance and control first, on a full-body base. Includes "
                 "a tai chi and kung fu practice around each session.",
        # Not offered to everyone: it carries someone's personal martial
        # practice, which would be baffling to anyone else. Visible only to
        # accounts it has been unlocked for.
        "private": True,
        "phases": KNEE_PHASES,
        "maintenance": KNEE_MAINTENANCE,
        "assessment": KNEE_ASSESSMENT,
        "soreness": "knee",
        "soreness_prompt": "How was the knee this morning?",
        "symptom_keywords": ["knee"],
        # A sore knee is a reason to ease off the legs, not the press-ups.
        # Hips are included because they control how the knee tracks.
        "soreness_targets": {"knee", "hip", "calf", "posterior"},
    },
}

DEFAULT_FOCUS = "general"

# Exercises where the band holds you up rather than fighting you. In a Spanish
# squat it is anchored behind and pulls the knees back so you can lean into it
# with vertical shins; a band too light will not hold the lean and the position
# collapses. So heavier is easier there, and progressing to a stiffer band —
# which is right for a pull-apart or a hip abduction — would be backwards.
ASSIST_BANDS = {"spanish squat", "single leg squat"}

# What bookends a session when the user has not built their own routine. A
# starting point only: practice is personal — tai chi, yoga, a warm-up walk —
# and lives in the practice_item table, not in a programme. Appending one
# person's martial routine to everybody's session was never right.
PRACTICE = {
    "general": {
        "before": [],
        "after": [Block("Stretches", "check", 1, 0, 0)],
    },
    "knee": {
        "before": [],
        "after": [Block("Stretches", "check", 1, 0, 0)],
    },
}


# ──────────────────────────────────────────────────────────────────────────
# Days when the session should be a different shape, not just lighter
# ──────────────────────────────────────────────────────────────────────────
#
# The back-off rule answers "how much", which is the right question for a sore
# knee. A migraine is a different question: the problem is bending down and
# exerting at all, so what is needed is a shorter list, not smaller numbers.
#
# Matched on the symptom name as a substring, and keyed by the intensity
# logged. An intensity with no entry imposes no limit.
SESSION_LIMITS = {
    # Headache carries the migraine thresholds rather than milder ones: for
    # this user a headache is a migraine, and migraine itself was never logged
    # once in 73 headache entries. Two symptoms for one experience meant the
    # one being used was the one being treated as the lesser.
    "headache": {
        1: {"max_exertion": 2, "allow_floor": True,
            "note": "Mild headache: the demanding work is out, the rest stands."},
        2: {"max_exertion": 1, "allow_floor": False,
            "note": "Headache: gentle and upright only — nothing that needs "
                    "bending down or real effort."},
        3: {"max_exertion": 1, "allow_floor": False,
            "note": "Bad headache: gentle and upright only. Stop at any point; "
                    "keeping the habit is the whole aim today."},
    },
    # Fatigue limits effort but not position — lying down is easier when tired,
    # not harder, so the floor stays available where a headache would rule it
    # out.
    "fatigue": {
        1: {"max_exertion": 2, "allow_floor": True,
            "note": "A bit flat: the demanding work is out."},
        2: {"max_exertion": 1, "allow_floor": True,
            "note": "Tired: gentle work only. Lying down is fine — it is effort "
                    "that is the problem today, not position."},
        3: {"max_exertion": 1, "allow_floor": True,
            "note": "Very tired: gentle work only, and stopping early is a "
                    "reasonable outcome."},
    },
}


# The three shapes a session can take. A logged symptom suggests one of these;
# it does not impose it. Someone who has taken something and feels fine knows
# more about today than their morning log does, and an app that refuses them a
# session on the strength of it is wrong — and teaches them not to log.
MODES = {
    "full":    {"max_exertion": 3, "allow_floor": True,
                "label": "Full session", "note": "Full session."},
    "reduced": {"max_exertion": 2, "allow_floor": True,
                "label": "Reduced", "note": "Reduced: the demanding work is out."},
    "gentle":  {"max_exertion": 1, "allow_floor": False,
                "label": "Gentle", "note": "Gentle: upright, no real effort."},
}
MODE_ORDER = ["full", "reduced", "gentle"]
