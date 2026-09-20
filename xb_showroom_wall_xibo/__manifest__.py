# -*- coding: utf-8 -*-
{
    'name': 'Showroom Wall — Xibo',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Publish the showroom wall on a Xibo screen in one click, as '
               'its default layout or only while pieces are being shown.',
    'description': """
Showroom Wall — Xibo
====================

Bridge between *Showroom Wall* and the Xibo connector. The wall itself is a
plain web page and works on any screen; this module saves the manual Xibo
setup when the screen is driven by Xibo:

* Pick the branch (point of sale) and its Xibo screen on the showroom screen,
  press **Publish on the videowall**, and the layout is built on the canvas
  of that screen (a 5760x1080 videowall gets the whole surface).
* **Always on screen** — the wall becomes the screen's default layout. The
  layout it replaces is remembered, and **Remove from the videowall** puts it
  back. Instant, and it does not depend on the player's live channel.
* **Only while pieces are shown** — the screen keeps its own default layout;
  the wall takes over when a sales person sends a piece and hands the screen
  back when the wall is cleared or left idle. A purchase thank-you always
  wins over the wall.
""",
    'author': 'Cristofferson Reyes Rodriguez',
    'website': 'https://www.xubax.com',
    'license': 'OPL-1',
    'depends': ['xb_showroom_wall', 'xibo_connector_pos'],
    'data': [
        'views/showroom_screen_views.xml',
    ],
    'installable': True,
    'auto_install': True,
    'application': False,
}
