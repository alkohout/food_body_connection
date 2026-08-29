"""The starting exercise catalogue.

Covers the user's existing routine as well as the new knee work: tai chi, the
kung fu pattern and side kicks load the knees too, so leaving them out would
make any load-management rule meaningless.

video_url is None where no link has been verified to resolve. An unchecked URL
is worse than none — a dead link on a form guide is exactly where a novice
lifter gets hurt — so links are added only once confirmed.

Columns: name, category, target, equipment, unilateral, isometric, cues, url
"""

# category:  strength | mobility | martial | conditioning
# target:    knee | hip | core | upper | posterior | calf | whole
# equipment: bodyweight | dumbbell | barbell | band | tube | none

_P = "https://library.theprehabguys.com/vimeo-video"

LIBRARY = [
    # ── Knee: isometric first. Best tolerated when squatting hurts, and often
    # eases pain within the set, so these are the entry point. ──────────────
    ("Spanish Squat", "strength", "knee", "band", False, True,
     "Band behind the knees, anchored low. Shins and torso stay vertical, sit "
     "back against the band. Hold 20-45s. Should not be sharp — a working ache "
     "is fine.",
     f"{_P}/spanish-squat-isometrics/"),
    ("Wall Sit", "strength", "knee", "bodyweight", False, True,
     "Back flat to the wall, knees no deeper than 90 degrees. Start shallower "
     "if the knees complain. Hold for time.", None),
    ("Terminal Knee Extension", "strength", "knee", "band", True, False,
     "Band above the knee, not on the calf. Straighten the last 20-30 degrees "
     "only. Very light band — form and a slow return beat resistance.",
     f"{_P}/standing-terminal-knee-extension-tkes/"),

    # ── Knee: eccentric control. This is the quality downhill tramping and
    # telemark actually demand, so it is trained deliberately. ──────────────
    ("Lateral Step Down", "strength", "knee", "bodyweight", True, False,
     "Stand on the edge of a step, lower slowly under control and tap the "
     "floor. Knee tracks over the middle toes, no inward collapse. Lower the "
     "step if the knee dives in.", f"{_P}/lateral-step-down/"),
    ("Anterior Step Down", "strength", "knee", "bodyweight", True, False,
     "Facing forwards off a step, lower under control. A band pulling the knee "
     "inwards that you resist teaches the tracking.",
     f"{_P}/anterior-step-down-rnt-2/"),

    # ── Knee: loaded. Added only once the above are comfortable. ────────────
    ("Goblet Squat", "strength", "knee", "dumbbell", False, False,
     "One dumbbell held at the chest. Squat only as deep as stays pain-free "
     "and build depth over weeks rather than in one session.", None),
    ("Box Squat", "strength", "knee", "dumbbell", False, False,
     "Squat to a set surface, pause, stand. The box fixes the depth so range "
     "can be increased deliberately.", None),
    ("Split Squat", "strength", "knee", "dumbbell", True, False,
     "Long stance, back knee drops towards the floor, front shin near "
     "vertical. Bodyweight before any dumbbell.", None),
    ("Single Leg Squat", "strength", "knee", "band", True, False,
     "Band around the knees for feedback. Depth only as far as control holds.",
     f"{_P}/single-leg-squat-band-around-knees/"),
    ("Wide Leg Squat", "strength", "knee", "bodyweight", False, False,
     "Feet wide, toes slightly out, knees track over the toes.", None),
    ("Lunge", "strength", "knee", "bodyweight", True, False,
     "Step out, lower straight down rather than forwards. Front shin near "
     "vertical to keep the load off the kneecap.", None),

    # ── Hip: knee tracking is controlled at the hip, so this is knee work. ──
    ("Standing Hip Abduction", "strength", "hip", "band", True, False,
     "Band at the knees, support against a wall. Lift to the side without the "
     "torso leaning away.",
     f"{_P}/standing-hip-abduction-band-at-knees-wall-supported/"),
    ("Lateral Band Walk", "strength", "hip", "band", False, False,
     "Band above the knees, small athletic stance. Keep tension the whole time "
     "— letting it go loses the point of the exercise.",
     f"{_P}/band-placement-for-sidesteps/"),
    ("Single Leg Glute Bridge", "strength", "hip", "bodyweight", True, False,
     "Drive through the heel, hips level throughout. Ribs down, no arching.",
     None),
    ("Romanian Deadlift", "strength", "posterior", "dumbbell", False, False,
     "Hinge at the hips with a soft knee, dumbbells close to the legs. Stop "
     "where the hamstrings run out, not where the back rounds.", None),

    # ── Calf and shin: the brakes on a descent. ─────────────────────────────
    ("Standing Calf Raise", "strength", "calf", "bodyweight", False, False,
     "Full range, slow lower. Add a dumbbell once 20 reps are easy.", None),
    ("Tibialis Raise", "strength", "calf", "bodyweight", False, False,
     "Heels down, lift the toes. Trains the muscle that controls the foot on "
     "downhills and is almost always the weak link.", None),

    # ── Core ───────────────────────────────────────────────────────────────
    ("Plank", "strength", "core", "bodyweight", False, True,
     "Straight line from head to heels, ribs down, glutes on.", None),
    ("Side Plank", "strength", "core", "bodyweight", True, True,
     "Hips stacked and lifted. Works the lateral chain that keeps the pelvis "
     "level on one leg.", None),
    ("Sit Up", "strength", "core", "bodyweight", False, False,
     "Controlled up and down, no yanking on the neck.", None),

    # ── Upper ──────────────────────────────────────────────────────────────
    ("Push Up", "strength", "upper", "bodyweight", False, False,
     "Body in one line, elbows about 45 degrees from the ribs.", None),
    ("Incline Push Up", "strength", "upper", "bodyweight", False, False,
     "Hands on a bench, step or worktop. The higher the hands, the easier it "
     "is — the regression for a push up that will not move.", None),
    ("Tricep Dip", "strength", "upper", "bodyweight", False, False,
     "Off a chair, shoulders down away from the ears. Stop if the shoulder "
     "front pinches.", None),
    ("Dumbbell Row", "strength", "upper", "dumbbell", True, False,
     "Hinged, flat back, pull to the hip rather than the chest.", None),
    ("Dumbbell Shoulder Press", "strength", "upper", "dumbbell", False, False,
     "Press overhead without flaring the ribs.", None),
    ("Dumbbell Floor Press", "strength", "upper", "dumbbell", False, False,
     "Lying on the floor, upper arms stop at the ground. Shoulder-friendly "
     "with no bench.", None),
    ("Bicep Curl", "strength", "upper", "dumbbell", False, False,
     "Elbows still, no swinging.", None),

    # ── Bodyweight stand-ins, for training away from the kit. ──────────────
    ("Quad Set", "strength", "knee", "bodyweight", True, True,
     "Leg straight, press the back of the knee down and tighten the thigh. "
     "Hold. The band-free version of a terminal knee extension.", None),
    ("Side Lying Hip Abduction", "strength", "hip", "bodyweight", True, False,
     "On your side, top leg straight and slightly behind the line of the body. "
     "Lift without rolling back — the same glute work as the banded version.",
     None),
    ("Pike Push Up", "strength", "upper", "bodyweight", False, False,
     "Hips high, head travels towards the floor between the hands. Shoulder "
     "work when there is no dumbbell to press.", None),

    # ── The existing practice. Logged because it loads the knees. ───────────
    ("Tai Chi Exercises", "martial", "whole", "none", False, False, None, None),
    ("Tai Chi Form 42", "martial", "whole", "none", False, False, None, None),
    ("Tai Chi Form 37", "martial", "whole", "none", False, False, None, None),
    ("Tai Chi Sword", "martial", "whole", "none", False, False, None, None),
    ("Kung Fu Pattern", "martial", "whole", "none", False, False, None, None),
    ("Side Kick", "martial", "hip", "none", True, False, None, None),
    ("Stretches", "mobility", "whole", "none", False, False, None, None),
]
