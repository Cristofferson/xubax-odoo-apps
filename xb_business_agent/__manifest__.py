# -*- coding: utf-8 -*-
{
    "name": "WhatsApp AI Agent – answers, leads and appointments",
    "summary": "An AI agent (Claude) answers your business WhatsApp: questions, prices and "
               "hours from your own knowledge base, leads in the CRM and bookings in Appointments.",
    "description": """
WhatsApp AI Agent
=================
Customers write to your WhatsApp at any hour. The agent answers them in their
language, using only what you wrote in its knowledge base (services, prices,
hours, FAQs and rules), so it never makes things up.

* **Leads in the CRM**: when someone shows interest it creates the opportunity
  (native CRM, medium WhatsApp) and assigns it to your team in turns.
* **Bookings in Appointments**: it offers real free slots of the appointment
  types you choose, books them, and can show or cancel the customer's
  upcoming appointments.
* **Reads what customers send**: photos, PDFs (receipts, forms, documents)
  and voice notes (transcribed with OpenAI, optional).
* **Hands over to a person** when it doesn't know, for payments or
  complaints, sensitive matters, or when the customer asks. If someone from
  the team replies in the chat, the agent goes quiet; type ``#agente`` or
  ``#bot`` to hand it back.
* **Rehearsal mode** (on by default): answers are left as internal notes,
  not sent, until you are happy with them.
* **Log with costs**: every reply, the tools it used and its cost in USD.

Needs Odoo Enterprise (WhatsApp and Appointments) and an Anthropic API key.
""",
    "author": "XUBAX",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Productivity/WhatsApp",
    "version": "19.0.1.0.0",
    "license": "OPL-1",
    "depends": ["whatsapp", "crm", "appointment_crm"],
    "external_dependencies": {"python": ["anthropic"]},
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/knowledge_views.xml",
        "views/job_views.xml",
        "views/whatsapp_account_views.xml",
        "views/menus.xml",
    ],
    "images": ["static/description/banner.png"],
    "price": 249.0,
    "currency": "USD",
    "installable": True,
    "application": False,
}
