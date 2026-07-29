# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Fill in the bill-payments reference for accounts that predate it.

    The field turned into a stored computed one, and Odoo does not recompute
    existing rows when a plain column becomes computed -- so every account
    already in the database would keep printing a deposit sheet with the
    services reference missing.

    Same rule as _services_reference: only a well-formed 88 reference yields a
    99 one, because anything else could end up on a sheet somebody deposits
    against.
    """
    cr.execute("""
        UPDATE xb_taecel_account
           SET deposit_reference_services = '99' || substring(btrim(deposit_reference) from 3)
         WHERE deposit_reference_services IS NULL
           AND btrim(deposit_reference) ~ '^88[0-9]+$'
    """)
