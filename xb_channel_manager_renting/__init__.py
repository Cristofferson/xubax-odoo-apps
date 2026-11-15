# -*- coding: utf-8 -*-
import logging

import pytz

from . import models

_logger = logging.getLogger(__name__)


def _post_init_stay_dates(env):
    """OTA orders created before the bridge existed (Channel Manager
    1.1 and older required Rental): give their lines the check-in /
    check-out dates, in the property's local time."""
    engine = env["xb.cm.engine"]
    lines = env["sale.order.line"].search([
        ("order_id.cm_reservation_id", "!=", False),
        ("start_date", "!=", False),
        ("return_date", "!=", False),
        ("cm_checkin", "=", False),
    ])
    done = 0
    for line in lines:
        tz = engine._property_tz(line.order_id.company_id)
        checkin = pytz.utc.localize(line.start_date).astimezone(tz).date()
        checkout = pytz.utc.localize(line.return_date).astimezone(tz).date()
        if checkout > checkin:
            line.write({"cm_checkin": checkin, "cm_checkout": checkout})
            done += 1
    _logger.info("Channel Manager rental bridge: stay dates set on %s "
                 "lines", done)
