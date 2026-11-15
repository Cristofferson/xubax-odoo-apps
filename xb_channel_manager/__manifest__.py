# -*- coding: utf-8 -*-
{
    'name': 'Hotel OTA Channel Manager (Airbnb, Booking.com, Expedia)',
    'summary': 'Channel manager for hotels and rentals: Airbnb, Booking.com, '
               'Expedia by iCal and Channex. Gestor de canales para hoteles y '
               'alquileres: reservas, disponibilidad, tarifas y temporadas.',
    'description': """
Hotel OTA Channel Manager
=========================
Connect Odoo Sales (Community or Enterprise), Rental and the Hotel
industry with the main hospitality platforms (OTAs):

* Universal **iCal two-way sync** (Airbnb, Booking.com, Vrbo and any
  platform supporting calendar import/export).
* **Channex.io driver**: real-time API availability & rate push plus
  reservation webhooks for Booking.com, Expedia, Airbnb, Agoda and 100+
  channels through a single connection.
* Reservation inbox with automatic Sales Order creation, room assignment
  and native availability blocking (Sales, Rental, Hotel industry).
* Works with Odoo Community: the stays are sale order lines with check-in
  and check-out dates. With the Rental app, the free
  *xb_channel_manager_renting* bridge installs itself.
* Overbooking guard, cancellation handling, full sync log.
""",
    'category': 'Sales/Sales',
    'version': '19.0.1.2.0',
    'author': 'XUBAX',
    'website': 'https://xubax.com',
    'license': 'OPL-1',
    'price': 249.00,
    'currency': 'USD',
    'support': 'cristofferson28@gmail.com',
    'depends': [
        'sale',
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
        'views/cm_season_views.xml',
        'views/menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'application': True,
    'installable': True,
}
