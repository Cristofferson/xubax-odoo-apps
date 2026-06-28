#!/usr/bin/env python3
"""Reference 'edge' sender for xb_footfall.

It batches crossing events locally and flushes them to the Odoo ingest
endpoint, tolerating network cuts (events queue until the POST succeeds).
Plug your real source into `read_crossings()`:

  * Hikvision/Dahua: poll ISAPI People Counting or subscribe to its event
    stream and yield (direction, count).
  * DIY edge: run YOLO + ByteTrack over the RTSP, emit a crossing each time a
    track passes the virtual line (sign of the crossing => direction).

No image ever leaves the device — only the count.
"""
import json
import time
import urllib.request

ODOO_URL = "https://anello.diamane.mx/xb_footfall/ingest"
DEVICE_UID = "anello-morelia-puerta1"
TOKEN = "PUT-DEVICE-TOKEN-HERE"
FLUSH_SECONDS = 30

_queue = []
_seq = 0


def read_crossings():
    """Yield (direction, count) tuples from the real sensor. Stub below."""
    # Replace with ISAPI polling or CV line-crossing detection.
    return []


def flush():
    global _queue
    if not _queue:
        return
    body = json.dumps({"device_uid": DEVICE_UID, "events": _queue}).encode()
    req = urllib.request.Request(
        ODOO_URL, data=body, method="POST",
        headers={"Authorization": "Bearer " + TOKEN,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            json.load(resp)
        _queue = []          # only clear on success → survives outages
    except Exception as exc:  # noqa: BLE001
        print("flush failed, will retry:", exc)


def main():
    global _seq
    last = time.monotonic()
    while True:
        for direction, count in read_crossings():
            _seq += 1
            _queue.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                           "direction": direction, "count": count,
                           "seq": _seq})
        if time.monotonic() - last >= FLUSH_SECONDS:
            flush()
            last = time.monotonic()
        time.sleep(1)


if __name__ == "__main__":
    main()
