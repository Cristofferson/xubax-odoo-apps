# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

import pytz
from markupsafe import Markup

from odoo import models
from odoo.tools import plaintext2html

DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class XbVaConversation(models.Model):
    _inherit = "xb.va.conversation"

    def _xb_va_appt_type(self):
        return self.config_id.sudo().xb_va_appointment_type_id

    def _xb_va_tz(self):
        appt = self._xb_va_appt_type()
        return appt.appointment_tz or self.config_id.company_id.partner_id.tz or "America/Mexico_City"

    def _xb_va_extra_tools(self):
        tools = super()._xb_va_extra_tools()
        if self._xb_va_appt_type():
            tools += [{
                "name": "ver_horarios_cita",
                "description": "Horarios libres para una cita en la tienda (%s). Úsala si el cliente quiere venir "
                               "con calma, con su pareja, o si conviene que lo atienda una persona en cita."
                               % self._xb_va_appt_type().name,
                "input_schema": {"type": "object", "properties": {
                    "desde": {"type": "string", "description": "Fecha AAAA-MM-DD desde la que buscar (opcional)."}}},
            }, {
                "name": "agendar_cita",
                "description": "Aparta la cita en un horario libre. Antes confirma con el cliente el horario, su "
                               "nombre y su celular (repíteselo dígito por dígito).",
                "input_schema": {"type": "object", "properties": {
                    "inicio": {"type": "string", "description": "AAAA-MM-DD HH:MM, uno de los horarios libres."},
                    "nombre": {"type": "string"},
                    "telefono": {"type": "string"}},
                    "required": ["inicio", "nombre", "telefono"]},
            }]
        return tools

    def _xb_va_slots(self, since=None, day_only=None):
        """Free slots [(start UTC, staff user)]: few and spread (morning, noon, afternoon), 8 at most."""
        appt = self._xb_va_appt_type()
        tzname = self._xb_va_tz()
        tz = pytz.timezone(tzname)
        reference = max(since or datetime.utcnow(), datetime.utcnow())
        by_day = {}
        for month in appt.sudo()._get_appointment_slots(tzname, reference_date=reference):
            for week in month["weeks"]:
                for day in week:
                    for slot in day.get("slots", []):
                        if not slot.get("staff_user_id"):
                            continue
                        local = tz.localize(datetime.strptime(slot["datetime"], "%Y-%m-%d %H:%M:%S"))
                        by_day.setdefault(local.date(), []).append(
                            (local.astimezone(pytz.utc), self.env["res.users"].browse(slot["staff_user_id"])))
        if day_only:
            return by_day.get(day_only, [])
        picked = []
        for day in sorted(by_day):
            slots = sorted(by_day[day], key=lambda s: s[0])
            picked += [slots[i] for i in sorted({0, len(slots) // 2, len(slots) - 1})]
        return picked[:8]

    def _xb_va_tool_ver_horarios_cita(self, args, ui):
        tz = pytz.timezone(self._xb_va_tz())
        since = None
        if args.get("desde"):
            try:
                since = tz.localize(datetime.strptime(args["desde"][:10], "%Y-%m-%d")).astimezone(pytz.utc).replace(tzinfo=None)
            except ValueError:
                return "La fecha debe ir como AAAA-MM-DD."
        free = self._xb_va_slots(since)
        if not free:
            return "No hay horarios libres en los próximos días; ofrece llamar a una persona."
        return "Horarios libres (%s min): %s" % (
            round(self._xb_va_appt_type().appointment_duration * 60),
            "; ".join("%s (%s)" % (t.astimezone(tz).strftime("%Y-%m-%d %H:%M"), DAYS[t.astimezone(tz).weekday()])
                      for t, _u in free))

    def _xb_va_tool_agendar_cita(self, args, ui):
        appt = self._xb_va_appt_type().sudo()
        tz = pytz.timezone(self._xb_va_tz())
        asked = (args.get("inicio") or "")[:16]
        digits = "".join(c for c in (args.get("telefono") or "") if c.isdigit())
        if len(digits) < 8:
            return "Falta el celular completo del cliente."
        try:
            local = tz.localize(datetime.strptime(asked, "%Y-%m-%d %H:%M"))
        except ValueError:
            return "El horario debe ir como AAAA-MM-DD HH:MM."
        match = [(t, u) for t, u in self._xb_va_slots(day_only=local.date())
                 if t.astimezone(tz).strftime("%Y-%m-%d %H:%M") == asked]
        if not match:
            return "Ese horario ya no está libre; vuelve a consultar ver_horarios_cita."
        start, staff = match[0]
        stop = start + timedelta(hours=appt.appointment_duration)
        start_n, stop_n = start.replace(tzinfo=None), stop.replace(tzinfo=None)
        if self.env["calendar.event"].sudo().search_count([
                ("user_id", "=", staff.id), ("start", "<", stop_n), ("stop", ">", start_n)]):
            return "Ese horario ya no está libre; vuelve a consultar ver_horarios_cita."
        name = (args.get("nombre") or "").strip()[:80] or digits
        partner = self._xb_va_find_partner(args.get("telefono"), name=name)
        self.write({"partner_id": partner.id})
        products = ", ".join(self.product_ids.mapped("name")[:5])
        description = plaintext2html("Agendada por %s en el kiosco %s.\nCelular: %s%s" % (
            self.config_id.xb_va_name, self.config_id.name, args.get("telefono"),
            ("\nLe interesó: %s" % products) if products else ""))
        # The capacity line is required: without it the Appointments app offers the slot again.
        vals = appt._prepare_calendar_event_values(
            1, [{"capacity_reserved": 1, "capacity_used": 1}], Markup(description),
            appt.appointment_duration, False, self.env["appointment.invite"], None, name, partner, staff,
            start_n, stop_n)
        event = self.env["calendar.event"].with_context(
            mail_notify_author=True, mail_create_nolog=True, mail_create_nosubscribe=True,
            allowed_company_ids=staff.company_ids.ids,
        ).sudo().create(vals)
        when = start.astimezone(tz)
        text = "%s %s · %s" % (DAYS[when.weekday()].capitalize(), when.strftime("%d/%m %H:%M"), staff.name)
        ui["actions"].append({"type": "note", "text": "📅 " + text})
        self.message_post(body="Cita apartada desde el kiosco: %s (evento %s)" % (text, event.id))
        return "Cita apartada: %s (%s min). Confírmasela al cliente." % (text, round(appt.appointment_duration * 60))
