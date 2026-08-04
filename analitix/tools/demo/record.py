# -*- coding: utf-8 -*-
"""Record the three demo scenes straight out of a headless browser."""
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(HERE + "/../../static/description/demo")

# The frame worth freezing for a poster, and how long the scene runs.
SHOT = {"door": 5000, "face": 4200, "zone": 9200}
LENGTH = {"door": 7500, "face": 9000, "zone": 10500}


def record(scene):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=HERE + "/raw",
            record_video_size={"width": 1280, "height": 720})
        page = ctx.new_page()
        page.goto("file://%s/overlay.html?s=%s" % (HERE, scene))
        page.wait_for_timeout(SHOT[scene])
        page.screenshot(path="%s/still_%s.png" % (HERE, scene))
        page.wait_for_timeout(LENGTH[scene] - SHOT[scene])
        video = page.video
        ctx.close()
        target = "%s/how-%s.webm" % (OUT, scene)
        if os.path.exists(target):
            os.remove(target)
        video.save_as(target)
        browser.close()
        print("ok %-5s %d KB" % (scene, os.path.getsize(target) // 1024))


if __name__ == "__main__":
    for name in (sys.argv[1:] or list(SHOT)):
        record(name)
