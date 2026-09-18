"""The tabs that are not Training.

Added because the last defect found by hand was here, not in training: typing
an exposure the list had never seen threw a TypeError, on the exact path the
feature exists for. The browser tests covered training because that is where
the recent work was; the bug was in the oldest part of the app.
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


STATS = {
    # The keys the server actually sends. Renaming them here once hid the
    # whole plotting section behind an empty state, under 425 logged rows.
    "Total allergens logged": 425,
    "Total symptoms logged": 269,
    "Total days tracked": 161,
    "Average allergens logged per day": 2.87,
    "Average symptoms logged per day": 2.4,
    "Triptan usage (last 28 days)": 8,
}


def run(tab, api, body, wait=700):
    with serve() as base, sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        try:
            page.route(f"{API}/**", api.handler)
            page.add_init_script(f"localStorage.setItem('access_token', {token()!r});")
            page.goto(f"{base}/dashboard.html")
            page.click(f'button.tab[data-tab="{tab}"]')
            page.wait_for_timeout(wait)
            body(page, api, errors)
        finally:
            browser.close()


def test_analysis_stats_and_the_plot_picker():
    """The picker is hidden unless the stats say there is data.

    Which made a renamed response key invisible: the numbers came back, the
    lookup missed, and the entire plotting section disappeared.
    """
    def body(page, api, errors):
        total = page.locator("#stat-total-allergens").inner_text()
        check("the exposure total is read from the response", total == "425", total)
        check("the symptom total too",
              page.locator("#stat-total-symptoms").inner_text() == "269")
        visible = page.eval_on_selector(
            ".analysis-picker-container", "el => getComputedStyle(el).display")
        check("the plot picker is shown when there is data", visible != "none", visible)
        empty = page.eval_on_selector(
            "#analysis-empty-state", "el => getComputedStyle(el).display")
        check("and the empty state is not", empty == "none", empty)
        check("no uncaught error", not errors, str(errors[:1]))
    run("analysis", Api(**{"/analysis/stats": STATS}), body)


def test_the_empty_state_still_works():
    """A genuinely empty account should see the empty state, not a broken page."""
    def body(page, api, errors):
        empty = page.eval_on_selector(
            "#analysis-empty-state", "el => getComputedStyle(el).display")
        check("a new account sees the empty state", empty == "block", empty)
        check("no uncaught error", not errors, str(errors[:1]))
    run("analysis", Api(**{"/analysis/stats": dict.fromkeys(STATS, 0)}), body)


def test_typing_an_unknown_exposure_offers_to_add_it():
    """It threw instead. The element had no id in the markup, and the branch
    that showed it dereferenced null — on the one path the feature is for."""
    def body(page, api, errors):
        # The autocomplete lives inside the Deeper Analysis panel, which the
        # picker has to reveal first — the select beside it is the list of
        # exposures already known, and has nothing to complete.
        page.select_option("#analysis-select", "deeper-analysis")
        page.wait_for_timeout(400)
        page.fill("#allergen-intensity-input", "Kumara")
        page.wait_for_timeout(800)
        check("no uncaught error when nothing matches", not errors, str(errors[:1]))
        shown = page.eval_on_selector(
            "#add-allergen-wrapper", "el => getComputedStyle(el).display")
        check("the add-new row is offered", shown == "block", shown)
        label = page.locator("#add-allergen-btn").inner_text()
        check("and names what you typed", "Kumara" in label, label)
    # Stats have to be non-empty or the picker stays hidden and the panel with
    # it; the empty exposure list is what makes "Kumara" unknown.
    run("analysis", Api(**{"/analysis/stats": STATS, "/allergens": [],
                           "/units": [], "/entries/allergens": []}), body)


def test_the_other_tabs_open_without_throwing():
    """Cheap, and it is how a missing element or a renamed field shows up."""
    for tab in ("symptom", "medication", "documents", "checkin"):
        def body(page, api, errors, tab=tab):
            check(f"the {tab} tab opens cleanly", not errors, str(errors[:1]))
        run(tab, Api(**{"/analysis/stats": STATS}), body)


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
