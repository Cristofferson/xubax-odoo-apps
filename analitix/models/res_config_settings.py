# -*- coding: utf-8 -*-
"""Los ajustes que sí son globales — que son pocos, y a propósito.

Casi todo en Analitix se configura **por tienda**, porque casi todo cambia de
una tienda a otra: las puertas, las zonas, los umbrales, quién recibe el aviso.
Meter eso en Ajustes generales sería mentir sobre cómo funciona el producto.

Lo que sí es global es la **política de retención**, y hasta ahora vivía
únicamente en Parámetros del Sistema — o sea, en el único lugar de Odoo donde un
cliente no entra nunca. Una política de datos personales escondida detrás de
Técnico > Parámetros no es una política: es un valor que nadie va a revisar.
"""
from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    analitix_event_retention_days = fields.Integer(
        string="Keep raw crossings for (days)",
        config_parameter="analitix.event_retention_days",
        help="How long the individual crossing events are kept before the "
             "nightly job deletes them. Zero means keep them for ever, which "
             "is the default: nobody's data should start disappearing because "
             "an addon was installed.\n\n"
             "Reports over long horizons read the daily rollup, not these "
             "events, so pruning does not lose a figure anybody looks at — and "
             "the job refuses to delete a day the rollup has not summarised "
             "yet.")

    analitix_store_count = fields.Integer(
        string="Stores", readonly=True, compute="_compute_analitix_counts")
    analitix_activated_count = fields.Integer(
        string="Activated", readonly=True, compute="_compute_analitix_counts")

    @api.depends_context("company")
    def _compute_analitix_counts(self):
        Store = self.env["analitix.store"]
        total = Store.search_count([])
        activated = Store.search_count([("activated", "=", True)])
        for record in self:
            record.analitix_store_count = total
            record.analitix_activated_count = activated

    def action_analitix_stores(self):
        return self.env["ir.actions.actions"]._for_xml_id(
            "analitix.action_store")

    def action_analitix_new_store(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("New Store"),
            "res_model": "analitix.store.setup",
            "view_mode": "form",
            "target": "new",
        }
