# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Point past transactions at their catalog product.

    Until this version the POS hook stored only the TAECEL product code, so
    every transaction born of a real sale showed an empty Product cell in the
    back office -- the seeded ones looked fine, which is exactly why it went
    unnoticed. The code is unique per account, so the match is exact; free
    amount carriers keep no product and are left alone.
    """
    cr.execute("""
        UPDATE xb_taecel_transaction t
           SET product_id = p.id
          FROM xb_taecel_product p
         WHERE t.product_id IS NULL
           AND t.product_code IS NOT NULL
           AND t.product_code != ''
           AND p.account_id = t.account_id
           AND p.code = t.product_code
    """)
