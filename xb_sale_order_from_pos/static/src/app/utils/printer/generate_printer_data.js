// XUBAX - Sales, Quotations & Layaway from POS (Phase 3 - display only)
// Adds the Sale Order data to the receipt. Odoo 20 draws every receipt from one QWeb
// template (point_of_sale.pos_order_receipt, extended in receipt/pos_order_receipt.xml)
// fed by GeneratePrinterData here, and by pos.order.receipt on the server.

import { patch } from "@web/core/utils/patch";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import { generateQRCodeDataUrl } from "@point_of_sale/utils";

patch(GeneratePrinterData.prototype, {
    generateReceiptData() {
        const data = super.generateReceiptData(...arguments);
        Object.assign(data.extra_data, this.xbGenerateSaleOrderData());
        return data;
    },

    /**
     * Sale Order data of this receipt's order, as plain values for the template:
     * - xb_so: the document (kind, name, dates, customer reference) and, with the
     *   detailed receipt, its Total / Paid / Balance, products and the payment QR.
     * - xb_created: the ticket printed when the document is CREATED from the cart
     *   (nothing paid, the cart is discarded): it is not a "pro forma" of a sale.
     * - xb_hide_self_invoice_qr: hide Odoo's self-invoice QR while a balance is due.
     */
    xbGenerateSaleOrderData() {
        const order = this.order;
        const config = this.config;
        const so = order.xbGetSaleOrderTotals?.() || null;
        const result = {
            xb_so: false,
            xb_created: Boolean(order.uiState?.xbSaleOrder),
            xb_hide_self_invoice_qr: false,
        };
        if (!so) {
            return result;
        }
        // Title by STATE: a quotation already confirmed reads as an order.
        let kind = so.type || false;
        if (kind === "quotation" && so.state === "sale") {
            kind = "order";
        }
        const enrich = Boolean(config.xb_enrich_receipt);
        const details =
            so.balance > 0 ? this.xbSaleOrderDetails(order) : [];
        let portalQr = false;
        if (enrich && config.xb_show_portal_link && so.portalUrl && so.balance > 0) {
            try {
                portalQr = generateQRCodeDataUrl(so.portalUrl);
            } catch (e) {
                // A QR failure must never break the receipt (it would stop the autoprint).
                console.warn("[xb] payment QR generation failed:", e, so.portalUrl);
            }
        }
        result.xb_so = {
            kind,
            name: so.name || "",
            partner_ref: so.partnerRef || false,
            delivery_date: so.deliveryDate || false,
            layaway_deadline: so.layawayDeadline || false,
            show_summary: enrich && so.paid > 0,
            settled: so.balance <= 0,
            total: this.formatCurrency(so.total || 0),
            paid: this.formatCurrency(so.paid || 0),
            balance: this.formatCurrency(so.balance || 0),
            details: enrich ? details : [],
            portal_qr: portalQr,
        };
        result.xb_hide_self_invoice_qr = Boolean(config.xb_autofactura_qr_paid_only && so.balance > 0);
        return result;
    },

    /**
     * The recovered Sale Order's own PRODUCT lines (name, qty, total), shown on the
     * advance ticket. Down-payment and non-product lines are left out.
     */
    xbSaleOrderDetails(order) {
        const so = order.lines?.find((l) => l.sale_order_origin_id)?.sale_order_origin_id;
        return (so?.order_line || [])
            .filter((l) => !l.is_downpayment && l.product_id)
            .map((l) => ({
                qty: l.product_uom_qty,
                name: l.product_id.display_name || l.display_name || "",
                total: this.formatCurrency(l.price_total),
            }));
    },
});
