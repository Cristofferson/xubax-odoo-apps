Meeting Links Domain – choose the domain of your calendar links
===============================================================

Odoo writes every meeting link from one system-wide parameter. This module
gives meeting links a domain of their own, without touching that parameter.

* Author: **Cristofferson Reyes** (XUBAX)
* License: OPL-1
* Compatible with: **Odoo 19.0** Community and Enterprise

The problem
-----------

The videocall link of a meeting, the *Accept* / *Decline* buttons of the
invitation, the reminder and the pages those buttons open are all built from
``web.base.url``. In a database that serves several brands — or when the
domain the staff uses is not the one a customer should see — the invitation
goes out carrying the wrong name.

Moving ``web.base.url`` is not a fix: the portal, the website links and any
custom development that reads it use the very same parameter, so correcting
the meetings breaks the rest.

What this module does
---------------------

Adds a *Meeting Links* section to **Settings ▸ Calendar** where the domain of
calendar links is set independently:

* **Odoo default** – nothing changes, the module is inert.
* **One domain for every meeting** – a single domain for the whole database.
* **One domain per company** – each company has its own field and its meetings
  follow the domain of the company organising them; the empty ones fall back
  to the general domain.

It covers every link that points back at the meeting: the videocall URL, the
invitation, reminder, date-change, update and cancellation emails, the
accept / decline / view buttons and the portal pages they open.

Meetings that already exist
---------------------------

A meeting stores its link when it is created, so a change of setting only
reaches new ones. The settings page has a **Save and update upcoming
meetings** button that rebuilds the videocall link of the meetings still to
come. The access token is left untouched, so invitations already sent keep
working — only the domain changes.

Online Appointments
-------------------

With Odoo's Online Appointments installed, a booking keeps the domain of the
website it was booked on: that is the one the attendee recognises, and the one
Odoo already resolves for that kind of meeting. Only the meetings your team
creates follow the domain configured here.

How it works
------------

The domain is resolved in ``get_base_url()`` on ``calendar.event`` and
``calendar.attendee``. That is the single point Odoo itself goes through:
``calendar`` builds the videocall URL from it, and ``mail`` calls it in
``_render_template_postprocess`` to turn the relative links of the templates
into absolute ones. No mail template is modified and no field is duplicated.

A domain that is empty or not a valid ``http(s)`` address is ignored rather
than patched up, and the meeting falls back to the base URL Odoo would have
used on its own.

Limits
------

The domain has to be served by this same Odoo instance. The module decides
which name is written into the link; it does not publish a new site nor set
up DNS or certificates.

Support
-------

soporte@xubax.com
