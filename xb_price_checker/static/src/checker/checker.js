/* Price checker screen: a barcode scanner types the code and Enter; the screen shows the product, then goes back. */
(function () {
    "use strict";
    function start() {
        const root = document.getElementById("xb_price_checker");
        if (!root) {
            return;
        }
        const $ = (selector) => root.querySelector(selector);
        const texts = {};
        for (const el of root.querySelectorAll(".xpc-texts [data-key]")) {
            texts[el.dataset.key] = el.textContent.trim();
        }
        const idle = (parseInt(root.dataset.idle, 10) || 15) * 1000;
        const input = $(".xpc-input");
        const screens = { wait: $(".xpc-wait"), result: $(".xpc-result"), message: $(".xpc-message") };
        let timer = null;
        let busy = false;

        function show(name, back) {
            clearTimeout(timer);
            for (const [key, el] of Object.entries(screens)) {
                el.classList.toggle("xpc-show", key === name);
            }
            if (name === "wait") {
                $(".xpc-hint").textContent = texts.hint;
            } else {
                timer = setTimeout(() => show("wait"), back);
            }
        }

        function setText(selector, value) {
            const el = $(selector);
            el.textContent = value || "";
            el.hidden = !value;
            return el;
        }

        async function lookup(code) {
            code = (code || "").trim();
            if (!code || busy) {
                return;
            }
            busy = true;
            if (screens.wait.classList.contains("xpc-show")) {
                $(".xpc-hint").textContent = texts.searching;
            }
            let answer = null;
            try {
                const response = await fetch("/price-checker/lookup", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {
                        config_id: parseInt(root.dataset.config, 10), token: root.dataset.token, barcode: code } }),
                });
                answer = (await response.json()).result || null;
            } catch {
                answer = null;
            }
            busy = false;
            if (!answer || !answer.found) {
                $(".xpc-message-title").textContent = answer ? texts.notFound : texts.offline;
                show("message", 5000);
                return;
            }
            const photo = $(".xpc-photo");
            photo.hidden = !answer.image;
            if (answer.image) {
                photo.src = "data:image/png;base64," + answer.image;
            }
            setText(".xpc-name", answer.name);
            setText(".xpc-ref", answer.reference);
            setText(".xpc-before", answer.before_text);
            setText(".xpc-discount", answer.discount_text);
            $(".xpc-before-row").hidden = !answer.before_text;
            setText(".xpc-price", answer.price_text).classList.toggle("xpc-sale", Boolean(answer.before_text));
            setText(".xpc-months", answer.months_text);
            const stock = setText(".xpc-stock", answer.stock_text);
            stock.classList.toggle("xpc-yes", answer.in_stock === true);
            stock.classList.toggle("xpc-no", answer.in_stock === false);
            show("result", idle);
            screens.result.scrollTop = 0;
        }

        // The scanner types into this field: keep the focus on it, without opening the on-screen keyboard.
        const focus = () => {
            if (document.activeElement !== input) {
                input.focus({ preventScroll: true });
            }
        };
        document.addEventListener("click", focus);
        setInterval(focus, 1000);
        focus();
        $(".xpc-form").addEventListener("submit", (event) => {
            event.preventDefault();
            const code = input.value;
            input.value = "";
            lookup(code);
        });
        $(".xpc-type").addEventListener("click", (event) => {
            event.stopPropagation();
            const code = window.prompt(texts.prompt);
            lookup(code);
        });
        show("wait");
    }
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
