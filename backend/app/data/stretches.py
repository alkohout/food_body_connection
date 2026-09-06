"""The stretch routine that sits behind the single "Stretches" practice item.

One checkbox called "Stretches" is not a prescription — it is a reminder to do
something unspecified, and what gets done under it drifts to whatever is
comfortable. This turns it into a named list that follows the session that was
actually just done, and that carries the two things a kicker needs.

Three ideas shape what is here.

Static holds go after, dynamic work goes before. A long hold before lifting
measurably drops force output for a while afterwards, so the pre-session slot
gets movement that raises temperature and range without the holds, and the
holds go at the end where they cost nothing.

Passive range is not kick height. Almost everyone can be pushed into more hip
flexion than they can produce on their own, and a kick is unassisted — so
range that has only ever been reached with a strap or a wall does not show up
in a kick. Every ladder here therefore ends with an unassisted hold at the new
end range. That last step is the one that moves a kick, and it is the one
normally left out.

Knee-safe by construction. The classic openers for kicking — hurdler sit,
frog, forced side splits, deep pigeon on a loaded shin — all work by putting
the knee somewhere it does not want to go, and the medial knee takes it. None
of them are in this file. Where a stretch has a knee-loading version and a
knee-quiet one, only the knee-quiet one is here, so nothing needs remembering
mid-routine.

Columns: name, when, targets, seconds, per_side, floor, knee_load, cues, url

`when`     before | after — dynamic prep, or a static hold.
`targets`  the exercise `target` values this follows: knee hip core upper
           posterior calf. Empty means it fits any day.
`floor`    needs lying or kneeling, so it drops out on a no-floor day.
`knee_load`the knee is bent under load or at end range, so it is swapped out
           while a knee is sore.

url is None throughout, deliberately. The exercise library only carries links
that have been opened and confirmed, because a dead link on a form guide is
exactly where someone gets hurt, and a plausible-looking URL is worse than no
URL. These get filled in the same way, once checked.
"""
from collections import namedtuple

Stretch = namedtuple(
    "Stretch", "name when targets seconds per_side floor knee_load cues url")


# ──────────────────────────────────────────────────────────────────────────
# Before: raise temperature and range without the holds
# ──────────────────────────────────────────────────────────────────────────

BEFORE = [
    Stretch("Leg Swings, Front and Back", "before", ("hip", "posterior", "knee"),
            0, True, False, False,
            "Hold a wall. Swing one leg forward and back, small at first and "
            "letting the height come up over 10-15 swings. Do not throw it to "
            "the top — a cold hamstring snapped at the end of a swing is the "
            "single most common way this goes wrong.", None),
    Stretch("Leg Swings, Across and Out", "before", ("hip",),
            0, True, False, False,
            "Face the wall. Swing one leg across the body and back out to the "
            "side, 10-15 each. Keep the hips square and let the leg do the "
            "travelling — this is the side kick's warm-up.", None),
    Stretch("Ankle Rock-Overs", "before", ("knee", "calf"),
            0, True, False, False,
            "Front foot flat, drive that knee forward past the toes and back, "
            "10-15 times. The heel must stay down. A stiff ankle is often what "
            "makes a squat or a step-down feel like a knee problem.", None),
    Stretch("Hip Circles", "before", ("hip", "knee"),
            0, True, False, False,
            "Stand tall, lift one knee to hip height and draw a slow circle "
            "with it, 8 each way. Control the whole circle rather than "
            "swinging through the easy part.", None),
    Stretch("Cossack Shifts", "before", ("hip", "knee"),
            0, False, False, True,
            "Wide stance, shift your weight over one bent leg with the other "
            "straight, then back. Stay high — this is a warm-up, and going "
            "deep here is where the inner knee complains.", None),
    Stretch("Shoulder Pass-Throughs", "before", ("upper",),
            0, False, False, False,
            "A belt or towel held wide, arms straight, up over the head and "
            "behind, 10 slow passes. Widen your grip until it goes without a "
            "shrug.", None),
    Stretch("Cat-Cow", "before", ("core", "upper", "posterior"),
            0, False, True, False,
            "On hands and knees, arch and round the spine slowly, 8-10 times, "
            "breathing with it.", None),
]


# ──────────────────────────────────────────────────────────────────────────
# After: the holds
# ──────────────────────────────────────────────────────────────────────────

AFTER = [
    Stretch("Supine Hamstring Stretch", "after", ("posterior", "hip", "knee"),
            40, True, True, False,
            "On your back, a belt round the foot, other leg flat. Raise the "
            "leg to the first real resistance, not to pain, and let it soften. "
            "Keep a slight bend at the knee if the back of the knee is the "
            "part that complains — the belly of the hamstring is the target, "
            "not the tendon.", None),
    Stretch("Standing Hamstring Stretch", "after", ("posterior", "hip", "knee"),
            40, True, False, False,
            "Heel on a low step, leg straight, toes up. Hinge forward from the "
            "hip with a flat back until the hamstring loads — rounding the "
            "back gives the feeling without the length. The floor-free stand-in "
            "for the supine version.", None),
    Stretch("Half-Kneeling Hip Flexor Stretch", "after", ("hip", "knee", "core"),
            40, True, True, True,
            "Something soft under the down knee. Tuck the tailbone under and "
            "squeeze that glute first, then lean forward only until you feel "
            "the front of the hip. The stretch comes from the tuck; leaning "
            "without it just bends the lower back.", None),
    Stretch("Standing Adductor Rock-Back", "after", ("hip",),
            40, True, False, False,
            "One leg out straight to the side, foot flat and toes forward, "
            "sink your weight back over the bent leg. The straight leg's knee "
            "stays locked and unloaded — that is what keeps this off the "
            "inner knee, which the frog and the side split do not.", None),
    Stretch("Supine Figure-4", "after", ("hip", "posterior"),
            40, True, True, False,
            "On your back, ankle across the opposite thigh, pull that thigh in "
            "towards you. This is the glute stretch pigeon gives you, without "
            "asking a bent knee to take your weight.", None),
    Stretch("90/90 Hip Rotation Hold", "after", ("hip",),
            35, True, True, False,
            "Sit with both knees at right angles, one leg in front, one out to "
            "the side. Lean gently over the front shin. Both knees stay at 90 "
            "degrees — never fold the back foot under you.", None),
    Stretch("Side-Lying Quad Stretch", "after", ("knee",),
            35, True, True, True,
            "Lie on your side, heel drawn towards the backside, knee stacked "
            "under the hip. Push the hip forward rather than pulling the heel "
            "harder — pulling is what grinds the kneecap.", None),
    Stretch("Standing Calf Stretch", "after", ("calf", "knee"),
            35, True, False, False,
            "Back leg straight and heel down for 30 seconds, then bend that "
            "knee and hold again. Two muscles, two positions — the bent-knee "
            "one is the one that matters for going downhill.", None),
    Stretch("Doorway Chest Stretch", "after", ("upper",),
            35, True, False, False,
            "Forearm on the frame, elbow at shoulder height, turn away from "
            "the arm. Stand tall rather than leaning through it.", None),
    Stretch("Child's Pose with Side Reach", "after", ("upper", "core"),
            35, True, True, False,
            "Sit back onto the heels, arms long, then walk both hands round to "
            "one side to open the ribs. Sit on a cushion if the knees object.",
            None),
    Stretch("Supine Spinal Twist", "after", ("core", "posterior"),
            35, True, True, False,
            "On your back, knees stacked and dropped to one side, opposite "
            "shoulder staying down. Breathe out and let it settle.", None),
]


# ──────────────────────────────────────────────────────────────────────────
# The kick ladders
# ──────────────────────────────────────────────────────────────────────────
#
# Three steps in a fixed order, and the order is the method rather than a
# preference. Hold to find the range, contract-relax to gain a little more,
# then lift into what was gained with nothing helping. Skipping the third step
# is why people stretch for months and kick the same height: the nervous
# system will not let you actively enter a range it has no strength in, so
# passive range that is never loaded is quietly discarded.
#
# Height also does not come only from the kicking leg. The pelvis has to tilt
# and the standing hip has to extend, so a locked-down lower back caps a front
# kick regardless of hamstring length, and a standing foot that will not turn
# out caps a side kick the same way.

AXE_LADDER = [
    Stretch("Hamstring Contract-Relax", "after", (), 0, True, True, False,
            "Belt round the foot, leg up to the first resistance. Press the "
            "leg down into the belt at about a third of your strength for 6 "
            "seconds, breathe out, relax, then take up the slack that appears. "
            "Three rounds a leg. Never press into pain.", None),
    Stretch("Active Straight-Leg Raise Hold", "after", (), 8, True, True, False,
            "Belt off, other leg flat. Lift the leg as high as it will go on "
            "its own and hold 8 seconds, 3 times a leg. It will be well below "
            "where the belt took you — that gap is the whole problem, and "
            "closing it is what raises the kick.", None),
    Stretch("Standing Front Kick Hold", "after", (), 6, True, False, False,
            "Hold a wall. Lift the straight leg in front as high as you can "
            "control and hold it there for 6 seconds, 3 a side. Chest tall. "
            "This is an axe kick with the speed taken out.", None),
]

SIDE_LADDER = [
    Stretch("Adductor Contract-Relax", "after", (), 0, True, False, False,
            "In the standing adductor rock-back, press the straight leg's foot "
            "down into the floor at about a third of your strength for 6 "
            "seconds, relax, then rock back a little further. Three rounds a "
            "leg.", None),
    Stretch("Standing Abduction Hold", "after", (), 8, True, False, False,
            "Hold a wall, turn the standing foot out, lift the other leg "
            "directly out to the side as high as it will go unassisted and "
            "hold 8 seconds, 3 a side. Hips stay stacked — letting them roll "
            "back turns it into a front kick and flatters the height.", None),
    Stretch("Chambered Side Kick Hold", "after", (), 6, True, False, False,
            "Chamber the knee high across the body, extend the leg out to the "
            "side and hold it for 6 seconds, 3 a side. Whatever height you can "
            "hold here is the height you have.", None),
]

LADDER_NOTE = ("Range you cannot hold on your own is range you cannot kick to, "
               "so each of these ends unassisted. Little and often beats one "
               "long session — this is worth doing on the days you are not "
               "training too.")


# ──────────────────────────────────────────────────────────────────────────
# Choosing the routine
# ──────────────────────────────────────────────────────────────────────────

BEFORE_LIMIT = 4
AFTER_LIMIT = 5

# Two ways into the same tissue, where the second exists only so the first has
# a stand-in on a day it is ruled out. Prescribing both is asking for the same
# stretch twice from two directions, which reads as padding and is what makes
# a routine feel long enough to skip.
EQUIVALENT = {
    "Supine Hamstring Stretch": "hamstring",
    "Standing Hamstring Stretch": "hamstring",
    "Supine Figure-4": "glute",
    "90/90 Hip Rotation Hold": "glute",
}


def _eligible(pool, day_targets, allow_floor, sore_knee):
    """Everything in the pool that suits today, best match first."""
    out = []
    for s in pool:
        if s.floor and not allow_floor:
            continue
        # A stretch that puts the knee at end range under load is the wrong
        # thing to hand someone whose knee is already sore, however good it is
        # on a quiet day.
        if s.knee_load and sore_knee:
            continue
        hit = [t for t in s.targets if t in day_targets]
        if s.targets and not hit:
            continue
        out.append((s, hit))
    # Stable, so the catalogue order breaks ties and the routine does not
    # reshuffle itself between two sessions that trained the same thing.
    out.sort(key=lambda pair: -len(pair[1]))
    seen, kept = set(), []
    for s, hit in out:
        group = EQUIVALENT.get(s.name)
        if group is not None:
            if group in seen:
                continue
            seen.add(group)
        kept.append((s, hit))
    return kept


def _why(hit, by_target, slot):
    """Name the exercises this pairs with, which is the point of matching."""
    names = []
    for t in hit:
        for name in by_target.get(t, []):
            if name not in names:
                names.append(name)
    if not names:
        return None
    lead = "Prepares for" if slot == "before" else "Follows"
    if len(names) > 2:
        rest = len(names) - 2
        names = names[:2] + [f"{rest} other{'s' if rest > 1 else ''}"]
    listed = (" and ".join(names) if len(names) < 3
              else ", ".join(names[:-1]) + " and " + names[-1])
    return f"{lead} {listed}."


def _step(s, why=None):
    return {"name": s.name, "seconds": s.seconds, "per_side": s.per_side,
            "cues": s.cues, "video_url": s.url, "why": why}


def routine_for(slot, by_target, *, kicks=False, allow_floor=True,
                sore_knee=False, rotation=0):
    """The named stretches for one practice slot on one day.

    `by_target` maps an exercise target to the exercises prescribed today that
    train it, so each stretch can say what it follows rather than appearing
    for no visible reason.

    `kicks` pins the flexibility ladder to every session instead of letting it
    come and go with the day's targets. Flexibility answers to frequency more
    than to session length, so for someone chasing kick height a little every
    day beats a long session twice a week — and for someone who is not, the
    ladder is a distraction that lengthens every session.
    """
    day_targets = set(by_target)
    if slot == "before":
        chosen = _eligible(BEFORE, day_targets, allow_floor, sore_knee)
        return [_step(s, _why(hit, by_target, slot))
                for s, hit in chosen[:BEFORE_LIMIT]]

    chosen = _eligible(AFTER, day_targets, allow_floor, sore_knee)
    steps = [_step(s, _why(hit, by_target, slot))
             for s, hit in chosen[:AFTER_LIMIT]]
    if not kicks:
        return steps

    # One ladder a session, alternating. Both every time is a quarter of an
    # hour on the end of a session that is already done, and the thing that
    # actually stops people doing their mobility work is length.
    ladder = AXE_LADDER if rotation % 2 == 0 else SIDE_LADDER
    goal = ("the axe kick — hamstring length and the strength to use it"
            if rotation % 2 == 0 else
            "the side kick — hip opening and the strength to hold it there")
    keep = [s for s, _ in _eligible(ladder, day_targets, allow_floor, sore_knee)]
    for i, s in enumerate(keep):
        steps.append(_step(s, f"Working towards {goal}." if i == 0 else None))
    return steps
