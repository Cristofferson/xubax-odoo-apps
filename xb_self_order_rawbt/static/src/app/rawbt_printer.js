import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BasePrinter } from "@point_of_sale/app/utils/printer/base_printer";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

/** Sends the kiosk's tickets to the RawBT app of the tablet, as ESC/POS. */
export class RawBTPrinter extends BasePrinter {
    setup({ width, method }) {
        super.setup(...arguments);
        this.width = width || 576;
        this.method = method || "intent";
    }

    processCanvas(canvas) {
        return window.XbRawBT.toBase64(window.XbRawBT.canvasToEscPos(canvas, this.width));
    }

    async sendPrintingJob(b64) {
        // RawBT gives no answer back: once Android has the job, it is printed.
        window.XbRawBT.send(b64, this.method);
        return { result: true };
    }

    openCashbox() {}

    getActionError() {
        return {
            successful: false,
            canRetry: true,
            message: {
                title: _t("The ticket could not be printed"),
                body: _t("Check that the RawBT app is installed and connected to the printer."),
            },
        };
    }

    getResultsError() {
        return this.getActionError();
    }
}

patch(SelfOrder.prototype, {
    async setup(...args) {
        await super.setup(...args);
        const rawbt = this.config?._xb_rawbt;
        if (rawbt && window.XbRawBT) {
            this.printer.setPrinter(new RawBTPrinter(rawbt));
        }
    },
});
