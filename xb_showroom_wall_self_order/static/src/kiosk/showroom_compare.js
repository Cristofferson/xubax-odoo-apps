/**
 * Comparar en el muro desde el kiosco, como el «Comparar» de la tienda en línea:
 * cada pieza se suma al muro al momento (al final; si ya estaba, se mueve al final;
 * pasando el máximo sale la más vieja). Casilla en la lista, botón en la ficha y una
 * barra con las miniaturas para quitar piezas o empezar de nuevo.
 */
import { patch } from "@web/core/utils/patch";
import { reactive, useState, onWillStart } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { ProductPage } from "@pos_self_order/app/pages/product_page/product_page";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";

const comparacion = reactive({ pieces: [], limit: 0, busy: false });

async function llamar(selfOrder, ruta, params = {}) {
    if (comparacion.busy) {
        return;
    }
    comparacion.busy = true;
    try {
        const res = await rpc(ruta, { access_token: selfOrder.access_token, ...params });
        if (res?.pieces) {
            comparacion.pieces = res.pieces;
            comparacion.limit = res.limit || comparacion.limit;
        }
        if (res?.error) {
            selfOrder.notification.add(res.error, { type: "warning" });
        } else if (res?.message) {
            selfOrder.notification.add(res.message, { type: "success" });
        }
        return res;
    } catch {
        selfOrder.notification.add(_t("The wall is not available right now."), { type: "danger" });
    } finally {
        comparacion.busy = false;
    }
}

const puedeComparar = (selfOrder, tmpl) =>
    Boolean(selfOrder.config._xb_showroom_kiosk && (!tmpl || tmpl.xb_showroom_enabled));

const metodos = {
    xbPuedeComparar(tmpl) {
        return puedeComparar(this.selfOrder, tmpl);
    },
    xbComparando(tmpl) {
        return this.xbCompare.pieces.some((p) => p.template_id === tmpl.id);
    },
    xbCompararTexto() {
        return _t("Comparing %(count)s of %(max)s", {
            count: this.xbCompare.pieces.length,
            max: this.xbCompare.limit,
        });
    },
    async xbQuitar(slotId) {
        await llamar(this.selfOrder, "/xb_showroom/kiosk/remove", { slot_id: slotId });
    },
    async xbNueva() {
        await llamar(this.selfOrder, "/xb_showroom/kiosk/clear");
    },
};

patch(ProductListPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.xbCompare = useState(comparacion);
        onWillStart(async () => {
            if (puedeComparar(this.selfOrder)) {
                await llamar(this.selfOrder, "/xb_showroom/kiosk/state");
            }
        });
    },
    ...metodos,
    async xbAlternar(tmpl) {
        const pieza = this.xbCompare.pieces.find((p) => p.template_id === tmpl.id);
        if (pieza) {
            await this.xbQuitar(pieza.slot_id);
        } else {
            await llamar(this.selfOrder, "/xb_showroom/kiosk/push", {
                template_id: tmpl.id,
                combination: [],
                mode: "compare",
            });
        }
    },
});

patch(ProductPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.xbCompare = useState(comparacion);
    },
    ...metodos,
    async showOnWall() {
        // A single piece replaces the comparison on the wall (as in the shop):
        // the bar follows what the wall now shows.
        await super.showOnWall(...arguments);
        await llamar(this.selfOrder, "/xb_showroom/kiosk/state");
    },
    async xbComparar() {
        const tmpl = this.props.productTemplate;
        const seleccion = this.state.selectedValues[tmpl.id];
        await llamar(this.selfOrder, "/xb_showroom/kiosk/push", {
            template_id: tmpl.id,
            combination: seleccion
                ? seleccion.getAllSelectedAttributeValuesIds().map((id) => Number(id))
                : [],
            mode: "compare",
        });
    },
});
