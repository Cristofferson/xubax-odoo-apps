// XUBAX - Sales, Quotations & Layaway from POS
// Delivery date asked when an order is created from the POS: Odoo's own date input,
// started on the probable date and with a way to leave the date empty. The answer
// goes to the native sale.order.commitment_date ("Delivery Date").

import { Component, onMounted, proxy, t, useProps } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { _t } from "@web/core/l10n/translation";

const { DateTime } = luxon;

export class XbDeliveryDatePopup extends Component {
    static template = "xb_sale_order_from_pos.XbDeliveryDatePopup";
    static components = { Dialog, DateTimeInput };
    props = useProps({
        title: t.string().optional(_t("Delivery date")),
        // Probable day, "YYYY-MM-DD".
        defaultDate: t.string().optional(),
        getPayload: t.function(),
        close: t.function(),
    });

    setup() {
        const probable = this.props.defaultDate ? DateTime.fromISO(this.props.defaultDate) : null;
        this.state = proxy({ date: probable?.isValid ? probable : this._today() });
        onMounted(() => {
            const input = document.querySelector(".xb-delivery-date-selector input");
            if (input) {
                input.classList.remove("o_input");
                input.classList.add("form-control", "form-control-lg");
            }
        });
    }
    // Today on the cashier's clock.
    _today() {
        return DateTime.local().startOf("day");
    }
    onDateChange(date) {
        this.state.date = date && date < this._today() ? this._today() : date;
    }
    confirm() {
        this.props.getPayload(this.state.date ? this.state.date.toISODate() : "");
        this.props.close();
    }
    noDate() {
        this.props.getPayload("");
        this.props.close();
    }
}
