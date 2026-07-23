# -*- coding: utf-8 -*-
{
    "name": "Products from Vendor Bills – User Manual (Knowledge)",
    "summary": "Ships the end-user manual for Products from Vendor Bills as a "
               "ready-to-read Knowledge article, in English and Spanish.",
    "description": """
Products from Vendor Bills – User Manual
========================================

Adds a complete, task-oriented **user manual** for *Products from Vendor Bills*
straight into the **Knowledge** app, so your team has it the day the app is
installed — no PDF to hunt for, no wiki to set up.

* A parent article with seven sections: how a bill comes in, reviewing the
  proposed products, the vendor codes, the cost policy, product images,
  configuration and troubleshooting.
* Written for the person doing the work, in plain language, using the exact
  labels they see on screen.
* **Bilingual**: English and Spanish. Each reader sees it in their own Odoo
  language.
* A normal Knowledge article once installed — edit it, add your own house
  rules, share it, print it.

Installs itself automatically when both *Products from Vendor Bills* and the
*Knowledge* app are present. It creates the manual only once; your later edits
are never overwritten.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Accounting/Accounting",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": [
        "xb_vendor_bill_products",
        "knowledge",
    ],
    "data": [],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "post_init_hook": "_xb_vbpk_post_init",
    "application": False,
    "installable": True,
    "auto_install": True,
}
