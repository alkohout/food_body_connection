"""What the page must do when you press things.

Each test is a bug that reached the person using the app.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness import API, Api, serve, token          # noqa: E402

from playwright.sync_api import sync_playwright     # noqa: E402

FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'pass' if ok else 'FAIL'}  {name}" + (f"  {detail}" if not ok else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


PLAN = {
    "day": "A", "kind": "strength", "kind_why": "Chosen explicitly.",
    "theme": "Squat, pull and core", "focus": "knee", "focus_label": "Knee",
    "phase": {"phase": 2, "label": "Load", "sessions_done": 20, "to_advance": "1 more"},
    "knee": {"action": "progress", "reason": "No lingering knee — progressing.",
             "awaiting_next_day": None},
    "blocks": [], "notes": [], "achievable_loads": [0, 2.5], "bands": [7.5],
    "tai_chi_form_due": None, "available_equipment": ["band"], "limits": None,
    "mode": "full", "suggested_mode": "full", "suggested_because": None,
    "modes": [{"key": "full", "label": "Full session"}],
    "soreness_word": "knee", "soreness_prompt": "How was the knee this morning?",
}


def open_training(page, base, api):
    page.route(f"{API}/**", api.handler)
    page.add_init_script(f"localStorage.setItem('access_token', {token()!r});")
    page.goto(f"{base}/dashboard.html")
    page.click('button.tab[data-tab="training"]')
    page.wait_for_timeout(700)


def run(name, api, body):
    with serve() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            open_training(page, base, api)
            body(page, api, errors)
        finally:
            browser.close()


def test_morning_score_is_asked_before_a_session():
    """It was skipped on three of the four routes into a session."""
    plan = dict(PLAN)
    plan["knee"] = dict(PLAN["knee"], awaiting_next_day=489)
    api = Api(**{"/training/today": plan})

    def body(page, api, errors):
        page.click("text=Start session")
        page.wait_for_timeout(500)
        asked = page.locator("text=Before you start").count() > 0
        check("starting a session asks for the morning score", asked)
        started = [r for r in api.seen
                   if r["path"] == "/training/sessions" and r["method"] == "POST"]
        check("and does not start one until it is answered", not started,
              f"{len(started)} sessions created")
        check("no uncaught error on the way", not errors, str(errors[:1]))
    run("gate", api, body)


def test_an_open_session_is_offered_back():
    """A reload stranded it: the runner came back empty and a second began."""
    api = Api(**{
        "/training/today": PLAN,
        "/training/sessions/open": {"session": {
            "session_id": 490, "date_time": "2026-09-19T05:03:00+00:00",
            "session_type": "strength", "duration_min": None, "overall_rpe": None,
            "notes": None, "next_day_knee": None,
            "sets": [{"set_id": 1, "exercise_name": "Push Up", "reps": 8},
                     {"set_id": 2, "exercise_name": "Push Up", "reps": 8}]}},
    })

    def body(page, api, errors):
        check("an interrupted session is offered back",
              page.locator("text=still open").count() > 0)
        check("and says how much is already in it",
              page.locator("text=2 sets logged").count() > 0)
        check("no uncaught error on the way", not errors, str(errors[:1]))
    run("resume", api, body)


def test_the_walk_appears_only_when_scheduled():
    """It was a step inside the runner, then briefly nowhere at all."""
    walk = {"exercise": "Brisk Walk", "exercise_id": 1, "low": 25, "high": 30,
            "prescription": "25-30 min", "form_cues": None, "why": "By breath.",
            "done": False, "logged_minutes": None, "session_id": None}

    def with_walk(page, api, errors):
        check("a scheduled walk gets its own card",
              page.locator("text=Today's walk").count() > 0)
        check("with a way to log it",
              page.locator("#tr-aerobic-min").count() > 0)
    run("walk", Api(**{"/training/today": PLAN,
                       "/training/aerobic": {"aerobic": walk}}), with_walk)

    def without(page, api, errors):
        check("no card on a day without one",
              page.locator("text=Today's walk").count() == 0)
    run("nowalk", Api(**{"/training/today": PLAN}), without)


def test_every_api_call_carries_a_token():
    """The refresh was wired in by hand at eight of thirty-six call sites."""
    api = Api(**{"/training/today": PLAN})

    def body(page, api, errors):
        page.wait_for_timeout(300)
        naked = [r for r in api.seen if not r["auth"].startswith("Bearer ")
                 and r["path"] not in ("/auth/user-count",)]
        check(f"all {len(api.seen)} requests carried a bearer token", not naked,
              str([r['path'] for r in naked][:4]))
    run("auth", api, body)


if __name__ == "__main__":
    for fn in [v for k, v in sorted(globals().items()) if k.startswith("test_")]:
        print(f"\n{fn.__name__}")
        fn()
    print("\n" + "=" * 58)
    if FAILURES:
        print(f"{len(FAILURES)} FAILED")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("all checks passed")
