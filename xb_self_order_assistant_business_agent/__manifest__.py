# -*- coding: utf-8 -*-
{
    "name": "Self-Order Kiosk - Virtual Seller + WhatsApp AI Agent",
    "summary": "One brain for the kiosk and WhatsApp: the virtual seller uses the WhatsApp agent's knowledge "
               "base, and the agent continues on WhatsApp the conversation the customer had at the kiosk.",
    "description": """
Bridge between the kiosk's Virtual Seller and the WhatsApp AI Agent.

* Shop knowledge: in each kiosk choose where the seller's knowledge comes from: only the kiosk
  settings, the WhatsApp agent's knowledge base (WhatsApp > AI Agent > Knowledge Base), or both.
  Write it once and both know it.
* Continuity: when a customer who talked to the kiosk seller writes to your WhatsApp (same mobile
  number, last 3 days), the agent knows that conversation and the products shown, and continues
  it instead of starting again.

Installs by itself when both apps are present.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Point of Sale",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["xb_self_order_assistant", "xb_business_agent"],
    "data": ["views/res_config_settings_views.xml"],
    "installable": True,
    "auto_install": True,
}
