#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analitix edge agent — reference implementation of the v1 ingest contract.

This runs on the mini-PC in the store, not inside Odoo.  It watches one camera,
counts people crossing a virtual line, and posts the crossings to Odoo.  Odoo
never sees an image; it never even has an endpoint that would accept one.

What this file is really about is the ugly part: a shop's internet is not a data
centre's.  It drops for ten minutes at a time, the router reboots at 3 a.m., a
cleaner unplugs the switch.  A counter that loses those hours is worse than no
counter, because the customer cannot tell the difference between "quiet
Tuesday" and "we were blind until noon".  So most of the code here is about
never losing a crossing:

* every crossing gets its uuid **before** the first send attempt, and keeps it
  across retries, restarts and power cuts — that is what makes Odoo's
  deduplication work (see ``doc/API.md`` §3);
* everything lands in an on-disk queue first, encrypted, and is only deleted
  once Odoo has explicitly acknowledged it;
* the queue is replayed **in order** with the original timestamps, so a
  recovered outage shows up as the hours it actually was and not as one
  impossible spike;
* the buffer is encrypted at rest, because a stolen mini-PC should be worth
  nothing (task 984, point 1).

Vision back-ends are pluggable. ``--source demo`` needs no camera at all and is
what the test suite and the demo videos use.

    python3 analitix_agent.py --config /etc/analitix/agent.yaml

Dependencies: ``requests``, ``cryptography``, ``pyyaml``. The CV back-end
(``ultralytics`` for YOLO, ``insightface`` for embeddings) is imported lazily,
so a counting-only deployment never installs it.
"""
import argparse
import base64
import json
import logging
import os
import queue
import signal
import sqlite3
import sys
import threading
import time
import uuid as uuid_lib
from datetime import datetime, timezone

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("analitix-agent requires 'requests' (pip install requests)")

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover
    sys.exit("analitix-agent requires 'cryptography' (pip install cryptography)")

_log = logging.getLogger("analitix.agent")

AGENT_VERSION = "1.0.0"
MAX_BATCH = 500          # half the server ceiling, leaving headroom
SEND_INTERVAL_S = 5
CONFIG_REFRESH_S = 3600


# ======================================================================
# Durable queue
# ======================================================================
class EventQueue:
    """An append-only, encrypted, crash-safe queue on local disk.

    SQLite rather than a JSON file: the agent is killed by power cuts, and a
    half-written JSON file loses the whole buffer, whereas SQLite's journal
    means the worst case is losing the single in-flight row.

    Each payload is encrypted with a key kept in a 0600 file beside the
    database. That is not real key isolation — anyone with root on the box has
    both — but it is the difference between a stolen mini-PC being a data breach
    and being a stolen mini-PC, which is the actual threat in a retail store.
    """

    def __init__(self, path, key_path):
        self.path = path
        self._fernet = Fernet(self._load_or_create_key(key_path))
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                uuid TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                payload BLOB NOT NULL
            )
        """)
        # Replay must be chronological, so the index is on arrival order.
        self._db.execute(
            "CREATE INDEX IF NOT EXISTS events_created_idx ON events (created_at)")
        self._db.commit()

    @staticmethod
    def _load_or_create_key(key_path):
        if os.path.exists(key_path):
            with open(key_path, "rb") as handle:
                return handle.read().strip()
        key = Fernet.generate_key()
        # Written 0600 before anything is put in it.
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(key)
        _log.info("Generated a new buffer encryption key at %s", key_path)
        return key

    def put(self, event):
        """Persist one event. It is not considered counted until this returns."""
        blob = self._fernet.encrypt(json.dumps(event).encode())
        with self._lock:
            try:
                self._db.execute(
                    "INSERT INTO events (uuid, created_at, payload) VALUES (?, ?, ?)",
                    (event["uuid"], time.time(), blob))
                self._db.commit()
            except sqlite3.IntegrityError:
                # Same uuid already queued — by construction this should not
                # happen, and if it does the queued copy is the one to keep.
                pass

    def peek(self, limit=MAX_BATCH):
        """Oldest ``limit`` events, in the order they happened."""
        with self._lock:
            rows = self._db.execute(
                "SELECT uuid, payload FROM events ORDER BY created_at, rowid LIMIT ?",
                (limit,)).fetchall()
        events = []
        for row_uuid, blob in rows:
            try:
                events.append(json.loads(self._fernet.decrypt(blob).decode()))
            except Exception:  # noqa: BLE001
                # Undecryptable row (key rotated, disk corruption). Drop it
                # rather than jam the queue behind it forever.
                _log.warning("Dropping an unreadable queued event %s", row_uuid)
                self.ack([row_uuid])
        return events

    def ack(self, uuids):
        """Delete exactly what the server said it holds — never more."""
        if not uuids:
            return
        with self._lock:
            self._db.executemany(
                "DELETE FROM events WHERE uuid = ?", [(u,) for u in uuids])
            self._db.commit()

    def size(self):
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]


# ======================================================================
# Odoo client
# ======================================================================
class OdooClient:
    """Thin HTTP client for the v1 API. Never raises at the caller."""

    def __init__(self, base_url, api_key, verify_tls=True, timeout=20):
        self.base = base_url.rstrip("/") + "/analitix/api/v1"
        self.timeout = timeout
        self.verify = verify_tls
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        })
        if not self.base.startswith("https://"):
            # Loud, because the server will refuse it anyway and a silent
            # failure here looks exactly like "the camera is broken".
            _log.warning("Endpoint is not HTTPS — Odoo will reject every "
                         "request unless the lab override is enabled.")

    def _call(self, method, path, payload=None):
        try:
            response = self.session.request(
                method, self.base + path,
                data=json.dumps(payload) if payload is not None else None,
                timeout=self.timeout, verify=self.verify)
        except requests.RequestException as error:
            return None, str(error)
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400:
            return None, body.get("error") or "http_%d" % response.status_code
        return body, None

    def send_events(self, events, queue_size):
        return self._call("POST", "/events", {
            "agent_version": AGENT_VERSION,
            "queue_size": queue_size,
            "events": events,
        })

    def heartbeat(self, queue_size):
        return self._call("POST", "/heartbeat", {
            "agent_version": AGENT_VERSION, "queue_size": queue_size})

    def fetch_config(self):
        return self._call("GET", "/config")

    def fetch_staff(self):
        return self._call("GET", "/staff_signatures")


# ======================================================================
# Staff matching, on the edge
# ======================================================================
class StaffMatcher:
    """Holds the store's signatures so matching happens without a round trip.

    This is the privacy-preferable path: the decision is made in-process, the
    crossing arrives at Odoo already labelled, and no face vector ever travels.
    """

    def __init__(self):
        self.signatures = []      # [(employee_ref, unit_vector)]
        self.threshold = 0.55
        self.enabled = True

    def load(self, payload):
        self.enabled = bool(payload.get("enabled", True))
        self.threshold = float(payload.get("threshold", 0.55))
        loaded = []
        for entry in payload.get("signatures", []):
            vector = entry.get("vector") or []
            if vector:
                loaded.append((entry.get("employee_ref"), _normalize(vector)))
        self.signatures = loaded
        _log.info("Loaded %d staff signature(s), threshold %.2f",
                  len(loaded), self.threshold)

    def match(self, vector):
        """Return ``(employee_ref, score)`` or ``(None, best_score)``."""
        if not self.enabled or not vector or not self.signatures:
            return None, 0.0
        probe = _normalize(vector)
        best_ref, best_score = None, 0.0
        for ref, known in self.signatures:
            if len(known) != len(probe):
                continue
            score = sum(a * b for a, b in zip(probe, known))
            if score > best_score:
                best_ref, best_score = ref, score
        if best_score >= self.threshold:
            return best_ref, best_score
        return None, best_score


def _normalize(vector):
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector] if norm else list(vector)


# ======================================================================
# Counting sources
# ======================================================================
class DemoSource:
    """A synthetic source, so the whole pipeline can be exercised without a camera.

    Used by the automated tests and by the screencasts, which is why it is in
    the shipped agent rather than in a test folder: a demo that runs different
    code from production proves nothing about production.
    """

    def __init__(self, rate_per_min=12):
        self.interval = 60.0 / max(rate_per_min, 1)
        self._stop = threading.Event()

    def crossings(self):
        toggle = True
        while not self._stop.is_set():
            time.sleep(self.interval)
            if self._stop.is_set():
                break
            yield {"direction": "in" if toggle else "out",
                   "count": 1, "track": "demo-%d" % int(time.time())}
            toggle = not toggle

    def stop(self):
        self._stop.set()


class LineCounterSource:
    """YOLO + ByteTrack over a virtual line. Imported lazily on purpose.

    ``ultralytics`` pulls in torch, which is a gigabyte the counting-only
    deployments do not need, and which the Odoo addon must never depend on.
    """

    def __init__(self, camera=0, line=None, model="yolov8n.pt", conf=0.35):
        self.camera = camera
        self.line = line or [[0, 540], [1920, 540]]
        self.model_path = model
        self.conf = conf
        self._stop = threading.Event()

    def crossings(self):
        try:
            import cv2
            from ultralytics import YOLO
        except ImportError:
            _log.error("Vision back-end unavailable — install 'ultralytics' and "
                       "'opencv-python', or run with --source demo.")
            return

        model = YOLO(self.model_path)
        capture = cv2.VideoCapture(self.camera)
        side_of_line = {}
        (x1, y1), (x2, y2) = self.line

        def side(px, py):
            # Sign of the cross product: which half-plane the point sits in.
            return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1) >= 0

        while not self._stop.is_set():
            ok, frame = capture.read()
            if not ok:
                time.sleep(0.5)
                continue
            results = model.track(frame, persist=True, classes=[0],
                                  conf=self.conf, verbose=False)
            if not results or results[0].boxes is None:
                continue
            boxes = results[0].boxes
            if boxes.id is None:
                continue
            for box, track_id in zip(boxes.xyxy.tolist(), boxes.id.tolist()):
                cx = (box[0] + box[2]) / 2
                cy = (box[1] + box[3]) / 2
                now_side = side(cx, cy)
                was_side = side_of_line.get(track_id)
                side_of_line[track_id] = now_side
                if was_side is not None and was_side != now_side:
                    yield {
                        "direction": "in" if now_side else "out",
                        "count": 1,
                        "track": str(int(track_id)),
                    }
            # The frame is dropped here, every iteration. It is never written to
            # disk, never queued and never sent. That is the whole privacy
            # promise, and it lives in this one fact.
        capture.release()

    def stop(self):
        self._stop.set()


# ======================================================================
# Agent
# ======================================================================
class Agent:

    def __init__(self, config):
        self.config = config
        self.client = OdooClient(
            config["odoo_url"], config["api_key"],
            verify_tls=config.get("verify_tls", True))
        state_dir = config.get("state_dir", "/var/lib/analitix")
        os.makedirs(state_dir, exist_ok=True)
        self.queue = EventQueue(
            os.path.join(state_dir, "queue.db"),
            os.path.join(state_dir, "buffer.key"))
        self.matcher = StaffMatcher()
        self.heartbeat_interval = config.get("heartbeat_interval_s", 60)
        self.paused = False
        self._stop = threading.Event()
        self._pending = queue.Queue()
        self.source = self._build_source()

    def _build_source(self):
        kind = self.config.get("source", "demo")
        if kind == "demo":
            return DemoSource(self.config.get("demo_rate_per_min", 12))
        return LineCounterSource(
            camera=self.config.get("camera", 0),
            line=self.config.get("line"),
            model=self.config.get("model", "yolov8n.pt"),
            conf=self.config.get("confidence", 0.35))

    # ------------------------------------------------------------------
    def refresh_config(self):
        """Adopt server-side settings, so a fleet is retuned from Odoo."""
        body, error = self.client.fetch_config()
        if error:
            _log.warning("Config refresh failed: %s", error)
            return
        store = body.get("store", {})
        self.heartbeat_interval = store.get(
            "heartbeat_interval_s", self.heartbeat_interval)
        self.paused = not store.get("capture_enabled", True)
        device_config = (body.get("device") or {}).get("config") or {}
        if device_config.get("line") and isinstance(self.source, LineCounterSource):
            self.source.line = device_config["line"]
        staff, staff_error = self.client.fetch_staff()
        if not staff_error:
            self.matcher.load(staff)

    # ------------------------------------------------------------------
    def capture_loop(self):
        """Turn detections into durable, uniquely-identified events."""
        for crossing in self.source.crossings():
            if self._stop.is_set():
                break
            if self.paused:
                # The store's kill switch is on. Do not record: pausing is
                # meant to stop capture, not to defer it.
                continue
            event = {
                # Minted here, once, before any attempt to send. Everything
                # about the retry story depends on this line.
                "uuid": str(uuid_lib.uuid4()),
                "ts": datetime.now(timezone.utc).isoformat(),
                "direction": crossing.get("direction", "in"),
                "count": int(crossing.get("count", 1)),
            }
            if crossing.get("track"):
                event["track"] = crossing["track"]
            if crossing.get("liveness") is not None:
                event["liveness"] = round(float(crossing["liveness"]), 4)
            if crossing.get("demographics") and self.config.get(
                    "send_demographics", True):
                # Age band, gender and expression — aggregate attributes only.
                # There is nothing identifying here and no image; it is what
                # makes "is my evening crowd younger than my morning crowd"
                # answerable.
                event["demographics"] = crossing["demographics"]

            vector = crossing.get("embedding")
            if vector:
                employee_ref, score = self.matcher.match(vector)
                if employee_ref:
                    event.update({"is_staff": True, "staff_score": round(score, 4),
                                  "employee_ref": employee_ref})
                elif self.config.get("send_embeddings", False):
                    # Only if the operator opted in: the default keeps every
                    # face vector inside the store.
                    event["embedding"] = _encode_vector(vector)
                    event["embedding_model"] = self.config.get(
                        "embedding_model", "buffalo_l")
            self.queue.put(event)

    # ------------------------------------------------------------------
    def send_loop(self):
        while not self._stop.is_set():
            self._flush_once()
            self._stop.wait(SEND_INTERVAL_S)

    def _flush_once(self):
        batch = self.queue.peek(MAX_BATCH)
        if not batch:
            return
        body, error = self.client.send_events(batch, self.queue.size())
        if error:
            if error == "capture_paused":
                self.paused = True
                _log.info("Store capture is paused; holding %d event(s).",
                          self.queue.size())
            elif error == "invalid_credentials":
                _log.error("Credentials rejected. Buffering; a technician must "
                           "rotate this device's key in Odoo.")
            else:
                _log.warning("Send failed (%s); %d event(s) buffered.",
                             error, self.queue.size())
            return
        self.paused = False
        # Delete only what Odoo confirmed it holds — never optimistically.
        self.queue.ack(body.get("acknowledged") or [])
        rejected = body.get("rejected") or []
        if rejected:
            # Rejected rows would otherwise be retried forever. They are dropped
            # deliberately and loudly: a malformed event is a bug to fix, not a
            # customer's visitor to preserve.
            _log.error("Odoo rejected %d event(s): %s", len(rejected),
                       json.dumps(rejected[:5]))
            self.queue.ack([batch[row["index"]]["uuid"] for row in rejected
                            if 0 <= row.get("index", -1) < len(batch)])
        _log.info("Sent %s, duplicates %s, remaining %d",
                  body.get("stored"), body.get("duplicates"), self.queue.size())

    # ------------------------------------------------------------------
    def heartbeat_loop(self):
        last_config = 0.0
        while not self._stop.is_set():
            body, error = self.client.heartbeat(self.queue.size())
            if not error:
                self.heartbeat_interval = body.get(
                    "heartbeat_interval_s", self.heartbeat_interval)
                self.paused = not body.get("capture_enabled", True)
            if time.time() - last_config > CONFIG_REFRESH_S:
                self.refresh_config()
                last_config = time.time()
            self._stop.wait(self.heartbeat_interval)

    # ------------------------------------------------------------------
    def run(self):
        _log.info("Analitix agent %s starting (source=%s, buffered=%d)",
                  AGENT_VERSION, self.config.get("source", "demo"),
                  self.queue.size())
        self.refresh_config()
        threads = [
            threading.Thread(target=self.capture_loop, name="capture", daemon=True),
            threading.Thread(target=self.send_loop, name="send", daemon=True),
            threading.Thread(target=self.heartbeat_loop, name="beat", daemon=True),
        ]
        for thread in threads:
            thread.start()
        try:
            while not self._stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self, *_args):
        if self._stop.is_set():
            return
        _log.info("Stopping; %d event(s) stay buffered for the next run.",
                  self.queue.size())
        self._stop.set()
        self.source.stop()
        # One last flush, so a planned restart does not sit on a full buffer.
        self._flush_once()


def _encode_vector(vector):
    import struct
    return base64.b64encode(
        struct.pack("<%df" % len(vector), *vector)).decode()


def load_config(path):
    with open(path, "r", encoding="utf-8") as handle:
        if path.endswith((".yaml", ".yml")):
            import yaml
            return yaml.safe_load(handle)
        return json.load(handle)


def main():
    parser = argparse.ArgumentParser(description="Analitix edge agent")
    parser.add_argument("--config", required=True, help="YAML or JSON config file")
    parser.add_argument("--source", choices=["demo", "line"],
                        help="Override the configured source")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    config = load_config(args.config)
    if args.source:
        config["source"] = args.source
    for required in ("odoo_url", "api_key"):
        if not config.get(required):
            sys.exit("Missing '%s' in %s" % (required, args.config))

    agent = Agent(config)
    signal.signal(signal.SIGTERM, agent.stop)
    signal.signal(signal.SIGINT, agent.stop)
    agent.run()


if __name__ == "__main__":
    main()
