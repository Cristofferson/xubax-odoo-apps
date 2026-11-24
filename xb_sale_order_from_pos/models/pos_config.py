# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.osv.expression import OR


class PosConfig(models.Model):
    _inherit = "pos.config"

    xb_rounding_product_id = fields.Many2one(
        "product.product",
        string="Settle rounding product",
        help="Fallback used when settling a sale order whose down payments cannot "
             "absorb the per-tax rounding cent in a 0% line (e.g. an all-16% order). "
             "Should be a 0% IVA service product with a valid SAT ClaveProdServ so "
             "the CFDI stamps.",
    )

    def _get_special_products(self):
        # Register the settle rounding products as POS special products (like pos_sale
        # does with its down payment product), so they are loaded in the register even
        # when the merchant keeps them available_in_pos=False: they are added
        # programmatically on a settle, never sold from the product list. On Odoo 17 this
        # is called on an EMPTY recordset, hence the search over every POS.
        products = super()._get_special_products()
        return products | self.env["pos.config"].search([]).mapped("xb_rounding_product_id")

    def _get_available_product_domain(self):
        domain = super()._get_available_product_domain()
        if self.xb_rounding_product_id:
            domain = OR([domain, [("id", "=", self.xb_rounding_product_id.id)]])
        return domain

    # --- Main toggle: enables the whole feature set for this POS ---
    xb_enable_sale_order = fields.Boolean(
        string="Create Sale Order / Quotation",
        help="Allow creating quotations, sale orders and layaways (apartados) "
             "from this Point of Sale.",
    )

    # --- Sub-toggles (only relevant when the main toggle is on) ---
    # NOTE on POS loading: pos.session._loader_params_pos_config reads ALL the
    # pos.config fields, so every xb_* field below is available in the POS frontend
    # as pos.config.<field> (Many2one as [id, name]).
    xb_allow_quotation = fields.Boolean(
        string="Allow quotations",
        help="Let the cashier create the order as a draft quotation that the "
             "customer can complete online or recover in-store.",
    )
    xb_differentiate_order_layaway = fields.Boolean(
        string="Differentiate Order and Layaway",
        help="OFF (default): the POS shows a single \"Order / Layaway\" action "
             "— a confirmed sale order with an optional advance (down payment).\n"
             "ON: the POS shows two separate actions — \"Order\" (confirmed, no "
             "advance) and \"Layaway\" (confirmed, with advance).\n"
             "\"Quotation\" is offered separately according to \"Allow "
             "quotations\".",
    )
    xb_default_so_state = fields.Selection(
        selection=[
            ("draft", "Quotation"),
            ("sale", "Confirmed order"),
        ],
        string="Default state",
        default="draft",
        help="Pre-selects which document type is highlighted by default in the POS "
             "create dialog: a draft Quotation, or a Sale Order / Layaway. It only "
             "sets the default choice — nothing is confirmed on creation (the order "
             "is confirmed natively when its payment is collected).",
    )
    xb_show_order_balance = fields.Boolean(
        string="Show total & pending balance",
        help="Display the order total and pending balance next to the order "
             "reference in the POS order panel.",
    )
    xb_enrich_receipt = fields.Boolean(
        string="Detailed order receipt",
        help="Add the order's product detail, total and pending balance to the "
             "printed receipt.",
    )
    xb_show_partner_ref = fields.Boolean(
        string="Show customer reference",
        help="Show the customer's reference code before their name.",
    )
    xb_autoprint_on_create = fields.Boolean(
        string="Auto-print receipt on create",
        help="Automatically print the order receipt right after creating the "
             "quotation / sale order / layaway from the POS.",
    )
    xb_duplicate_receipt_on_create = fields.Boolean(
        string="Print the order receipt in duplicate",
        help="Print the order receipt twice when it is created from the POS: two "
             "identical tickets, one for the customer and one for the shop. "
             "Quotations are always printed once, whatever this setting says. Only "
             "applies to the receipt printed on creation, and requires "
             "\"Auto-print receipt on create\".",
    )
    xb_ask_quotation_delivery = fields.Boolean(
        string="Ask how to deliver each quotation",
        help="When a quotation is created from the POS, ask how the customer wants "
             "it: printed, by WhatsApp, by email, or any combination, chosen for each "
             "quotation. What is sent is the same ticket that is printed. WhatsApp is "
             "offered only when the WhatsApp add-on is installed and this Point of "
             "Sale has a quotation template.",
    )
    xb_list_until_delivered = fields.Boolean(
        string="Keep paid orders listed until delivered",
        help="In the POS list of orders to recover (Quotation/Order button), keep the "
             "orders and layaways created here while their goods are pending delivery, "
             "even when fully paid, so they can be delivered from the POS. Closing an "
             "order asks whether the customer takes the piece now: if not, only the "
             "balance is charged, as a down payment, and the piece stays in stock. "
             "Odoo's own list only shows orders with a balance.",
    )
    xb_show_portal_link = fields.Boolean(
        string="Show online portal link on receipt",
        help="Add the order's online portal link (with access token) and a short "
             "instruction to the receipt, so the customer can review, add advances "
             "or settle the order online. Requires Online Payment and payment "
             "providers to be configured.",
    )
    xb_autofactura_qr_paid_only = fields.Boolean(
        string="Self-invoice QR only when settled",
        default=True,
        help="Controls the native self-invoice (\"Need an invoice?\") QR on receipts "
             "linked to a Sale Order.\n"
             "Enabled (default): the self-invoice QR appears only when the balance is "
             "0 (settlement / fully-paid ticket), avoiding a double QR alongside the "
             "online payment QR on advance tickets.\n"
             "Disabled: the self-invoice QR appears on every ticket where it applies "
             "(native behaviour), for merchants that invoice each ticket. The online "
             "payment QR is independent (balance > 0 + 'Show online portal link').",
    )
