# -*- coding: utf-8 -*-
from odoo import models


class XbVaConversation(models.Model):
    _inherit = "xb.va.conversation"

    def _xb_va_quote_modes(self):
        config = self.config_id.sudo()
        return config._xb_kiosk_quotation_modes() if hasattr(config, "_xb_kiosk_quotation_modes") else {}

    def _xb_va_extra_tools(self):
        tools = super()._xb_va_extra_tools()
        modes = self._xb_va_quote_modes()
        if self.presence != "phone" and (modes.get("print") or modes.get("whatsapp")):
            ways = [w for w, on in (("imprimir", modes.get("print")), ("whatsapp", modes.get("whatsapp"))) if on]
            tools.append({
                "name": "cotizacion_del_carrito",
                "description": "Hace la cotización de lo que el cliente tiene en el carrito: abre la ventana donde "
                               "escribe su nombre y celular, y se la lleva impresa en la impresora del kiosco o en su "
                               "WhatsApp. Antes agrega la pieza con agregar_al_carrito. Formas: %s." % ", ".join(ways),
                "input_schema": {"type": "object", "properties": {
                    "forma": {"type": "string", "enum": ways}}, "required": ["forma"]},
            })
        return tools

    def _xb_va_tool_cotizacion_del_carrito(self, args, ui):
        way = "whatsapp" if args.get("forma") == "whatsapp" else "print"
        ui["actions"].append({"type": "kiosk_quote", "mode": way})
        return ("Se abrió en pantalla la ventana de la cotización: dile que escriba su nombre y celular y toque "
                "el botón; %s." % ("sale impresa en el kiosco" if way == "print" else "le llega a su WhatsApp"))
