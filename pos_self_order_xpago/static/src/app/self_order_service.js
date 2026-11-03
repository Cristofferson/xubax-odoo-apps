import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

patch(SelfOrder.prototype, {
    filterPaymentMethods(pms) {
        const pm = super.filterPaymentMethods(...arguments);
        const xpago = pms.filter((rec) => rec.use_payment_terminal === "xpago");
        return [...new Set([...pm, ...xpago])];
    },
});
