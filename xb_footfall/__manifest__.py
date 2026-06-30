# -*- coding: utf-8 -*-
{
    "name": "Footfall Analytics (People Counting)",
    "version": "19.0.1.2.1",
    "category": "Point of Sale",
    "summary": "Count store visitors from any sensor (CCTV people-counting or "
               "edge CV) and cross them with POS sales to get the conversion KPI.",
    "description": """
Footfall Analytics — People Counting into Odoo
==============================================
Ingest store-entrance counting events from ANY source through a single,
sensor-agnostic HTTP endpoint, and turn them into retail KPIs.

* Sensor-agnostic: native CCTV people-counting (Hikvision/Dahua ISAPI), a DIY
  edge mini-PC (YOLO + ByteTrack virtual line), or an IR beam counter all post
  the SAME event payload. Odoo never sees an image — only the counter.
* Token-secured ingest controller (one token per device).
* Devices and raw crossing events as first-class models.
* Hourly dashboard (graph/pivot) that LEFT-JOINs POS orders to compute the star
  metric: conversion = tickets / visitors.
* Privacy-first (LFPDPPP): the sensor emits only the count; demographics off.

Sell it as a recurring "Footfall Analytics" subscription line per store.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "company": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "license": "OPL-1",
    "depends": [
        "base",
        "mail",
        "point_of_sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/footfall_store_views.xml",
        "views/footfall_device_views.xml",
        "views/footfall_event_views.xml",
        "views/footfall_hourly_views.xml",
        "views/menus.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "price": 0.00,
    "currency": "USD",
    "installable": True,
    "application": True,
    "auto_install": False,
}
