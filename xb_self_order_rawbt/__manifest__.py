# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - USB Printer (RawBT)",
    "summary": "The kiosk prints its tickets on its own USB or Bluetooth receipt printer "
               "through the RawBT app (Android), instead of an Epson network printer.",
    "description": """
Self-Order Kiosk - USB Printer (RawBT)
======================================
Many Android kiosks come with a built-in receipt printer on USB, which Odoo cannot
reach: the kiosk only prints on Epson ePOS network printers. With this module the
kiosk sends its tickets, as ESC/POS, to the RawBT app on the same tablet, which
prints them on the printer it is connected to (USB, Bluetooth or network).

Switch it on per kiosk: Point of Sale settings > Mobile self-order & Kiosk >
Kiosk printer through RawBT. A test page prints a sample ticket to check the
paper width and the sending method on the tablet.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["pos_self_order"],
    "data": [
        "views/res_config_settings_views.xml",
        "views/printer_test_templates.xml",
    ],
    "assets": {
        "pos_self_order.assets": [
            "xb_self_order_rawbt/static/lib/xb_rawbt.js",
            "xb_self_order_rawbt/static/src/app/rawbt_printer.js",
        ],
    },
    "application": False,
    "installable": True,
    "auto_install": False,
}
