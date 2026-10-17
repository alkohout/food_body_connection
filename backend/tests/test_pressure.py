"""The pressure metrics and the triptan likelihood built on them."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.pressure import _to_daily                    # noqa: E402
from app.analysis.pressure_stats import (MIN_DAYS, bands,      # noqa: E402
                                         signed_change)

FAILURES = []


def check(label, ok, detail=""):
    print(f"  {'pass' if ok else 'FAIL'}  {label}" + (f"  — {detail}" if not ok else ""))
    if not ok:
        FAILURES.append(label)


def _hourly(values, day="2026-01-01"):
    times = [f"{day}T{h:02d}:00" for h in range(len(values))]
    return times, values


def test_a_rise_is_measured_as_well_as_a_fall():
    """Only falls were recorded, which made a rising front look like a flat day."""
    times, vals = _hourly([1000, 1002, 1006, 1012])
    row = _to_daily(times, vals)["2026-01-01"]
    check("a steady climb is recorded as a rise", row["rise24"] == 12.0, str(row))
    check("and not as a fall", row["drop24"] == 0.0, str(row))

    times, vals = _hourly([1012, 1006, 1002, 1000])
    row = _to_daily(times, vals)["2026-01-01"]
    check("a steady drop is recorded as a fall", row["drop24"] == 12.0, str(row))
    check("and not as a rise", row["rise24"] == 0.0, str(row))

    # The case the whole metric exists for: down and back up inside a day nets
    # to nothing, and is exactly the day people describe.
    times, vals = _hourly([1010, 1000, 1010])
    row = _to_daily(times, vals)["2026-01-01"]
    check("a fall and recovery is not scored as a quiet day",
          row["drop24"] == 10.0 and row["rise24"] == 10.0, str(row))
    check("and the swing takes the larger of the two", row["swing24"] == 10.0,
          str(row))


def test_the_day_is_signed_by_its_larger_move():
    check("a mostly-falling day is negative",
          signed_change({"drop24": 9.0, "rise24": 2.0}) == -9.0)
    check("a mostly-rising day is positive",
          signed_change({"drop24": 2.0, "rise24": 9.0}) == 9.0)
    check("a day with neither is zero", signed_change({}) == 0.0)


def _series(n, move_at, start=date(2026, 1, 1)):
    """n quiet days, with a big move on the days in `move_at`."""
    out = {}
    for i in range(n):
        d = start + timedelta(days=i)
        big = i in move_at
        out[d.isoformat()] = {"drop24": 20.0 if big else 1.0, "rise24": 0.0}
    return out


def test_a_likelihood_needs_enough_days():
    rows = _series(MIN_DAYS - 1, set())
    check("too few days gives no answer, rather than a number", bands(rows, set()) is None)


def test_the_likelihood_finds_a_real_association():
    """Built so the extreme days carry every triptan."""
    n = 200
    moves = set(range(0, 20))
    rows = _series(n, moves)
    start = date(2026, 1, 1)
    trip = {start + timedelta(days=i) for i in moves}

    r = bands(rows, trip)
    check("every band reports its denominator",
          all(b["days"] > 0 for b in r["bands"]), str(r["bands"]))
    check("the rate is triptans over days",
          all(abs(b["rate"] - b["triptans"] / b["days"]) < 1e-9 for b in r["bands"]))
    check("the extreme days are separated out", r["extreme_rate"] == 1.0,
          str(r["extreme_rate"]))
    check("the rest carry none", r["rest_rate"] == 0.0, str(r["rest_rate"]))
    check("and it is called significant", r["p_value"] is not None
          and r["p_value"] < 0.001, str(r["p_value"]))


def test_no_association_is_reported_as_none():
    """The honest answer when the weather explains nothing."""
    n = 200
    rows = _series(n, set(range(0, 100)))
    start = date(2026, 1, 1)
    # Triptans spread evenly across both halves.
    trip = {start + timedelta(days=i) for i in range(0, n, 4)}
    r = bands(rows, trip)
    check("an even spread is not significant", r["p_value"] > 0.05, str(r["p_value"]))
    check("the baseline is the overall rate",
          abs(r["baseline"] - len(trip) / n) < 1e-9, str(r["baseline"]))


def test_a_lag_shifts_the_question():
    """A response a day later should be found by lag=1, not lag=0."""
    n = 200
    moves = set(range(0, 20))
    rows = _series(n, moves)
    start = date(2026, 1, 1)
    trip = {start + timedelta(days=i + 1) for i in moves}
    same = bands(rows, trip, lag=0)
    next_day = bands(rows, trip, lag=1)
    check("the next-day response is found at lag 1", next_day["extreme_rate"] == 1.0,
          str(next_day["extreme_rate"]))
    check("and is not credited to the same day",
          same["extreme_rate"] < next_day["extreme_rate"],
          f"{same['extreme_rate']} vs {next_day['extreme_rate']}")


if __name__ == "__main__":
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
