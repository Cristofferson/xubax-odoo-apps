/* Showroom remote control, as used from the shop assistant's tablet.
 *
 * The buttons are rendered hidden and only revealed once the server confirms
 * a screen exists, so the shop looks untouched when no wall is set up.
 */
(function () {
    "use strict";

    var buttons = document.querySelectorAll(".o_showroom_btn");
    if (!buttons.length) { return; }

    var screens = [];
    var current = null;
    var token = null;
    var labels = {};   // filled by the server, already translated

    /* Each tablet belongs to a wall. The choice is kept in this browser, so
       it survives every page the sales person opens, and the tablet of one
       branch keeps sending to that branch's wall. A setup link can also fix
       it once: /shop?showroom_screen=<id>. Storage may be unavailable
       (private mode); the tablet then simply starts on the first wall. */
    var STORE_KEY = "xb_showroom_screen";

    function remembered() {
        try { return parseInt(window.localStorage.getItem(STORE_KEY), 10) || null; }
        catch (e) { return null; }
    }

    function remember(id) {
        try { window.localStorage.setItem(STORE_KEY, String(id)); }
        catch (e) { /* not kept: the tablet falls back to the first wall */ }
    }

    function requested() {
        try {
            return parseInt(new URLSearchParams(window.location.search).get("showroom_screen"), 10) || null;
        } catch (e) { return null; }
    }

    function useScreen(id) {
        var screen = screens.filter(function (s) { return s.id === id; })[0] || screens[0];
        current = screen.id;
        token = screen.token || null;
        document.querySelectorAll(".o_showroom_screen").forEach(function (select) {
            select.value = String(current);
        });
        return screen;
    }

    function rpc(route, params) {
        return fetch(route, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params || {},
                id: Math.floor(Math.random() * 1e9),
            }),
        }).then(function (response) {
            return response.json();
        }).then(function (payload) {
            if (payload.error) {
                throw new Error(payload.error.data && payload.error.data.message
                    || payload.error.message || "rpc error");
            }
            return payload.result || {};
        });
    }

    function reveal() {
        var bars = document.querySelectorAll(".o_showroom_bar");
        bars.forEach(function (bar) { bar.classList.remove("d-none"); });
        if (bars.length) { document.body.classList.add("o_showroom_has_bar"); }
        buttons.forEach(function (button) { button.classList.remove("d-none"); });
        if (screens.length > 1) {
            document.querySelectorAll(".o_showroom_screen").forEach(function (select) {
                select.textContent = "";
                screens.forEach(function (screen) {
                    var option = document.createElement("option");
                    option.value = screen.id;
                    option.textContent = screen.name;
                    select.appendChild(option);
                });
                select.value = String(current);
                select.classList.remove("d-none");
                select.addEventListener("change", function () {
                    var screen = useScreen(parseInt(select.value, 10));
                    remember(screen.id);
                    say((labels.screen_set || "%s").replace("%s", screen.name));
                    refreshNow();
                });
            });
        }
    }

    /* A small mirror of the wall, so the sales person never has to turn
       around to check what the customer is looking at. While comparing,
       each piece carries a cross to take just that one off the wall. */
    function screenInfo() {
        return screens.filter(function (screen) { return screen.id === current; })[0] || screens[0] || {};
    }

    function removeSlot(slotId) {
        rpc("/showroom/remove", { screen_id: current, slot_id: slotId }).then(function (result) {
            if (result.error) { return say(result.error, true); }
            say(labels.removed);
            refreshNow();
        }).catch(function (error) {
            say(String(error.message || error), true);
        });
    }

    function setClearLabels(comparing) {
        document.querySelectorAll(".o_showroom_clear").forEach(function (button) {
            var text = comparing ? labels.new_compare : labels.back_idle;
            if (text) { button.textContent = text; }
        });
    }

    function refreshNow() {
        var slots = document.querySelectorAll(".o_showroom_now");
        if (!slots.length || !token) { return; }
        fetch("/showroom/wall/" + encodeURIComponent(token) + "/state",
              { cache: "no-store", credentials: "omit" })
            .then(function (response) { return response.json(); })
            .then(function (state) {
                var live = state.live && state.pieces.length;
                var comparing = live && state.mode === "compare";
                setClearLabels(comparing);
                slots.forEach(function (node) {
                    node.textContent = "";
                    if (!live) {
                        node.textContent = labels.idle || "";
                        return;
                    }
                    var max = screenInfo().compare_max || state.pieces.length;
                    node.appendChild(document.createTextNode(comparing && labels.comparing_of
                        ? labels.comparing_of.replace("%(count)s", state.pieces.length)
                                             .replace("%(max)s", max)
                        : (labels.on_air || "")));
                    state.pieces.forEach(function (piece) {
                        var item = document.createElement(comparing ? "button" : "span");
                        item.className = "o_showroom_thumb";
                        var img = document.createElement("img");
                        img.src = piece.image;
                        img.alt = piece.reference || piece.name;
                        item.appendChild(img);
                        if (comparing && piece.slot) {
                            item.type = "button";
                            item.title = labels.remove || "";
                            item.setAttribute("aria-label",
                                (labels.remove || "") + " " + (piece.reference || piece.name));
                            var cross = document.createElement("span");
                            cross.className = "o_showroom_x";
                            cross.textContent = "\u00d7";
                            item.appendChild(cross);
                            item.addEventListener("click", function (event) {
                                event.preventDefault();
                                removeSlot(piece.slot);
                            });
                        }
                        node.appendChild(item);
                    });
                });
            })
            .catch(function () { /* the bar simply shows nothing */ });
    }

    /* One notice at a time. A single timer, so an older notice clearing
       itself can never wipe a newer one before it was read. */
    var sayTimer = null;
    function say(message, isError, seconds) {
        document.querySelectorAll(".o_showroom_feedback").forEach(function (node) {
            node.textContent = message || "";
            node.classList.toggle("text-danger", !!isError);
            node.classList.toggle("text-success", !isError);
        });
        if (sayTimer) { clearTimeout(sayTimer); sayTimer = null; }
        if (message) {
            sayTimer = setTimeout(function () {
                sayTimer = null;
                document.querySelectorAll(".o_showroom_feedback").forEach(function (node) {
                    node.textContent = "";
                });
            }, (seconds || 4) * 1000);
        }
    }

    /* The price the customer is looking at right now, so the wall shows the
       same figure instead of one recomputed somewhere else. */
    function shownPrice() {
        var node = document.querySelector("#product_details .oe_price, .oe_price");
        if (!node) { return null; }
        var digits = (node.textContent || "").replace(/[^0-9.,]/g, "");
        if (!digits) { return null; }
        // Whichever separator comes last is the decimal one.
        var lastDot = digits.lastIndexOf(".");
        var lastComma = digits.lastIndexOf(",");
        var normalised;
        if (lastComma > lastDot) {
            normalised = digits.replace(/\./g, "").replace(",", ".");
        } else {
            normalised = digits.replace(/,/g, "");
        }
        var value = parseFloat(normalised);
        return isNaN(value) ? null : value;
    }

    function productForm() {
        return document.querySelector("#product_details form")
            || document.querySelector("#product_details")
            || document;
    }

    /* The page keeps the variant id at 0 when the chosen metal and size have
       no product yet (dynamic variants), so the options themselves travel:
       the wall then names exactly what the customer picked. */
    function choiceFromForm() {
        var form = productForm();
        var productInput = form.querySelector("input.product_id, input[name='product_id']");
        var templateInput = form.querySelector("input.product_template_id, input[name='product_template_id']");
        var combination = Array.from(form.querySelectorAll(
            "input.js_variant_change:checked, select.js_variant_change"
        )).map(function (node) { return parseInt(node.value, 10); })
          .filter(function (id) { return id > 0; });
        return {
            product_id: productInput ? (parseInt(productInput.value, 10) || null) : null,
            template_id: templateInput ? (parseInt(templateInput.value, 10) || null) : null,
            combination: combination,
        };
    }

    function push(button) {
        var params = {
            mode: button.dataset.showroomMode || "single",
            screen_id: current,
        };
        if (button.dataset.showroomFromForm) {
            var choice = choiceFromForm();
            params.product_id = choice.product_id;
            params.template_id = choice.template_id;
            params.combination = choice.combination;
            params.price = shownPrice();
        } else {
            params.template_id = parseInt(button.dataset.showroomTemplate, 10) || null;
        }
        if (!params.product_id && !params.template_id) {
            say(labels.unknown, true);
            return;
        }
        button.disabled = true;
        rpc("/showroom/push", params).then(function (result) {
            if (result.error) { return say(result.error, true); }
            if (result.message) {
                say(result.message, false, 8);   // a piece left the wall: give time to read it
            } else {
                say(result.mode === "compare"
                    ? (labels.comparing || "%s").replace("%s", result.count)
                    : labels.pushed);
            }
            refreshNow();
        }).catch(function (error) {
            say(String(error.message || error), true);
        }).then(function () {
            button.disabled = false;
        });
    }

    buttons.forEach(function (button) {
        button.addEventListener("click", function (event) {
            event.preventDefault();
            event.stopPropagation();
            push(button);
        });
    });

    document.querySelectorAll(".o_showroom_clear").forEach(function (button) {
        button.addEventListener("click", function (event) {
            event.preventDefault();
            var fresh = labels.new_compare && button.textContent.trim() === labels.new_compare;
            rpc("/showroom/clear", { screen_id: current }).then(function () {
                say(fresh ? labels.compare_ready : labels.cleared);
                refreshNow();
            });
        });
    });

    rpc("/showroom/screens", {}).then(function (result) {
        screens = result.screens || [];
        labels = result.labels || {};
        if (!screens.length) { return; }
        var asked = requested();
        if (asked && screens.some(function (s) { return s.id === asked; })) {
            remember(asked);
        }
        useScreen(remembered());
        reveal();
        refreshNow();
        setInterval(refreshNow, 5000);
    }).catch(function () {
        /* No screen, no remote control: leave the shop exactly as it was. */
    });
})();
