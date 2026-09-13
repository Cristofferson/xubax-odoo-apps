/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS
// Asks, for each quotation created from the POS, how the customer wants it:
// printed, by WhatsApp, by email, or any combination. The POS store opens it right
// after the cashier picks "Quotation" and BEFORE anything is created, so "Cancel"
// leaves the cart untouched. Whatever the channel, the customer gets the same
// ticket the POS prints.

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { isValidEmail } from "@point_of_sale/utils";

// Same loose check as the native receipt screen: the real authority is WhatsApp's
// own formatter, server-side, with the customer's country.
const PHONE_RE = /^\+?[()\d\s-.]{8,18}$/;

const digits = (value) => (value || "").replace(/\D/g, "");

export class XbQuotationDeliveryPopup extends Component {
    static template = "xb_sale_order_from_pos.XbQuotationDeliveryPopup";
    static components = { Dialog };
    static props = {
        partnerName: { type: String, optional: true },
        email: { type: String, optional: true },
        phone: { type: String, optional: true },
        allowWhatsapp: { type: Boolean, optional: true },
        print: { type: Boolean, optional: true },
        getPayload: Function,
        close: Function,
    };
    static defaultProps = {
        partnerName: "",
        email: "",
        phone: "",
        allowWhatsapp: false,
        print: true,
    };

    setup() {
        this.state = useState({
            print: this.props.print,
            whatsapp: false,
            email: false,
            phoneValue: this.props.phone,
            emailValue: this.props.email,
        });
    }

    get phoneError() {
        return this.state.whatsapp && !PHONE_RE.test(this.state.phoneValue.trim());
    }

    get emailError() {
        return this.state.email && !isValidEmail(this.state.emailValue.trim());
    }

    get canConfirm() {
        return !this.phoneError && !this.emailError;
    }

    get nothingChosen() {
        return !this.state.print && !this.state.whatsapp && !this.state.email;
    }

    // Tell the cashier what happens to the customer's contact with what she typed,
    // mirroring the backend rule: an empty field is filled, an existing one is
    // never overwritten (a different value is used for this send only).
    get phoneHint() {
        const typed = this.state.phoneValue.trim();
        if (!typed) {
            return "";
        }
        if (!this.props.phone) {
            return _t("It will be saved on the customer's contact.");
        }
        if (digits(typed) !== digits(this.props.phone)) {
            return _t("Only this time: the customer's contact keeps %s.", this.props.phone);
        }
        return "";
    }

    get emailHint() {
        const typed = this.state.emailValue.trim();
        if (!typed) {
            return "";
        }
        if (!this.props.email) {
            return _t("It will be saved on the customer's contact.");
        }
        if (typed.toLowerCase() !== this.props.email.trim().toLowerCase()) {
            return _t("Only this time: the customer's contact keeps %s.", this.props.email);
        }
        return "";
    }

    confirm() {
        if (!this.canConfirm) {
            return;
        }
        this.props.getPayload({
            print: this.state.print,
            phone: this.state.whatsapp ? this.state.phoneValue.trim() : false,
            email: this.state.email ? this.state.emailValue.trim() : false,
        });
        this.props.close();
    }
}
