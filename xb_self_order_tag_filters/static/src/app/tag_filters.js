/**
 * Botón flotante «Filtrar» en la lista de productos del kiosco.
 *
 * Bloques: primero las secciones de la tienda marcadas como filtro (p. ej. Metal), luego los
 * grupos de etiquetas. Dentro de un bloque las opciones suman (OR); entre bloques se combinan
 * (AND). El estado vive en el servicio para sobrevivir a la ficha del producto, y se limpia al
 * cambiar de categoría o al volver a la pantalla de inicio.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useState, onWillStart } from "@odoo/owl";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";
import { LandingPage } from "@pos_self_order/app/pages/landing_page/landing_page";

const emptyFilters = () => ({ categoryId: null, selected: {}, open: false });

/** Los valores filtrables de un producto: [{group, id, name, sequence}] */
function productValues(product) {
    const values = [...(product._xb_sections || [])];
    for (const tag of product.product_tag_ids || []) {
        if (tag._xb_group) {
            values.push({
                group: { ...tag._xb_group, id: `g${tag._xb_group.id}` },
                id: `t${tag.id}`,
                name: tag.name,
                sequence: tag._xb_seq || 0,
            });
        }
    }
    return values;
}

function hasValue(product, groupId, valueId) {
    return productValues(product).some((v) => v.group.id === groupId && v.id === valueId);
}

patch(LandingPage.prototype, {
    setup() {
        super.setup(...arguments);
        onWillStart(() => {
            this.selfOrder.xbFilters = emptyFilters();
        });
    },
});

patch(ProductListPage.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.selfOrder.xbFilters) {
            this.selfOrder.xbFilters = emptyFilters();
        }
        this.xbFilters = useState(this.selfOrder.xbFilters);
    },

    selectCategory(category) {
        if (category !== this.state.selectedCategory) {
            this.xbResetFilters();
            this.xbFilters.open = false;
        }
        return super.selectCategory(...arguments);
    },

    get xbActive() {
        return !!this.selfOrder.kioskMode && this.xbFilters.categoryId === this.selectedCategory?.id;
    },

    /** Productos de la categoría actual, sin filtrar. */
    xbBaseProducts() {
        const category = this.selectedCategory;
        return category ? super.getProducts(category) : [];
    },

    /** Bloques con al menos dos opciones, o una que no todos los productos tienen. */
    get xbGroups() {
        if (!this.selfOrder.kioskMode) {
            return [];
        }
        const products = this.xbBaseProducts();
        const groups = new Map();
        for (const product of products) {
            const seen = new Set();
            for (const v of productValues(product)) {
                const key = `${v.group.id}/${v.id}`;
                if (seen.has(key)) {
                    continue;
                }
                seen.add(key);
                if (!groups.has(v.group.id)) {
                    groups.set(v.group.id, { ...v.group, values: new Map() });
                }
                const values = groups.get(v.group.id).values;
                if (!values.has(v.id)) {
                    values.set(v.id, { id: v.id, name: v.name, sequence: v.sequence, total: 0 });
                }
                values.get(v.id).total++;
            }
        }
        return [...groups.values()]
            .map((g) => ({
                ...g,
                isSection: String(g.id).startsWith("c"),
                values: [...g.values.values()].sort(
                    (a, b) => a.sequence - b.sequence || a.name.localeCompare(b.name)
                ),
            }))
            .filter((g) => g.values.length > 1 || g.values[0].total < products.length)
            .sort((a, b) => (b.isSection - a.isSection) || a.sequence - b.sequence);
    },

    xbSelected(groupId) {
        return (this.xbActive && this.xbFilters.selected[groupId]) || [];
    },

    xbMatches(product, skipGroupId) {
        return Object.entries(this.xbActive ? this.xbFilters.selected : {}).every(
            ([groupId, ids]) =>
                groupId === skipGroupId || !ids.length || ids.some((id) => hasValue(product, groupId, id))
        );
    },

    /** Cuántos productos quedarían al sumar esta opción a su bloque. */
    xbCount(groupId, valueId) {
        return this.xbBaseProducts().filter(
            (p) => hasValue(p, groupId, valueId) && this.xbMatches(p, groupId)
        ).length;
    },

    get xbCountActive() {
        if (!this.xbActive) {
            return 0;
        }
        return Object.values(this.xbFilters.selected).reduce((n, ids) => n + ids.length, 0);
    },

    get xbResultCount() {
        return this.xbBaseProducts().filter((p) => this.xbMatches(p)).length;
    },

    get xbResultLabel() {
        const n = this.xbResultCount;
        return n === 1 ? _t("1 result") : _t("%s results", n);
    },

    get xbSeeLabel() {
        const n = this.xbResultCount;
        return n === 1 ? _t("See 1 result") : _t("See %s results", n);
    },

    xbToggle(group, value) {
        if (!this.xbActive) {
            this.xbResetFilters();
            this.xbFilters.categoryId = this.selectedCategory.id;
        }
        const ids = this.xbFilters.selected[group.id] || [];
        const on = ids.includes(value.id);
        if (group.isSection) {
            // Una sección es de elección única (un solo metal a la vez).
            this.xbFilters.selected[group.id] = on ? [] : [value.id];
        } else {
            this.xbFilters.selected[group.id] = on
                ? ids.filter((id) => id !== value.id)
                : [...ids, value.id];
        }
    },

    xbResetFilters() {
        this.xbFilters.categoryId = null;
        this.xbFilters.selected = {};
    },

    xbOpen() {
        this.xbFilters.open = true;
    },

    xbClose() {
        this.xbFilters.open = false;
        this.productListRef.el?.scrollTo({ top: 0 });
    },

    getProducts(category) {
        const products = super.getProducts(...arguments);
        if (!this.xbActive || category !== this.selectedCategory || !this.xbCountActive) {
            return products;
        }
        return products.filter((p) => this.xbMatches(p));
    },
});
