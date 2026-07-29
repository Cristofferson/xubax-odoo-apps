/** @odoo-module **/
// XUBAX - Jewelry Repairs & Workshop, Point of Sale bridge.
// The signature pad the counter uses at the three moments that matter:
// taking a piece in, handing it to a jeweler, and giving it back.
//
// It wraps the native NameAndSignature component rather than a canvas of our
// own, so the pad behaves exactly like every other signature in Odoo and keeps
// working when the framework changes underneath.

import { Component, useState, markup } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { NameAndSignature } from "@web/core/signature/name_and_signature";
import { _t } from "@web/core/l10n/translation";

export class JewelrySignaturePopup extends Component {
    static template = "xb_jewelry_service_pos.JewelrySignaturePopup";
    static components = { Dialog, NameAndSignature };
    static props = {
        title: { type: String, optional: true },
        subtitle: { type: String, optional: true },
        terms: { type: String, optional: true },
        defaultName: { type: String, optional: true },
        required: { type: Boolean, optional: true },
        getPayload: { type: Function },
        close: { type: Function },
    };
    static defaultProps = {
        title: _t("Signature"),
        subtitle: "",
        terms: "",
        defaultName: "",
        required: true,
    };

    setup() {
        // NameAndSignature fills these accessors in once its canvas is mounted.
        this.signature = useState({
            name: this.props.defaultName,
            isSignatureEmpty: true,
            getSignatureImage: () => "",
            resetSignature: () => {},
        });
        this.state = useState({ warn: false });
    }

    /**
     * The terms are rich text written by the shop's own manager in the
     * settings, and are meant to be read by the customer as a paragraph, not
     * shown as a string of tags. They never come from the customer, so
     * rendering them as markup is the same trust the printed receipt gives
     * them.
     */
    get termsMarkup() {
        return this.props.terms ? markup(this.props.terms) : "";
    }

    get nameAndSignatureProps() {
        // "draw" forces the hand drawn pad: a typed name is not a signature,
        // and what protects the shop is the customer's own stroke.
        return {
            signature: this.signature,
            signatureType: "signature",
            mode: "draw",
        };
    }

    confirm() {
        if (this.props.required && this.signature.isSignatureEmpty) {
            this.state.warn = true;
            return;
        }
        const dataUrl = this.signature.isSignatureEmpty
            ? ""
            : this.signature.getSignatureImage();
        this.props.getPayload({
            name: this.signature.name || this.props.defaultName || "",
            signature: dataUrl ? dataUrl.split(",")[1] : "",
        });
        this.props.close();
    }

    cancel() {
        this.props.close();
    }
}
