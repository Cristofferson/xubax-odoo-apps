#!/usr/bin/env python3
"""xb_footfall edge CV agent — RTSP → YOLOv11 + ByteTrack → virtual line → ingest.

Pulls one RTSP stream (a door channel re-emitted by a DVR, or an IP/USB camera),
detects people, tracks them, and counts each time a track crosses a virtual line.
Each crossing becomes one `{direction, count}` event, batched and POSTed to the
Odoo endpoint `/xb_footfall/ingest` with a per-device Bearer token.

Privacy by design: no image, no frame and no face ever leaves the device — only
the count. Frames are decoded in memory and discarded; nothing is written to disk
(the only exception is the separate `calibrate.py`, run by hand during setup).

Config comes from a YAML file (see config.example.yaml); any key can be overridden
by an env var `XBF_<KEY>` (e.g. XBF_TOKEN, XBF_RTSP_URL). Run:

    python3 counter.py --config config.yaml
"""
import argparse
import json
import logging
import os
import signal
import sys
import time
import urllib.request

import yaml

_log = logging.getLogger("xbf.edge")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULTS = {
    "rtsp_url": "",                 # rtsp://user:pass@dvr-ip:554/...  (or 0 for USB cam)
    "odoo_url": "",                 # https://<client>.diamane.mx/xb_footfall/ingest
    "device_uid": "store-door1",    # informational; auth is by token
    "token": "",                    # per-device Bearer token from Odoo
    "line": [0.5, 0.0, 0.5, 1.0],   # x1,y1,x2,y2 normalized 0..1 (default: vertical center)
    "swap_direction": False,        # flip which side counts as "in"
    "model": "yolo11n.pt",          # ultralytics weights (n=nano, fastest on CPU)
    "imgsz": 640,
    "conf": 0.35,
    "tracker": "bytetrack.yaml",
    "classes": [0],                 # COCO class 0 = person
    "target_fps": 6,                # process at most N frames/sec (skip the rest)
    "flush_seconds": 30,            # how often to POST the queued events
    "reconnect_seconds": 5,         # backoff when the RTSP stream drops
    "log_level": "INFO",
    "device": "cpu",                # "cpu" or "0" for a CUDA gpu (Jetson)
}


def load_config(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path) as fh:
            cfg.update({k: v for k, v in (yaml.safe_load(fh) or {}).items()})
    # env overrides: XBF_<UPPER_KEY>
    for key in cfg:
        env = os.environ.get("XBF_" + key.upper())
        if env is None:
            continue
        default = DEFAULTS[key]
        if isinstance(default, bool):
            cfg[key] = env.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(default, list):
            cfg[key] = json.loads(env)
        elif isinstance(default, int):
            cfg[key] = int(env)
        elif isinstance(default, float):
            cfg[key] = float(env)
        else:
            cfg[key] = env
    missing = [k for k in ("rtsp_url", "odoo_url", "token") if not cfg[k]]
    if missing:
        raise SystemExit("config error: missing required keys: " + ", ".join(missing))
    return cfg


# ---------------------------------------------------------------------------
# Geometry — segment-vs-segment crossing
# ---------------------------------------------------------------------------
def _side(p, a, b):
    """Signed area: >0 on one side of line a->b, <0 on the other, 0 on it."""
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def _crosses(p0, p1, a, b):
    """True iff the movement segment p0->p1 intersects the door segment a->b."""
    d1, d2 = _side(p0, a, b), _side(p1, a, b)
    d3, d4 = _side(a, p0, p1), _side(b, p0, p1)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


class LineCounter:
    """Counts a crossing once per track, with the direction from which side the
    track started on. `line` is in pixel coords for the current frame size."""

    def __init__(self, line_px, swap=False, ttl_frames=90):
        self.a = (line_px[0], line_px[1])
        self.b = (line_px[2], line_px[3])
        self.swap = swap
        self.ttl = ttl_frames
        self.last = {}        # track_id -> (centroid, frames_since_seen-as-age)

    def update(self, tracks, frame_idx):
        """tracks: list of (track_id, cx, cy). Returns list of "in"/"out"."""
        out = []
        seen = set()
        for tid, cx, cy in tracks:
            seen.add(tid)
            now = (cx, cy)
            prev = self.last.get(tid)
            if prev is not None and _crosses(prev[0], now, self.a, self.b):
                # side of the *previous* point decides the direction
                forward = _side(prev[0], self.a, self.b) < 0
                if self.swap:
                    forward = not forward
                out.append("in" if forward else "out")
            self.last[tid] = (now, frame_idx)
        # forget stale tracks so memory stays bounded
        for tid in [t for t, v in self.last.items()
                    if t not in seen and frame_idx - v[1] > self.ttl]:
            del self.last[tid]
        return out


# ---------------------------------------------------------------------------
# Poster — batch + survive network outages (events queue until POST succeeds)
# ---------------------------------------------------------------------------
class Poster:
    def __init__(self, url, token, device_uid):
        self.url = url
        self.token = token
        self.device_uid = device_uid
        self.queue = []
        self.seq = 0

    def add(self, direction):
        self.seq += 1
        self.queue.append({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "direction": direction,
            "count": 1,
            "seq": self.seq,
        })

    def flush(self):
        if not self.queue:
            return
        body = json.dumps({
            "device_uid": self.device_uid,
            "events": self.queue,
        }).encode()
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json",
                     # Identify with a real UA: the default "Python-urllib/x"
                     # is blocked by Cloudflare-fronted Odoo sites (403).
                     "User-Agent": "xb-footfall-edge/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                json.load(resp)
            _log.info("flushed %d events", len(self.queue))
            self.queue = []          # only clear on success → survives outages
        except Exception as exc:     # noqa: BLE001
            _log.warning("flush failed (%d queued), will retry: %s",
                         len(self.queue), exc)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run(cfg):
    # Prefer RTSP over TCP: many DVRs drop frames on the default UDP transport,
    # which shows up as repeated "stream read failed, reconnecting". Set before
    # the first VideoCapture so FFmpeg picks it up. A user env override wins.
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

    # Heavy imports deferred so --help and config errors are instant.
    import cv2
    from ultralytics import YOLO

    model = YOLO(cfg["model"])
    poster = Poster(cfg["odoo_url"], cfg["token"], cfg["device_uid"])

    stop = {"flag": False}
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.update(flag=True))

    src = cfg["rtsp_url"]
    if str(src).isdigit():
        src = int(src)            # USB camera index
    min_dt = 1.0 / max(cfg["target_fps"], 1)
    last_flush = time.monotonic()

    while not stop["flag"]:
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            _log.warning("cannot open stream, retrying in %ss", cfg["reconnect_seconds"])
            time.sleep(cfg["reconnect_seconds"])
            continue
        _log.info("stream open: %s", cfg["device_uid"])
        counter = None
        frame_idx = 0
        last_proc = 0.0
        last_dbg = 0.0
        while not stop["flag"]:
            ok, frame = cap.read()
            if not ok:
                _log.warning("stream read failed, reconnecting")
                break
            now = time.monotonic()
            if now - last_proc < min_dt:      # throttle to target_fps
                continue
            last_proc = now
            frame_idx += 1

            if counter is None:               # build line once we know the frame size
                h, w = frame.shape[:2]
                lx = cfg["line"]
                line_px = (lx[0] * w, lx[1] * h, lx[2] * w, lx[3] * h)
                counter = LineCounter(line_px, swap=cfg["swap_direction"])
                _log.info("frame %dx%d, line=%s", w, h, [round(v) for v in line_px])

            res = model.track(frame, persist=True, classes=cfg["classes"],
                              conf=cfg["conf"], imgsz=cfg["imgsz"],
                              tracker=cfg["tracker"], device=cfg["device"],
                              verbose=False)[0]
            tracks = []
            if res.boxes is not None and res.boxes.id is not None:
                ids = res.boxes.id.int().tolist()
                xyxy = res.boxes.xyxy.tolist()
                for tid, (x1, y1, x2, y2) in zip(ids, xyxy):
                    tracks.append((tid, (x1 + x2) / 2.0, (y1 + y2) / 2.0))

            # Detection heartbeat: only logs when someone is in frame, so a walk
            # that produces no "crossing" can be told apart from no detection.
            ndet = len(res.boxes) if res.boxes is not None else 0
            if ndet and now - last_dbg >= 3.0:
                _log.info("detectando %d persona(s) en cuadro (con seguimiento=%d)",
                          ndet, len(tracks))
                last_dbg = now

            for direction in counter.update(tracks, frame_idx):
                poster.add(direction)
                _log.info("crossing: %s (queued=%d)", direction, len(poster.queue))

            if time.monotonic() - last_flush >= cfg["flush_seconds"]:
                poster.flush()
                last_flush = time.monotonic()

        cap.release()
        if not stop["flag"]:
            time.sleep(cfg["reconnect_seconds"])

    poster.flush()           # best-effort drain on shutdown
    _log.info("stopped")


def main():
    ap = argparse.ArgumentParser(description="xb_footfall edge CV counter")
    ap.add_argument("--config", default=os.environ.get("XBF_CONFIG", "config.yaml"))
    args = ap.parse_args()
    cfg = load_config(args.config)
    logging.basicConfig(
        level=getattr(logging, cfg["log_level"].upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    _log.info("xb_footfall edge starting: device=%s model=%s",
              cfg["device_uid"], cfg["model"])
    run(cfg)


if __name__ == "__main__":
    main()
