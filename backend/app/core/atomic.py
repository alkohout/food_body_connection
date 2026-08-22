"""Replace a file in one indivisible step.

Writing in place truncates the file and then fills it, so any reader that
arrives mid-write sees a short or empty file. Writing to a temporary file in
the same directory and renaming it means a reader sees either the whole old
file or the whole new one, and os.replace is atomic on POSIX regardless of
which process is on the other side — which an in-process lock cannot be, since
production runs two worker processes.
"""
import os
import tempfile
from pathlib import Path


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
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
