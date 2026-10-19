# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller + Appointments",
    "summary": "The kiosk's virtual seller books appointments: \"Do you want to come on Saturday with your partner?\"",
    "description": """
Bridge between the kiosk's Virtual Seller and Odoo Appointments. Choose an appointment type
per kiosk: the seller offers free times and books the appointment with the customer's name
and mobile, exactly like a booking from the website (calendar, staff, reminders).
Installs by itself when both apps are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "appointment"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": True,
}
