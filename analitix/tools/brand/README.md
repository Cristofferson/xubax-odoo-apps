# Visual identity source

`icons.html` and `banners.html` are the *source* of the published icon and
banner. They are plain HTML and CSS, rendered to PNG with headless Chromium —
no binary design file that only one machine can open, and no dependency on a
font or an asset nobody can find in a year.

Chosen for the listing: **icon A** (the doorway with the counting line across
it — literally what the product measures) and **banner 2** (the floor plan with
its zones, which shows the product instead of describing it).

The other proposals are deliberately left in the files. When somebody asks
"why does it look like this", the alternatives that were considered are the
answer, and regenerating a variant is a two-line edit rather than a redesign.

## Regenerating

```bash
python - <<'PY'
from playwright.sync_api import sync_playwright
base = "file://" + __import__("os").getcwd() + "/"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.goto(base + "icons.html")
    pg.locator("#a").screenshot(path="../../static/description/icon.png")
    pg.goto(base + "banners.html")
    pg.locator("#b2").screenshot(path="../../static/description/banner.png")
    b.close()
PY
```

Sizes are fixed in the CSS: the icon element is 512×512 and each banner is
1200×600, which is what apps.odoo.com expects. Do not scale the output — render
at the target size so the type stays crisp.
