# -*- coding: utf-8 -*-
"""Post-migration for v19.0.1.6.3.

Two clean-ups:

1. ``res_partner.xibo_show_in_public_screens`` left on NULL.
   The field defaults to True, but rows that were never touched by the ORM
   after the column appeared kept NULL — and NULL reads as False in Python.
   The effect was silent and confusing: those customers got the anonymous
   "valued customer" greeting on the screen even though their name was
   right there on the ticket. NULL means "never decided", so it must
   behave like the default (visible). Rows explicitly set to False are
   deliberate opt-outs and are left alone.

2. ``xibo_display`` screen geometry starts empty.
   The new columns are filled on the next sync with the CMS; nothing to do
   here beyond logging, since ``_layout_geometry()`` resolves lazily when
   a layout is built before that sync happens.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        "UPDATE res_partner SET xibo_show_in_public_screens = TRUE "
        "WHERE xibo_show_in_public_screens IS NULL"
    )
    _logger.info(
        "[XIBO MIGRATION 19.0.1.6.3] %s contact(s) had no public-screen "
        "preference and were set to visible (the field default)",
        cr.rowcount,
    )
