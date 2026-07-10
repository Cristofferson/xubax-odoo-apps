/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

/**
 * Capture Special Date popup.
 *
 * Shown to the cashier when a product whose POS category triggers a
 * special-date capture is added to the order AND the order has a
 * customer assigned.
 *
 * A product may belong to several trigger categories, each mapped to a
 * different event type. In that case `choices` holds more than one entry
 * and the popup lets the cashier pick which event applies.
 *
 * Props expected:
 *   partnerName  - display name of the customer
 *   choices      - [{wishTypeId, name, icon}], at least one entry. When
 *                  more than one, a selector is shown.
 *   defaultDate  - ISO 'YYYY-MM-DD' string (next Saturday)
 *   onConfirm(date, wishTypeId) - async fn called with the chosen date and
 *                                 the selected wish type if user accepts
 *   onLater()       - fn called if user clicks "Later" (keeps pending)
 *   onDismiss()     - fn called if user clicks "Doesn't apply" (clears pending)
 */
export class CaptureSpecialDatePopup extends Component {
    static template = "xb_special_dates.CaptureSpecialDatePopup";
    static components = { Dialog };
    static props = {
        partnerName: String,
        choices: Array,
        defaultDate: String,
        onConfirm: Function,
        onLater: Function,
        onDismiss: Function,
        close: Function,
    };

    setup() {
        this.state = useState({
            date: this.props.defaultDate,
            wishTypeId: this.props.choices[0].wishTypeId,
            busy: false,
        });
        this.notification = useService("notification");
    }

    /** True when the product matched more than one event type. */
    get multiple() {
        return this.props.choices.length > 1;
    }

    /** The currently selected choice (drives header icon and the text). */
    get selectedChoice() {
        return (
            this.props.choices.find(
                (c) => c.wishTypeId === this.state.wishTypeId
            ) || this.props.choices[0]
        );
    }

    /** Formatted version of the chosen date for display purposes. */
    get formattedDate() {
        if (!this.state.date) return "";
        try {
            const d = new Date(this.state.date + "T00:00:00");
            return d.toLocaleDateString(undefined, {
                weekday: "long",
                year: "numeric",
                month: "long",
                day: "numeric",
            });
        } catch (e) {
            return this.state.date;
        }
    }

    onSelectChoice(wishTypeId) {
        this.state.wishTypeId = wishTypeId;
    }

    onDateChange(ev) {
        this.state.date = ev.target.value;
    }

    async onClickConfirm() {
        if (this.state.busy) return;
        if (!this.state.date) {
            this.notification.add(_t("Please pick a date."), { type: "warning" });
            return;
        }
        if (!this.state.wishTypeId) {
            this.notification.add(_t("Please pick an event type."), {
                type: "warning",
            });
            return;
        }
        this.state.busy = true;
        try {
            await this.props.onConfirm(this.state.date, this.state.wishTypeId);
        } catch (err) {
            console.warn("[xb_special_dates] capture confirm failed:", err);
            this.notification.add(
                _t("Could not save the reminder. Please try again."),
                { type: "danger" }
            );
            this.state.busy = false;
            return;
        }
        this.props.close();
    }

    onClickLater() {
        this.props.onLater();
        this.props.close();
    }

    onClickDismiss() {
        this.props.onDismiss();
        this.props.close();
    }
}
