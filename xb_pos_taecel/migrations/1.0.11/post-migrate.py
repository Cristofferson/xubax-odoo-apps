# -*- coding: utf-8 -*-
def migrate(cr, version):
    """Silence the failures that predate the counter warning.

    From this version on, a rejected recharge raises a popup at the register
    that sold it, and it keeps coming back until someone dismisses it. Applied
    to history that would mean every past failure erupting on the next open
    register -- days or weeks late, against orders already refunded by hand,
    and pointing at whichever session happens to be open. Those were handled
    (or missed) by other means; only what fails from now on is actionable.
    """
    cr.execute("""
        UPDATE xb_taecel_transaction
           SET cashier_alert_date = now() AT TIME ZONE 'UTC'
         WHERE state IN ('failed', 'timeout')
           AND cashier_alert_date IS NULL
    """)
