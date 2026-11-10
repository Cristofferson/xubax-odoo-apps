# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Fill in the bill-payments reference for affiliates that predate it.

    See the twin migration in xb_pos_taecel: a plain column that becomes a
    stored computed field is not recomputed for existing rows, so without this
    every affiliate already registered would print a sheet with half its
    funding details missing.
    """
    cr.execute("""
        UPDATE xb_taecel_affiliate
           SET deposit_reference_services = '99' || substring(btrim(deposit_reference) from 3)
         WHERE deposit_reference_services IS NULL
           AND btrim(deposit_reference) ~ '^88[0-9]+$'
    """)
