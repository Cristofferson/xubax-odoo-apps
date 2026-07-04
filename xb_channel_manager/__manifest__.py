# -*- coding: utf-8 -*-
{
    'name': 'Hotel OTA Channel Manager (Airbnb, Booking.com, Expedia)',
    'summary': 'Sync rooms, availability, rates and reservations with OTA '
               'platforms: universal iCal (Airbnb, Booking.com, Vrbo) and '
               'Channex API (Booking.com, Expedia, Airbnb and 100+ channels).',
    'description': """
Hotel OTA Channel Manager
=========================
Connect the Odoo Hotel / Rental booking flow with the main hospitality
platforms (OTAs):

* Universal **iCal two-way sync** (Airbnb, Booking.com, Vrbo and any
  platform supporting calendar import/export).
* **Channex.io driver**: real-time API availability & rate push plus
  reservation webhooks for Booking.com, Expedia, Airbnb, Agoda and 100+
  channels through a single connection.
* Reservation inbox with automatic Sales Order creation, room assignment
  and native availability blocking (Hotel industry / Rental).
* Overbooking guard, cancellation handling, full sync log.
""",
    'category': 'Sales/Rental',
    'version': '19.0.1.0.0',
    'author': 'Cristofferson Reyes Rodriguez',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'price': 249.00,
    'currency': 'USD',
    'support': 'cristofferson28@gmail.com',
    'depends': [
        'sale_renting',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/cm_channel_views.xml',
        'views/cm_listing_views.xml',
        'views/cm_reservation_views.xml',
        'views/cm_log_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
}
