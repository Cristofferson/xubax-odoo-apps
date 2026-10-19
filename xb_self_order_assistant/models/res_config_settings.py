# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    xb_va_anthropic_key = fields.Char("Virtual seller: Anthropic key", config_parameter="xb_self_order_assistant.anthropic_key")
    xb_va_openai_key = fields.Char("Virtual seller: OpenAI key", config_parameter="xb_self_order_assistant.openai_key")

    pos_xb_va_enabled = fields.Boolean(related="pos_config_id.xb_va_enabled", readonly=False)
    pos_xb_va_name = fields.Char(related="pos_config_id.xb_va_name", readonly=False)
    pos_xb_va_name_say = fields.Char(related="pos_config_id.xb_va_name_say", readonly=False)
    pos_xb_va_gender = fields.Selection(related="pos_config_id.xb_va_gender", readonly=False)
    pos_xb_va_voice_id = fields.Many2one(related="pos_config_id.xb_va_voice_id", readonly=False)
    pos_xb_va_avatar_id = fields.Many2one(related="pos_config_id.xb_va_avatar_id", readonly=False)
    pos_xb_va_avatar_face = fields.Image(related="pos_config_id.xb_va_avatar_id.image")
    pos_xb_va_start_full = fields.Boolean(related="pos_config_id.xb_va_start_full", readonly=False)
    pos_xb_va_position = fields.Selection(related="pos_config_id.xb_va_position", readonly=False)
    pos_xb_va_continuous = fields.Boolean(related="pos_config_id.xb_va_continuous", readonly=False)
    pos_xb_va_scan = fields.Boolean(related="pos_config_id.xb_va_scan", readonly=False)
    pos_xb_va_speak = fields.Boolean(related="pos_config_id.xb_va_speak", readonly=False)
    pos_xb_va_listen = fields.Boolean(related="pos_config_id.xb_va_listen", readonly=False)
    pos_xb_va_voice_style = fields.Char(related="pos_config_id.xb_va_voice_style", readonly=False)
    pos_xb_va_button = fields.Char(related="pos_config_id.xb_va_button", readonly=False)
    pos_xb_va_greeting = fields.Char(related="pos_config_id.xb_va_greeting", readonly=False)
    pos_xb_va_knowledge = fields.Text(related="pos_config_id.xb_va_knowledge", readonly=False)
    pos_xb_va_sales_style = fields.Selection(related="pos_config_id.xb_va_sales_style", readonly=False)
    pos_xb_va_instructions = fields.Text(related="pos_config_id.xb_va_instructions", readonly=False)
    pos_xb_va_model = fields.Selection(related="pos_config_id.xb_va_model", readonly=False)
    pos_xb_va_engine = fields.Selection(related="pos_config_id.xb_va_engine", readonly=False)
    pos_xb_va_rt_voice = fields.Selection(related="pos_config_id.xb_va_rt_voice", readonly=False)
    pos_xb_va_rt_model = fields.Selection(related="pos_config_id.xb_va_rt_model", readonly=False)
    pos_xb_va_handoff_label = fields.Char(related="pos_config_id.xb_va_handoff_label", readonly=False)
    pos_xb_va_ho_discuss = fields.Boolean(related="pos_config_id.xb_va_ho_discuss", readonly=False)
    pos_xb_va_ho_pos = fields.Boolean(related="pos_config_id.xb_va_ho_pos", readonly=False)
    pos_xb_va_ho_email = fields.Boolean(related="pos_config_id.xb_va_ho_email", readonly=False)
    pos_xb_va_ho_user_ids = fields.Many2many(related="pos_config_id.xb_va_ho_user_ids", readonly=False)
    pos_xb_va_ho_pos_ids = fields.Many2many(related="pos_config_id.xb_va_ho_pos_ids", readonly=False)
    pos_xb_va_tap_url = fields.Char(related="pos_config_id.xb_va_tap_url")
    pos_xb_va_greet = fields.Selection(related="pos_config_id.xb_va_greet", readonly=False)
    pos_xb_va_greet_text = fields.Char(related="pos_config_id.xb_va_greet_text", readonly=False)
    pos_xb_va_weekly_report = fields.Boolean(related="pos_config_id.xb_va_weekly_report", readonly=False)
    pos_xb_va_idle_seconds = fields.Integer(related="pos_config_id.xb_va_idle_seconds", readonly=False)
    pos_xb_va_daily_limit = fields.Float(related="pos_config_id.xb_va_daily_limit", readonly=False)

    def action_xb_va_hear_voice(self):
        """Opens the greeting spoken with the chosen voice, to compare voices before saving."""
        self.ensure_one()
        self.pos_config_id.write({"xb_va_voice_id": self.pos_xb_va_voice_id.id,
                                  "xb_va_voice_style": self.pos_xb_va_voice_style,
                                  "xb_va_name": self.pos_xb_va_name,
                                  "xb_va_name_say": self.pos_xb_va_name_say,
                                  "xb_va_greeting": self.pos_xb_va_greeting})
        return {"type": "ir.actions.act_url", "target": "new",
                "url": "/xb-va/%s/sample" % self.pos_config_id.id}
