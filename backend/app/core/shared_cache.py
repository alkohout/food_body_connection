"""A small JSON cache on disk, shared by every worker process.

The analysis context is expensive to build and was cached in a module-level
dict. That dict is per process, so with two workers a context built while
serving one request did nothing for the next request if the load balancer sent
it to the other worker. In practice that meant generating an AI summary made
the following chat question fast only about half the time — and when it was
slow, the long rebuild is what left the worker busy enough to be killed by
uvicorn's health check.

Entries here are shared across workers and survive restarts and deploys. Each
one carries a validity token, supplied by the caller: a fingerprint of the
underlying rows, or a calendar day. A token mismatch is a miss, so stale data
is never returned rather than being served with a TTL's worth of lag.

The files hold decrypted tracking data. That is the same posture as the plot
cache, which already writes rendered images of that same data to this same
directory; both rely on file permissions rather than encryption at rest.
"""
import hashlib
import json
import logging
import os
from pathlib import Path

from app.core.atomic import atomic_write

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("PLOT_CACHE_DIR", "/opt/foodbodyconnection/plot_cache"))


def _path(name: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(name.encode()).hexdigest()}.cache.json"


def read(name: str, token: str):
    """The cached value, or None if it is absent, unreadable or stale."""
    try:
        raw = _path(name).read_bytes()
    except OSError:
        return None            # includes FileNotFoundError: a plain miss

    if not raw:
        # An empty file means a write was interrupted. Treat it as a miss
        # rather than letting json raise.
        return None

    try:
        blob = json.loads(raw)
    except ValueError:
        logger.warning("discarding unparseable cache entry %s", name)
        return None

    if blob.get("token") != token:
        return None
    return blob.get("value")


def write(name: str, token: str, value) -> None:
    """Store a value. Best effort: caching must never break what it speeds up."""
    try:
        atomic_write(
            _path(name),
            json.dumps({"token": token, "value": value}, default=str).encode(),
        )
    except Exception:
        logger.warning("shared cache write failed for %s", name, exc_info=True)
