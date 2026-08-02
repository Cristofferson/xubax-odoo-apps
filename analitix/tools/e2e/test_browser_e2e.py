# -*- coding: utf-8 -*-
"""End-to-end through the browser, with Playwright, against a running Odoo.

Everything here is done the way a person does it: log in, click a menu, read a
number. No ORM, no test client. What that buys over the in-process suite is the
half of the product the suite cannot see — that the view actually renders, that
the record rule holds when a user *types a URL* rather than calling search(),
and that a control which exists in Python is reachable by the person who needs
it.

Three of these are worth more than the rest:

* **Guessing a URL.** A record rule is usually tested by calling ``search()``
  as a user. That is not how data leaks. Data leaks when somebody pastes the
  id of a record they were never shown, so that is what the isolation journey
  does.
* **The kill switch, across two interfaces.** Pause capture by clicking the
  button, then post to the ingest API and watch it be refused. Neither half
  proves anything alone.
* **The double control, with two logins.** The rule that the author of a
  watch-list entry cannot confirm it is only really tested by two people.
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import requests
from playwright.sync_api import sync_playwright

BASE = os.environ.get("E2E_URL", "http://127.0.0.1:8171")
API = BASE + "/analitix/api/v1"
SHOTS = os.environ.get("E2E_SHOTS", "/tmp/e2e/shots")
os.makedirs(SHOTS, exist_ok=True)

_state = json.load(open(os.environ["E2E_STATE"], encoding="utf-8"))
_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name,
                        ("  — %s" % detail) if detail and not condition else ""))
    return bool(condition)


# ----------------------------------------------------------------------
# Browser helpers
# ----------------------------------------------------------------------
def login(page, user, password=None):
    password = password or (user + "_pw")
    page.goto(BASE + "/web/login", wait_until="domcontentloaded")
    page.fill("input[name=login]", user)
    page.fill("input[name=password]", password)
    page.click("button[type=submit]")
    page.wait_for_selector(".o_main_navbar", timeout=45000)
    page.wait_for_timeout(1200)


def open_action(page, xmlid, settle=3000):
    page.goto(BASE + "/odoo/action-" + xmlid, wait_until="domcontentloaded")
    try:
        page.wait_for_selector(".o_content, .o_action_manager", timeout=30000)
    except Exception:
        pass
    page.wait_for_timeout(settle)


def body_text(page):
    return page.inner_text("body")


def shot(page, name):
    try:
        page.screenshot(path="%s/%s.png" % (SHOTS, name))
    except Exception:
        pass


def post_crossing(key, direction="in"):
    return requests.post(
        API + "/events",
        headers={"Authorization": "Bearer %s" % key,
                 "Content-Type": "application/json"},
        data=json.dumps({"events": [{
            "uuid": str(uuid.uuid4()),
            "ts": datetime.now(timezone.utc).isoformat(),
            "direction": direction, "count": 1,
        }]}), timeout=30)


# ======================================================================
# Journey 1 — the app opens and the numbers are on screen
# ======================================================================
def journey_dashboard(page):
    login(page, "admin", "admin")
    open_action(page, "analitix.action_hourly")
    text = body_text(page)
    check("the conversion dashboard opens", "Conversion" in text, text[:200])

    # Switch to the list, where the KPI columns actually are.
    switch = page.locator(".o_switch_view.o_list").first
    if switch.count():
        switch.click()
        page.wait_for_timeout(2500)
    # Filter to the store the agent fed rather than hoping it is on the first
    # page: the demo data alone fills 154 rows.
    page.fill(".o_searchview_input", _state["store_name"])
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    text = body_text(page)
    check("the dashboard shows the store the agent fed",
          _state["store_name"] in text,
          "the E2E store is not on the dashboard")
    shot(page, "01-dashboard")

    open_action(page, "analitix.action_device_health")
    # The health list opens grouped by status, so a device sits inside a
    # collapsed group and is not in the page text. Search for it, the way
    # somebody looking for one camera in a fleet would.
    page.fill(".o_searchview_input", "E2E front")
    page.keyboard.press("Enter")
    page.wait_for_timeout(3000)
    # Then open the group it landed in — a collapsed group shows a count, not
    # the row, and this screen groups by status by default.
    group = page.locator(".o_group_header").first
    if group.count():
        group.click()
        page.wait_for_timeout(2000)
    text = body_text(page)
    # The list shows the device's NAME; the uid lives on the form. Asserting on
    # the uid was asserting on something no screen shows.
    check("device health opens and lists the E2E device",
          "E2E front counter" in text, text[:300])
    shot(page, "02-device-health")


# ======================================================================
# Journey 2 — isolation, including by guessing a URL
# ======================================================================
def journey_isolation(page):
    login(page, _state["scoped_login"], _state["scoped_password"])

    open_action(page, "analitix.action_store")
    text = body_text(page)
    check("a scoped manager sees their own store",
          _state["store_name"] in text, text[:300])
    check("a scoped manager does not see the other customer's store",
          "E2E Other Customer" not in text,
          "another customer's store was listed")
    shot(page, "03-scoped-store-list")

    # The one that matters: paste the id of a record they were never shown.
    page.goto("%s/odoo/action-analitix.action_store/%d" % (
        BASE, _state["other_store_id"]), wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    text = body_text(page)
    denied = ("E2E Other Customer" not in text)
    check("guessing another store's URL does not open it", denied,
          "the record rendered for a user who was never given it")
    shot(page, "04-scoped-url-guess")


# ======================================================================
# Journey 3 — the kill switch, across the UI and the API
# ======================================================================
def journey_kill_switch(page):
    login(page, "admin", "admin")

    check("ingest works before the switch is touched",
          post_crossing(_state["api_key"]).status_code == 200)

    page.goto("%s/odoo/action-analitix.action_store/%d" % (
        BASE, _state["store_id"]), wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    pause = page.get_by_role("button", name="Pause Capture").first
    check("the kill switch is on the store form", pause.count() > 0)
    if pause.count():
        pause.click()
        page.wait_for_timeout(1200)
        # It asks first — stopping a customer's capture should not be one click.
        confirm = page.locator(".modal-footer button.btn-primary").first
        if confirm.count():
            check("the kill switch asks before it stops a shop's capture", True)
            confirm.click()
        page.wait_for_timeout(3000)
    shot(page, "05-capture-paused")

    response = post_crossing(_state["api_key"])
    check("a paused store refuses ingest at the API",
          response.status_code in (403, 423) or
          (response.json() or {}).get("error") in ("capture_disabled", "paused"),
          "got %s %s" % (response.status_code, response.text[:160]))

    resume = page.get_by_role("button", name="Resume Capture").first
    if resume.count():
        resume.click()
        page.wait_for_timeout(3000)
    check("ingest works again once capture is resumed",
          post_crossing(_state["api_key"]).status_code == 200)


# ======================================================================
# Journey 4 — the watch list, driven by two different people
# ======================================================================
def journey_watchlist(page):
    login(page, _state["security_a"])

    open_action(page, "analitix.action_watch_person")
    check("the security role reaches the watch list",
          "Watch List" in body_text(page))

    page.locator("button.o_list_button_add, .o-kanban-button-new").first.click()
    page.wait_for_timeout(2500)
    page.fill("div[name=display_label] input", "E2E entry")
    page.fill("div[name=reason] textarea", "Created by the end-to-end run.")
    store_field = page.locator("div[name=store_id] input").first
    store_field.click()
    store_field.fill(_state["store_name"])
    page.wait_for_timeout(1500)
    option = page.locator(".o-autocomplete--dropdown-item").first
    if option.count():
        option.click()
    page.wait_for_timeout(800)
    page.keyboard.press("Alt+s")
    page.wait_for_timeout(3000)
    shot(page, "06-watchlist-draft")

    text = body_text(page)
    check("a new entry is created awaiting confirmation",
          "Awaiting confirmation" in text or "draft" in text.lower(),
          text[:300])
    check("the form says plainly that it does nothing yet",
          "does nothing yet" in text.lower() or "nobody until" in text.lower(),
          "the warning about the double control is missing")

    # The author tries to confirm their own entry.
    confirm = page.get_by_role("button", name="Confirm").first
    if confirm.count():
        confirm.click()
        page.wait_for_timeout(1200)
        dialog = page.locator(".modal-footer button.btn-primary").first
        if dialog.count():
            dialog.click()
        page.wait_for_timeout(2500)
    text = body_text(page)
    check("the author cannot confirm their own entry",
          "cannot confirm" in text.lower() or "second authorised" in text.lower(),
          "the double control did not stop the author")
    shot(page, "07-watchlist-refused")


# ======================================================================
# Journey 5 — the chain console, as a regional manager
# ======================================================================
def journey_console(page):
    login(page, _state["regional_login"])

    text = body_text(page)
    check("a regional manager gets the Analitix app", "Analitix" in text)

    open_action(page, "analitix.action_chain_report")
    text = body_text(page)
    check("the chain console opens for a regional manager",
          "Chain Console" in text or "Conv" in text, text[:250])
    check("the console shows the region's own store",
          _state["store_name"] in text or "E2E" in text,
          "the regional's own store is not in the console")
    shot(page, "08-chain-console")

    # A regional manager configures nothing: the store form is not theirs.
    open_action(page, "analitix.action_watch_person", settle=2500)
    text = body_text(page)
    check("a regional manager cannot reach the watch list",
          "E2E entry" not in text,
          "a commercial role reached the watch list")


# ======================================================================
# Journey 6 — the manuals open, in the right language
# ======================================================================
def journey_manuals(page):
    login(page, "admin", "admin")
    response = page.request.get(BASE + "/analitix/manual/user")
    check("the user manual resolves and is served",
          response.ok and "Analitix" in response.text(),
          "status %s" % response.status)
    response = page.request.get(BASE + "/analitix/manual/implementer")
    check("the implementation guide resolves and is served",
          response.ok and "Analitix" in response.text(),
          "status %s" % response.status)


def main():
    print("== Analitix E2E: the browser ==")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for journey in (journey_dashboard, journey_isolation,
                        journey_kill_switch, journey_watchlist,
                        journey_console, journey_manuals):
            # A fresh context per journey: cookies do not leak between roles,
            # and an Odoo error dialog left open by one journey cannot block
            # the login form of the next — which is exactly what happened the
            # first time this ran.
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            try:
                journey(page)
            except Exception as error:  # noqa: BLE001
                check("%s completed" % journey.__name__, False, repr(error)[:400])
                shot(page, "error-%s" % journey.__name__)
            finally:
                context.close()
        browser.close()

    failed = [name for name, ok, _ in _results if not ok]
    print("\n%d checks, %d failed" % (len(_results), len(failed)))
    for name, ok, detail in _results:
        if not ok:
            print("  FAILED: %s — %s" % (name, detail[:300]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
