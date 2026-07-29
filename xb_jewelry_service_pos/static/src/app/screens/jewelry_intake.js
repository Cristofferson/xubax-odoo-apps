/** @odoo-module **/
// XUBAX - Intake wizard.
// One question per screen. The cashier never chooses what to do next, only
// answers what is in front of them, and cannot move on while something the
// shop needs as evidence is missing.

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { JewelrySignaturePopup } from "@xb_jewelry_service_pos/app/signature/jewelry_signature";

export class JewelryIntakeDialog extends Component {
    static template = "xb_jewelry_service_pos.JewelryIntakeDialog";
    static components = { Dialog };
    static props = {
        partner: Object,
        hasCamera: { type: Boolean, optional: true },
        order: { type: Object, optional: true },
        settings: { type: Object, optional: true },
        close: Function,
    };

    setup() {
        this.pos = useService("pos");
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.state = useState({
            step: 0,
            saving: false,
            metals: [],
            tipos: [],
            medidas: [],
            piece: {
                description: "",
                piece_type_id: false,
                metal_value_id: false,
                weight_g: 0,
                size_value_id: false,
                length_cm: 0,
                stone_count: 0,
                has_diamond: false,
                has_laser_inscription: false,
                diamond_tester: false,
                laser_inscription: "",
                note: "",
            },
            serviceType: "repair", // repair | custom | transform
            spec: "",
            inputPieces: [], // el oro que trae el cliente para una hechura
            photos: {}, // code -> {kind_id, image}
            signedBy: this.props.partner?.name || "",
            signature: null, // base64 png, no data-URL prefix
            usePhone: false,
            photoLink: null,
            savedRepair: null,
            settings: this.props.settings || {},
        });

        onWillStart(async () => {
            // La caja decide la compañía: en un grupo con varias, la del
            // usuario no tiene por qué ser aquella bajo la que factura el
            // mostrador, y de ahí cuelga a qué compañía pertenece la pieza.
            const cfgId = this.pos.config.id;
            // Los tres catálogos salen de lo que la tienda ya tiene cargado:
            // categorías de producto para el tipo, y sus atributos para
            // metal y medida.
            const calls = [
                this.orm.call("repair.order", "xb_pos_metal_values", [cfgId]),
                this.orm.call("repair.order", "xb_pos_piece_types", []),
                this.orm.call("repair.order", "xb_pos_sizes", [cfgId]),
            ];
            if (!this.props.settings) {
                calls.push(this.orm.call("repair.order", "xb_pos_settings", [cfgId]));
            }
            const [metals, tipos, medidas, settings] = await Promise.all(calls);
            this.state.metals = metals;
            this.state.tipos = tipos;
            this.state.medidas = medidas;
            if (settings) {
                this.state.settings = settings;
            }
            if (tipos.length && !this.state.piece.piece_type_id) {
                this.state.piece.piece_type_id = tipos[0].id;
            }
        });
    }

    get dialogTitle() {
        // Título traducible: pasarlo como literal en el template lo deja en
        // inglés aunque el resto de la caja esté en español.
        return this.state.photoLink ? _t("Photos from a phone") : _t("Receive a piece");
    }

    get pieceKind() {
        const id = parseInt(this.state.piece.piece_type_id, 10);
        return this.state.tipos.find((c) => c.id === id)?.kind || "other";
    }

    get kinds() {
        // The photo checklist is data, and it adapts to the piece in hand:
        // no ring size on a chain, no laser shot without an inscription, and
        // no design reference on a straight repair. The "after" shots belong
        // to the far end of the job and have no business on this screen.
        const all = this.pos.models["xb.jewelry.photo.kind"].getAll();
        return all
            .filter((k) => {
                if (k.stage === "after") {
                    return false;
                }
                if (k.stage === "design") {
                    return this.state.serviceType !== "repair";
                }
                return this.kindApplies(k);
            })
            .sort((a, b) => a.sequence - b.sequence);
    }

    kindApplies(kind) {
        switch (kind.condition) {
            case "ring":
                return this.pieceKind === "ring";
            case "chain":
                return this.pieceKind === "chain";
            case "diamond":
                return !!this.state.piece.has_diamond;
            case "diamond_laser":
                // Nadie puede fotografiar una inscripción que no existe.
                return (
                    !!this.state.piece.has_diamond &&
                    !!this.state.piece.has_laser_inscription
                );
            default:
                return true;
        }
    }

    /** Todo lo que se le debe a la pieza, se tome hoy o mañana. */
    get missingPhotos() {
        return this.kinds.filter((k) => k.required && !this.state.photos[k.code]);
    }

    /**
     * Lo que se exige AQUÍ, con el cliente enfrente. Es a propósito un
     * subconjunto: el resto se puede tomar después desde un celular, y la
     * pieza no sale al taller hasta que estén todas de todos modos.
     */
    get missingNow() {
        const policy = this.state.settings.intake_photo_policy || "none";
        if (policy === "none") {
            return [];
        }
        if (policy === "min") {
            const code = this.state.settings.intake_main_photo_code;
            const main = code
                ? this.kinds.find((k) => k.code === code)
                : this.kinds[0];
            return main && !this.state.photos[main.code] ? [main] : [];
        }
        return this.missingPhotos;
    }

    get steps() {
        const steps = ["kind", "piece"];
        if (this.state.serviceType !== "repair") {
            steps.push("spec");
        }
        return steps.concat(["metal", "photos", "sign"]);
    }

    setServiceType(type) {
        this.state.serviceType = type;
    }

    get currentStep() {
        return this.steps[this.state.step];
    }

    canAdvance() {
        if (this.currentStep === "piece") {
            return !!this.state.piece.description.trim();
        }
        if (this.currentStep === "photos") {
            // Handing the photos to a phone is an accepted way out: the piece
            // still cannot go to the workshop until they exist, so nothing is
            // lost by taking them a minute later.
            return this.state.usePhone || this.missingNow.length === 0;
        }
        return true;
    }

    usePhoneForPhotos() {
        this.state.usePhone = true;
        this.next();
    }

    next() {
        if (!this.canAdvance()) {
            return;
        }
        if (this.state.step < this.steps.length - 1) {
            this.state.step++;
        }
    }

    previous() {
        if (this.state.step > 0) {
            this.state.step--;
        }
    }

    get signatureRequired() {
        return !!this.state.settings.require_intake_signature;
    }

    /**
     * The customer signs on the same screen the piece was described on. This
     * is the receipt for someone else's gold, so when the shop has made it
     * mandatory the piece is simply not taken in without it.
     */
    async captureSignature() {
        const payload = await makeAwaitable(this.dialog, JewelrySignaturePopup, {
            title: _t("Intake receipt"),
            subtitle: _t(
                "The customer confirms they leave the piece as described, with "
                + "the photos just taken."
            ),
            terms: this.state.settings.intake_terms || "",
            defaultName: this.state.signedBy,
            required: this.signatureRequired,
        });
        if (!payload) {
            return;
        }
        this.state.signature = payload.signature || null;
        if (payload.name) {
            this.state.signedBy = payload.name;
        }
    }

    clearSignature() {
        this.state.signature = null;
    }

    /**
     * Build the sale order payload with xb_sale_order_from_pos's own builder
     * instead of a copy of it. That module works out the exact POS taxes to
     * the cent and sanitizes the line notes; reimplementing any of that here
     * would mean two versions of the same arithmetic drifting apart.
     *
     * The builder lives on the ControlButtons prototype, so we borrow it with
     * a stand-in object carrying the only thing it needs, the POS store.
     * Returns null when that module is not installed, or the cart is empty,
     * in which case the piece is still taken into custody on its own.
     */
    /**
     * The sale order the cashier already raised on this cart, if any.
     *
     * "Create Order" stashes it here; both buttons feed the same cart to the
     * same backend method, so without looking first the counter ends up with
     * two documents for one ring.
     */
    get existingSaleOrder() {
        return this.props.order?.uiState?.xbSaleOrder || null;
    }

    buildSalePayload() {
        const order = this.props.order;
        if (!order || !order.getOrderlines?.().length) {
            return null;
        }
        if (this.existingSaleOrder?.sale_order_id) {
            // Already invoiced through the other button: the piece links to
            // that order instead of raising a second one.
            return null;
        }
        const helper = Object.create(ControlButtons.prototype);
        helper.pos = this.pos;
        if (typeof helper.xbBuildOrderPayload !== "function") {
            return null;
        }
        let payload;
        try {
            payload = helper.xbBuildOrderPayload(order);
        } catch {
            return null;
        }
        // Honour whatever the shop configured as its default kind of document
        // rather than asking the cashier a second question they already
        // answered in the settings.
        let choice = { type: "quotation", confirm: false, with_down_payment: false };
        try {
            const options = helper.xbGetOrderTypeOptions();
            const selected = options.find((o) => o.isSelected) || options[0];
            if (selected) {
                choice = selected.item;
            }
        } catch {
            // keep the conservative default
        }
        return { ...payload, ...choice };
    }

    addInputPiece() {
        this.state.inputPieces.push({
            description: "",
            weight_g: 0,
            metal_value_id: false,
        });
    }

    removeInputPiece(index) {
        this.state.inputPieces.splice(index, 1);
    }

    async onPhotoPicked(kind, ev) {
        const file = ev.target.files?.[0];
        if (!file) {
            return;
        }
        const base64 = await this.fileToBase64(file);
        this.state.photos[kind.code] = { kind_id: kind.id, image: base64 };
    }

    fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result.split(",")[1]);
            reader.onerror = reject;
            reader.readAsDataURL(file);
        });
    }

    photoPreview(code) {
        const photo = this.state.photos[code];
        return photo ? `data:image/jpeg;base64,${photo.image}` : false;
    }

    async save() {
        if (this.missingNow.length && !this.state.usePhone) {
            this.notification.add(_t("Some required photos are missing."), {
                type: "warning",
            });
            return;
        }
        if (this.signatureRequired && !this.state.signature) {
            this.notification.add(_t("The customer still has to sign."), {
                type: "warning",
            });
            return;
        }
        this.state.saving = true;
        try {
            // Un <select> entrega texto; el servidor espera enteros o falso.
            const num = (v) => {
                const n = parseInt(v, 10);
                return Number.isNaN(n) ? false : n;
            };
            const vals = {
                ...this.state.piece,
                piece_type_id: num(this.state.piece.piece_type_id),
                metal_value_id: num(this.state.piece.metal_value_id),
                size_value_id: num(this.state.piece.size_value_id),
                partner_id: this.props.partner.id,
                pos_config_id: this.pos.config.id,
                service_type: this.state.serviceType,
                spec: this.state.spec || false,
                input_pieces: this.state.inputPieces.map((p) => ({
                    description: p.description,
                    weight_g: parseFloat(p.weight_g) || 0,
                    metal_value_id: num(p.metal_value_id),
                })),
                photos: Object.values(this.state.photos),
                signed_by: this.state.signedBy,
                signature: this.state.signature || false,
                // Misma pasada: la custodia y el pedido que se va a cobrar.
                // Si la cajera ya lo levantó con «Create Order», se reutiliza
                // ese en vez de crear un segundo por la misma pieza.
                sale_order_id: this.existingSaleOrder?.sale_order_id || false,
                sale_payload: this.buildSalePayload(),
            };
            const repair = await this.orm.call(
                "repair.order", "xb_pos_receive_piece", [vals]
            );
            // Remember the order on the cart so "Create Order" knows it is
            // already done and refuses to raise a twin.
            const so = repair.sale_order;
            if (so?.sale_order_id && this.props.order) {
                this.props.order.uiState.xbSaleOrder = {
                    ...(this.props.order.uiState.xbSaleOrder || {}),
                    ...so,
                };
            }
            this.notification.add(
                _t("Piece received: %s", repair.name),
                { type: "success" }
            );
            if (this.state.usePhone) {
                // Keep the dialog open on the QR: the counter needs it on
                // screen while somebody points a phone at it.
                this.state.savedRepair = repair;
                this.state.photoLink = await this.orm.call(
                    "repair.order", "xb_pos_photo_link", [repair.id]
                );
                this.state.step = this.steps.length; // QR screen
                return;
            }
            this.props.close();
        } catch (error) {
            this.notification.add(
                error?.data?.message || _t("The piece could not be received."),
                { type: "danger" }
            );
        } finally {
            this.state.saving = false;
        }
    }
}
