# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import format_amount, format_date, format_datetime
from odoo.tools.image import image_data_uri

# Width of the ticket image, in pixels: the receipt printer scales it to its paper.
XB_TICKET_WIDTH = 512


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _xb_kiosk_qr_uri(self, url):
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

    def _xb_kiosk_ticket_values(self):
        self.ensure_one()
        order = self.sudo()
        env = order.with_context(lang=order.partner_id.lang or self.env.lang or "en_US").env
        company = order.company_id
        tz = order.partner_id.tz or company.partner_id.tz or self.env.user.tz or "UTC"
        lines = [{
            "qty": "%g" % line.product_uom_qty,
            "name": line.product_id.display_name or line.name,
            "subtotal": format_amount(env, line.price_total, order.currency_id),
            "unit": format_amount(env, line.price_unit, order.currency_id),
            "uom": line.product_uom_id.name,
            "discount": line.discount,
        } for line in order.order_line.filtered(lambda l: not l.display_type and not l.is_downpayment)]
        address = company.partner_id
        # A branch prints its parent's tax ID, as the POS ticket does.
        vat = company.vat or company.root_id.vat or ""
        validity = format_date(env, order.validity_date) if order.validity_date else ""
        seller = (order.user_id.name or "").split(" ")[0]
        return {
            "order": order,
            "company": company,
            "logo": image_data_uri(company.logo) if company.logo else "",
            "title": env._("QUOTATION %s", order.name),
            "date": format_datetime(env, order.date_order, tz=tz, dt_format="d/M/y, h:mm a"),
            "seller": seller,
            "customer": order.partner_id.name,
            "lines": lines,
            "total": format_amount(env, order.amount_total, order.currency_id),
            "validity": validity,
            "qr": order._xb_kiosk_qr_uri(order.get_base_url() + order.get_portal_url()),
            "address_lines": [
                address.street or "",
                ", ".join(p for p in (address.city, address.state_id.code, address.zip) if p),
            ],
            "vat": vat,
            "email": company.email or "",
            "phone": company.phone or "",
            "website": company.website or "",
            "labels": {
                "served": env._("Served by: %s", seller),
                "total": env._("Total"),
                "pay": env._("Pay or review your order online:"),
                "valid": env._("Valid until %s", validity),
                "vat": env._("Tax ID: %s", vat),
                "phone": env._("Phone: %s", company.phone or ""),
                "discount": env._("Discount"),
            },
        }

    def _xb_kiosk_ticket_image(self, as_base64=False):
        """JPEG of the quotation drawn like the POS ticket, for the kiosk's printer."""
        self.ensure_one()
        html = self.env["ir.qweb"]._render(
            "xb_self_order_quotation.kiosk_ticket_image", self._xb_kiosk_ticket_values())
        # Height 0 = as tall as the ticket.
        image = self.env["ir.actions.report"]._run_wkhtmltoimage(
            [str(html)], XB_TICKET_WIDTH, 0, image_format="jpg")[0]
        if not image:
            raise UserError(_("Could not draw the image of %s.", self.name))
        return base64.b64encode(image) if as_base64 else image

    def _xb_kiosk_send_whatsapp(self, phone):
        """Send the kiosk quotation to the customer's WhatsApp. Done by the WhatsApp
        add-on (xb_self_order_quotation_whatsapp)."""
        raise UserError(_("WhatsApp is not available on this kiosk."))

    def _xb_kiosk_send_email(self):
        """Send the kiosk quotation to the customer's email, with the same template
        and PDF as the «Send by email» button of Sales."""
        self.ensure_one()
        template = self.env.ref("sale.email_template_edi_sale", raise_if_not_found=False)
        if not template:
            raise UserError(_("Email is not available on this kiosk."))
        order = self.sudo()
        order._portal_ensure_token()
        # Sent on behalf of the company: nobody sold it yet.
        order.with_context(force_send=True).message_post_with_source(
            template,
            email_layout_xmlid="mail.mail_notification_layout_with_responsible_signature",
            subtype_xmlid="mail.mt_comment",
            author_id=order.company_id.partner_id.id,
        )
