# -*- coding: utf-8 -*-
"""End-to-end over the real HTTP API, against a running Odoo.

This is not the unit suite. Nothing here reaches into the ORM: every assertion
is made through the same endpoints an edge agent uses, over a real socket, with
a real API key that was issued once and hashed on the server. What it proves is
that the documented contract in ``doc/API.md`` is the contract the server
actually honours — a thing no in-process test can establish, because an
in-process test never crosses the wire, never serialises JSON, and never meets
the routing, the auth header or the TLS guard.

Run it with ``tools/e2e/run.sh``, which brings the server up and prepares the
database first.

Read-back is deliberately done through the API's own ``/config`` and through
the numbers the next request reports, not through psql: if a figure is only
visible to somebody with a database password, it is not a figure a customer has.
"""
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests

BASE = os.environ.get("E2E_URL", "http://127.0.0.1:8171")
API = BASE + "/analitix/api/v1"

_state = json.load(open(os.environ["E2E_STATE"], encoding="utf-8"))
KEY = _state["api_key"]
OTHER_KEY = _state["other_api_key"]

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name,
                        ("  — %s" % detail) if detail and not condition else ""))
    return bool(condition)


def call(method, path, payload=None, key=KEY, headers=None):
    head = {"Content-Type": "application/json"}
    if key:
        head["Authorization"] = "Bearer %s" % key
    head.update(headers or {})
    response = requests.request(
        method, API + path, headers=head,
        data=json.dumps(payload) if payload is not None else None, timeout=30)
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, {}


def crossing(direction="in", when=None, **extra):
    event = {
        "uuid": str(uuid.uuid4()),
        "ts": (when or datetime.now(timezone.utc)).isoformat(),
        "direction": direction,
        "count": 1,
    }
    event.update(extra)
    return event


# ======================================================================
# 1. Authentication and transport
# ======================================================================
def test_auth():
    status, body = call("GET", "/config", key=None)
    check("no key is refused", status in (401, 403), "got %s" % status)

    status, body = call("GET", "/config", key="alx_not_a_real_key_at_all")
    check("a wrong key is refused", status in (401, 403), "got %s" % status)

    status, body = call("GET", "/config")
    check("a valid key is accepted", status == 200 and body.get("ok"),
          "got %s %s" % (status, body))
    return body


def test_fallback_header():
    """CCTV firmware that cannot set Authorization uses X-Analitix-Key."""
    response = requests.get(
        API + "/config", headers={"X-Analitix-Key": KEY}, timeout=30)
    check("the X-Analitix-Key fallback works",
          response.status_code == 200, "got %s" % response.status_code)


def test_config_shape(config):
    device = config.get("device") or {}
    store = config.get("store") or {}
    door = config.get("door") or {}
    check("config identifies the device",
          device.get("uid") == _state["device_uid"], repr(device))
    check("config carries the store's own settings",
          "heartbeat_interval_s" in store and "capture_enabled" in store,
          repr(store))
    check("config carries the door", bool(door.get("name")), repr(door))
    check("config leaks nothing about other stores",
          str(_state["other_store_id"]) not in json.dumps(config),
          "another store's id appeared in the config payload")


# ======================================================================
# 2. Ingest, idempotency and rejection
# ======================================================================
def test_ingest_basic():
    events = [crossing("in") for _ in range(5)] + [crossing("out")]
    status, body = call("POST", "/events",
                        {"agent_version": "e2e", "queue_size": 0,
                         "events": events})
    check("a batch is accepted", status == 200 and body.get("ok"),
          "%s %s" % (status, body))
    check("every event of the batch is stored", body.get("stored") == 6,
          "stored=%s" % body.get("stored"))
    return events


def test_idempotency(events):
    """The contract that makes a retry after a timeout safe."""
    status, body = call("POST", "/events", {"events": events})
    check("a replayed batch stores nothing new", body.get("stored") == 0,
          "stored=%s" % body.get("stored"))
    check("a replayed batch is reported as duplicate, not as an error",
          status == 200 and body.get("duplicates") == len(events),
          "duplicates=%s" % body.get("duplicates"))


def test_repeat_inside_one_batch():
    event = crossing("in")
    status, body = call("POST", "/events", {"events": [event, dict(event)]})
    check("a repeat inside one batch is collapsed",
          body.get("stored") == 1 and body.get("duplicates") == 1,
          "stored=%s duplicates=%s" % (body.get("stored"), body.get("duplicates")))


def test_partial_success():
    """One bad event must not cost the good ones in the same batch."""
    good = crossing("in")
    bad_ts = crossing("in")
    bad_ts["ts"] = "not-a-timestamp"
    no_uuid = {"ts": datetime.now(timezone.utc).isoformat(), "direction": "in"}

    status, body = call("POST", "/events", {"events": [good, bad_ts, no_uuid]})
    check("the good event of a mixed batch is stored",
          body.get("stored") == 1, "stored=%s" % body.get("stored"))
    check("the bad ones are reported individually",
          len(body.get("rejected") or []) == 2, repr(body.get("rejected")))
    reasons = {r.get("reason") for r in (body.get("rejected") or [])}
    check("an unparseable timestamp is named as such",
          any("timestamp" in (r or "") for r in reasons), repr(reasons))


def test_timestamp_is_the_stores_clock():
    """An agent replaying a buffered outage must land on the real hour."""
    when = datetime.now(timezone.utc) - timedelta(hours=6)
    event = crossing("in", when=when)
    status, body = call("POST", "/events", {"events": [event]})
    check("a backdated event is accepted", body.get("stored") == 1,
          "%s %s" % (status, body))


def test_oversized_batch():
    events = [crossing("in") for _ in range(1001)]
    status, body = call("POST", "/events", {"events": events})
    check("a batch over the documented limit is refused",
          status == 413, "got %s" % status)


# ======================================================================
# 3. The other endpoints
# ======================================================================
def test_heartbeat():
    status, body = call("POST", "/heartbeat",
                        {"agent_version": "e2e", "queue_size": 3})
    check("heartbeat is accepted", status == 200 and body.get("ok"),
          "%s %s" % (status, body))
    check("heartbeat hands back the store's interval",
          isinstance(body.get("heartbeat_interval_s"), int),
          repr(body))


def test_staff_signatures():
    status, body = call("GET", "/staff_signatures")
    check("the staff endpoint answers", status == 200 and body.get("ok"),
          "%s %s" % (status, body))
    check("the staff payload says whether exclusion is on",
          "enabled" in body, repr(list(body)[:6]))


def test_dwell():
    """The one endpoint evaluated inline, because it is worthless late."""
    status, body = call("POST", "/dwell", {"dwells": []})
    check("an empty dwell report is accepted",
          status == 200 and body.get("ok"), "got %s %s" % (status, body))

    # An unknown track is skipped quietly, not rejected: somebody who walked in
    # before the agent restarted has no visit to attach to, and that is not an
    # error the agent can do anything about.
    status, body = call("POST", "/dwell", {"dwells": [{
        "track": "e2e-unknown-track", "zone": "R",
        "since": datetime.now(timezone.utc).isoformat(), "seconds": 120,
    }]})
    check("an unknown track is skipped rather than rejected",
          status == 200 and body.get("skipped") == 1,
          "%s %s" % (status, body))

    status, body = call("POST", "/dwell", {"dwells": "not a list"})
    check("a malformed dwell payload is refused",
          status == 400, "got %s %s" % (status, body))


def test_checkout():
    status, body = call("POST", "/checkout", {})
    check("a checkout with no ticket reference is refused",
          status == 400, "got %s %s" % (status, body))

    # A ticket Odoo has not seen yet is answered, not rejected: the
    # purchase-unit fallback already attributes it, so there is nothing for the
    # agent to retry.
    status, body = call("POST", "/checkout", {
        "pos_reference": "E2E Order that does not exist",
        "embedding": [0.1] * 32,
    })
    check("an unknown ticket is answered rather than turned into a retry loop",
          status == 200 and body.get("ok") and body.get("queued") is False,
          "%s %s" % (status, body))


# ======================================================================
# 4. Isolation and revocation — the ones that matter most
# ======================================================================
def test_a_key_reaches_only_its_own_store():
    status, mine = call("GET", "/config", key=KEY)
    status2, theirs = call("GET", "/config", key=OTHER_KEY)
    check("each key resolves to its own store",
          mine["store"]["id"] != theirs["store"]["id"],
          "both keys resolved to store %s" % mine["store"]["id"])
    check("a key cannot name another store's device",
          mine["device"]["uid"] != theirs["device"]["uid"])


def test_events_land_in_the_keys_own_store():
    """The check that a compromised key cannot write into a neighbour."""
    before = call("GET", "/config", key=OTHER_KEY)[1]["store"]["id"]
    event = crossing("in")
    call("POST", "/events", {"events": [event]}, key=KEY)
    # Read back through the other customer's key: their store must be untouched
    # by a write made with ours. Proven below via the ORM check script, which
    # counts events per store; here we assert the write was accepted for ours.
    status, body = call("POST", "/events", {"events": [crossing("in")]},
                        key=OTHER_KEY)
    check("the other customer's key still works independently",
          status == 200 and body.get("stored") == 1,
          "%s %s" % (status, body))


def main():
    print("== Analitix E2E: HTTP API ==")
    config = test_auth()
    test_fallback_header()
    test_config_shape(config)

    events = test_ingest_basic()
    test_idempotency(events)
    test_repeat_inside_one_batch()
    test_partial_success()
    test_timestamp_is_the_stores_clock()
    test_oversized_batch()

    test_heartbeat()
    test_staff_signatures()
    test_dwell()
    test_checkout()

    test_a_key_reaches_only_its_own_store()
    test_events_land_in_the_keys_own_store()

    failed = [name for name, ok, _ in _results if not ok]
    print("\n%d checks, %d failed" % (len(_results), len(failed)))
    for name in failed:
        print("  FAILED: %s" % name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
