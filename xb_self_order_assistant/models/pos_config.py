# -*- coding: utf-8 -*-
import hashlib
import hmac
import logging
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

XB_VA_MODELS = [
    ("claude-haiku-5-5", "Fast and cheap (Claude Haiku)"),
    ("claude-sonnet-5-5", "Balanced (Claude Sonnet)"),
    ("claude-opus-5-5", "Best answers, slower (Claude Opus)"),
]


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_va_enabled = fields.Boolean("Virtual seller")
    xb_va_name = fields.Char("Seller name", default="Sofía")
    xb_va_name_say = fields.Char(
        "How to say the name", help="Only for the voice, when the name is written in a special way "
        "(e.g. AnelIA is said Anelia).")
    xb_va_gender = fields.Selection(
        [("female", "Woman"), ("male", "Man")], string="Seller is a", default="female")
    xb_va_voice_id = fields.Many2one(
        "xb.va.voice", string="Voice", domain="[('gender', '=', xb_va_gender)]",
        default=lambda self: self.env.ref("xb_self_order_assistant.voice_nova", raise_if_not_found=False))
    xb_va_avatar_id = fields.Many2one(
        "xb.va.avatar", string="Avatar", domain="[('gender', '=', xb_va_gender)]",
        help="The face of the seller. Empty = a round light.")
    xb_va_start_full = fields.Boolean(
        "Start full screen", default=True,
        help="The seller fills the screen when the customer opens it, like talking to a person.")
    xb_va_position = fields.Selection([("right", "Bottom right"), ("left", "Bottom left")],
                                      string="Button position", default="right")
    xb_va_continuous = fields.Boolean(
        "Hands-free conversation", default=True,
        help="After speaking, the seller listens again by itself: the customer just talks.")
    xb_va_scan = fields.Boolean(
        "Reads cards and barcodes", default=True,
        help="When the customer brings a card (NFC) or a barcode to the kiosk reader, the seller "
             "recognizes the product and talks about it.")
    xb_va_speak = fields.Boolean("Speaks its answers", default=True)
    xb_va_listen = fields.Boolean("Listens (microphone)", default=True)
    xb_va_voice_style = fields.Char(
        "Way of speaking", default="Warm and friendly, calm pace, Mexican Spanish accent.",
        help="How the voice sounds: accent, pace, mood.")
    xb_va_button = fields.Char("Button text", translate=True)
    xb_va_greeting = fields.Char("Greeting", translate=True)
    xb_va_knowledge = fields.Text(
        "What it knows about your shop",
        help="Delivery times, sizes, warranties, payment methods, hours, policies... "
             "The seller only states what is written here or in the product data.")
    xb_va_sales_style = fields.Selection([
        ("consultative", "Consultative: advises, never pushes"),
        ("balanced", "Balanced: advises and proposes the next step"),
        ("assertive", "Sales-driven: shows, highlights and closes"),
    ], string="Way of selling", default="balanced", required=True)
    xb_va_instructions = fields.Text(
        "Extra rules", help="E.g. 'Always offer the engraving', 'Never talk about discounts'.")
    xb_va_model = fields.Selection(XB_VA_MODELS, string="Intelligence", default="claude-sonnet-5-5")
    xb_va_engine = fields.Selection([
        ("classic", "Step by step (listens, thinks, answers)"),
        ("realtime", "Instant conversation (live voice)"),
    ], string="Conversation", default="classic", required=True,
        help="Instant: answers in about a second and can be interrupted, like a person (OpenAI Realtime). "
             "Step by step: waits until the customer finishes, then thinks and answers.")
    xb_va_rt_model = fields.Selection([
        ("gpt-realtime-2.1-mini", "Live voice, fast and cheap"),
        ("gpt-realtime-2.1", "Live voice, best answers"),
    ], string="Live voice model", default="gpt-realtime-2.1")
    xb_va_rt_voice = fields.Selection([
        ("tts", "Voice with adjustable accent (recommended for Spanish)"),
        ("live", "The live model's own voice (fastest, can be interrupted)"),
    ], string="Voice in instant conversation", default="tts", required=True,
        help="The live model's own voice keeps an English accent in other languages. With the adjustable "
             "voice the seller still listens and thinks live, and speaks with the chosen voice and accent.")
    xb_va_handoff_label = fields.Char("Call a person: button text", translate=True)
    xb_va_ho_discuss = fields.Boolean("Chat in Odoo", default=True)
    xb_va_ho_pos = fields.Boolean("Alert on the cash registers", default=True)
    xb_va_ho_email = fields.Boolean("E-mail")
    xb_va_ho_user_ids = fields.Many2many(
        "res.users", "xb_va_pos_config_handoff_user_rel", "config_id", "user_id",
        string="People who attend", domain="[('share', '=', False)]")
    xb_va_ho_pos_ids = fields.Many2many(
        "pos.config", "xb_va_pos_config_handoff_pos_rel", "config_id", "target_id",
        string="Cash registers that get the alert",
        domain="[('id', '!=', id), ('self_ordering_mode', '!=', 'kiosk')]",
        help="Empty = every cash register of the company.")
    xb_va_tap_url = fields.Char(
        "Link for the kiosk's NFC sticker", compute="_compute_xb_va_tap_url",
        help="Write it on an NFC sticker on the kiosk (e.g. with the free app NFC Tools): when the customer "
             "brings their phone close, the seller moves to their phone with the whole conversation.")
    xb_va_greet = fields.Selection([
        ("off", "Does not greet"),
        ("voice", "Greets out loud and waves"),
        ("open", "Opens full screen and starts talking"),
    ], string="When someone comes close", default="voice", required=True,
        help="Uses the kiosk camera (Analitix if it is installed, else a simple movement detector; no "
             "picture is kept) to notice someone standing in front of the kiosk.")
    xb_va_greet_text = fields.Char("Greeting when someone comes close", translate=True)
    xb_va_weekly_report = fields.Boolean(
        "Weekly summary by e-mail", default=True,
        help="Every Monday the people who attend get the week's numbers: conversations, sales, "
             "what customers asked for and what the shop did not have.")
    xb_va_idle_seconds = fields.Integer("Restart after (seconds without use)", default=90)
    xb_va_daily_limit = fields.Float(
        "Daily spending limit (USD)", default=5.0,
        help="When reached, the button hides until the next day. 0 = no limit.")

    def _xb_va_tap_token(self):
        self.ensure_one()
        self._ensure_access_token()
        return hmac.new(self.sudo().access_token.encode(), b"xb-va-tap", hashlib.sha256).hexdigest()[:24]

    def _compute_xb_va_tap_url(self):
        for config in self:
            config.xb_va_tap_url = config.id and config.xb_va_enabled and "%s/xb-va/k/%s/%s" % (
                config.get_base_url(), config.id, config._xb_va_tap_token())

    @api.onchange("xb_va_gender")
    def _onchange_xb_va_gender(self):
        if self.xb_va_voice_id.gender != self.xb_va_gender:
            self.xb_va_voice_id = self.env["xb.va.voice"].search([("gender", "=", self.xb_va_gender)], limit=1)
        if self.xb_va_avatar_id and self.xb_va_avatar_id.gender != self.xb_va_gender:
            self.xb_va_avatar_id = self.env["xb.va.avatar"].search([("gender", "=", self.xb_va_gender)], limit=1)

    def _xb_va_knowledge_text(self):
        """What the seller knows about the shop. Other apps (WhatsApp agent) can add theirs."""
        self.ensure_one()
        return (self.xb_va_knowledge or "").strip()

    # ------------------------------------------------------------------ kiosk payload
    def _xb_va_default(self, key):
        if key == "button":
            return _("Can I help you?")
        if key == "greeting":
            return _("Hi, I'm %s. What are you looking for today?") % (self.xb_va_name or "Sofía")
        return _("Call a person from the shop")

    def _xb_va_settings(self):
        self.ensure_one()
        if not self.xb_va_enabled:
            return False
        return {
            "name": self.xb_va_name or "Sofía",
            "gender": self.xb_va_gender or "female",
            "speak": self.xb_va_speak,
            "listen": self.xb_va_listen,
            "button": self.xb_va_button or self._xb_va_default("button"),
            "greeting": self.xb_va_greeting or self._xb_va_default("greeting"),
            "handoff": self.xb_va_handoff_label or self._xb_va_default("handoff"),
            "idle": max(self.xb_va_idle_seconds or 90, 20),
            "avatar": self.xb_va_avatar_id._xb_va_payload() if self.xb_va_avatar_id else False,
            "start_full": self.xb_va_start_full,
            "engine": self.xb_va_engine or "classic",
            "rt_voice": self.xb_va_rt_voice or "tts",
            "scan": self.xb_va_scan,
            "greet": self.xb_va_greet or "off",
            "greet_text": self.xb_va_greet_text or _(
                "Hi! I'm %s. Can I help you find something special?") % (self.xb_va_name or "Sofía"),
            "share": self.env["xb.va.conversation"]._xb_va_share_channels(self),
            "position": self.xb_va_position or "right",
            "continuous": self.xb_va_continuous and self.xb_va_listen,
            "available": not self._xb_va_over_budget(),
        }

    def _load_pos_self_data_read(self, records, config):
        read_records = super()._load_pos_self_data_read(records, config)
        if read_records:
            read_records[0]["_xb_va"] = config.sudo()._xb_va_settings()
        return read_records

    def _xb_va_over_budget(self):
        if not self.xb_va_daily_limit:
            return False
        today = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        spent = sum(self.env["xb.va.conversation"].sudo().search([
            ("config_id", "=", self.id), ("create_date", ">=", today)]).mapped("cost_usd"))
        return spent >= self.xb_va_daily_limit

    # ------------------------------------------------------------------ calling a person
    def _xb_va_handoff(self, conversation, summary):
        """Tell the shop's people that a customer at this kiosk wants a person."""
        self.ensure_one()
        config = self.sudo()
        title = _("Customer at the kiosk %s asks for a person") % config.name
        products = conversation.product_ids.mapped("name")
        lines = [summary or _("No summary.")]
        if products:
            lines.append(_("Products shown: %s") % ", ".join(products[:6]))
        done = []
        if config.xb_va_ho_discuss and config.xb_va_ho_user_ids:
            channel = config._xb_va_handoff_channel()
            body = Markup("<b>%s</b><br/>%s") % (title, Markup("<br/>").join(escape(l) for l in lines))
            channel.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_comment",
                                 author_id=self.env.ref("base.partner_root").id)
            done.append("discuss")
        if config.xb_va_ho_pos:
            targets = config.xb_va_ho_pos_ids or self.search([
                ("company_id", "=", config.company_id.id), ("self_ordering_mode", "!=", "kiosk"),
                ("id", "!=", config.id)])
            payload = {"title": title, "body": "\n".join(lines), "kiosk": config.name}
            for target in targets.filtered("current_session_id"):
                target._notify("XB_VA_HANDOFF", payload)
                done.append("pos:%s" % target.id)
        if config.xb_va_ho_email:
            emails = [u.email for u in config.xb_va_ho_user_ids if u.email]
            if emails:
                self.env["mail.mail"].sudo().create({
                    "subject": title,
                    "body_html": Markup("<p>%s</p>") % Markup("<br/>").join(escape(l) for l in lines),
                    "email_to": ",".join(emails),
                    "email_from": config.company_id.email_formatted or self.env.user.email_formatted,
                    "auto_delete": True,
                }).send()
                done.append("email")
        _logger.info("xb_va handoff kiosk %s conversation %s -> %s", config.id, conversation.id, done)
        return done

    def _xb_va_handoff_channel(self):
        self.ensure_one()
        Channel = self.env["discuss.channel"].sudo()
        name = _("Virtual seller · %s") % self.name
        channel = Channel.search([("xb_va_config_id", "=", self.id)], limit=1)
        if not channel:
            channel = Channel.create({"name": name, "channel_type": "group", "xb_va_config_id": self.id})
        partners = self.xb_va_ho_user_ids.partner_id
        missing = partners - channel.channel_member_ids.partner_id
        if missing:
            channel._add_members(partners=missing)
        return channel


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    xb_va_config_id = fields.Many2one("pos.config", index="btree_not_null", ondelete="set null")


class PosConfigWeekly(models.Model):
    _inherit = "pos.config"

    def _xb_va_week_numbers(self, since):
        self.ensure_one()
        convs = self.env["xb.va.conversation"].sudo().search([
            ("config_id", "=", self.id), ("create_date", ">=", since), ("turns", ">", 0)])
        searches = self.env["xb.va.search"].sudo().search([("config_id", "=", self.id), ("create_date", ">=", since)])
        counts = {}
        for search in searches.filtered(lambda s: not s.found):
            key = search.text.strip().lower()
            counts[key] = counts.get(key, 0) + 1
        wanted = {}
        for conv in convs:
            for tmpl in conv.product_ids:
                wanted[tmpl.name] = wanted.get(tmpl.name, 0) + 1
        sold = convs.filtered("converted")
        return {
            "conversations": len(convs),
            "questions": sum(convs.mapped("turns")),
            "with_products": len(convs.filtered("product_ids")),
            "cart": len(convs.filtered("cart_added")),
            "sales": len(sold),
            "sales_amount": sum(sold.mapped("sale_amount")),
            "appointments": len(convs.filtered("appointment")),
            "phone": len(convs.filtered("went_phone")),
            "whatsapp": len(convs.filtered("shared")),
            "person": len(convs.filtered("handoff")),
            "cost": sum(convs.mapped("cost_usd")),
            "missing": sorted(counts.items(), key=lambda kv: -kv[1])[:8],
            "top": sorted(wanted.items(), key=lambda kv: -kv[1])[:8],
        }

    @api.model
    def _cron_xb_va_weekly_digest(self):
        since = fields.Datetime.now() - timedelta(days=7)
        for config in self.sudo().search([("xb_va_enabled", "=", True), ("xb_va_weekly_report", "=", True)]):
            emails = [u.email for u in config.xb_va_ho_user_ids if u.email]
            if not emails:
                continue
            lang = config.company_id.partner_id.lang or "en_US"
            config = config.with_context(lang=lang)
            numbers = config._xb_va_week_numbers(since)
            if not numbers["conversations"]:
                continue
            env = config.env
            rows = [
                (env._("Conversations"), numbers["conversations"]),
                (env._("Questions answered"), numbers["questions"]),
                (env._("Showed products"), numbers["with_products"]),
                (env._("Added to cart"), numbers["cart"]),
                (env._("Ended in a sale or quotation"), numbers["sales"]),
                (env._("Amount of those sales"), config.currency_id.format(numbers["sales_amount"])),
                (env._("Appointments booked"), numbers["appointments"]),
                (env._("Took it to their phone"), numbers["phone"]),
                (env._("Sent by WhatsApp"), numbers["whatsapp"]),
                (env._("Asked for a person"), numbers["person"]),
                (env._("AI cost (USD)"), "%.2f" % numbers["cost"]),
            ]
            body = self.env["ir.qweb"]._render("xb_self_order_assistant.weekly_digest", {
                "config": config, "n": numbers, "rows": rows, "labels": {
                    "period": env._("Last 7 days"), "top": env._("Most shown products"),
                    "missing": env._("Asked for and not found")}})
            self.env["mail.mail"].sudo().create({
                "subject": config.env._("%(seller)s this week at %(kiosk)s: %(count)s conversations, %(sales)s sales",
                                        seller=config.xb_va_name, kiosk=config.name,
                                        count=numbers["conversations"], sales=numbers["sales"]),
                "body_html": body,
                "email_to": ",".join(emails),
                "email_from": config.company_id.email_formatted or self.env.ref("base.partner_root").email_formatted,
                "auto_delete": True,
            })
