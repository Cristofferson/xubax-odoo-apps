/**
 * XUBAX - Boutique theme for the self-order kiosk: each kiosk sets its colors, fonts,
 * corners, columns, price, gallery, button words and installable app in its settings.
 */
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { onMounted, onPatched, useState } from "@odoo/owl";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { insertKioskStyle } from "@pos_self_order/app/kiosk_style";
import { OrderWidget } from "@pos_self_order/app/components/order_widget/order_widget";
import { ProductListPage } from "@pos_self_order/app/pages/product_list_page/product_list_page";
import { ProductPage } from "@pos_self_order/app/pages/product_page/product_page";
import { CartPage } from "@pos_self_order/app/pages/cart_page/cart_page";
import { ConfirmationPage } from "@pos_self_order/app/pages/confirmation_page/confirmation_page";

const FONTS = {
    cormorant: '"XbBqCormorant", "Cormorant Garamond", Georgia, serif',
    playfair: '"XbBqPlayfair", "Playfair Display", Georgia, serif',
    montserrat: '"XbBqMontserrat", "Montserrat", system-ui, sans-serif',
    jost: '"XbBqJost", "Jost", system-ui, sans-serif',
    lato: '"XbBqLato", "Lato", system-ui, sans-serif',
    serif: 'Georgia, "Times New Roman", serif',
    sans: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
};

/** The kiosk's boutique settings, or false when the theme is off. */
export function boutique(selfOrder) {
    return selfOrder.config._xb_bq || false;
}

/** The word the kiosk owner wrote, else the theme's own (translated) word. */
export function boutiqueText(bq, key) {
    const own = bq && bq.texts && bq.texts[key];
    if (own) {
        return own;
    }
    return {
        checkout: _t("View my selection"),
        order: _t("Pay at the counter"),
        cart_title: _t("Your selection"),
        done: _t("All set! See you at the counter"),
        number: _t("Your order number"),
        from: _t("From"),
    }[key];
}

function mix(hex, other, weight) {
    const a = parseInt(hex.slice(1), 16);
    const b = parseInt(other.slice(1), 16);
    const channel = (shift) =>
        Math.round(((a >> shift) & 255) * weight + ((b >> shift) & 255) * (1 - weight));
    return "#" + ((1 << 24) | (channel(16) << 16) | (channel(8) << 8) | channel(0)).toString(16).slice(1);
}

function applyBoutique(bq) {
    const root = document.documentElement;
    root.classList.add("xb-bq", `xb-bq-corners-${bq.corners}`);
    const vars = {
        "--xb-bq-primary": bq.primary,
        "--xb-bq-primary-d": mix(bq.primary, "#000000", 0.85),
        "--xb-bq-soft": mix(bq.primary, "#FFFFFF", 0.12),
        "--xb-bq-ink": bq.ink,
        "--xb-bq-muted": mix(bq.ink, "#FFFFFF", 0.62),
        "--xb-bq-photo": bq.photo,
        "--xb-bq-line": bq.line,
        "--xb-bq-title-font": FONTS[bq.font_title] || FONTS.serif,
        "--xb-bq-body-font": FONTS[bq.font_body] || FONTS.sans,
        "--xb-bq-cols": String(bq.columns),
        "--xb-bq-cols-wide": String(bq.columns + 1),
        "--xb-bq-radius": bq.corners === "rounded" ? "0.9rem" : "0",
    };
    for (const [name, value] of Object.entries(vars)) {
        root.style.setProperty(name, value);
    }
    // Buttons and highlights in the main color (Odoo takes it from the company otherwise).
    insertKioskStyle(bq.primary);
    if (bq.app) {
        startApp();
    }
}

function startApp() {
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.register("/xb-boutique/sw.js", { scope: "/pos-self/" }).catch(() => {});
    }
    const installed = () =>
        window.matchMedia("(display-mode: fullscreen)").matches ||
        window.matchMedia("(display-mode: standalone)").matches;
    // In a plain browser tab, the first touch switches to full screen.
    document.addEventListener(
        "pointerdown",
        () => {
            if (!installed() && !document.fullscreenElement && document.documentElement.requestFullscreen) {
                document.documentElement.requestFullscreen({ navigationUI: "hide" }).catch(() => {});
            }
        },
        { capture: true }
    );
}

patch(selfOrderIndex.prototype, {
    setup() {
        super.setup(...arguments);
        const bq = boutique(this.selfOrder);
        if (bq) {
            applyBoutique(bq);
        }
    },
});

patch(OrderWidget.prototype, {
    get buttonToShow() {
        const res = super.buttonToShow;
        const bq = boutique(this.selfOrder);
        if (!bq) {
            return res;
        }
        const page = this.router.activeSlot;
        if (page === "product_list") {
            return { ...res, label: boutiqueText(bq, "checkout") };
        }
        if (page === "cart") {
            return { ...res, label: boutiqueText(bq, "order") };
        }
        return res;
    },
});

patch(ProductListPage.prototype, {
    xbBqText(key) {
        return boutiqueText(boutique(this.selfOrder), key);
    },
    /**
     * Price of the list card. With "From", products whose options change the price
     * show the cheapest combination.
     */
    xbBqPrice(product) {
        const selfOrder = this.selfOrder;
        const bq = boutique(selfOrder);
        let extra = 0;
        let range = false;
        for (const line of product.attribute_line_ids || []) {
            const extras = (line.product_template_value_ids || []).map((v) => v.price_extra || 0);
            if (!extras.length) {
                continue;
            }
            const low = Math.min(...extras);
            extra += low;
            range = range || Math.max(...extras) !== low;
        }
        const from = bq.price === "from" && (range || Boolean(product._xb_desde));
        // A jewel priced by its metal already brings its own lowest price.
        if (!from || !extra || product._xb_desde) {
            return { from, amount: selfOrder.getProductDisplayPrice(product) };
        }
        const pricelist = selfOrder.currentOrder.preset_id?.pricelist_id || selfOrder.config.pricelist_id;
        const price = product.getPrice(pricelist, 1, extra);
        const taxes = product.getTaxDetails({
            overridedValues: { price, fiscalPosition: selfOrder.currentOrder?.fiscal_position_id || false },
        });
        return {
            from,
            amount: selfOrder.isTaxesIncludedInPrice() ? taxes.total_included : taxes.total_excluded,
        };
    },
});

function playVideos() {
    // Chrome only autoplays when the muted PROPERTY is set; the attribute is not enough.
    for (const video of document.querySelectorAll(".xb_bq_video")) {
        if (!video.muted) {
            video.muted = true;
        }
        if (video.paused) {
            video.play().catch(() => {});
        }
    }
}

patch(ProductPage.prototype, {
    setup() {
        super.setup(...arguments);
        this.xbBq = useState({ slide: 0 });
        onMounted(playVideos);
        onPatched(playVideos);
    },
    get xbBqGallery() {
        const bq = boutique(this.selfOrder);
        return bq ? bq.gallery : "single";
    },
    /** Video first (if any), then the main photo and the extra photos. */
    get xbBqSlides() {
        const product = this.props.productTemplate;
        const media = product._xb_bq_media || {};
        const main = `/web/image/product.template/${product.id}/image_1024?unique=${product.write_date}`;
        const slides = [];
        if ((media.video || []).length) {
            slides.push({ key: "video", video: media.video, poster: main });
        }
        slides.push({ key: "main", src: main });
        for (const [index, src] of (media.photos || []).entries()) {
            slides.push({ key: `photo${index}`, src });
        }
        return slides;
    },
    xbBqOnScroll(ev) {
        const el = ev.currentTarget;
        this.xbBq.slide = Math.round(el.scrollLeft / Math.max(el.clientWidth, 1));
    },
});

patch(CartPage.prototype, {
    xbBqText(key) {
        return boutiqueText(boutique(this.selfOrder), key);
    },
});

patch(ConfirmationPage.prototype, {
    xbBqText(key) {
        return boutiqueText(boutique(this.selfOrder), key);
    },
});
