# -*- coding: utf-8 -*-
from odoo import fields, models


class XbBusinessKnowledge(models.Model):
    """What the agent knows about the business: services, prices, hours, FAQs and
    rules. Edited in Odoo; the agent reads it in every chat."""
    _name = "xb.business.knowledge"
    _description = "WhatsApp agent knowledge base"
    _order = "kind, sequence, id"

    name = fields.Char("Title", required=True)
    kind = fields.Selection([
        ("service", "Service"),
        ("price", "Price"),
        ("schedule", "Hours and location"),
        ("faq", "FAQ"),
        ("policy", "Rule or policy"),
    ], string="Type", required=True, default="faq")
    content = fields.Text("Content", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    account_ids = fields.Many2many(
        "whatsapp.account", string="Numbers",
        help="Empty = applies to every number with the agent.")

    def _xb_as_text(self):
        titulos = dict(self._fields["kind"].selection)
        partes = []
        for kind, titulo in titulos.items():
            items = self.filtered(lambda r: r.kind == kind)
            if not items:
                continue
            partes.append(f"## {titulo}")
            partes += [f"### {r.name}\n{r.content.strip()}" for r in items]
        return "\n\n".join(partes)
