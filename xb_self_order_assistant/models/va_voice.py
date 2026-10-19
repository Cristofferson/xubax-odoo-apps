# -*- coding: utf-8 -*-
from odoo import fields, models


class XbVaVoice(models.Model):
    """A voice the virtual seller can speak with (an OpenAI text-to-speech voice)."""
    _name = "xb.va.voice"
    _description = "Virtual seller voice"
    _order = "gender, sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, help="Voice name at OpenAI, e.g. nova.")
    gender = fields.Selection([("female", "Woman"), ("male", "Man")], required=True)
    description = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
