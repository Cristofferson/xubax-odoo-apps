/**
 * XUBAX - Virtual seller: the products it recommends are shown in the kiosk's own product
 * list, exactly as if the customer had filtered them by hand.
 */
import { patch } from "@web/core/utils/patch";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";

patch(ProductListPage.prototype, {
    /** Products chosen by the virtual seller, in its order; empty = the normal list. */
    get xbVaPicks() {
        const ids = this.selfOrder.xbVaPicks || [];
        const Template = this.selfOrder.models["product.template"];
        return ids.map((id) => Template.get(id)).filter(Boolean);
    },

    getProducts(category) {
        const picks = this.xbVaPicks;
        return picks.length ? picks : super.getProducts(...arguments);
    },

    xbVaShowAll() {
        this.selfOrder.xbVaPicks = [];
    },
});
