# -*- coding: utf-8 -*-
{
    "name": "Meeting Links Domain – choose the domain of your calendar links",
    "summary": "Pick the domain Odoo writes into meeting links: videocall URL, "
               "invitation, reminder and update emails, and the accept / "
               "decline pages. One domain for everyone or one per company.",
    "description": """
Meeting Links Domain
====================

Odoo builds every link of a meeting from a single system-wide parameter, the
base URL. If your database serves several brands, or if the domain your staff
uses is not the one you want in front of a customer, the invitation you send
carries the wrong name: the videocall link, the *Accept* and *Decline* buttons
and the reminder all point at a domain that has nothing to do with the meeting.

Changing that parameter is not a real option — it is the same one used by the
portal, by your website links and by any custom development that reads it, so
moving it to fix meetings breaks everything else.

This module separates the two. Meeting links get their own domain, set from
*Settings ▸ Calendar ▸ Meeting Links*, and the rest of Odoo keeps using the
base URL exactly as before.

What it covers
--------------
Every link that points back at a meeting, not only the videocall:

* The **videocall link** of the meeting (Odoo Discuss).
* The **invitation email**, and its *Accept*, *Decline* and *View* buttons.
* The **reminder email** sent before the meeting.
* The **date change**, **update** and **cancellation** emails.
* The **portal pages** those buttons open.

And the videocall page itself: it announces the **name of your company**
instead of the bare *Odoo* Odoo puts there, which is exactly what WhatsApp,
Telegram or Slack show when someone pastes the link into a chat. Each company
can also announce a different name — the brand your customers know rather than
the legal name of the company.

Two ways to set it
------------------
* **One domain for every meeting** — the simplest case: type the domain and
  every meeting in the database uses it.
* **One domain per company** — each company gets its own field, and its
  meetings follow the domain of the company that organises them. Companies
  left empty fall back to the general one.

Leaving it on *Odoo default* makes the module inert: the database behaves
exactly as it did before installing it, which also makes it safe to uninstall.

Meetings that already exist
---------------------------
The link of a meeting is stored when it is created, so a change of setting
only reaches new ones. The settings page has a button that rebuilds the
videocall link of the meetings that have not happened yet. It does **not**
change their access token, so the links you already sent keep working — only
the domain in front of them changes.

Online Appointments
-------------------
If you use Odoo's Online Appointments, a booking keeps the domain of the
website it was booked on — the one the attendee recognises, and the one Odoo
already resolves for that kind of meeting. Only the meetings your team creates
follow the domain configured here.

Technical notes
---------------
* The domain is resolved through ``get_base_url()`` on ``calendar.event`` and
  ``calendar.attendee``, the single point Odoo itself uses to turn the
  relative links of the mail templates into absolute ones. No mail template is
  modified and no field is duplicated, so the module keeps working after an
  Odoo update.
* An empty or malformed domain is ignored instead of being patched up: the
  meeting falls back to the base URL Odoo would have used.
* The domain has to be served by the same Odoo instance — the module chooses
  which name is written in the link, it does not publish a new site.

Compatibility
-------------
* Odoo 19.0 Community and Enterprise.
* Calendar (``calendar``). Online Appointments is supported when installed,
  but not required.
""",
    "author": "Cristofferson Reyes",
    "maintainer": "XUBAX",
    "website": "https://www.xubax.com",
    "support": "soporte@xubax.com",
    "category": "Productivity/Calendar",
    "version": "19.0.1.2.1",
    "license": "OPL-1",
    "price": 29.00,
    "currency": "USD",
    "depends": [
        "calendar",
        "mail",
        "base_setup",
    ],
    "data": [
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": [
        "static/description/banner.png",
    ],
    "application": False,
    "installable": True,
    "auto_install": False,
}
