# -*- coding: utf-8 -*-
"""Generate the photorealistic base plates for the listing.

The product overlay — bounding boxes, the virtual line, the counters, the dwell
timer — is composited on top afterwards in HTML, so that half stays accurate to
what Analitix actually does. Only the scene underneath is generated.

No real person appears in any of these: the people are synthetic, which is the
only defensible way to illustrate a face-recognition product on a public page.
"""
import base64
import json
import os
import sys
import urllib.request

KEY = open("/home/ubuntu/.secrets/openai_image.key").read().strip()
OUT = os.path.dirname(os.path.abspath(__file__)) + "/plates"
os.makedirs(OUT, exist_ok=True)

COMMON = (" Photorealistic, shot on a real camera, natural available light, "
          "believable everyday scene, no text, no watermark, no logos, "
          "no graphic overlays, documentary look.")

SCENES = {
    "door": (
        "Overhead security-camera view looking straight down at the entrance "
        "doorway of a small upmarket jewellery boutique. Three shoppers are "
        "walking in through the doorway and one is walking out, seen from "
        "directly above so we mostly see the tops of their heads and shoulders. "
        "Polished stone floor, glass door, warm interior lighting spilling in "
        "from the street. Slight wide-angle lens distortion typical of a "
        "ceiling-mounted camera." + COMMON),
    "zone": (
        "Interior of a small upmarket jewellery shop. A woman in her thirties "
        "stands alone at a glass display counter, leaning slightly forward, "
        "looking down at rings inside the case, clearly waiting. No shop "
        "assistant anywhere near her; the counter behind is empty. Warm "
        "spotlights on the cabinets, quiet mid-afternoon feeling, a sense of "
        "someone who has been standing there a while." + COMMON),
    "face": (
        "View from a small camera mounted at face height beside the entrance of "
        "a jewellery shop, looking at a man in his forties who has just walked "
        "in and is facing the camera direction naturally, mid-stride, not posing "
        "and not looking at the lens. Shop interior softly out of focus behind "
        "him. The framing is plain and functional, like a real security "
        "camera frame rather than a portrait." + COMMON),
    "install": (
        "Back room of a small jewellery shop. On a wooden shelf sits a small "
        "fanless mini computer the size of a paperback, next to a domestic "
        "internet router, with two neat cables running to it. Boxes of stock "
        "and a chair in the background, ordinary working clutter, daylight from "
        "one window. Nothing futuristic, nothing rack-mounted." + COMMON),
    "cameras": (
        "Three security cameras lying side by side on a plain wooden workbench, "
        "photographed from slightly above: on the left an old analogue dome "
        "camera with a coaxial BNC cable and a small USB capture stick beside "
        "it, in the middle a simple USB webcam, on the right a modern white IP "
        "bullet camera with an ethernet cable. Even soft light, product-record "
        "look rather than advertising." + COMMON),
    "blind": (
        "Overhead security-camera view looking down at the entrance area of a "
        "jewellery shop, where most of the frame is blocked by the top of a "
        "tall cardboard promotional display that somebody has left directly "
        "under the camera. Only a thin sliver of floor and doorway is still "
        "visible along one edge. Ordinary shop lighting." + COMMON),
    "floor": (
        "Wide interior view of a small upmarket jewellery shop from a high "
        "corner near the ceiling, showing four separate glass display counters "
        "around the room and the till at the back, with two customers and one "
        "assistant somewhere in the space. Warm cabinet lighting, polished "
        "floor, the whole sales floor visible at once." + COMMON),
    "walkout": (
        "Interior of a small jewellery shop seen from behind the counters. In "
        "the foreground a man in a jacket is walking out through the glass door "
        "empty-handed, no bag, not looking back. Further inside, a shop "
        "assistant is handing a small bag across the counter to a second "
        "customer. Warm light, an ordinary weekday afternoon." + COMMON),
    "frustrated": (
        "A woman in her forties standing at a jewellery shop counter, arms "
        "folded, looking off to one side with a tight, impatient expression, "
        "clearly having waited too long. Nobody is behind the counter in front "
        "of her. Seen from the height and angle of a small camera above the "
        "cabinets." + COMMON),
}


def generate(name, prompt):
    body = json.dumps({
        "model": "gpt-image-2",
        "prompt": prompt,
        "size": "1536x1024",
        "n": 1,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": "Bearer %s" % KEY,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as response:
        payload = json.load(response)
    item = payload["data"][0]
    raw = base64.b64decode(item["b64_json"])
    path = "%s/%s.png" % (OUT, name)
    with open(path, "wb") as fh:
        fh.write(raw)
    print("ok %-6s %d KB" % (name, len(raw) // 1024))


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(SCENES)
    for name in wanted:
        try:
            generate(name, SCENES[name])
        except Exception as error:  # noqa: BLE001
            print("FAIL", name, repr(error)[:300], file=sys.stderr)
