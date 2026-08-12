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
import tempfile
import time
from io import BytesIO
from pathlib import Path
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("PLOT_CACHE_DIR", "/opt/foodbodyconnection/plot_cache"))
FRESH_TTL = 3600  # seconds — serve without regenerating for 1 hour


def _png_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.png"


def _meta_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.md5(key.encode()).hexdigest()}.json"


def _atomic_write(path: Path, data: bytes) -> None:
    """Replace a cache file in one indivisible step.

    Path.write_bytes truncates the file and then fills it, so any reader that
    arrives mid-write gets a short or empty file — a corrupt PNG, which the
    browser drops silently with no server-side error. Writing to a temporary
    file in the same directory and renaming it means a reader sees either the
    whole old file or the whole new one.

    Renaming is also the only thing that can work here. The previous guard was
    a threading.Lock, which serialises nothing between the two worker processes
    production runs — and it did not cover the read path at all. os.replace is
    atomic on POSIX no matter which process is on the other side.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Never leave a stray .tmp behind for a failed write.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _read(key: str) -> tuple[bytes | None, float]:
    """Return (data, age_seconds). data=None if no cache entry exists."""
    try:
        png, meta = _png_path(key), _meta_path(key)
        if png.exists() and meta.exists():
            ts = json.loads(meta.read_text())["ts"]
            data = png.read_bytes()
            # A cached entry that is somehow empty is worse than no entry: it
            # would be served as a broken image. Treat it as a miss.
            if not data:
                return None, float("inf")
            return data, time.time() - ts
    except Exception:
        pass
    return None, float("inf")


def _write(key: str, data: bytes) -> None:
    # PNG first, then the timestamp. If a reader lands between the two it sees
    # the new image with the old timestamp — it serves a correct plot and
    # schedules a needless refresh. The other order would serve a stale image
    # while claiming it is fresh.
    _atomic_write(_png_path(key), data)
    _atomic_write(_meta_path(key),
                  json.dumps({"ts": time.time(), "key": key}).encode())


def invalidate_cache(key: str) -> None:
    """Mark a cache entry as stale. Next request serves the old plot
    immediately and regenerates a fresh one in the background."""
    meta = _meta_path(key)
    if meta.exists():
        _atomic_write(meta, json.dumps({"ts": 0, "key": key}).encode())


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
