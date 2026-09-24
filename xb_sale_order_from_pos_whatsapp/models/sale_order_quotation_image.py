# -*- coding: utf-8 -*-
# XUBAX - Sales, Quotations & Layaway from POS - WhatsApp add-on
import base64
import io

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_amount, format_datetime
from odoo.tools.image import image_data_uri

# Width of the ticket image, in pixels: the one the POS ticket is sent at. WhatsApp
# shows it full width on the phone, so a narrow receipt reads better than an A4 page.
XB_TICKET_WIDTH = 512


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ------------------------------------------------------------------
    # Which template, and when
    # ------------------------------------------------------------------
    def _xb_wa_quotation_templates(self):
        """Every quotation template of the order's company (one per Point of Sale)."""
        self.ensure_one()
        return self.env["pos.config"].sudo().search([
            ("company_id", "=", self.company_id.id),
            ("xb_quotation_wa_template_id", "!=", False),
        ]).xb_quotation_wa_template_id

    def _xb_wa_quotation_template(self):
        """The approved template the quotation goes with: the one the company's Point
        of Sale already sends it with, so no new template has to be approved."""
        self.ensure_one()
        return self._xb_wa_quotation_templates().filtered(
            lambda t: t.status == "approved"
        )[:1]

    def _xb_wa_quotation_applies(self):
        """A quotation still to be accepted, never an order or a layaway."""
        self.ensure_one()
        return bool(
            self.state in ("draft", "sent")
            and self.xb_so_kind not in ("order", "layaway", "order_layaway")
            and self.order_line.filtered(lambda l: not l.display_type)
            and self._xb_wa_quotation_template()
        )

    # ------------------------------------------------------------------
    # The image
    # ------------------------------------------------------------------
    def _xb_quotation_qr_uri(self, url):
        """PNG data URI of a QR code for ``url`` ('' when qrcode is missing). Inline:
        the renderer runs with local file access off and no network."""
        try:
            import qrcode
        except ImportError:
            return ""
        img = qrcode.make(url, border=1, box_size=6)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    def _xb_quotation_image_values(self):
        self.ensure_one()
        order = self.sudo()
        lang = order.partner_id.lang or self.env.lang or "en_US"
        env = order.with_context(lang=lang).env
        company = order.company_id
        tz = order.user_id.tz or self.env.user.tz or order._xb_tz()
        portal_url = order.get_base_url() + order.get_portal_url()
        lines = []
        for line in order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment):
            lines.append({
                "qty": ("%g" % line.product_uom_qty),
                "name": line.product_id.display_name or line.name,
                "subtotal": format_amount(env, line.price_total, order.currency_id),
                "unit": format_amount(env, line.price_unit, order.currency_id),
                "uom": line.product_uom_id.name,
                "discount": line.discount,
            })
        address = company.partner_id
        # A branch prints its parent's tax ID, as the POS ticket does.
        vat = company.vat or company.root_id.vat or ""
        return {
            "order": order,
            "company": company,
            "logo": image_data_uri(company.logo) if company.logo else "",
            "title": env._("QUOTATION %s", order.name),
            "date": format_datetime(env, order.date_order, tz=tz, dt_format="d/M/y, h:mm a"),
            "seller": (order.user_id.name or "").split(" ")[0],
            "customer": order.partner_id.name,
            "lines": lines,
            "total": format_amount(env, order.amount_total, order.currency_id),
            "validity": order.xb_wa_validity_date if order.validity_date else "",
            "qr": order._xb_quotation_qr_uri(portal_url),
            "address_lines": [
                address.street or "",
                ", ".join(p for p in (address.city, address.state_id.code, address.zip) if p),
            ],
            "vat": vat,
            "email": company.email or "",
            "phone": company.phone or "",
            "website": company.website or "",
            "labels": {
                "served": env._("Served by: %s", (order.user_id.name or "").split(" ")[0]),
                "total": env._("Total"),
                "pay": env._("Pay or review your order online:"),
                "valid": env._("Valid until %s", order.xb_wa_validity_date),
                "vat": env._("Tax ID: %s", vat),
                "phone": env._("Phone: %s", company.phone or ""),
                "discount": env._("Discount"),
            },
        }

    def _xb_quotation_image(self, as_base64=False):
        """JPEG of the quotation drawn like the POS ticket, for the template's header."""
        self.ensure_one()
        html = self.env["ir.qweb"]._render(
            "xb_sale_order_from_pos_whatsapp.quotation_ticket_image",
            self._xb_quotation_image_values(),
        )
        # Height 0 = as tall as the ticket.
        image = self.env["ir.actions.report"]._run_wkhtmltoimage(
            [str(html)], XB_TICKET_WIDTH, 0, image_format="jpg"
        )[0]
        if not image:
            raise UserError(_("Could not draw the image of %s.", self.name))
        return base64.b64encode(image) if as_base64 else image

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def _xb_send_wa_quotation(self, phone=None):
        """Send the quotation by WhatsApp with an image of it and return the number it
        went to. Same safety as the notices: the company's own approved template, to
        the order's own customer."""
        self.ensure_one()
        self._xb_check_notice_rights()
        order = self.sudo()
        template = order._xb_wa_quotation_template()
        if not template:
            raise UserError(_("%s has no approved WhatsApp template for quotations.", order.company_id.name))
        if not order._xb_wa_quotation_applies():
            raise UserError(_("%s is not a quotation waiting for the customer.", order.name))
        phone = phone or order.partner_id.phone
        if not phone:
            raise UserError(_(
                "%(customer)s has no phone number: add it to the contact and try again.",
                customer=order.partner_id.display_name,
            ))
        # Same rule as the POS: fill the customer's phone only when it has none; a
        # different number is used for this send only.
        if not order.partner_id.phone:
            order.partner_id.phone = phone
        ticket = self.env["ir.attachment"].sudo().create({
            "name": "%s.jpg" % order.name,
            "raw": order._xb_quotation_image(),
            "mimetype": "image/jpeg",
            "res_model": order._name,
            "res_id": order.id,
        })
        message = order._xb_wa_send_template(template, phone=phone, attachment=ticket)
        if order.state == "draft":
            # As when the quotation is sent by email: it is now with the customer.
            order.state = "sent"
        return message.mobile_number_formatted or phone
