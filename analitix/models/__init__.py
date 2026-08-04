# -*- coding: utf-8 -*-
# Import order matters for abstract models: Odoo resolves `_inherit` as it loads
# the classes, so a mixin has to exist before anything that inherits it.
# analitix_audit defines analitix.audited.mixin, which analitix_face_signature
# uses, so it comes near the top rather than at the end.
from . import analitix_crypto
from . import analitix_audit
from . import analitix_job
from . import analitix_store
from . import analitix_door
from . import analitix_device
from . import analitix_event
from . import analitix_staff_signature
from . import analitix_face_signature
from . import analitix_demographic
from . import analitix_visit_group
from . import analitix_visitor
from . import analitix_alert
from . import analitix_zone
from . import analitix_poi
from . import analitix_lost_sale
from . import analitix_sale_match
from . import analitix_anomaly
from . import analitix_signage
from . import analitix_watchlist
from . import analitix_customer_context
from . import analitix_attendance
from . import analitix_activation
from . import analitix_subscription
from . import analitix_value_report
from . import analitix_chain
from . import analitix_daily
from . import analitix_hourly
from . import analitix_reports
from . import analitix_chain_report
from . import analitix_demo_floor
from . import res_config_settings
from . import res_users
