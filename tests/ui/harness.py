"""A browser with the real page in it, and a stubbed API behind it.

Everything that has broken recently broke in the browser, and the browser had
no test able to press a button. The engine has a suite; the page had a syntax
parser. So the resume card went into the wrong function, three routes skipped
the knee question, and the walk appeared in the planner but not the session —
each found by the person using it rather than by anything here.

No backend: every request is answered from a dictionary, which makes a test a
statement about the page rather than about the server. The page is served over
HTTP rather than from a file, because it is an ES module and file:// will not
load one.

    python3 tests/ui/test_ui.py
"""
import base64
import contextlib
import functools
import http.server
import json
import os
import threading
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
API = "https://foodbodyconnection.159.13.61.101.nip.io"


def token(minutes=55):
    """A JWT shaped well enough for the page's own expiry check."""
    payload = {"sub": "4", "email": "t@example.invalid",
               "exp": int(time.time()) + minutes * 60}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{body}.signature"


@contextlib.contextmanager
def serve():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    httpd.RequestHandlerClass.log_message = lambda *a, **k: None
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()


class Api:
    """Canned answers, and a record of what was asked."""

    def __init__(self, **overrides):
        self.seen = []
        self.routes = dict(DEFAULTS)
        self.routes.update(overrides)

    def handler(self, route, request):
        path = request.url[len(API):].split("?")[0]
        self.seen.append({"path": path, "method": request.method,
                          "auth": request.headers.get("authorization", "")})
        body = self.routes.get(path)
        if callable(body):
            body = body(request)
        if body is None:
            body = {}
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(body))


DEFAULTS = {
    "/auth/me": {"user_id": 4, "email": "t@example.invalid"},
    "/auth/user-count": {"user_count": 8},
    "/auth/refresh": lambda req: {"access_token": token(), "token_type": "bearer"},
    "/allergens": [],
    "/symptoms": [],
    "/units": [],
    "/entries/allergens": [],
    "/entries/symptoms": [],
    "/checkin/variables": [],
    "/training/exercises": [],
    "/training/sessions": [],
    "/training/sessions/open": {"session": None},
    "/training/practice": {"items": []},
    "/training/aerobic": {"aerobic": None},
    "/training/focus": {"focus": "knee", "options": []},
    "/training/spacing": {"spacing": "daily"},
    "/training/equipment": {"unset": False, "items": []},
    "/training/checkin": {"items": []},
    "/training/exercises/seed": {"added": 0},
    "/training/today": None,      # set per test
}
