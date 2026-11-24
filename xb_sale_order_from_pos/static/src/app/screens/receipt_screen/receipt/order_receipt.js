/** @odoo-module **/
// XUBAX - Sales, Quotations & Layaway from POS (Phase 3 - display only)
// Receipt header: the fiscal entity's RFC. The Sale Order data itself is added to the
// receipt data by Order.export_for_printing (models/pos_order.js). Clean-room.

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ReceiptHeader } from "@point_of_sale/app/screens/receipt_screen/receipt/receipt_header/receipt_header";

patch(ReceiptHeader.prototype, {
    // (i) Footer RFC = the fiscal ENTITY's RFC the CFDI issues under: the company's
    // own, or for a branch without one, the parent's (res.company.xb_cfdi_emisor_rfc,
    // computed exactly like l10n_mx_edi's issuer). Falls back to the native behaviour.
    get vatText() {
        const company = this.props.data.company;
        const rfc = company?.xb_cfdi_emisor_rfc;
        if (!rfc) {
            return super.vatText;
        }
        const vatLabel = company.country?.vat_label;
        return vatLabel
            ? _t("%(vatLabel)s: %(vatId)s", { vatLabel, vatId: rfc })
            : _t("Tax ID: %(vatId)s", { vatId: rfc });
    },
});
