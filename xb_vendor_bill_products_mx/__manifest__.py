# -*- coding: utf-8 -*-
{
    "name": "Products from Vendor Bills – CFDI 4.0 (Mexico)",
    "summary": "Brings the product matching, creation, cost policy and image "
               "search of Products from Vendor Bills to the Mexican CFDI 4.0 "
               "XML that vendors send.",
    "description": """
Products from Vendor Bills – CFDI 4.0
=====================================

Odoo's Mexican localisation reads the CFDI 4.0 XML a vendor sends and fills
the vendor bill with it. For the products, it looks for a match on
``NoIdentificacion`` and on the description, and when it finds none the line
is left as plain text.

With this bridge installed, every CFDI line goes through the same treatment as
any other electronic invoice:

* Matched against the code **that vendor** uses for your product, taken from
  the vendor pricelist — not against your internal reference.
* Unknown items proposed for review, or created, according to your setting.
* ``ClaveProdServ`` kept on the proposal, and ``ClaveUnidad`` used to pick the
  unit of measure when the Mexican UNSPSC catalogue is loaded.
* Vendor code learned, cost updated according to your policy, image searched.

The amounts, taxes, withholdings and ``ObjetoImp`` that the localisation
imported are never modified.

Installs itself as soon as both *Products from Vendor Bills* and Odoo's
Mexican localisation (``l10n_mx_edi``) are present.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Accounting/Localizations",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": [
        "xb_vendor_bill_products",
        "l10n_mx_edi",
    ],
    "data": [],
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": True,
}
