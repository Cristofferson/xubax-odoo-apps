/** TAECEL sale flow, as a POS dialog.
 *
 *  Steps: pick carrier -> pick amount (catalog carriers) or type amount
 *  (free-amount carriers) -> capture and validate the reference -> add the
 *  line to the current order. It never contacts TAECEL: dispatch happens
 *  server-side once the transactional API is on file. This dialog only builds
 *  a correct, validated order line.
 */
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { usePos } from "../compat";

const FORMAT_NUMERIC = "1";
const FORMAT_EMAIL = "3";

export class XbTaecelSaleDialog extends Component {
    static template = "xb_pos_taecel.SaleDialog";
    static components = { Dialog };
    static props = { close: Function };

    setup() {
        this.pos = usePos();
        this.state = useState({
            step: "carrier", // carrier | amount | reference
            carrier: null,
            product: null, // catalog: chosen product; free: null
            amount: 0,
            reference: "",
            referenceConfirm: "",
            error: "",
        });
    }

    // -- data ------------------------------------------------------------
    get dialogTitle() {
        return _t("Airtime & Bill Payments");
    }

    get carriers() {
        return this.pos.xbTaecelCarriers;
    }

    /** Carriers grouped by their category, for a tidy picker. */
    get carrierGroups() {
        const groups = {};
        for (const carrier of this.carriers) {
            const key = carrier.category || _t("Other");
            (groups[key] ||= []).push(carrier);
        }
        return Object.entries(groups).map(([name, carriers]) => ({ name, carriers }));
    }

    get products() {
        return this.pos.xbTaecelProductsForCarrier(this.state.carrier);
    }

    get isCatalog() {
        return this.state.carrier && this.state.carrier.carrier_type !== "1";
    }

    get customerFee() {
        return this.state.carrier?.customer_fee || 0;
    }

    get total() {
        return (this.state.amount || 0) + this.customerFee;
    }

    get walletWarning() {
        const carrier = this.state.carrier;
        if (!carrier) {
            return null;
        }
        const balance = this.pos.xbTaecelWalletBalance(carrier.bolsa_id);
        if (balance !== null && this.total > balance) {
            return _t("This wallet has only %s left.", this.formatCurrency(balance));
        }
        return null;
    }

    formatCurrency(value) {
        return this.pos.env.utils.formatCurrency(value);
    }

    // -- navigation ------------------------------------------------------
    selectCarrier(carrier) {
        this.state.carrier = carrier;
        this.state.product = null;
        this.state.amount = 0;
        this.state.reference = "";
        this.state.referenceConfirm = "";
        this.state.error = "";
        this.state.step = this.isCatalog ? "amount" : "reference";
    }

    selectProduct(product) {
        this.state.product = product;
        this.state.amount = product.amount;
        this.state.step = "reference";
    }

    back() {
        this.state.error = "";
        if (this.state.step === "reference") {
            this.state.step = this.isCatalog ? "amount" : "carrier";
        } else if (this.state.step === "amount") {
            this.state.step = "carrier";
        }
    }

    // -- validation ------------------------------------------------------
    /** Validate the reference against the carrier's Campos spec. Returns an
     *  error string, or "" when the reference is acceptable. */
    validateReference() {
        const carrier = this.state.carrier;
        const ref = (this.state.reference || "").trim();
        if (carrier?.field_required && !ref) {
            return _t("Enter the %s.", carrier.field_label || _t("reference"));
        }
        const min = carrier?.field_min || 0;
        const max = carrier?.field_max || 0;
        if (min && ref.length < min) {
            return _t("The %(label)s needs at least %(n)s characters.", {
                label: carrier.field_label || _t("reference"),
                n: min,
            });
        }
        if (max && ref.length > max) {
            return _t("The %(label)s allows at most %(n)s characters.", {
                label: carrier.field_label || _t("reference"),
                n: max,
            });
        }
        const fmt = carrier?.field_format;
        if (fmt === FORMAT_NUMERIC && ref && !/^\d+$/.test(ref)) {
            return _t("The %s must be numeric.", carrier.field_label || _t("reference"));
        }
        if (fmt === FORMAT_EMAIL && ref && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(ref)) {
            return _t("Enter a valid email.");
        }
        if (carrier?.field_confirm && ref !== (this.state.referenceConfirm || "").trim()) {
            return _t("The two references do not match.");
        }
        if (!this.isCatalog && this.state.amount <= 0) {
            return _t("Enter an amount greater than zero.");
        }
        return "";
    }

    // -- confirm ---------------------------------------------------------
    async confirm() {
        const error = this.validateReference();
        if (error) {
            this.state.error = error;
            return;
        }
        const product = this.pos.xbTaecelProduct;
        if (!product) {
            this.state.error = _t(
                "The TAECEL sale product is missing. Reinstall the module or "
                + "contact support."
            );
            return;
        }
        const carrier = this.state.carrier;
        const reference = (this.state.reference || "").trim();
        const label = `${carrier.name} ${this.formatCurrency(this.state.amount)} · ${reference}`;

        // Manual price (amount + fee): passing price_unit makes the line
        // price_type "manual", so no pricelist recompute overrides it.
        //
        // Odoo 19's addLineToOrder builds the line from ``product_tmpl_id`` (a
        // product.template) -- it reads taxes_id off it and picks the variant
        // itself. Odoo 18 took ``product_id`` (a variant). xbTaecelProduct
        // returns whichever the running version loads, so route it to the key
        // that version expects (templates expose product_variant_ids).
        const productKey =
            "product_variant_ids" in product ? "product_tmpl_id" : "product_id";
        const line = await this.pos.addLineToCurrentOrder(
            {
                [productKey]: product,
                qty: 1,
                price_unit: this.total,
                taecel_is_taecel: true,
                taecel_carrier_id: carrier,
                taecel_product_code: this.state.product?.code || "",
                taecel_reference: reference,
                taecel_bolsa_id: carrier.bolsa_id,
                taecel_fee: this.customerFee,
            },
            {}
        );
        if (line) {
            // Two different fields, because the POS reads two different ones:
            //   * the receipt prints ``full_product_name``;
            //   * the on-screen orderline prints ``product_id.name`` and, under
            //     it, ``customer_note``.
            // Assign full_product_name directly -- ``setFullProductName()``
            // takes no argument in Odoo 19: it recomputes the name from the
            // product and would silently drop the label.
            line.full_product_name = label;
            const note = `${carrier.name} · ${reference}`;
            if (line.setCustomerNote) {
                line.setCustomerNote(note);
            } else {
                line.customer_note = note;
            }
        }
        this.props.close();
    }
}
