/** Odoo 18 / 19 JS compatibility for the POS.
 *
 *  The POS moved several modules between 18.0 and 19.0, and the SaaS 18.x
 *  builds already ship the 19.0 layout:
 *
 *      symbol       Odoo 18.0                 Odoo saas~18.2+ and 19.0
 *      -----------  ------------------------  ------------------------------
 *      PosStore     app/store/pos_store       app/services/pos_store
 *      usePos       app/store/pos_hook        app/hooks/pos_hook
 *
 *  ES imports are static, so importing both paths is not an option: the
 *  missing one makes the loader fail this module and everything under it.
 *  Instead we read the symbols back out of the module registry, which every
 *  supported version exposes as ``odoo.loader.modules`` (a Map). By the time
 *  this file runs the whole point_of_sale bundle is already loaded -- the
 *  static import below both guarantees that ordering and gives us the one
 *  symbol whose path never moved.
 *
 *  Everything else in static/src imports its POS symbols from here, never from
 *  @point_of_sale directly, so no other file needs a version check and the
 *  module ships unchanged for 18.0, 18.x and 19.0.
 */
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

/** Candidate module paths per symbol, newest layout first. */
const PATHS = {
    PosStore: ["@point_of_sale/app/services/pos_store", "@point_of_sale/app/store/pos_store"],
    usePos: ["@point_of_sale/app/hooks/pos_hook", "@point_of_sale/app/store/pos_hook"],
};

function resolve(symbol) {
    const modules = odoo.loader.modules;
    for (const path of PATHS[symbol]) {
        const mod = modules.get(path);
        if (mod && symbol in mod) {
            return mod[symbol];
        }
    }
    throw new Error(
        `xb_pos_taecel: could not resolve "${symbol}" from the Point of Sale bundle ` +
            `(tried ${PATHS[symbol].join(", ")}). This Odoo version is not supported yet.`
    );
}

export const PosStore = resolve("PosStore");
export const usePos = resolve("usePos");
export { ControlButtons };
