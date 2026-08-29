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
                   "C": "Knee control, pull and core"},
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
            "C": [
                Block("Wall Sit", "iso", 3, 20, 45),
                Block("Terminal Knee Extension", "reps", 3, 10, 15),
                Block("Prone Y Raise", "reps", 3, 8, 15),
                Block("Tricep Dip", "reps", 3, 5, 12),
                Block("Bird Dog", "reps", 3, 6, 12),
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
    },
}

DEFAULT_FOCUS = "general"

# The practice that bookends a session. This really belongs to the person
# rather than to the programme — tai chi has nothing to do with knees — but
# per-user practice is a bigger feature than this, and appending someone
# else's martial routine to every user's session would be worse than the
# approximation. Whoever needs their own can have it made configurable.
TAI_CHI_FORM = "__TAI_CHI_FORM__"
TAI_CHI_FORMS = ["Tai Chi Form 42", "Tai Chi Form 37"]

PRACTICE = {
    "general": {
        "before": [],
        "after": [Block("Stretches", "check", 1, 0, 0)],
    },
    "knee": {
        "before": [
            Block("Tai Chi Exercises", "check", 1, 0, 0),
            Block(TAI_CHI_FORM, "check", 1, 0, 0),
            Block("Tai Chi Sword", "check", 1, 0, 0),
        ],
        "after": [
            Block("Stretches", "check", 1, 0, 0),
            Block("Kung Fu Pattern", "check", 1, 0, 0),
            Block("Side Kick", "reps", 2, 10, 20),
        ],
    },
}
