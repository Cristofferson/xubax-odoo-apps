import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { ProductPage } from "@pos_self_order/app/pages/product_page/product_page";

patch(ProductPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.wall = useState({ sending: false });
    },

    get canShowOnWall() {
        return Boolean(
            this.selfOrder.config._xb_showroom_kiosk &&
                this.props.productTemplate?.xb_showroom_enabled
        );
    },

    async showOnWall() {
        if (this.wall.sending) {
            return;
        }
        this.wall.sending = true;
        const template = this.props.productTemplate;
        const selection = this.state.selectedValues[template.id];
        const combination = selection
            ? selection.getAllSelectedAttributeValuesIds().map((id) => Number(id))
            : [];
        try {
            const result = await rpc("/xb_showroom/kiosk/push", {
                access_token: this.selfOrder.access_token,
                template_id: template.id,
                combination,
            });
            if (result?.ok) {
                this.selfOrder.notification.add(result.message, { type: "success" });
            } else {
                this.selfOrder.notification.add(
                    result?.error || _t("The wall is not available right now."),
                    { type: "warning" }
                );
            }
        } catch {
            this.selfOrder.notification.add(_t("The wall is not available right now."), {
                type: "danger",
            });
        } finally {
            // A second tap right away would only bounce off the pause.
            setTimeout(() => (this.wall.sending = false), 1500);
        }
    },
});
