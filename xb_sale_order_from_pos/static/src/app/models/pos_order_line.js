// XUBAX - Sales, Quotations & Layaway from POS (Phase 4)
// Fix the Settle of OUR sale orders (xb_so_kind) when they carry MULTIPLE partial
// advances. Clean-room, native-only.

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    /**
     * On Settle, pos_sale sets the cart qty of a down-payment (service) line on a
     * CONFIRMED SO from `qty_to_invoice`. The native multi down-payment flow leaves
     * that field inconsistent: only the latest advance stays at -1; earlier advances
     * become 0 -> they do NOT deduct -> the customer is over-charged.
     *
     * For OUR sale orders, route the down-payment CREDIT lines through the qty
     * formula `product_uom_qty - max(qty_delivered, qty_invoiced)`, which yields -1
     * per real advance (product_uom_qty = 0, qty_invoiced = 1). So EVERY advance
     * deducts and the settle charge equals sale.order.amount_unpaid, for any number
     * of partial advances. Only the POS cart quantity changes here: the SO's
     * is_downpayment lines, their qty_invoiced and any account.move are untouched.
     */
    getConvertedQuantityFromSaleOrderline(convertedLine, soLine) {
        if (soLine.order_id?.xb_so_kind && soLine.is_downpayment) {
            return (
                convertedLine.product_uom_qty -
                Math.max(convertedLine.qty_delivered, convertedLine.qty_invoiced)
            );
        }
        return super.getConvertedQuantityFromSaleOrderline(...arguments);
    },
});
