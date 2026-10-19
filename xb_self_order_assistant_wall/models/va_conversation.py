# -*- coding: utf-8 -*-
from odoo import fields, models

from odoo.addons.xb_showroom_wall.controllers.wall import _may_show
from odoo.addons.xb_showroom_wall_self_order.controllers.kiosk import KIOSK_PAUSE


class XbVaConversation(models.Model):
    _inherit = "xb.va.conversation"

    wall_screen_id = fields.Many2one("xb.showroom.screen", string="Wall", readonly=True, index="btree_not_null")
    wall_text = fields.Text(readonly=True)
    wall_seq = fields.Integer(readonly=True)
    wall_audio_id = fields.Many2one("ir.attachment", readonly=True)

    def _xb_va_extra_tools(self):
        tools = super()._xb_va_extra_tools()
        if self.config_id.sudo()._xb_showroom_kiosk_screen():
            tools.append({
                "name": "mostrar_en_muro",
                "description": "Solo para productos con se_puede_ver_en_muro=true. "
                               "Pone el producto en la pantalla grande (videowall) de la tienda, con las opciones "
                               "elegidas. Con comparar=true lo agrega junto a los que ya están para compararlos. "
                               "Ofrécelo cuando al cliente le guste una pieza: «¿Quieres verla en grande?».",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "producto_id": {"type": "integer"},
                        "opciones": {"type": "array", "items": {"type": "string"}},
                        "comparar": {"type": "boolean"},
                    },
                    "required": ["producto_id"],
                },
            })
        if self.presence == "wall":
            tools.append({
                "name": "regresar_al_kiosco",
                "description": "Regresas de la pantalla grande al kiosco (tu voz vuelve a salir del kiosco).",
                "input_schema": {"type": "object", "properties": {}},
            })
        return tools

    def _xb_va_brief(self, tmpl):
        data = super()._xb_va_brief(tmpl)
        if self.config_id.sudo()._xb_showroom_kiosk_screen():
            # Only these can go to the wall: the seller offers it only for them.
            data["se_puede_ver_en_muro"] = bool(tmpl.xb_showroom_enabled)
        return data

    def _xb_va_wall_push(self, tmpl, options, mode):
        """Puts the piece on the kiosk's wall with the same rules as the kiosk's own button
        (wall enabled for the piece, pause between pieces, comparison limit, shop price)."""
        config = self.config_id.sudo()
        screen = config._xb_showroom_kiosk_screen()
        tmpl = tmpl.sudo()
        if not screen or not config.has_active_session:
            return {"error": "El muro no está disponible desde este kiosco ahorita."}
        if not tmpl.xb_showroom_enabled or not _may_show(screen, tmpl):
            return {"error": "Esta pieza no se puede mostrar en el muro."}
        if mode == "single" and screen.mode == "single":
            last = screen.slot_ids.filtered(lambda s: s.source == "kiosk")[:1]
            if last and (fields.Datetime.now() - last.create_date).total_seconds() < KIOSK_PAUSE:
                return {"error": "Un momento: el muro está mostrando la pieza que se acaba de mandar."}
        product = (tmpl._get_variant_for_combination(options) if options else None) or tmpl.product_variant_id
        # The kiosk's own price (the button's helper needs a website request the seller does not have).
        amount = None if screen.show_price == "none" else (
            self._xb_va_combination_price(tmpl, options) if options else self._xb_va_price(tmpl))
        entry = {"product": product, "options": options, "price": amount,
                 "currency": config.currency_id if amount is not None else None}
        entries = [entry]
        if mode == "compare":
            own = screen.slot_ids.filtered(lambda s: s.source == "kiosk") if screen.mode == "compare" \
                else screen.slot_ids.browse()
            already = own.filtered(lambda s: s.product_id.product_tmpl_id == tmpl)
            entries = [{"product": s.product_id, "options": s.option_ids, "price": s.price,
                        "currency": s.currency_id} for s in own - already] + [entry]
        res = screen.with_context(xb_showroom_source="kiosk")._push_entries(entries, mode=mode)
        return {"ok": True, "message": "Comparando %s piezas en el muro." % res["count"] if mode == "compare"
                else "¡Listo, ya está en el muro!"}

    def _xb_va_run_tool_inner(self, name, args, ui):
        text, error = super()._xb_va_run_tool_inner(name, args, ui)
        config = self.config_id.sudo()
        # The customer wants to see a piece: on the wall too, without waiting to be asked.
        if (name == "abrir_producto" and not error and config.xb_va_auto_wall and self.presence != "phone"
                and config._xb_showroom_kiosk_screen()):
            tmpl = self._xb_va_product(args.get("producto_id"))
            if tmpl and tmpl.sudo().xb_showroom_enabled:
                wall = self._xb_va_tool_mostrar_en_muro({"producto_id": tmpl.id}, ui)
                if not wall.startswith("No se pudo"):
                    self.sudo().went_wall = True
                    text = "%s También la puse en la pantalla grande: díselo al cliente («mírala en grande»). %s" % (
                        text, wall)
        return text, error

    def _xb_va_tool_mostrar_en_muro(self, args, ui):
        tmpl = self._xb_va_product(args.get("producto_id"))
        if not tmpl:
            return "Ese producto no está en este kiosco."
        chosen, _missing = self._xb_va_resolve_options(tmpl, args.get("opciones"))
        result = self._xb_va_wall_push(tmpl, chosen, "compare" if args.get("comparar") else "single")
        if result.get("error"):
            return "No se pudo: %s" % result["error"]
        config = self.config_id.sudo()
        if config.xb_va_follow_wall and self.presence != "wall":
            self.sudo().write({"presence": "wall", "wall_screen_id": config._xb_showroom_kiosk_screen().id})
            ui["actions"].append({"type": "voice_away", "on": True})
            return ("%s Tú también te pasaste a la pantalla grande: ahora el cliente te ve y te oye desde ahí. "
                    "Dile que voltee a verte en la pantalla grande." % (result.get("message") or ""))
        return "%s Dile al cliente que voltee a la pantalla grande." % (result.get("message") or "")

    def _xb_va_tool_regresar_al_kiosco(self, args, ui):
        self.sudo().presence = "kiosk"
        ui["actions"].append({"type": "voice_away", "on": False})
        return "Ya regresaste al kiosco."

    def _xb_va_on_seller_text(self, text):
        """On the wall, the seller says it from there: subtitles and voice for the wall."""
        super()._xb_va_on_seller_text(text)
        if self.presence != "wall" or not self.wall_screen_id or not text:
            return
        conv = self.sudo()
        audio = False
        if conv.config_id.xb_va_speak:
            try:
                data, _new = conv._xb_va_speech(conv.config_id, text)
                audio = self.env["ir.attachment"].sudo().create({
                    "name": "xb_va_wall_%s_%s.mp3" % (conv.id, conv.wall_seq + 1), "raw": data,
                    "res_model": conv._name, "res_id": conv.id, "mimetype": "audio/mpeg"})
                conv.voice_chars += len(text)
            except Exception:  # noqa: BLE001 - without voice the subtitles still show
                audio = False
        old = conv.wall_audio_id
        conv.write({"wall_text": text, "wall_seq": conv.wall_seq + 1, "wall_audio_id": audio.id if audio else False})
        if old:
            old.unlink()
