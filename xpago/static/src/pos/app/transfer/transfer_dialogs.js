/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { Component, onWillUnmount, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";
import { formatClabe, minutesLeft } from "@xpago/pos/app/transfer/transfer_utils";

/** Who pays: XPago makes the CLABE out to them and emails them the transfer details. */
export class XpagoTransferCustomerDialog extends Component {
    static template = "xpago.TransferCustomerDialog";
    static components = { Dialog };
    static props = ["defaults", "amount", "getPayload", "close"];

    setup() {
        this.state = useState({ ...this.props.defaults, tried: false });
    }

    get title() {
        return _t("Pay by transfer: who pays?");
    }

    get errors() {
        const errors = {};
        if (!this.state.name.trim()) {
            errors.name = true;
        }
        if (!/^\S+@\S+\.\S+$/.test(this.state.email.trim())) {
            errors.email = true;
        }
        if (this.state.phone.replace(/\D/g, "").length < 10) {
            errors.phone = true;
        }
        return errors;
    }

    confirm() {
        this.state.tried = true;
        if (Object.keys(this.errors).length) {
            return;
        }
        this.props.getPayload({
            name: this.state.name.trim(),
            email: this.state.email.trim(),
            phone: this.state.phone.trim(),
        });
        this.props.close();
    }
}

/** The CLABE of the sale, big, while the customer transfers. The register keeps asking behind it. */
export class XpagoTransferDialog extends Component {
    static template = "xpago.TransferDialog";
    static components = { Dialog };
    static props = ["entry", "renew", "cancel", "hide", "print", "close"];

    setup() {
        this.view = useState(this.props.entry.view);
        this.clock = useState({ now: Date.now() });
        const timer = setInterval(() => (this.clock.now = Date.now()), 15000);
        onWillUnmount(() => clearInterval(timer));
    }

    get title() {
        return _t("Payment by transfer (SPEI)");
    }

    get clabeText() {
        return formatClabe(this.view.clabe);
    }

    get minutes() {
        return minutesLeft(this.view.expires_at, this.clock.now);
    }

    get partly() {
        return this.view.amount_received > 0 && this.view.amount_due > 0;
    }

    get qrUrl() {
        if (!this.view.checkout_url) {
            return "";
        }
        const value = encodeURIComponent(this.view.checkout_url);
        return `/report/barcode?barcode_type=QR&value=${value}&width=200&height=200`;
    }

    money(value) {
        return this.env.utils.formatCurrency(value || 0);
    }

    async copy() {
        try {
            await navigator.clipboard.writeText(this.view.clabe);
            this.env.services.notification.add(_t("CLABE copied"), { type: "success" });
        } catch {
            this.env.services.notification.add(_t("Could not copy: dictate it or print it."), { type: "warning" });
        }
    }
}

/** A slip with the CLABE, for a customer who would rather take it on paper. Odoo 17: the receipt header takes the
 *  header data of the order. */
export class XpagoClabeReceipt extends Component {
    static template = "xpago.ClabeReceipt";
    static components = { ReceiptHeader };
    static props = ["headerData", "view", "amountText", "clabeText", "expiresText"];
}
