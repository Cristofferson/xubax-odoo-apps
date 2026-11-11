/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS
// Delivery date asked when an order is created from the POS. It is Odoo's own
// date picker (the one "Ship Later" uses), started on the probable date instead of
// today and with a way to leave the date empty. The answer goes to the native
// sale.order.commitment_date ("Delivery Date").

import { _t } from "@web/core/l10n/translation";
import { DatePickerPopup } from "@point_of_sale/app/components/popups/date_picker_popup/date_picker_popup";

const { DateTime } = luxon;

export class XbDeliveryDatePopup extends DatePickerPopup {
    static template = "xb_sale_order_from_pos.XbDeliveryDatePopup";
    static props = {
        ...DatePickerPopup.props,
        defaultDate: { type: String, optional: true },
    };
    static defaultProps = {
        ...DatePickerPopup.defaultProps,
        title: _t("Delivery date"),
    };

    setup() {
        super.setup();
        if (this.props.defaultDate) {
            this.state.shippingDate = this.props.defaultDate;
        }
    }
    // Today on the cashier's clock: Odoo's picker takes it in UTC, which in Mexico
    // is already tomorrow every evening.
    _today() {
        return DateTime.local().toISODate();
    }
    noDate() {
        this.props.getPayload("");
        this.props.close();
    }
}
