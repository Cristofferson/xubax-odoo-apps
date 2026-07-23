/** Odoo 18 / 19 JS compatibility for the POS.
 *
 *  ES imports are static, so the version differences in module paths cannot be
 *  shimmed at runtime -- they are resolved here, in ONE file. This is the 19.0
 *  branch. To port to 18.0, only this file changes:
 *
 *      Odoo 19 (this file)                    Odoo 18
 *      -------------------------------------  ------------------------------------
 *      app/services/pos_store  -> PosStore    app/store/pos_store
 *      app/hooks/pos_hook      -> usePos      app/store/pos_hook
 *      components/navbar/navbar -> Navbar     app/navbar/navbar
 *
 *  Everything else in static/src imports its POS symbols from here, never from
 *  @point_of_sale directly, so no other file needs a version check.
 */
export { PosStore } from "@point_of_sale/app/services/pos_store";
export { usePos } from "@point_of_sale/app/hooks/pos_hook";
export { Navbar } from "@point_of_sale/app/components/navbar/navbar";
export { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
