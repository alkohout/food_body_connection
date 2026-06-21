"""Simple in-process PNG cache with TTL.

Usage:
    from app.core.plot_cache import cached_png

    @router.get("/plot_foo")
    def plot_foo(current_user=Depends(...), db=Depends(...)):
        def generate() -> BytesIO:
            ...
            return buf
        return cached_png(f"foo_{current_user.user_id}", generate)
"""
import time
from io import BytesIO
from threading import Lock

from fastapi.responses import StreamingResponse

TTL = 300  # seconds — cache each plot for 5 minutes

_store: dict[str, tuple[float, bytes]] = {}
_lock = Lock()


def cached_png(key: str, generate_fn) -> StreamingResponse:
    with _lock:
        entry = _store.get(key)
        if entry and time.time() - entry[0] < TTL:
            return StreamingResponse(
                BytesIO(entry[1]),
                media_type="image/png",
                headers={"Cache-Control": f"private, max-age={TTL}"},
            )

    buf: BytesIO = generate_fn()
    data = buf.getvalue()

    with _lock:
        _store[key] = (time.time(), data)

    return StreamingResponse(
        BytesIO(data),
        media_type="image/png",
        headers={"Cache-Control": f"private, max-age={TTL}"},
    )
