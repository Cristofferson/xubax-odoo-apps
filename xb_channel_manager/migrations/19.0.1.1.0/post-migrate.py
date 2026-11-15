# -*- coding: utf-8 -*-
"""1.1.0: the single «Channex rate plan ID» of each room becomes a line of
the new rate plan table, so rooms keep pushing their rate after the
update."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'xb_cm_listing'
           AND column_name = 'channex_rate_plan_id'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        INSERT INTO xb_cm_rate_plan
               (name, sequence, active, listing_id, channel_id,
                channex_rate_plan_id, percent, amount, min_stay,
                create_uid, write_uid, create_date, write_date)
        SELECT 'Standard', 10, true, l.id, l.channel_id,
               l.channex_rate_plan_id, 0, 0, 0, 1, 1, now(), now()
          FROM xb_cm_listing l
         WHERE coalesce(l.channex_rate_plan_id, '') != ''
           AND NOT EXISTS (SELECT 1 FROM xb_cm_rate_plan p
                            WHERE p.listing_id = l.id)
    """)
