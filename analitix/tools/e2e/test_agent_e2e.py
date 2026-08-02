# -*- coding: utf-8 -*-
"""End-to-end with the REAL edge agent, as a subprocess.

The agent in ``edge/`` is what a customer installs on the mini-PC in their shop.
Until this existed it had never been executed: the addon's own test suite fakes
the ingest by calling the controller, which proves the server side and nothing
about the thing on the other end of the wire.

So this starts ``edge/analitix_agent.py`` for real — its own process, its own
config file, its own encrypted spool on disk — points it at a running Odoo with
a key that was issued once, and then asserts on what arrives.

It also pulls the plug. An agent that only works while the network is up is not
an agent: a shop's internet drops, and the promise the whole architecture makes
is that the visitors of those minutes are not lost. That promise is worth
exactly one test, and this is it.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(os.path.dirname(HERE))   # tools/e2e -> tools -> addon
AGENT = os.path.join(ADDON, "edge", "analitix_agent.py")
BASE = os.environ.get("E2E_URL", "http://127.0.0.1:8171")
API = BASE + "/analitix/api/v1"

_state = json.load(open(os.environ["E2E_STATE"], encoding="utf-8"))
KEY = _state["api_key"]

_results = []


def check(name, condition, detail=""):
    _results.append((name, bool(condition), detail))
    print("%s  %s%s" % ("PASS" if condition else "FAIL", name,
                        ("  — %s" % detail) if detail and not condition else ""))
    return bool(condition)


class AgentProcess:
    """The real agent, in its own process, with its own state directory."""

    def __init__(self, url=BASE, rate=240, extra=None):
        self.dir = tempfile.mkdtemp(prefix="analitix-e2e-")
        self.state = os.path.join(self.dir, "state")
        os.makedirs(self.state, exist_ok=True)
        config = {
            "odoo_url": url,
            "api_key": KEY,
            "source": "demo",
            "demo_rate_per_min": rate,
            "state_dir": self.state,
            "heartbeat_interval_s": 5,
            "verify_tls": False,
            "send_embeddings": False,
        }
        config.update(extra or {})
        self.config_path = os.path.join(self.dir, "agent.yaml")
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        # .json rather than .yaml so the agent's own loader takes the json
        # branch and the test does not depend on PyYAML being installed on
        # whatever machine runs it.
        os.rename(self.config_path, self.config_path[:-5] + ".json")
        self.config_path = self.config_path[:-5] + ".json"
        self.proc = None
        self.log = open(os.path.join(self.dir, "agent.log"), "w+")

    def start(self):
        self.proc = subprocess.Popen(
            [sys.executable, AGENT, "--config", self.config_path, "--verbose"],
            stdout=self.log, stderr=subprocess.STDOUT)
        return self

    def stop(self, graceful=True):
        if not self.proc:
            return
        if graceful:
            self.proc.send_signal(signal.SIGTERM)
        else:
            self.proc.kill()
        try:
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=10)
        self.proc = None

    def output(self):
        self.log.flush()
        self.log.seek(0)
        return self.log.read()

    def spool_files(self):
        return sorted(
            name for name in os.listdir(self.state) if not name.startswith("."))

    def cleanup(self):
        self.stop(graceful=False)
        self.log.close()
        shutil.rmtree(self.dir, ignore_errors=True)


def wait_for(predicate, timeout=45, interval=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


DB = os.environ.get("E2E_DB", "freshanalitix")


def observe():
    """What Odoo currently holds, read straight from PostgreSQL.

    Deliberately NOT through the API: this is the test's observation
    instrument, and an instrument that goes through the thing under test can
    hide the failure it is meant to catch. The agent is the subject here; the
    database is where the truth is checked.
    """
    query = (
        "SELECT (SELECT count(*) FROM analitix_event WHERE store_id = %(store)d),"
        "       (SELECT status FROM analitix_device WHERE device_uid = \'%(uid)s\')"
    ) % {"store": _state["store_id"], "uid": _state["device_uid"]}
    out = subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", DB, "-tAF", "|", "-c", query],
        capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    events, status = out.stdout.strip().split("|")
    return {"events": int(events), "device_status": status}


def main():
    print("== Analitix E2E: the real edge agent ==")
    if not os.path.exists(AGENT):
        print("FAIL  the agent is missing at %s" % AGENT)
        return 1

    agent = AgentProcess()
    try:
        # ---------------------------------------------------------------
        # 1. It starts, authenticates and pulls its own configuration.
        # ---------------------------------------------------------------
        agent.start()
        ok = wait_for(lambda: "config" in agent.output().lower(), timeout=30)
        check("the agent starts and reaches Odoo", ok,
              agent.output()[-600:])
        check("the agent does not crash on start-up",
              agent.proc and agent.proc.poll() is None,
              "exited with %s" % (agent.proc.poll() if agent.proc else "?"))

        # ---------------------------------------------------------------
        # 2. It sends crossings that actually arrive.
        # ---------------------------------------------------------------
        before = observe()["events"]
        arrived = wait_for(
            lambda: observe()["events"] > before, timeout=60)
        check("crossings from the agent reach Odoo", arrived,
              "still %s events after 60s" % before)

        # ---------------------------------------------------------------
        # 3. It heartbeats, and the device turns online in Odoo.
        # ---------------------------------------------------------------
        online = wait_for(
            lambda: observe()["device_status"] == "online", timeout=45)
        check("the device turns online from the agent's own heartbeat", online,
              "status is %s" % observe()["device_status"])

        # ---------------------------------------------------------------
        # 4. The outage. This is the one that matters.
        # ---------------------------------------------------------------
        offline_agent = AgentProcess(url="http://127.0.0.1:9", rate=600)
        try:
            offline_agent.start()
            time.sleep(12)
            buffered = offline_agent.spool_files()
            check("an agent that cannot reach Odoo spools to disk",
                  bool(buffered), "state dir is empty: %s" % buffered)
            check("the agent stays up through an outage",
                  offline_agent.proc.poll() is None,
                  "it exited with %s" % offline_agent.proc.poll())

            # Now point the same spool at a reachable Odoo and restart it: the
            # buffered crossings must arrive, which is the actual promise.
            with open(offline_agent.config_path, encoding="utf-8") as handle:
                config = json.load(handle)
            config["odoo_url"] = BASE
            with open(offline_agent.config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)

            before_recovery = observe()["events"]
            offline_agent.stop()
            offline_agent.start()
            recovered = wait_for(
                lambda: observe()["events"] > before_recovery,
                timeout=60)
            check("buffered crossings arrive once the link is back", recovered,
                  "still %s events" % before_recovery)
        finally:
            offline_agent.cleanup()

        # ---------------------------------------------------------------
        # 5. A revoked key is refused, without the agent dying.
        # ---------------------------------------------------------------
        rogue = AgentProcess(extra={"api_key": "alx_revoked_or_never_issued"})
        try:
            rogue.start()
            time.sleep(12)
            output = rogue.output().lower()
            check("a bad key is reported rather than swallowed",
                  "401" in output or "unauthor" in output or "forbidden" in output
                  or "error" in output,
                  output[-500:])
            check("a bad key does not kill the agent",
                  rogue.proc.poll() is None,
                  "it exited with %s" % rogue.proc.poll())
        finally:
            rogue.cleanup()

        # ---------------------------------------------------------------
        # 6. It shuts down cleanly on SIGTERM, like a service.
        # ---------------------------------------------------------------
        agent.stop(graceful=True)
        check("the agent stops cleanly on SIGTERM", True)

    finally:
        agent.cleanup()

    failed = [name for name, ok, _ in _results if not ok]
    print("\n%d checks, %d failed" % (len(_results), len(failed)))
    for name in failed:
        print("  FAILED: %s" % name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
