/** TAECEL helpers on the POS store: access the loaded catalog and open the
 *  sale flow. All version-sensitive imports are funnelled through compat.js so
 *  the Odoo 18 branch only edits that one file. */
import { patch } from "@web/core/utils/patch";
import { PosStore } from "./compat";
import { XbTaecelSaleDialog } from "./taecel_sale_dialog/taecel_sale_dialog";

patch(PosStore.prototype, {
    /** The single TAECEL account loaded for this POS, if any. */
    get xbTaecelAccount() {
        const accounts = this.models["xb.taecel.account"]?.getAll() || [];
        return accounts[0] || null;
    },

    get xbTaecelEnabled() {
        return Boolean(this.xbTaecelAccount);
    },

    get xbTaecelCarriers() {
        return (this.models["xb.taecel.carrier"]?.getAll() || []).filter(
            (c) => c.active !== false
        );
    },

    /** Fixed-amount products for a catalog carrier, cheapest first. */
    xbTaecelProductsForCarrier(carrier) {
        if (!carrier) {
            return [];
        }
        return (this.models["xb.taecel.product"]?.getAll() || [])
            .filter((p) => p.carrier_id?.id === carrier.id && p.active !== false)
            .sort((a, b) => (a.amount || 0) - (b.amount || 0));
    },

    get xbTaecelWallets() {
        return this.models["xb.taecel.wallet"]?.getAll() || [];
    },

    xbTaecelWalletBalance(bolsaId) {
        const wallet = this.xbTaecelWallets.find((w) => w.bolsa_id === String(bolsaId));
        return wallet ? wallet.balance : null;
    },

    /** The generic product every TAECEL line hangs off (see product_data.xml).
     *  In 19 the POS sells product.template; fall back to a variant if needed. */
    get xbTaecelProduct() {
        const templates = this.models["product.template"]?.getAll() || [];
        const tmpl = templates.find((p) => p.default_code === "XBTAECEL");
        if (tmpl) {
            return tmpl;
        }
        const products = this.models["product.product"]?.getAll() || [];
        return products.find((p) => p.default_code === "XBTAECEL") || null;
    },

    async xbOpenTaecelSale() {
        this.dialog.add(XbTaecelSaleDialog, {});
    },
});
