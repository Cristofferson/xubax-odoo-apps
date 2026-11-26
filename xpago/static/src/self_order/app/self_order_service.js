import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

patch(SelfOrder.prototype, {
    filterPaymentMethods(pms) {
        const pm = super.filterPaymentMethods(...arguments);
        const xpago = pms.filter((rec) => ["xpago", "xpago_spei"].includes(rec.use_payment_terminal));
        return [...new Set([...pm, ...xpago])];
    },
});
