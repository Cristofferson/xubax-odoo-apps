/** @odoo-module */
/** TAECEL helpers on the POS store (Odoo 17): keep the loaded catalog, open
 *  the sale flow, and carry the TAECEL data of an order line to the server. */
import { patch } from "@web/core/utils/patch";
import { PosStore, Orderline } from "./compat";
import { XbTaecelSaleDialog } from "./taecel_sale_dialog/taecel_sale_dialog";

const TAECEL_MODELS = [
    "xb.taecel.account",
    "xb.taecel.wallet",
    "xb.taecel.carrier",
    "xb.taecel.product",
    "xb.taecel.transaction",
];

/** Odoo 17 sends a many2one as [id, name]; the dialog reads it as {id, name}, like 18+. */
function m2o(value) {
    return Array.isArray(value) ? { id: value[0], name: value[1] } : value || null;
}

patch(PosStore.prototype, {
    async _processData(loadedData) {
        await super._processData(...arguments);
        this.xbTaecelData = {};
        for (const model of TAECEL_MODELS) {
            this.xbTaecelData[model] = (loadedData[model] || []).map((rec) => {
                const out = { ...rec };
                for (const key of ["account_id", "carrier_id", "currency_id", "product_id", "pos_order_id"]) {
                    if (key in out) {
                        out[key] = m2o(out[key]);
                    }
                }
                return out;
            });
        }
    },

    xbTaecelAll(model) {
        return (this.xbTaecelData && this.xbTaecelData[model]) || [];
    },

    /** The single TAECEL account loaded for this POS, if any. */
    get xbTaecelAccount() {
        return this.xbTaecelAll("xb.taecel.account")[0] || null;
    },

    get xbTaecelEnabled() {
        return Boolean(this.xbTaecelAccount);
    },

    get xbTaecelCarriers() {
        return this.xbTaecelAll("xb.taecel.carrier").filter((c) => c.active !== false);
    },

    xbTaecelCarrierById(id) {
        return this.xbTaecelAll("xb.taecel.carrier").find((c) => c.id === id) || null;
    },

    /** Fixed-amount products for a catalog carrier, cheapest first. */
    xbTaecelProductsForCarrier(carrier) {
        if (!carrier) {
            return [];
        }
        return this.xbTaecelAll("xb.taecel.product")
            .filter((p) => p.carrier_id?.id === carrier.id && p.active !== false)
            .sort((a, b) => (a.amount || 0) - (b.amount || 0));
    },

    get xbTaecelWallets() {
        return this.xbTaecelAll("xb.taecel.wallet");
    },

    xbTaecelWallet(bolsaId) {
        return this.xbTaecelWallets.find((w) => w.bolsa_id === String(bolsaId)) || null;
    },

    xbTaecelWalletBalance(bolsaId) {
        const wallet = this.xbTaecelWallet(bolsaId);
        return wallet ? wallet.balance : null;
    },

    /** Balances as they stand right now, keyed by bolsa id; null when the read fails (offline). */
    async xbTaecelFetchBalances() {
        const account = this.xbTaecelAccount;
        if (!account) {
            return null;
        }
        try {
            return await this.orm.call("xb.taecel.wallet", "xb_pos_balances", [account.id]);
        } catch {
            return null;
        }
    },

    /** Amount already committed to a wallet by the order being built. */
    xbTaecelCommitted(bolsaId) {
        const lines = this.get_order()?.get_orderlines() || [];
        return lines
            .filter((l) => l.taecel_is_taecel && String(l.taecel_bolsa_id) === String(bolsaId))
            // The wallet pays the amount plus the provider charge; the XPago and business fees stay in the till.
            .reduce(
                (sum, l) =>
                    sum + (l.get_unit_price() || 0) - (l.taecel_fee || 0) + (l.taecel_carrier_id?.provider_fee || 0),
                0
            );
    },

    /** The generic product every TAECEL line hangs off (see product_data.xml). */
    get xbTaecelProduct() {
        const products = Object.values(this.db.product_by_id || {});
        return (
            products.find((p) => p.default_code === "XBTOPUP" || p.default_code === "XBTAECEL") || null
        );
    },

    /** Add a TAECEL line at a manual price; returns the line. */
    xbTaecelAddLine(product, price, extras) {
        const order = this.get_order() || this.add_new_order();
        order.add_product(product, {
            quantity: 1,
            price,
            merge: false,
            extras: { price_type: "manual", ...extras },
        });
        return order.get_selected_orderline();
    },

    async xbOpenTaecelSale() {
        this.env.services.dialog.add(XbTaecelSaleDialog, {});
    },
});

const LINE_FIELDS = [
    "taecel_is_taecel",
    "taecel_product_code",
    "taecel_reference",
    "taecel_bolsa_id",
    "taecel_fee",
    "taecel_fee_xpago",
    "taecel_fee_merchant",
];

patch(Orderline.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        if (this.taecel_is_taecel) {
            for (const key of LINE_FIELDS) {
                json[key] = this[key];
            }
            json.taecel_carrier_id = this.taecel_carrier_id?.id || false;
        }
        return json;
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        if (json.taecel_is_taecel) {
            for (const key of LINE_FIELDS) {
                this[key] = json[key];
            }
            this.taecel_carrier_id =
                this.pos.xbTaecelCarrierById?.(json.taecel_carrier_id) ||
                (json.taecel_carrier_id ? { id: json.taecel_carrier_id } : null);
        }
    },

    clone() {
        const line = super.clone(...arguments);
        for (const key of [...LINE_FIELDS, "taecel_carrier_id"]) {
            line[key] = this[key];
        }
        return line;
    },
});
