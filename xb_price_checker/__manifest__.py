{
    "name": "Verificador de precios – Price Checker for Point of Sale",
    "summary": "Verificador de precios para tu tienda: el cliente escanea un producto y ve foto, precio, descuento, "
               "existencias y meses sin intereses. Funciona en cualquier tableta con lector de código de barras. "
               "Price checker kiosk for any tablet with a barcode scanner.",
    "description": """
Price Checker for Point of Sale
===============================

A price checker for the shop floor: the customer scans a product and sees its photo, its price with the
pricelist and taxes of your store, the price before the discount, whether the store has it and the months
without interest it can be paid in.

* Works on any tablet, phone or screen with a barcode scanner that types the code (USB, Bluetooth or built in).
  Open the link of the Point of Sale once and leave it there: no user, no back office.
* Uses the prices of the Point of Sale you choose: its pricelist, its taxes and the stock of its warehouse.
* Stock without numbers: "Available in this store" or "Out of stock".
* Months without interest when the XPago payment rules are installed.
* Goes back to its welcome screen by itself.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "price": 28.00,
    "currency": "USD",
    "depends": ["point_of_sale"],
    "data": [
        "views/price_checker_templates.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "xb_price_checker.assets": [
            "xb_price_checker/static/src/checker/checker.css",
            "xb_price_checker/static/src/checker/checker.js",
        ],
    },
    "images": [
        "static/description/banner.png",
        "static/description/icon.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
