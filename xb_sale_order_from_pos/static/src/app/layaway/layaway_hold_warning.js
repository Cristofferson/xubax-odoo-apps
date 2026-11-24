// XUBAX - Sales, Quotations & Layaway from POS (1.3.0)
// Before selling a piece laid away for another customer, show whose layaway holds it
// and ask the cashier to confirm. The register does not stop a sale on its own: the
// laid-away piece is still in stock (layaways from the register create no delivery).

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { ask } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { formatDate } from "@web/core/l10n/dates";

const { DateTime } = luxon;

patch(PosStore.prototype, {
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        if (!(await this.xbConfirmLaidAway(vals))) {
            return;
        }
        return await super.addLineToCurrentOrder(...arguments);
    },

    async xbConfirmLaidAway(vals) {
        // Lines that settle or pay a sale order are that order's own goods.
        if (!this.company?.xb_layaway_warn_reserved || vals?.sale_order_origin_id) {
            return true;
        }
        // A product card sends the template; a single-variant template is the piece
        // itself (a template with variants is resolved later, when its variant is
        // chosen, and is not checked here).
        let product =
            typeof vals?.product_id === "number"
                ? this.models["product.product"].get(vals.product_id)
                : vals?.product_id;
        if (!product && vals?.product_tmpl_id) {
            const tmpl =
                typeof vals.product_tmpl_id === "number"
                    ? this.models["product.template"].get(vals.product_tmpl_id)
                    : vals.product_tmpl_id;
            const variants = tmpl?.product_variant_ids || [];
            product = variants.length === 1 ? variants[0] : null;
        }
        if (!product || product.type !== "consu" || product.is_storable === false) {
            return true;
        }
        let info;
        try {
            const result = await this.data.silentCall("sale.order", "xb_pos_layaway_holds", [
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
        const inCart = (this.getOrder()?.getOrderlines() || [])
            .filter((l) => l.product_id?.id === product.id && !l.sale_order_origin_id)
            .reduce((s, l) => s + (l.qty || 0), 0);
        const wanted = inCart + (vals.qty || 1);
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
        return await ask(this.dialog, {
            title: _t("This piece is laid away"),
            body: _t(
                "%(product)s is laid away for:\n%(holds)s\n\nSell it anyway?",
                { product: product.display_name, holds }
            ),
            confirmLabel: _t("Sell anyway"),
            cancelLabel: _t("Don't sell"),
        });
    },
});
