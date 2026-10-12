# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Up to 1.0 the jewelry drawings were always on: kiosks that already had the filters keep them.
    cr.execute("UPDATE pos_config SET xb_tf_icons = 'jewelry' WHERE self_ordering_mode = 'kiosk'")
