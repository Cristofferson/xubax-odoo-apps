import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { ProductInfoPopup } from "@point_of_sale/app/components/popups/product_info_popup/product_info_popup";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

/* Sends one piece to the register's wall through the same route as the
   sales person's tablet, so the wall applies the very same rules (enabled
   products, published in the company's shop, «from» price...). */
async function sendToWall(pos, payload, mode = "single") {
    const notify = (message, type) => pos.notification.add(message, { type });
    try {
        // «compare» keeps what is on the wall and adds the piece at the end,
        // exactly like «Compare» on the tablet.
        const result = await rpc("/showroom/push", {
            screen_id: pos.config._xb_showroom_screen_id,
            mode,
            ...payload,
        });
        if (result?.ok) {
            const done =
                mode === "compare"
                    ? _t("On the wall: comparing %s.", result.count)
                    : _t("Look at the wall!");
            notify(result.message || done, "success");
        } else {
            notify(result?.error || _t("The wall is not available right now."), "warning");
        }
    } catch {
        notify(_t("The wall is not available right now."), "danger");
    }
}

function wallReady(pos, template) {
    return Boolean(pos.config._xb_showroom_screen_id && template?.xb_showroom_enabled);
}

patch(ProductInfoPopup.prototype, {
    get canShowOnWall() {
        return wallReady(this.pos, this.props.productTemplate);
    },
    async showOnWall(mode = "single") {
        // The piece as it is in the catalogue: the wall shows its «from» price.
        await sendToWall(this.pos, { template_id: this.props.productTemplate.id }, mode);
    },
});

patch(ControlButtons.prototype, {
    get wallLine() {
        const line = this.currentOrder?.getSelectedOrderline();
        return line && wallReady(this.pos, line.product_id?.product_tmpl_id) ? line : null;
    },
    async sendLineToWall(mode = "single") {
        const line = this.wallLine;
        if (!line) {
            return;
        }
        const combination = (line.attribute_value_ids || []).map((value) => value.id);
        // With options the exact version is rebuilt from them on the server
        // (dynamic variants rarely exist as products); without them the
        // line's own variant goes. The price is the one on the ticket before
        // any discount: a discount is between the cashier and the customer.
        await sendToWall(this.pos, {
            template_id: line.product_id.product_tmpl_id.id,
            product_id: combination.length ? 0 : line.product_id.id,
            combination,
            price: line.displayPriceUnitNoDiscount,
        }, mode);
    },
});
