/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (1.3.0)
// Before selling a piece laid away for another customer, show whose layaway holds it
// and ask the cashier to confirm. The register does not stop a sale on its own: the
// laid-away piece is still in stock (layaways from the register create no delivery).

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { formatDate } from "@web/core/l10n/dates";

const { DateTime } = luxon;

patch(PosStore.prototype, {
    async addProductToCurrentOrder(product, options = {}) {
        const resolved = Number.isInteger(product) ? this.db.get_product_by_id(product) : product;
        if (!(await this.xbConfirmLaidAway(resolved, options))) {
            return;
        }
        return await super.addProductToCurrentOrder(...arguments);
    },

    async xbConfirmLaidAway(product, options = {}) {
        // Only storable goods can be laid away (a layaway holds a piece in stock).
        if (!this.company?.xb_layaway_warn_reserved || !product || product.type !== "product") {
            return true;
        }
        let info;
        try {
            const result = await this.orm.silent.call("sale.order", "xb_pos_layaway_holds", [
                [product.id],
                this.config.id,
            ]);
            info = result?.[product.id];
        } catch {
            return true; // offline or slow: never block a sale on this check
        }
        if (!info) {
            return true;
        }
        const inCart = (this.get_order()?.get_orderlines() || [])
            .filter((l) => l.get_product()?.id === product.id && !l.sale_order_origin_id)
            .reduce((s, l) => s + (l.get_quantity() || 0), 0);
        const wanted = inCart + (options.quantity || 1);
        if (info.on_hand - info.held >= wanted) {
            return true; // enough free stock besides what is laid away
        }
        const holds = info.holds
            .map((h) =>
                h.deadline
                    ? _t("%(name)s, %(partner)s (until %(deadline)s)", {
                          ...h,
                          deadline: formatDate(DateTime.fromISO(h.deadline)),
                      })
                    : _t("%(name)s, %(partner)s", h)
            )
            .join("\n");
        const { confirmed } = await this.popup.add(ConfirmPopup, {
            title: _t("This piece is laid away"),
            body: _t("%(product)s is laid away for:\n%(holds)s\n\nSell it anyway?", {
                product: product.display_name,
                holds,
            }),
            confirmText: _t("Sell anyway"),
            cancelText: _t("Don't sell"),
        });
        return confirmed;
    },
});

// A scanned barcode adds the product straight to the order: ask there too.
patch(ProductScreen.prototype, {
    async _barcodeProductAction(code) {
        const product = await this._getProductByBarcode(code);
        if (product) {
            const quantity = ["weight", "quantity"].includes(code.type) ? code.value : 1;
            if (!(await this.pos.xbConfirmLaidAway(product, { quantity }))) {
                return;
            }
        }
        return await super._barcodeProductAction(...arguments);
    },
});
