# The demo visuals on the listing

`static/description/demo/how-{door,face,zone}.webm` are recorded from
`overlay.html`, which composites the real product overlay — the virtual line,
the tracked boxes and their track ids, the in/out/inside counters, the dwell
timer, the nudge — on top of a photorealistic base plate in `crop/`.

The overlay half is accurate to what the edge agent actually does. The shop
underneath is generated (`gen.py`, OpenAI images) with synthetic people, and
carries an `Illustration` stamp on screen: no real person's face goes on a
public page for a product whose promise is that it never keeps one.

Nine scenes in all: `door`, `face`, `zone` are recorded as video; `install`,
`cameras`, `floor`, `walkout`, `frustrated` and `blind` are stills, because
nothing in them moves and a still loads instantly on a listing page.

To re-record:

    python3 gen.py [scene ...]      # only if the plates need regenerating
    # crop each plate to 1280x720 (16:9) into crop/
    python3 record.py               # the three videos
    # the stills come from overlay.html?s=<scene> screenshotted at its own beat

`plates/`, `grid/` and the check renders are working files and stay out of git.

`tools/` is excluded from the published package by `package.sh`.
