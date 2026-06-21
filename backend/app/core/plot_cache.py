"""Disk-backed PNG cache with stale-while-revalidate.

Cached plots survive server restarts and deploys. When data changes,
the cache entry is marked stale; the next request serves the old plot
instantly while a fresh one generates in the background.

Usage in a route:
    @router.get("/plot_foo")
    def plot_foo(
        background_tasks: BackgroundTasks,
        current_user=Depends(...), db=Depends(...),
    ):
        def generate() -> BytesIO:
            ...
            return buf
        return cached_png(f"foo_{current_user.user_id}", generate, background_tasks)

Invalidate when data changes (e.g. after a successful POST):
    from app.core.plot_cache import invalidate_cache
    invalidate_cache(f"foo_{current_user.user_id}")
"""
import hashlib
import json
import logging
import os
import time
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("PLOT_CACHE_DIR", "/opt/foodbodyconnection/plot_cache"))
FRESH_TTL = 3600  # seconds — serve without regenerating for 1 hour

_lock = Lock()


def _png_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.png"


def _meta_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _read(key: str) -> tuple[bytes | None, float]:
    """Return (data, age_seconds). data=None if no cache entry exists."""
    try:
        png, meta = _png_path(key), _meta_path(key)
        if png.exists() and meta.exists():
            ts = json.loads(meta.read_text())["ts"]
            return png.read_bytes(), time.time() - ts
    except Exception:
        pass
    return None, float("inf")


def _write(key: str, data: bytes) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with _lock:
        _png_path(key).write_bytes(data)
        _meta_path(key).write_text(json.dumps({"ts": time.time(), "key": key}))


def invalidate_cache(key: str) -> None:
    """Mark a cache entry as stale. Next request serves the old plot
    immediately and regenerates a fresh one in the background."""
    meta = _meta_path(key)
    with _lock:
        if meta.exists():
            meta.write_text(json.dumps({"ts": 0, "key": key}))


def cached_png(
    key: str,
    generate_fn,
    background_tasks: BackgroundTasks | None = None,
) -> StreamingResponse:
    data, age = _read(key)

    if data is not None and age < FRESH_TTL:
        return _response(data)

    if data is not None and background_tasks is not None:
        # Stale — return old plot immediately, regenerate behind the scenes
        def _regen():
            try:
                _write(key, generate_fn().getvalue())
                logger.info("Background cache refresh done: %s", key)
            except Exception as e:
                logger.error("Background cache refresh failed %s: %s", key, e)

        background_tasks.add_task(_regen)
        return _response(data)

    # No cache yet — generate synchronously (first ever request)
    buf = generate_fn()
    data = buf.getvalue()
    _write(key, data)
    return _response(data)


def _response(data: bytes) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(data), media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )
