# -*- coding: utf-8 -*-
from datetime import datetime

import pytz

from odoo.tests import tagged

from odoo.addons.pos_self_order.tests.self_order_common_test import SelfOrderCommonTest


@tagged("post_install", "-at_install")
class TestSellerAppointments(SelfOrderCommonTest):

    def test_offer_and_book(self):
        """The seller lists free times and books one, like a booking from the website."""
        staff = self.env.ref("base.user_admin")
        appt = self.env["appointment.type"].create({
            "name": "Visit the shop", "appointment_tz": "America/Mexico_City", "appointment_duration": 1,
            "schedule_based_on": "users", "staff_user_ids": [(6, 0, staff.ids)], "min_schedule_hours": 1,
            "max_schedule_days": 15,
            "slot_ids": [(0, 0, {"weekday": str(d), "start_hour": 9, "end_hour": 18}) for d in range(1, 8)],
        })
        self.pos_config.write({"self_ordering_mode": "kiosk", "xb_va_enabled": True,
                               "xb_va_appointment_type_id": appt.id})
        conv = self.env["xb.va.conversation"].create({"config_id": self.pos_config.id})
        self.assertIn("agendar_cita", [t["name"] for t in conv._xb_va_tools()])
        text, error = conv._xb_va_run_tool("ver_horarios_cita", {}, conv._xb_va_new_ui())
        self.assertFalse(error, text)
        first = text.split(": ", 1)[1].split(" (")[0]
        ui = conv._xb_va_new_ui()
        text, error = conv._xb_va_run_tool("agendar_cita", {"inicio": first, "nombre": "Ana López",
                                                            "telefono": "999 870 1203"}, ui)
        self.assertFalse(error, text)
        self.assertIn("Cita apartada", text)
        start = pytz.timezone("America/Mexico_City").localize(datetime.strptime(first, "%Y-%m-%d %H:%M"))
        event = self.env["calendar.event"].search([("appointment_type_id", "=", appt.id)])
        self.assertEqual(len(event), 1)
        self.assertEqual(event.start, start.astimezone(pytz.utc).replace(tzinfo=None))
        self.assertEqual(conv.partner_id.name, "Ana López")
        # The same time is not free any more.
        text, _error = conv._xb_va_run_tool("agendar_cita", {"inicio": first, "nombre": "Otro",
                                                             "telefono": "4430000000"}, conv._xb_va_new_ui())
        self.assertIn("ya no está libre", text)
