#!/usr/bin/env python3
"""Calibration helper for the xb_footfall edge agent.

Grabs ONE frame from the configured RTSP stream and writes a local JPG with a
0..1 normalized grid and the current virtual line drawn on top, so you can pick
the line endpoints for config.yaml (`line: [x1, y1, x2, y2]`).

This is the ONLY part of the edge that ever touches an image, and it is run by
hand during setup — the resulting JPG stays on the device. Delete it afterwards.

    python3 calibrate.py --config config.yaml --out door.jpg
"""
import argparse
import os

import yaml

from counter import DEFAULTS


def load(path):
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path) as fh:
            cfg.update(yaml.safe_load(fh) or {})
    return cfg


def main():
    ap = argparse.ArgumentParser(description="grab a frame and overlay a grid + line")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--out", default="calibrate.jpg")
    args = ap.parse_args()
    cfg = load(args.config)

    import cv2
    src = cfg["rtsp_url"]
    if str(src).isdigit():
        src = int(src)
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise SystemExit("cannot open stream: %s" % cfg["rtsp_url"])
    ok, frame = None, None
    for _ in range(10):                 # skip the first few (often green/garbage)
        ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise SystemExit("could not read a frame")

    h, w = frame.shape[:2]
    # 0.1 grid with normalized labels
    for i in range(1, 10):
        x = int(w * i / 10.0)
        y = int(h * i / 10.0)
        cv2.line(frame, (x, 0), (x, h), (60, 60, 60), 1)
        cv2.line(frame, (0, y), (w, y), (60, 60, 60), 1)
        cv2.putText(frame, "%.1f" % (i / 10.0), (x + 2, 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        cv2.putText(frame, "%.1f" % (i / 10.0), (2, y - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
    # current line from config (green) with in/out hint
    lx = cfg["line"]
    a = (int(lx[0] * w), int(lx[1] * h))
    b = (int(lx[2] * w), int(lx[3] * h))
    cv2.line(frame, a, b, (0, 220, 0), 3)
    cv2.putText(frame, "LINE %s" % lx, (10, h - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 0), 2)

    cv2.imwrite(args.out, frame)
    print("wrote %s (%dx%d). Pick line endpoints as fractions of W,H and set "
          "`line: [x1,y1,x2,y2]` in config.yaml. Place the line across the "
          "doorway, perpendicular to the walking path. If in/out come out "
          "swapped, set `swap_direction: true`." % (args.out, w, h))


if __name__ == "__main__":
    main()
