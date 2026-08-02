# Translation source

`make_es_po.py` rebuilds `i18n/es.po`, `es_419.po` and `es_MX.po` from
`i18n/analitix.pot` plus the dictionaries in `es_batch2.py` … `es_batch8.py`.

As of phase 5 the coverage is complete: every `msgid` in the `.pot` has a
Spanish string. A run that reports fewer entries than the `.pot` holds means a
new or edited string needs a translation, not that the file is fine.

Why a generator rather than editing the `.po` files by hand:

* the three Spanish locales are written from one source, so they cannot drift;
* a translation whose `msgid` does not match the `.pot` **exactly** is dropped
  by Odoo without any message — the generator reports those instead of letting
  them disappear;
* view strings carry the XML's line breaks and indentation inside their
  `msgid`. `BATCH3` is matched on a whitespace-collapsed form so nobody has to
  transcribe indentation by hand.

## Regenerating after changing a string

```bash
odoo-bin i18n export -c <conf> -d <db> analitix     # refresh the .pot
cd addons/analitix && python3 tools/i18n/make_es_po.py
```

`tools/` is excluded from the published apps.odoo.com zip, like `edge/`.
