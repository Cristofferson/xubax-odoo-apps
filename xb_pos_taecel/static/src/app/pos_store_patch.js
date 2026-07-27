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

    xbTaecelWallet(bolsaId) {
        return this.xbTaecelWallets.find((w) => w.bolsa_id === String(bolsaId)) || null;
    },

    xbTaecelWalletBalance(bolsaId) {
        const wallet = this.xbTaecelWallet(bolsaId);
        return wallet ? wallet.balance : null;
    },

    /** Balances as they stand right now, keyed by bolsa id.
     *
     *  The figures loaded with the session age as the day goes on -- other
     *  registers spend the same wallets, and a register is often open for
     *  hours. Returns null when the read fails (offline): the caller then
     *  falls back to the loaded figures rather than blocking sales.
     */
    async xbTaecelFetchBalances() {
        const account = this.xbTaecelAccount;
        if (!account) {
            return null;
        }
        try {
            return await this.env.services.orm.call(
                "xb.taecel.wallet",
                "xb_pos_balances",
                [account.id]
            );
        } catch {
            return null;
        }
    },

    /** Amount already committed to a wallet by the order being built.
     *
     *  Two $200 recharges on one ticket draw on the same wallet, so checking
     *  each against the full balance would let a single ticket overdraw it.
     */
    xbTaecelCommitted(bolsaId) {
        const order = this.getOrder?.() || this.get_order?.() || null;
        const lines = order?.lines || [];
        return lines
            .filter((l) => l.taecel_is_taecel && String(l.taecel_bolsa_id) === String(bolsaId))
            .reduce((sum, l) => sum + ((l.price_unit || 0) - (l.taecel_fee || 0)), 0);
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
