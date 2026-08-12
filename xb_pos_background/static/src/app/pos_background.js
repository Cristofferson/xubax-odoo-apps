/** @odoo-module **/

import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";

// Odoo paints the standby and login screens with
//   background-image: var(--homeMenu-bg-image, url(".../background-light.svg"))
//   background-color: var(--homeMenu-bg-color, $o-gray-200)
// and the POS logo with
//   background-image: var(--navbar-logo, url("/web/static/img/odoo_logo.svg"))
// Neither variable is defined in the Point of Sale, so filling them in is all
// it takes: no core stylesheet is overwritten and no core template is patched,
// which is what keeps this module out of the way of Odoo's own updates.
const BG_IMAGE_VAR = "--homeMenu-bg-image";
const BG_COLOR_VAR = "--homeMenu-bg-color";
const LOGO_VAR = "--navbar-logo";

// How each "Image fit" option maps onto the three background properties our
// own stylesheet reads. Kept here so the whole mapping is visible at once.
const FITS = {
    cover: { size: "cover", repeat: "no-repeat", position: "center" },
    contain: { size: "contain", repeat: "no-repeat", position: "center" },
    tile: { size: "auto", repeat: "repeat", position: "top left" },
    center: { size: "auto", repeat: "no-repeat", position: "center" },
};

const MAX_DARKENING = 80;

// Odoo writes the clock and the date of those screens in dark gray, which is
// right over its own light background and invisible over a dark picture. When
// the background ends up dark, the clock is turned white and given a soft
// shadow so it holds up over a busy photograph too.
const LIGHT_TEXT = "#FFFFFF";
const LIGHT_TEXT_SHADOW = "0 1px 4px rgba(0, 0, 0, 0.55)";

patch(Chrome.prototype, {
    setup() {
        super.setup(...arguments);
        // The `.pos` div is the root element of this component, so it is in the
        // document by the time onMounted runs and it lives as long as the POS
        // session does: the variables are written once and never re-applied.
        onMounted(() => this.xbApplyBackground());
    },

    xbApplyBackground() {
        const config = this.pos?.config;
        const root = document.querySelector(".pos");
        if (!config || !root) {
            return;
        }
        const style = root.style;

        const imageUrl = config._xb_bg_url;
        const color = (config.xb_bg_color || "").trim();

        if (imageUrl) {
            style.setProperty(BG_IMAGE_VAR, `url("${imageUrl}")`);
        } else if (color) {
            // A color on its own still has to push the Odoo artwork out of the
            // way, otherwise it would only show through its transparent parts.
            style.setProperty(BG_IMAGE_VAR, "none");
        }
        if (color) {
            style.setProperty(BG_COLOR_VAR, color);
        }

        const fit = FITS[config.xb_bg_fit] || FITS.cover;
        style.setProperty("--xb-pos-bg-size", fit.size);
        style.setProperty("--xb-pos-bg-repeat", fit.repeat);
        style.setProperty("--xb-pos-bg-position", fit.position);

        const darkening = Math.min(
            Math.max(config.xb_bg_darkening || 0, 0),
            MAX_DARKENING
        );
        style.setProperty("--xb-pos-bg-darkening", String(darkening / 100));

        if (config._xb_light_text) {
            style.setProperty("--xb-pos-bg-text", LIGHT_TEXT);
            style.setProperty("--xb-pos-bg-text-shadow", LIGHT_TEXT_SHADOW);
        }

        if (config._xb_logo_url) {
            style.setProperty(LOGO_VAR, `url("${config._xb_logo_url}")`);
        }
    },
});
