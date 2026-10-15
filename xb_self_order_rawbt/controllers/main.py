# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class RawBTTest(http.Controller):

    @http.route("/xb_rawbt/test/<int:config_id>", type="http", auth="public", website=False)
    def rawbt_test(self, config_id, access_token=None, **kw):
        """Page to open on the kiosk tablet: prints a sample ticket through RawBT with
        each sending method, to check which one works and the paper width."""
        config = request.env["pos.config"].sudo().browse(config_id).exists()
        if not config or not access_token or config.access_token != access_token:
            raise request.not_found()
        # In the kiosk's language: the page is opened on the kiosk tablet.
        lang = config.self_ordering_default_language_id.code or config.company_id.partner_id.lang
        if lang:
            request.update_context(lang=lang)
        version = request.env["ir.module.module"].sudo().search(
            [("name", "=", "xb_self_order_rawbt")], limit=1).latest_version or ""
        html = request.env["ir.qweb"]._render("xb_self_order_rawbt.printer_test", {
            "config": config,
            "width": int(config.xb_rawbt_paper or 576),
            "method": config.xb_rawbt_method or "intent",
            # In the URL of the script: a tablet that kept an older copy loads this one.
            "version": version,
        })
        return request.make_response("<!DOCTYPE html>\n" + str(html), headers=[
            ("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])
