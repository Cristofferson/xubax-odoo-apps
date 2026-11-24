/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 4)
// The register's list of orders to recover (pos_sale's "Quotation/Order" screen) and
// its Settle / down payment. Clean-room, native-only.
// - The listed orders carry the fields our guards and receipt need.
// - With xb_list_until_delivered, orders made here stay listed until delivered, and
//   closing one asks whether the customer takes the piece now.
// - Settling one of our orders closes its balance to EXACTLY amount_unpaid.

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";
import { Orderline } from "@point_of_sale/app/store/models";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { SaleOrderManagementScreen } from "@pos_sale/app/order_management_screen/sale_order_management_screen/sale_order_management_screen";
import { SaleOrderManagementControlPanel } from "@pos_sale/app/order_management_screen/sale_order_management_control_panel/sale_order_management_control_panel";

// Sale Order fields the register reads on the orders it lists (sale.order._XB_POS_SO_FIELDS).
const XB_SO_FIELDS = [
    "xb_so_kind",
    "access_token",
    "commitment_date",
    "xb_layaway_deadline",
    "xb_layaway_down_percent",
    "xb_layaway_min_payment",
    "xb_layaway_state",
    "xb_layaway_expired_on",
];

let fetcherPatched = false;

patch(SaleOrderManagementScreen.prototype, {
    setup() {
        super.setup(...arguments);
        // pos_sale's fetcher is a service whose class is not exported: extend its
        // prototype once, from its live instance.
        if (!fetcherPatched) {
            fetcherPatched = true;
            patch(Object.getPrototypeOf(this.saleOrderFetcher), {
                async _getOrderIdsForCurrentPage(limit, offset) {
                    const orders = await super._getOrderIdsForCurrentPage(...arguments);
                    if (orders.length) {
                        const extra = await this.orm.read(
                            "sale.order",
                            orders.map((o) => o.id),
                            XB_SO_FIELDS
                        );
                        const byId = Object.fromEntries(extra.map((r) => [r.id, r]));
                        for (const order of orders) {
                            Object.assign(order, byId[order.id] || {});
                        }
                    }
                    return orders;
                },
            });
        }
    },

    async _getSaleOrder(id) {
        const saleOrder = await super._getSaleOrder(...arguments);
        // The order's own product lines, printed on the advance ticket.
        const clicked = this.xbSettle?.clicked;
        if (clicked?.id !== id) {
            return saleOrder;
        }
        clicked.xb_lines = (saleOrder.order_line || [])
            .filter((l) => !l.is_downpayment && l.product_id)
            .map((l) => ({
                product_uom_qty: l.product_uom_qty,
                product_name: l.product_id[1] || "",
                total: l.price_total,
            }));
        return saleOrder;
    },

    /**
     * Wraps pos_sale's flow: it asks "What do you want to do?" and then builds the
     * cart. We watch its answer through the popup service:
     * - "Settle" with xb_list_until_delivered asks whether the customer takes the
     *   piece now; "only paying" turns it into a down payment of the whole balance
     *   (pos_sale's own down-payment line), so the piece stays in stock and the
     *   order stays listed until it is really delivered.
     * - After a Settle of one of our orders, the cart is reconciled to the cent.
     */
    async onClickSaleOrder(clickedOrder) {
        const pos = this.pos;
        const popup = this.popup;
        const xb = { choice: null, forcedDown: null, clicked: clickedOrder };
        this.xbSettle = xb;
        this.popup = Object.create(popup);
        this.popup.add = async (Comp, props) => {
            if (Comp === NumberPopup && xb.forcedDown !== null) {
                return { confirmed: true, payload: "0" };
            }
            const res = await popup.add(Comp, props);
            if (Comp === SelectionPopup && xb.choice === null && res.confirmed) {
                xb.choice = res.payload;
                if (res.payload === "settle" && pos.config.xb_list_until_delivered) {
                    const answer = await pos.xbAskHandOver(clickedOrder);
                    if (!answer) {
                        xb.choice = "cancel";
                        return { confirmed: false, payload: null };
                    }
                    if (answer === "pay") {
                        xb.choice = "xbPay";
                        xb.forcedDown = clickedOrder.amount_unpaid || 0;
                        return { confirmed: true, payload: "dpAmount" };
                    }
                }
            }
            return res;
        };
        try {
            await super.onClickSaleOrder(...arguments);
        } finally {
            this.popup = popup;
            this.xbSettle = null;
        }
        if (xb.choice === "settle" && clickedOrder.xb_so_kind) {
            await this.xbReconcileSettle(clickedOrder);
        }
    },

    _createDownpaymentLines(sale_order, total_down_payment, clickedOrder, down_payment_product) {
        if (this.xbSettle?.forcedDown !== null && this.xbSettle?.forcedDown !== undefined) {
            total_down_payment = this.xbSettle.forcedDown;
        }
        return super._createDownpaymentLines(
            sale_order,
            total_down_payment,
            clickedOrder,
            down_payment_product
        );
    },

    /**
     * After the native Settle builds the cart, our SO's portion total can land ~1¢
     * off sale.order.amount_unpaid (the source of truth) due to per-tax-group
     * rounding when the down-payment credits net against the products. Reconcile it:
     *
     *   delta = amount_unpaid - portion
     *   |delta| <= 0.02:
     *     Option 1: shift the last 0%-tax down-payment CREDIT line by delta. Taxed
     *               groups are NOT touched; only a 0% base moves.
     *     Option 2 (no 0% credit line): add a 0%-tax "rounding" line for delta using
     *               config.xb_rounding_product_id.
     * Only the POS cart is changed.
     */
    async xbReconcileSettle(clickedOrder) {
        const pos = this.pos;
        const order = pos.get_order();
        const ourLines = order
            .get_orderlines()
            .filter((l) => l.sale_order_origin_id?.id === clickedOrder.id);
        if (!ourLines.length) {
            return;
        }
        const round = (v) => round_pr(v, pos.currency.rounding);
        const portion = ourLines.reduce((s, l) => s + (l.get_price_with_tax() || 0), 0);
        const delta = round(clickedOrder.amount_unpaid - portion);
        if (delta === 0 || Math.abs(delta) > 0.02) {
            return; // nothing to reconcile, or a real (non-rounding) mismatch -> guard handles it
        }

        const dpId = pos.config.down_payment_product_id?.[0];
        const isZeroRate = (l) => l.get_taxes().every((t) => t.amount === 0);

        // Option 1: absorb into the last 0%-rate down-payment credit line.
        const zeroCredit = ourLines
            .filter((l) => l.get_product().id === dpId && isZeroRate(l))
            .at(-1);
        if (zeroCredit) {
            // Credit qty is -1 and 0% tax, so the line total = -price. Lowering the
            // unit price by delta raises the order total by delta.
            zeroCredit.set_unit_price(zeroCredit.get_unit_price() - delta);
            return;
        }

        // Option 2 (fallback) is OPT-IN: only when the merchant configured a rounding
        // product. If none, the guard's 0.01 tolerance lets the settle pass.
        const roundingId = pos.config.xb_rounding_product_id?.[0];
        if (!roundingId) {
            return;
        }
        let roundingProduct = pos.db.get_product_by_id(roundingId);
        if (!roundingProduct) {
            await pos._addProducts([roundingId], false);
            roundingProduct = pos.db.get_product_by_id(roundingId);
        }
        if (!roundingProduct) {
            return;
        }
        const line = new Orderline(
            { env: this.env },
            {
                pos,
                order,
                product: roundingProduct,
                price: delta,
                price_type: "automatic",
                sale_order_origin_id: clickedOrder,
            }
        );
        line.set_unit_price(delta);
        order.add_orderline(line);
    },
});

patch(SaleOrderManagementControlPanel.prototype, {
    /**
     * The list of orders to recover, with one more case. Odoo's own list hides an
     * order once it is invoiced (a settle at the register invoices its lines), so an
     * order or layaway paid in full could vanish before its goods were handed over.
     * With xb_list_until_delivered, orders created here stay listed while their goods
     * are pending delivery (xb_pending_delivery), paid or not, and leave the list once
     * delivered, unless they still owe money. Orders created in Sales keep the rule
     * "listed while there is a balance", unless the customer paid them online (website
     * or payment link): those wait at the store, paid, to be handed over.
     */
    _computeDomain() {
        const domain = super._computeDomain(...arguments);
        if (!this.pos.config.xb_list_until_delivered) {
            return domain;
        }
        // pos_sale's domain starts with its two base conditions; the rest is the search.
        return [
            ["state", "!=", "cancel"],
            "|",
            "&",
            ["invoice_status", "!=", "invoiced"],
            ["amount_unpaid", ">", 0],
            "&",
            ["xb_pending_delivery", "=", true],
            "|",
            ["xb_so_kind", "!=", false],
            ["transaction_ids.state", "in", ["done", "authorized"]],
            ...domain.slice(2),
        ];
    },
});

patch(PosStore.prototype, {
    /**
     * "Close the order" (pos_sale's Settle) hands the goods over: the POS order takes
     * them out of stock and the order leaves the list of orders to deliver. Ask first
     * whether the customer takes the piece now. Resolves to "deliver", "pay", or
     * undefined when the cashier closes the question.
     */
    async xbAskHandOver(sale_order) {
        const due = round_pr(sale_order.amount_unpaid || 0, this.currency.rounding);
        const list = [
            {
                id: "deliver",
                item: "deliver",
                label: _t("Yes, the customer takes it"),
                description: _t("The order is closed and the piece leaves the inventory."),
            },
        ];
        if (due > 0) {
            list.push({
                id: "pay",
                item: "pay",
                label: _t("No, only paying"),
                description: _t(
                    "%s is charged as a down payment; the order stays in the list until the piece is delivered.",
                    this.env.utils.formatCurrency(due)
                ),
            });
        }
        const { confirmed, payload } = await this.popup.add(SelectionPopup, {
            title:
                due > 0
                    ? _t("Is the customer taking the piece now?")
                    : _t("Hand over the piece now? The order is already paid."),
            list,
        });
        return confirmed ? payload : undefined;
    },

    /**
     * Round-trip: pos.order.create_from_ui sends back, for each synced order, the
     * FRESH Sale Orders it is linked to (balance and state after this payment). Copy
     * them onto the sale order the lines point to, so the receipt drawn right after
     * paying shows the real balance.
     */
    async _save_to_server(orders, options) {
        const serverIds = await super._save_to_server(...arguments);
        try {
            for (const res of serverIds || []) {
                if (!res?.xb_sale_orders?.length) {
                    continue;
                }
                const order = this.get_order_list().find((o) => o.name === res.pos_reference);
                if (!order) {
                    continue;
                }
                const fresh = Object.fromEntries(res.xb_sale_orders.map((so) => [so.id, so]));
                for (const line of order.get_orderlines()) {
                    const so = line.sale_order_origin_id;
                    if (so && fresh[so.id]) {
                        Object.assign(so, fresh[so.id]);
                    }
                }
            }
        } catch (error) {
            console.warn("[xb] could not refresh the linked sale orders:", error);
        }
        return serverIds;
    },
});
