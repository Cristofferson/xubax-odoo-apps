/** @odoo-module */
/** Odoo 17 POS symbols, in one place.
 *
 *  The 18+ builds of this module read PosStore / usePos out of the module
 *  registry because those paths moved; on 17 they sit at their original
 *  paths, and the control bar is extended through ProductScreen instead of
 *  ControlButtons. Everything else in static/src imports its POS symbols from
 *  here.
 */
export { PosStore } from "@point_of_sale/app/store/pos_store";
export { usePos } from "@point_of_sale/app/store/pos_hook";
export { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
export { Orderline } from "@point_of_sale/app/store/models";
