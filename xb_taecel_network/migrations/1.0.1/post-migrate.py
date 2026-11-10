# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Turn the blank account numbers already stored into real NULLs.

    Before 1.0.1 the field was required, so an affiliate registered before
    TAECEL handed over its number went in as an empty string -- and an empty
    string counts as a value for unique(taecel_uid, account_id), so the second
    such affiliate could not be registered at all. Postgres keeps NULLs
    distinct, which is what we want here.
    """
    cr.execute("""
        UPDATE xb_taecel_affiliate
           SET taecel_uid = NULLIF(BTRIM(taecel_uid), '')
         WHERE taecel_uid IS DISTINCT FROM NULLIF(BTRIM(taecel_uid), '')
    """)
