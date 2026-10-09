/**
 * Cotización desde el kiosco: el cliente deja su nombre y celular y se lleva la
 * cotización impresa (en la impresora del kiosco) y/o la recibe por WhatsApp. Se crea
 * igual que las cotizaciones de la caja.
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { CartPage } from "@pos_self_order/app/pages/cart_page/cart_page";

export class XbQuoteTicket extends Component {
    static template = "xb_self_order_quotation.Ticket";
    static props = { src: String };
}

export class XbQuoteDialog extends Component {
    static template = "xb_self_order_quotation.Dialog";
    static props = { modo: String, close: Function };

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        const modos = this.selfOrder.config._xb_quotation || {};
        this.modos = modos;
        this.privacyUrl = modos.privacy_url || false;
        this.state = useState({
            name: "",
            phone: "",
            privacy: false,
            print: this.props.modo === "print" && modos.print,
            whatsapp: this.props.modo === "whatsapp" && modos.whatsapp,
            sending: false,
            error: "",
            done: null,
            typing: false,
            keyboard: 0,
            visibleHeight: 0,
        });
        this.dialogRef = useRef("dialog");
        this.field2Ref = useRef("field2");
        // Tablets in kiosk mode have no system "back" key: the on-screen keyboard covers
        // the bottom of the screen and cannot be dismissed. Follow the visible viewport
        // to keep the dialog above the keyboard, and offer a button to hide it.
        const vv = window.visualViewport;
        const onViewport = () => {
            if (!vv) {
                return;
            }
            this.state.keyboard = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
            this.state.visibleHeight = Math.round(vv.height);
        };
        const onFocus = (ev) => {
            if (ev.target.matches?.(".xb_quote_dialog input:not([type=checkbox])")) {
                this.state.typing = true;
                setTimeout(() => ev.target.scrollIntoView({ block: "nearest" }), 300);
            }
        };
        const onBlur = () => {
            setTimeout(() => {
                const el = document.activeElement;
                this.state.typing = Boolean(el?.matches?.(".xb_quote_dialog input:not([type=checkbox])"));
            }, 0);
        };
        onMounted(() => {
            vv?.addEventListener("resize", onViewport);
            vv?.addEventListener("scroll", onViewport);
            document.addEventListener("focusin", onFocus);
            document.addEventListener("focusout", onBlur);
            onViewport();
        });
        onWillUnmount(() => {
            vv?.removeEventListener("resize", onViewport);
            vv?.removeEventListener("scroll", onViewport);
            document.removeEventListener("focusin", onFocus);
            document.removeEventListener("focusout", onBlur);
        });
    }

    get dialogStyle() {
        const { keyboard, visibleHeight } = this.state;
        if (!keyboard) {
            return "";
        }
        return `bottom: ${keyboard}px !important; max-height: ${Math.round(visibleHeight * 0.95)}px;`;
    }

    hideKeyboard() {
        document.activeElement?.blur();
        this.state.typing = false;
    }

    onKeydown(ev, action) {
        if (ev.key !== "Enter") {
            return;
        }
        ev.preventDefault();
        if (action === "next") {
            this.field2Ref.el?.focus();
        } else {
            this.hideKeyboard();
        }
    }

    onDialogPointerDown(ev) {
        // Touching the dialog outside the fields hides the keyboard.
        if (!ev.target.closest("input, button, label, a")) {
            this.hideKeyboard();
        }
    }

    get digits() {
        return (this.state.phone || "").replace(/\D/g, "");
    }

    get canSend() {
        const s = this.state;
        return (
            // The server checks the number with the rules of the company's country.
            !s.sending && s.privacy && s.name.trim().length >= 2 && this.digits.length >= 7 &&
            (s.print || s.whatsapp)
        );
    }

    lines() {
        return this.selfOrder.currentOrder.lines
            .filter((l) => !l.combo_parent_id && l.product_id?.product_tmpl_id)
            .map((l) => ({
                template_id: l.product_id.product_tmpl_id.id,
                ptav_ids: [
                    ...(l.product_id.product_template_attribute_value_ids || []),
                    ...(l.attribute_value_ids || []),
                ].map((v) => v.id),
                qty: l.qty,
            }));
    }

    async send() {
        if (!this.canSend) {
            return;
        }
        const s = this.state;
        s.sending = true;
        s.error = "";
        try {
            const res = await rpc("/xb_kiosk/quotation", {
                access_token: this.selfOrder.access_token,
                name: s.name,
                phone: s.phone,
                lines: this.lines(),
                send_whatsapp: s.whatsapp,
            });
            if (!res?.ok) {
                s.error = res?.error || _t("The quotation could not be made. Please ask at the counter.");
                return;
            }
            let impresa = false;
            if (s.print && res.image) {
                try {
                    // A printer that does not answer must not leave the customer waiting.
                    const limite = new Promise((resolve) => setTimeout(() => resolve(false), 20000));
                    impresa = Boolean(
                        await Promise.race([
                            this.selfOrder.printer.print(XbQuoteTicket, {
                                src: "data:image/jpeg;base64," + res.image,
                            }),
                            limite,
                        ])
                    );
                } catch {
                    impresa = false;
                }
            }
            s.done = {
                name: res.name,
                customer: res.customer.split(" ")[0],
                whatsapp: res.whatsapp === true,
                whatsappFailed: s.whatsapp && res.whatsapp !== true,
                printed: s.print && impresa,
                printFailed: s.print && !impresa,
            };
        } catch {
            s.error = _t("The quotation could not be made. Please ask at the counter.");
        } finally {
            s.sending = false;
        }
    }

    finish() {
        this.selfOrder.cancelOrder();
        this.props.close();
        this.router.navigate("default");
    }
}

patch(CartPage.prototype, {
    get xbQuotation() {
        const modos = this.selfOrder.config._xb_quotation || {};
        return modos.print || modos.whatsapp ? modos : null;
    },
    xbQuote(modo) {
        this.dialog.add(XbQuoteDialog, { modo });
    },
});
