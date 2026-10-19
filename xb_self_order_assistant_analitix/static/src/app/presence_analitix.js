/**
 * XUBAX - Virtual seller + Analitix: Analitix's camera tells the seller when someone stops in
 * front of the kiosk (a stop that lasts a moment, not someone walking past) and when they leave.
 */
import { patch } from "@web/core/utils/patch";
import { KioskCamera } from "@analitix_self_order/app/kiosk_camera";

const ARRIVE_MS = 1500;
const announce = (present) => window.dispatchEvent(new CustomEvent("xb-va-presence", { detail: { present } }));

patch(KioskCamera.prototype, {
    start() {
        // Analitix is watching the camera: the seller does not open it a second time.
        window.xbVaPresenceExternal = true;
        return super.start(...arguments);
    },
    open(now) {
        const stop = super.open(...arguments);
        setTimeout(() => {
            if (this.current && this.current.uuid === stop.uuid) {
                announce(true);
            }
        }, ARRIVE_MS);
        return stop;
    },
    close() {
        const had = Boolean(this.current);
        const result = super.close(...arguments);
        if (had) {
            announce(false);
        }
        return result;
    },
});
