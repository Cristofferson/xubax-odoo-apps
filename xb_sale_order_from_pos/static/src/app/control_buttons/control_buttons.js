/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 2 frontend)
// Original, clean-room implementation. Adds a control button to create a
// Quotation / Order / Layaway from the current POS cart by calling the backend
// method sale.order.xb_create_order_from_pos. It does NOT replace the native
// pos_sale loader button ("Quotation/Order").

import { Component } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { OrderReceipt } from "@point_of_sale/app/screens/receipt_screen/receipt/order_receipt";
import { XbQuotationDeliveryPopup } from "@xb_sale_order_from_pos/app/components/xb_quotation_delivery_popup/xb_quotation_delivery_popup";
import { XbDeliveryDatePopup } from "@xb_sale_order_from_pos/app/components/xb_delivery_date_popup/xb_delivery_date_popup";

export class XbCreateSaleOrderButton extends Component {
    static template = "xb_sale_order_from_pos.XbCreateSaleOrderButton";

    setup() {
        this.pos = usePos();
    }

    /**
     * Build the order-type options offered to the cashier, honoring the per-POS
     * toggles. Each entry's `item` is the flag set sent to the backend.
     * - "Quotation"      iff xb_allow_quotation.
     * - xb_differentiate_order_layaway OFF -> single "Order / Layaway"
     *   (confirmed; advance is optional, added later via the native flow).
     * - xb_differentiate_order_layaway ON  -> "Order" (confirmed, no advance)
     *   and "Layaway" (confirmed, with advance).
     */
    xbGetOrderTypeOptions() {
        const config = this.pos.config;
        const options = [];

        if (config.xb_allow_quotation) {
            options.push({
                id: "quotation",
                label: _t("Quotation"),
                item: { type: "quotation", confirm: false, with_down_payment: false },
            });
        }

        if (config.xb_differentiate_order_layaway) {
            options.push({
                id: "order",
                label: _t("Order"),
                item: { type: "order", confirm: true, with_down_payment: false },
            });
            options.push({
                id: "layaway",
                label: _t("Layaway"),
                item: { type: "layaway", confirm: true, with_down_payment: true },
            });
        } else {
            options.push({
                id: "order_layaway",
                label: _t("Order / Layaway"),
                item: { type: "order_layaway", confirm: true, with_down_payment: false },
            });
        }

        // Honor xb_default_so_state by pre-highlighting the matching entry:
        // "draft" -> Quotation (if offered); "sale" -> first confirmed option.
        const wantDraft = config.xb_default_so_state === "draft";
        const firstConfirmed = options.find((o) => o.item.confirm);
        for (const opt of options) {
            opt.isSelected = wantDraft ? opt.id === "quotation" : opt === firstConfirmed;
        }
        if (!options.some((o) => o.isSelected) && options.length) {
            options[0].isSelected = true;
        }

        return options;
    }

    /**
     * Conservatively drop integration metadata from a POS line customer note.
     * In some deployments line customer notes are auto-filled with bin/product tags
     * like "[B3] articulo_mb=3SJ041 solo_metal variante_unica". If the text starts
     * with a "[B<n>]" bin tag AND also carries one of the integration markers
     * (articulo_mb=, sintetica/sin_codigo, OBSERV:), it is pure metadata and we
     * return "". Otherwise the text is returned unchanged.
     */
    xbSanitizeCustomerNote(txt) {
        const text = txt || "";
        const hasBinTag = /^\s*\[B\d+\]/.test(text);
        const hasMarker =
            text.includes("articulo_mb=") ||
            text.includes("sintetica/sin_codigo") ||
            text.includes("OBSERV:");
        return hasBinTag && hasMarker ? "" : text;
    }

    /**
     * Build the backend payload from the current order, forcing the EXACT POS
     * taxes (already mapped by the fiscal position) for 1:1 parity.
     */
    xbBuildOrderPayload(order) {
        const fp = order.fiscal_position;
        const lines = order.get_orderlines().map((line) => ({
            product_id: line.get_product().id,
            qty: line.get_quantity(),
            // Same unit price semantics as sale.order.line (taxes included or not
            // according to the taxes themselves).
            price_unit: line.get_unit_price(),
            discount: line.get_discount(),
            tax_ids: line._getProductTaxesAfterFiscalPosition().map((tax) => tax.id),
            customer_note: this.xbSanitizeCustomerNote(line.get_customer_note()),
            internal_note: line.getNote?.() || line.note || "",
        }));

        return {
            pos_config_id: this.pos.config.id,
            partner_id: order.get_partner().id,
            pricelist_id: order.pricelist ? order.pricelist.id : false,
            fiscal_position_id: fp ? fp.id : false,
            // Odoo 17's register has no order-level notes.
            note: "",
            internal_note: "",
            lines,
            amount_total: round_pr(order.get_total_with_tax(), this.pos.currency.rounding),
        };
    }

    async click() {
        const order = this.pos.get_order();
        if (!order) {
            return;
        }
        const popup = this.pos.popup;

        if (!order.get_partner()) {
            popup.add(ErrorPopup, {
                title: _t("Missing customer"),
                body: _t("Select a customer before creating the order."),
            });
            return;
        }

        if (!order.get_orderlines().length) {
            popup.add(ErrorPopup, {
                title: _t("Empty order"),
                body: _t("Add at least one product before creating the order."),
            });
            return;
        }

        // This cart may already have raised its order elsewhere: another module
        // can create one from the same cart and stash it here. A second document
        // for the same goods is never what anybody wanted. Our own flow discards the
        // cart right after creating, so this cannot fire on a repeat click.
        const pending = order.xbSaleOrder;
        if (pending?.sale_order_id) {
            popup.add(ErrorPopup, {
                title: _t("This cart already has an order"),
                body: _t(
                    "%s was already created from these products. Charge or " +
                        "edit that one instead of raising a second document " +
                        "for the same goods.",
                    pending.name || ""
                ),
            });
            return;
        }

        // Read the cart into a PLAIN payload before any popup.
        const basePayload = this.xbBuildOrderPayload(order);

        // Choose the order type. Skip the popup when there is a single option.
        const options = this.xbGetOrderTypeOptions();
        let choice;
        if (options.length === 1) {
            choice = options[0].item;
        } else {
            const { confirmed, payload } = await popup.add(SelectionPopup, {
                title: _t("Create from POS"),
                list: options,
            });
            if (!confirmed || !payload) {
                return;
            }
            choice = payload;
        }

        await this.pos.xbCreateOrderFromPos({
            ...basePayload,
            type: choice.type,
            confirm: choice.confirm,
            with_down_payment: choice.with_down_payment,
        });
    }
}

ProductScreen.addControlButton({
    component: XbCreateSaleOrderButton,
    condition: function () {
        return this.pos.config.xb_enable_sale_order;
    },
});

patch(PosStore.prototype, {
    /**
     * Create the Sale Order from a fully-plain POS payload. Lives on the POS store,
     * which outlives the button component.
     *
     * @param {Object} payload Plain, already-serialized data (no reactive refs).
     */
    async xbCreateOrderFromPos(payload) {
        // The down-payment product may not be available in the POS; the backend guard
        // (sale.order.xb_create_order_from_pos) remains the authority.
        if (payload.with_down_payment && !this.config.down_payment_product_id) {
            this.popup.add(ErrorPopup, {
                title: _t("Down-payment product missing"),
                body: _t(
                    "To register a layaway advance, set the down-payment product first:\n" +
                        "Point of Sale ▸ Settings ▸ this POS ▸ Down Payment Product."
                ),
            });
            return;
        }

        // Delivery date, for orders and layaways only (a quotation commits to
        // nothing yet): proposed with Odoo's probable date and editable; "No date"
        // leaves it empty. Discarding the window cancels, with the cart intact.
        if (payload.type !== "quotation") {
            const deliveryDate = await this.xbAskDeliveryDate(payload);
            if (deliveryDate === undefined) {
                return;
            }
            payload = { ...payload, commitment_date: deliveryDate || false };
        }

        // Quotation delivery: ask, for THIS quotation, how the customer wants it
        // (printed / WhatsApp / email, any combination). Asked BEFORE creating, so
        // "Cancel" leaves the cart intact and nothing is created.
        let delivery = null;
        if (payload.type === "quotation" && this.config.xb_ask_quotation_delivery) {
            delivery = await this.xbAskQuotationDelivery(payload.partner_id);
            if (!delivery) {
                return;
            }
        }
        const wantsSending = Boolean(delivery && (delivery.phone || delivery.email));
        const notification = this.env.services.pos_notification;

        try {
            const result = await this.orm.call("sale.order", "xb_create_order_from_pos", [
                payload,
            ]);
            notification.add(_t("%s created from POS.", result.name), 4000);
            // [Phase 3] Stash the SO totals + portal URL on the order so the receipt
            // can show Total / Down payment / Balance and the online link.
            const createdOnOrder = this.get_order();
            let ticketImage = false;
            if (createdOnOrder) {
                createdOnOrder.xbSaleOrder = {
                    sale_order_id: result.sale_order_id,
                    name: result.name,
                    state: result.state,
                    amount_total: result.amount_total,
                    amount_unpaid: result.amount_unpaid,
                    portal_url: result.portal_url,
                    partner_ref: result.partner_ref,
                    commitment_date: result.commitment_date || false,
                    layaway_deadline: result.layaway_deadline || false,
                    type: payload.type,
                };
                // Gated by the per-POS toggle xb_autoprint_on_create, or, when the
                // cashier was asked how to deliver this quotation, by her answer.
                const shouldPrint = delivery ? delivery.print : this.config.xb_autoprint_on_create;
                if (shouldPrint) {
                    // xb_duplicate_receipt_on_create: print the SAME ticket twice (one
                    // for the customer, one for the shop). A QUOTATION is always
                    // printed ONCE.
                    const isQuotation = payload.type === "quotation";
                    const copies =
                        this.config.xb_duplicate_receipt_on_create && !isQuotation ? 2 : 1;
                    for (let copy = 1; copy <= copies; copy++) {
                        // A print failure must NEVER abort the flow: the Sale Order is
                        // already created; the cashier can reprint.
                        try {
                            await this.env.services.printer.print(
                                OrderReceipt,
                                {
                                    data: createdOnOrder.export_for_printing(),
                                    formatCurrency: this.env.utils.formatCurrency,
                                },
                                { webPrintFallback: true }
                            );
                        } catch (printErr) {
                            console.warn(
                                `[xb] autoprint copy ${copy}/${copies} failed (order already created):`,
                                printErr
                            );
                            break;
                        }
                    }
                }
                // The customer gets the SAME ticket the POS prints: draw it while the
                // cart still exists (it is discarded right below).
                if (wantsSending) {
                    ticketImage = await this.xbRenderTicketImage(createdOnOrder);
                }
            }
            // Discard the consumed cart for ALL three types and open a fresh empty
            // one (after the receipt has been printed above). The advance is
            // collected by recovering the SO with the native flow.
            const consumed = this.get_order();
            this.add_new_order();
            if (consumed) {
                this.removeOrder(consumed, false);
            }
            if (wantsSending) {
                await this.xbSendOrderFromPos(result, delivery, ticketImage);
            }
        } catch (error) {
            const message =
                error?.data?.message || error?.message || _t("Could not create the order.");
            this.popup.add(ErrorPopup, {
                title: _t("Could not create the order"),
                body: message,
            });
        }
    },

    /**
     * Ask the delivery date. Resolves to "YYYY-MM-DD", "" for no date, or undefined
     * when the cashier discards the window. Starts on the probable date Odoo computes
     * from the products' lead times; if that cannot be read, on today.
     */
    async xbAskDeliveryDate(payload) {
        let probable = "";
        try {
            probable = await this.orm.call("sale.order", "xb_pos_expected_delivery_date", [
                payload.lines.map((line) => line.product_id),
            ]);
        } catch (error) {
            console.warn("[xb] could not compute the probable delivery date:", error);
        }
        const { confirmed, payload: date } = await this.popup.add(XbDeliveryDatePopup, {
            ...(probable ? { defaultDate: probable } : {}),
        });
        return confirmed ? date : undefined;
    },

    /**
     * Ask how the customer wants THIS quotation. Resolves to {print, phone, email}
     * (phone / email are false when that channel was not chosen), or undefined when
     * the cashier cancels.
     */
    async xbAskQuotationDelivery(partnerId) {
        const partner = this.db.get_partner_by_id(partnerId);
        const { confirmed, payload } = await this.popup.add(XbQuotationDeliveryPopup, {
            partnerName: partner?.name || "",
            phone: partner?.phone || partner?.mobile || "",
            email: partner?.email || "",
            // WhatsApp needs the optional WhatsApp add-on, which adds a per-POS
            // template; it does not exist on Odoo 17, so the channel stays hidden.
            allowWhatsapp: Boolean(this.config.xb_quotation_wa_template_id),
            print: Boolean(this.config.xb_autoprint_on_create),
        });
        return confirmed ? payload : undefined;
    },

    /**
     * The printed ticket as a base64 JPEG: same component and data as the printed
     * one, same classes as the native "send receipt by email". False when it cannot
     * be drawn.
     */
    async xbRenderTicketImage(order) {
        try {
            return await this.env.services.renderer.toJpeg(
                OrderReceipt,
                {
                    data: order.export_for_printing(),
                    formatCurrency: this.env.utils.formatCurrency,
                },
                { addClass: "pos-receipt-print p-3" }
            );
        } catch (renderErr) {
            console.warn("[xb] could not draw the quotation ticket:", renderErr);
            return false;
        }
    },

    /**
     * Send the just-created quotation's ticket by WhatsApp and/or email. Never
     * throws: the quotation already exists, so a failure is reported to the cashier
     * and the POS carries on.
     */
    async xbSendOrderFromPos(result, delivery, ticketImage) {
        const name = result.name;
        const notification = this.env.services.pos_notification;
        const sendLater = _t("The quotation is saved: you can send it from the Sales app.");
        if (!ticketImage) {
            this.popup.add(ErrorPopup, {
                title: _t("%s was not sent", name),
                body:
                    _t("The ticket image could not be generated, so nothing was sent.") +
                    "\n\n" +
                    sendLater,
            });
            return;
        }
        notification.add(_t("Sending %s…", name), 3000);
        let outcome;
        try {
            outcome = await this.orm.call("sale.order", "xb_send_order_from_pos", [
                [result.sale_order_id],
                {
                    pos_config_id: this.config.id,
                    ticket_image: ticketImage,
                    phone: delivery.phone || false,
                    email: delivery.email || false,
                },
            ]);
        } catch (error) {
            this.popup.add(ErrorPopup, {
                title: _t("%s was not sent", name),
                body: (error?.data?.message || error?.message || "") + "\n\n" + sendLater,
            });
            return;
        }
        const failures = [];
        for (const [channel, res] of Object.entries(outcome || {})) {
            const isWhatsapp = channel === "whatsapp";
            if (res.ok) {
                notification.add(
                    isWhatsapp
                        ? _t("%(name)s sent by WhatsApp to %(to)s.", { name, to: res.to })
                        : _t("%(name)s sent by email to %(to)s.", { name, to: res.to }),
                    4000
                );
            } else {
                failures.push(
                    isWhatsapp
                        ? _t("WhatsApp (%(to)s): %(error)s", { to: res.to, error: res.error })
                        : _t("Email (%(to)s): %(error)s", { to: res.to, error: res.error })
                );
            }
        }
        if (failures.length) {
            this.popup.add(ErrorPopup, {
                title: _t("%s could not be sent", name),
                body: failures.join("\n\n") + "\n\n" + sendLater,
            });
        }
    },
});
