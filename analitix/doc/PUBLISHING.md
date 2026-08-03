# Publishing Analitix to apps.odoo.com

The store publishes by cloning the repository, so "publishing" is really two
things: making sure the repository is in a state the store can serve, and doing
the parts of the listing that only a human with the account can do.

Everything mechanical is checked by `tools/package.sh`, which builds the archive
and **fails** rather than warns. Everything else is below.

---

## 1. Before you publish — the mechanical checks

```bash
cd analitix
tools/package.sh /tmp
```

It asserts, and exits non-zero on any of them:

* `edge/` **is** in the archive. It used to be excluded, on the reasoning that
  the agent was a separate product; measured, it is 33 KB of Python whose heavy
  libraries are pip requirements on the shop's own machine. Leaving it out sold
  a customer a receiver with nothing to receive — and the manual inside the
  module told them to fetch it from a repository they do not have.
* `tools/` is not in the archive — build machinery is not what a customer
  installs.
* No `__pycache__`, no `.pyc`.
* The manifest declares **no** computer-vision dependency. This addon receives
  JSON and nothing else; an `external_dependencies` entry naming `torch` or
  `insightface` would make it uninstallable on a plain Odoo server *and* would
  be a false statement about where the work happens.
* Every file the listing needs is present: `index.html`, icon, banner, all four
  manuals, the `.pot` and the Spanish catalogues, `CHANGELOG.md`, `doc/API.md`.

## 2. Clean install with demo data, and the full suite

```bash
odoo-bin -d fresh_db -i analitix --with-demo --stop-after-init \
         --test-enable --test-tags=/analitix --workers=0
```

Both matter, and neither substitutes for the other:

* an **upgrade** does not run the demo generators, because they sit in a
  `noupdate` block — only a fresh install proves the demo shop actually builds;
* several tests behave differently with demo data present (the job queue has a
  real backlog ahead of them, the anomaly cron sweeps a real fleet). Running the
  suite only against an empty database hides that.

Expected: **268 passed, 0 failed**, and the demo database opens with two stores
showing today's visitors and a green health badge.

## 3. Translations

```bash
odoo-bin i18n export -c <conf> -d <db> -o analitix/i18n/analitix.pot analitix
python3 tools/i18n/make_es_po.py
```

The generator prints how many of the `.pot`'s entries it translated. That number
must equal the number of entries in the `.pot`. A translation whose `msgid` does
not match is dropped by Odoo **in silence**, so the generator reporting them is
the only warning anyone gets.

## 4. Security review before each release

- [ ] Every model has an `ir.model.access.csv` line, and the watch list is
      readable only by `analitix.group_security`.
- [ ] Every store-scoped model has a **global** record rule. Global, not
      group-attached: "manager of store A" and "may read store B" are unrelated
      statements on a shared instance.
- [ ] `tests/test_isolation.py` passes with two customers on one database.
- [ ] Ingest endpoints require a per-device key, enforce TLS, and are idempotent.
- [ ] The audit log is still append-only for everybody, including the
      administrator.
- [ ] No group is granted to anybody by the module's own data except the two
      administrator accounts on `group_manager` — and `group_security` and
      `group_corporate` to nobody at all. (The demo data grants both to the
      administrator so a reviewer can open the watch list and the chain
      console; that applies only to a database installed `--with-demo`.)

## 5. Screenshots and screencasts

They are captured from the real UI over the module's demo data, so they can be
regenerated whenever the product moves rather than drifting out of date. Do
regenerate them when a screen in them changes — a listing whose screenshots show
last year's interface reads as an abandoned app.

## 6. The listing itself — needs a human with the account

- [ ] **Price and currency.** The manifest carries `price: 499.00` USD. Confirm
      it still matches what the listing form says before submitting — the two
      are set separately and only one of them is in version control.
- [ ] **Icon and banner.** `static/description/icon.png` (512×512) and
      `banner.png` (1200×600).
- [ ] Category **Point of Sale**, Odoo version **19.0**, licence **OPL-1**.
- [ ] Support e-mail and website match the manifest.
- [ ] Upload, then open the published page and click through every video and
      screenshot — the store rewrites relative paths, and a broken asset on the
      listing is the first thing a buyer sees.
- [ ] Record the published URL in the project task's chatter.

## 7. What Odoo's reviewer will look at

Worth checking yourself first, in their order:

1. It installs on a clean Odoo 19 with no manual steps.
2. The description renders — the manifest's RST must be valid, and
   `index.html` must not depend on anything external.
3. No external service is contacted without the user asking for it.
4. Security: ACLs and record rules present and sane.
5. The module does what the listing says it does. The demo data is what lets a
   reviewer confirm that in five minutes without any hardware, which is why it
   is a publication requirement here and not a nicety.
