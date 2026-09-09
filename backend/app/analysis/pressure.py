"""Barometric pressure for one location, historical and forecast.

Why this exists: migraine is widely reported to track dramatic changes in
barometric pressure, and this user's own logs are the only way to find out
whether that is true for them. The app cannot answer that without the weather,
so the weather comes in as a layer alongside the symptom logs rather than as a
claim about them.

Two endpoints, because one will not do it. The archive runs several days
behind real time, so anything recent — and obviously anything in the future —
has to come from the forecast endpoint, which also serves up to 92 days of
past readings. Historical days are fetched from the archive and cached
permanently, because they do not change; recent and future days are refetched,
because they do.

Nothing personal leaves the machine. The request carries a latitude, a
longitude and a date range, and no health data of any kind.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

# Christchurch. A per-user location would be better and is a bigger change:
# it needs a column, a settings control and a geocoder. Until someone outside
# this city asks for it, a constant is honest about what the feature knows.
DEFAULT_LAT, DEFAULT_LON = -43.5321, 172.6362
TIMEZONE = "Pacific/Auckland"

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"

# The archive is authoritative but late; leave a margin rather than discovering
# the gap as a run of missing days.
ARCHIVE_LAG_DAYS = 7
FORECAST_TTL_S = 3 * 3600
NET_TIMEOUT_S = 30

_CACHE_DIR = os.environ.get(
    "PLOT_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "plot_cache"),
)


def _cache_path(name):
    os.makedirs(os.path.join(_CACHE_DIR, "pressure"), exist_ok=True)
    return os.path.join(_CACHE_DIR, "pressure", name)


def _get(url, params):
    full = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full, timeout=NET_TIMEOUT_S) as r:
        return json.loads(r.read())


def _to_daily(times, values):
    """Hourly readings to one row per local day.

    `drop24` is the largest fall from any peak in the preceding 24 hours, which
    is the shape people describe — a front coming through — rather than the
    net change between two arbitrary midnights, which can be zero on a day the
    pressure fell 10 hPa and recovered.
    """
    rows, order = {}, []
    for i, (t, v) in enumerate(zip(times, values)):
        if v is None:
            continue
        d = t[:10]
        if d not in rows:
            rows[d] = {"readings": [], "drop24": 0.0}
            order.append(d)
        rows[d]["readings"].append(v)
        window = [x for x in values[max(0, i - 24):i + 1] if x is not None]
        if window:
            rows[d]["drop24"] = max(rows[d]["drop24"], max(window) - v)

    out = {}
    prev_mean = None
    for d in order:
        vals = rows[d]["readings"]
        mean = sum(vals) / len(vals)
        out[d] = {
            "mean": round(mean, 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
            "range": round(max(vals) - min(vals), 1),
            "drop24": round(rows[d]["drop24"], 1),
            "delta": round(mean - prev_mean, 1) if prev_mean is not None else 0.0,
        }
        prev_mean = mean
    return out


def _archive(start, end, lat, lon):
    data = _get(ARCHIVE, {
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(),
        "end_date": end.isoformat(), "hourly": "pressure_msl", "timezone": TIMEZONE,
    })
    return _to_daily(data["hourly"]["time"], data["hourly"]["pressure_msl"])


def _recent_and_ahead(past_days, ahead, lat, lon):
    data = _get(FORECAST, {
        "latitude": lat, "longitude": lon, "hourly": "pressure_msl",
        "past_days": min(max(past_days, 1), 92),
        "forecast_days": min(max(ahead, 1), 16), "timezone": TIMEZONE,
    })
    return _to_daily(data["hourly"]["time"], data["hourly"]["pressure_msl"])


def series(start: date, end: date, ahead: int = 0,
           lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> dict:
    """Daily pressure metrics from `start` to `end`, plus `ahead` days forecast.

    Returns {"YYYY-MM-DD": {...}}. Missing days are simply absent — a gap in
    the weather is not a reason to fail a plot of somebody's symptoms.
    """
    today = date.today()
    key = f"{lat:.3f}_{lon:.3f}.json".replace("-", "m")
    path = _cache_path(key)
    cached = {}
    if os.path.exists(path):
        try:
            cached = json.loads(open(path, encoding="utf-8").read())
        except (ValueError, OSError):
            logger.warning("pressure cache unreadable; refetching")

    settled = today - timedelta(days=ARCHIVE_LAG_DAYS)
    want_archive_end = min(end, settled)
    missing = [d for d in _days(start, want_archive_end) if d.isoformat() not in cached]
    if missing:
        try:
            fetched = _archive(min(missing), max(missing), lat, lon)
            cached.update(fetched)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(cached, fh)
        except Exception as exc:                       # noqa: BLE001
            logger.warning("pressure archive fetch failed: %s", exc)

    out = {d.isoformat(): cached[d.isoformat()]
           for d in _days(start, want_archive_end) if d.isoformat() in cached}

    # Anything the archive has not settled yet, and anything ahead.
    if end > settled or ahead:
        recent = _cached_forecast(settled, end, ahead, lat, lon)
        for d, row in recent.items():
            if start.isoformat() <= d <= (end + timedelta(days=ahead)).isoformat():
                out[d] = row
    return dict(sorted(out.items()))


def _cached_forecast(settled, end, ahead, lat, lon):
    path = _cache_path(f"forecast_{lat:.3f}_{lon:.3f}.json".replace("-", "m"))
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < FORECAST_TTL_S:
        try:
            return json.loads(open(path, encoding="utf-8").read())
        except (ValueError, OSError):
            pass
    try:
        past = (date.today() - settled).days + 2
        rows = _recent_and_ahead(past, max(ahead, 1), lat, lon)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rows, fh)
        return rows
    except Exception as exc:                           # noqa: BLE001
        logger.warning("pressure forecast fetch failed: %s", exc)
        return {}


def _days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)
