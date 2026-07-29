/** @odoo-module **/
// XUBAX - Jewelry hub dialog for the Point of Sale.
// Four actions and nothing else: receive a piece, look one up, deliver it, or
// hand a batch to a jeweler.

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { JewelryIntakeDialog } from "@xb_jewelry_service_pos/app/screens/jewelry_intake";
import { JewelrySignaturePopup } from "@xb_jewelry_service_pos/app/signature/jewelry_signature";

const STATE_LABELS = {
    draft: _t("New"),
    pending_auth: _t("Waiting authorization"),
    confirmed: _t("In custody"),
    under_repair: _t("At workshop"),
    inspection: _t("Being inspected"),
    rework: _t("Sent back"),
    done: _t("Ready for pickup"),
    delivered: _t("Delivered"),
};

export class JewelryDialog extends Component {
    static template = "xb_jewelry_service_pos.JewelryDialog";
    static components = { Dialog };
    static props = {
        getPartner: { type: Function, optional: true },
        getOrder: { type: Function, optional: true },
        close: Function,
    };

    setup() {
        this.pos = useService("pos");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            view: "menu", // menu | search | detail | dispatch
            query: "",
            results: [],
            selected: null,
            onlyReady: false,
            loading: false,
            signedBy: "",
            settings: {},
            // Workshop hand-over
            jewelers: [],
            jewelerId: false,
            promisedDate: "",
            picked: {}, // repair id -> true
        });
        onWillStart(async () => {
            const [hasCamera, settings] = await Promise.all([
                this.detectCamera(),
                this.orm.call("repair.order", "xb_pos_settings", [this.pos.config.id]),
            ]);
            this.hasCamera = hasCamera;
            this.state.settings = settings;
        });
    }

    /**
     * Registers differ from till to till: a tablet has a camera, the desktop
     * at the back does not. Knowing which one we are on decides whether the
     * photos can be taken here or have to come from a phone.
     */
    async detectCamera() {
        try {
            if (!navigator.mediaDevices?.enumerateDevices) {
                return false;
            }
            const devices = await navigator.mediaDevices.enumerateDevices();
            return devices.some((d) => d.kind === "videoinput");
        } catch {
            return false;
        }
    }

    get dialogTitle() {
        return _t("Jewelry");
    }

    stateLabel(state) {
        return STATE_LABELS[state] || state;
    }

    async openIntake() {
        const partner = this.props.getPartner?.();
        if (!partner) {
            this.notification.add(
                _t("Select the customer on the order first."),
                { type: "warning" }
            );
            return;
        }
        this.props.close();
        this.dialog.add(JewelryIntakeDialog, {
            partner,
            hasCamera: this.hasCamera,
            order: this.props.getOrder?.(),
            settings: this.state.settings,
        });
    }

    async openSearch(onlyReady) {
        this.state.view = "search";
        this.state.onlyReady = onlyReady;
        await this.search();
    }

    async search() {
        this.state.loading = true;
        try {
            this.state.results = await this.orm.call(
                "repair.order",
                "xb_pos_search",
                [this.state.query, this.state.onlyReady, 40,
                 this.state.view === "dispatch" ? "dispatch" : null]
            );
        } finally {
            this.state.loading = false;
        }
    }

    // --- Workshop hand-over -------------------------------------------
    /**
     * A jeweler normally takes a whole order, but one order can be split
     * across jewelers by specialty, so the counter picks pieces rather than
     * orders. The commitment date is typed here because it is the jeweler,
     * not the shop, who decides when the work will be done.
     */
    async openDispatch() {
        this.state.view = "dispatch";
        this.state.picked = {};
        this.state.jewelerId = false;
        this.state.promisedDate = "";
        this.state.loading = true;
        try {
            const [jewelers] = await Promise.all([
                this.orm.call("repair.order", "xb_pos_jewelers", [this.pos.config.id]),
                this.search(),
            ]);
            this.state.jewelers = jewelers;
        } finally {
            this.state.loading = false;
        }
    }

    togglePick(row) {
        if (row.dispatch_blocker) {
            this.notification.add(row.dispatch_blocker, { type: "warning" });
            return;
        }
        if (this.state.picked[row.id]) {
            delete this.state.picked[row.id];
        } else {
            this.state.picked[row.id] = true;
        }
    }

    get pickedIds() {
        return Object.keys(this.state.picked).map((id) => parseInt(id, 10));
    }

    async confirmDispatch() {
        const ids = this.pickedIds;
        if (!ids.length) {
            this.notification.add(_t("Pick at least one piece."), { type: "warning" });
            return;
        }
        const jewelerId = parseInt(this.state.jewelerId, 10);
        if (!jewelerId) {
            this.notification.add(_t("Pick the jeweler."), { type: "warning" });
            return;
        }
        const jeweler = this.state.jewelers.find((j) => j.id === jewelerId);
        let signature = false;
        let signedBy = jeweler?.name || "";
        if (this.state.settings.require_dispatch_signature) {
            const payload = await makeAwaitable(this.dialog, JewelrySignaturePopup, {
                title: _t("Workshop hand-over"),
                subtitle: _t(
                    "The jeweler signs for the pieces they are taking with them."
                ),
                defaultName: signedBy,
                required: true,
            });
            if (!payload || !payload.signature) {
                return;
            }
            signature = payload.signature;
            signedBy = payload.name || signedBy;
        }
        this.state.loading = true;
        try {
            const dispatch = await this.orm.call("repair.order", "xb_pos_dispatch", [
                ids,
                jewelerId,
                signature,
                signedBy,
                this.state.promisedDate || false,
                this.pos.config.id,
            ]);
            this.notification.add(
                _t("%(count)s piece(s) handed over: %(ref)s", {
                    count: ids.length,
                    ref: dispatch.name,
                }),
                { type: "success" }
            );
            this.props.close();
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The hand-over could not be recorded."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }

    select(row) {
        this.state.selected = row;
        this.state.signedBy = row.partner_name || "";
        this.state.view = "detail";
    }

    back() {
        if (this.state.view === "dispatch") {
            this.state.view = "menu";
            return;
        }
        this.state.view = this.state.selected ? "search" : "menu";
        this.state.selected = null;
    }

    async deliver() {
        const row = this.state.selected;
        let signature = false;
        let signedBy = this.state.signedBy;
        if (this.state.settings.require_delivery_signature) {
            const payload = await makeAwaitable(this.dialog, JewelrySignaturePopup, {
                title: _t("Delivery receipt"),
                subtitle: _t(
                    "The customer confirms the piece they are taking back is "
                    + "theirs and the work is the one agreed."
                ),
                terms: this.state.settings.delivery_terms || "",
                defaultName: signedBy || row.partner_name || "",
                required: true,
            });
            if (!payload || !payload.signature) {
                return;
            }
            signature = payload.signature;
            signedBy = payload.name || signedBy;
        }
        this.state.loading = true;
        try {
            await this.orm.call("repair.order", "xb_pos_deliver", [
                row.id,
                signature,
                signedBy,
            ]);
            this.notification.add(
                _t("%s delivered.", row.name),
                { type: "success" }
            );
            this.props.close();
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("Could not deliver the piece."),
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }
}
