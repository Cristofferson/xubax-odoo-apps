/* Showroom wall front-end.
 *
 * Polls Odoo and paints whatever the tablet pushed. Two rules matter on a
 * shop floor: never blank the wall because a request failed, and never
 * restart a video that is already playing the right piece.
 */
(function () {
    "use strict";

    var cfg = JSON.parse(document.getElementById("cfg").textContent || "{}");
    var wall = document.getElementById("wall");
    var idle = document.getElementById("idle");
    var logo = document.body.dataset.logo || "";
    var plain = null;
    var rev = null;
    var idleLoaded = "";
    var failures = 0;
    var shopWindow = null;   // {pieces, interval, index, timer}

    var root = document.documentElement;
    root.style.setProperty("--accent", cfg.accent || "#cda349");
    if (cfg.background) {
        root.style.setProperty("--bg", cfg.background);
        document.body.style.background = cfg.background;
    }

    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) { node.className = cls; }
        if (text !== undefined && text !== null && text !== "") { node.textContent = text; }
        return node;
    }

    function media(piece, state) {
        /* The shop window changes piece every few seconds: starting a new
           video that often is what stutters on a modest player, so unless the
           screen asks for it the window rotates photographs and the video is
           kept for the piece a sales person puts on the wall. */
        var enVitrina = state && state.live === false;
        var fuentes = (enVitrina && !state.idle_video)
            ? []
            : (piece.videos || (piece.video ? [{ url: piece.video, type: "video/mp4" }] : []));
        if (fuentes.length) {
            var video = el("video");
            // One <source> per format: a player whose browser lacks the H.264
            // decoder still plays the WebM copy, and the picture never goes
            // missing without anyone noticing.
            fuentes.forEach(function (fuente) {
                var source = document.createElement("source");
                source.src = fuente.url;
                source.type = fuente.type;
                video.appendChild(source);
            });
            video.autoplay = true;
            video.loop = true;
            video.muted = true;          // browsers only autoplay muted video
            video.playsInline = true;
            video.setAttribute("muted", "");
            video.setAttribute("playsinline", "");
            video.preload = "auto";
            // A missing or unplayable file must not leave an empty panel: the
            // error fires on the <video> when no source could be played.
            video.addEventListener("error", function () {
                var img = el("img");
                img.src = piece.image;
                if (video.parentNode) { video.parentNode.replaceChild(img, video); }
            }, true);
            /* El panel toma su color de fondo de la FOTO del anillo, y el
               vídeo trae el suyo, de otra sesión de estudio: con los dos
               juntos se dibuja un rectángulo. En cuanto hay un cuadro, se lee
               su esquina y el panel se pinta de ese mismo color. */
            video.addEventListener("loadeddata", function () {
                try {
                    var lienzo = document.createElement("canvas");
                    lienzo.width = 16; lienzo.height = 16;
                    var ctx = lienzo.getContext("2d");
                    ctx.drawImage(video, 0, 0, 16, 16);
                    var punto = ctx.getImageData(1, 1, 1, 1).data;
                    var banda = video.parentNode && video.parentNode.closest
                        ? video.parentNode.closest(".band")
                        : null;
                    if (banda) {
                        banda.style.background = "rgb(" + punto[0] + "," + punto[1] + "," + punto[2] + ")";
                    }
                } catch (e) { /* sin permiso para leer el cuadro: queda el fondo de la foto */ }
            });
            // Some embedded browsers ignore the autoplay attribute; asking
            // once the file is ready costs nothing where it already plays.
            video.addEventListener("canplay", function () {
                var intento = video.play();
                if (intento && intento.catch) { intento.catch(function () { /* queda el primer cuadro */ }); }
            });
            return video;
        }
        var img = el("img");
        img.src = piece.image;
        img.alt = piece.name || "";
        return img;
    }

    function specLine(spec) {
        var line = el("div", "spec");
        line.appendChild(el("span", null, spec.label + ": "));
        line.appendChild(el("b", null, spec.value));
        return line;
    }

    function shot(url, cls) {
        var img = el("img", cls);
        img.src = url;
        img.alt = "";
        return img;
    }

    function facts(piece) {
        var box = el("div", "facts");
        box.appendChild(el("div", "name", piece.name));
        box.appendChild(el("div", "rule"));
        (piece.specs || []).forEach(function (spec) {
            box.appendChild(specLine(spec));
        });
        if (piece.price) { box.appendChild(el("div", "price", piece.price)); }
        if (piece.reference) { box.appendChild(el("div", "ref", piece.reference)); }
        return box;
    }

    function invite(piece, state) {
        var box = el("div", "invite");
        if (logo) { box.appendChild(shot(logo, "brand")); }
        if (piece.qr) {
            var row = el("div", "qrow");
            row.appendChild(shot(piece.qr, "qr"));
            row.appendChild(el("div", "qrtext", state.qr_text || ""));
            box.appendChild(row);
        }
        return box;
    }

    /* One piece across the wall: the turning video owns the centre panel, the
       piece in its case goes left with the specs, and the piece worn on a hand
       goes right with the QR. A piece without those shots simply falls back to
       specs and QR, so an incomplete catalogue never leaves a panel broken. */
    /* ---------------------------------------------------------------
       COLOUR BANDS
       Every panel is a grid with a row per element: headline, piece, data.
       Nothing is positioned on top of anything else, so a long product name
       can never land on the jewel — it wraps inside its own row instead.
       --------------------------------------------------------------- */
    function bandRow(cls, child) {
        var row = el("div", cls);
        if (child) { row.appendChild(child); }
        return row;
    }

    function dataStrip(piece, limit) {
        var strip = el("div", "band-strip");
        (piece.specs || []).slice(0, limit || 4).forEach(function (spec) {
            var item = el("span", "strip-item");
            item.appendChild(el("span", "strip-label", spec.label));
            item.appendChild(el("b", null, spec.value));
            strip.appendChild(item);
        });
        return strip;
    }

    function goldBand(piece, state) {
        /* La foto manda: ocupa la pantalla completa y los rótulos van sobre
           un velo, no en franjas que le roben alto. */
        var band = el("section", "band band-gold");
        var shots = piece.shots || {};
        band.appendChild(shot(shots.case || piece.ring || piece.image, "band-bleed case"));
        band.appendChild(el("div", "band-veil bottom"));

        var foot = el("div", "band-foot over-bottom");
        var left = el("div", "band-footcol");
        left.appendChild(el("div", "band-kicker", state.case_text || ""));
        left.appendChild(el("div", "band-ref", piece.reference ? "Ref. " + piece.reference : ""));
        foot.appendChild(left);
        if (logo) { foot.appendChild(shot(logo, "band-logo")); }
        band.appendChild(foot);
        return band;
    }

    function titleBlock(piece, cls, headline) {
        /* Dos renglones: el nombre grande y el metal debajo en cursiva. Con
           una sola línea todo pesaba igual y el título se leía como etiqueta. */
        var box = el("div", cls);
        var head = el("h1", "band-headline");
        // Sólo el nombre se recorta a dos renglones: el metal va aparte y
        // nunca desaparece por culpa de un nombre largo.
        head.appendChild(el("span", "band-name", headline || piece.name || ""));
        if (piece.subtitle) {
            head.appendChild(el("span", "band-sub", piece.subtitle));
        }
        box.appendChild(head);
        box.appendChild(el("div", "band-rule"));
        var strip = dataStrip(piece, 3);
        strip.classList.add("inline");
        box.appendChild(strip);
        return box;
    }

    function paperBand(piece, state) {
        /* El vídeo se queda a sangre completa —no se cede un pixel— y el
           título se apoya en la esquina baja, donde el cuadro sólo tiene
           fondo de estudio: nada cae sobre la joya. */
        var band = el("section", "band band-light");
        if (piece.bg) { band.style.background = piece.bg; }
        var stage = el("div", "band-stage");
        stage.appendChild(media(piece, state));
        band.appendChild(stage);
        band.appendChild(el("div", "band-corner-veil"));
        band.appendChild(titleBlock(piece, "band-corner"));
        if (piece.reference) {
            band.appendChild(el("div", "band-ref corner-right", "Ref. " + piece.reference));
        }
        return band;
    }

    function photoBand(piece, state) {
        var band = el("section", "band band-photo");
        var shots = piece.shots || {};
        var picture = shots.hand || shots.case || piece.image;
        band.appendChild(shot(picture, "band-bleed"));
        band.appendChild(el("div", "band-scrim"));

        var over = el("div", "band-over");
        over.appendChild(el("h2", "band-worn", state.worn_text || ""));
        if (piece.price) { over.appendChild(el("div", "band-price", piece.price)); }
        if (piece.qr) {
            var row = el("div", "band-qrow");
            row.appendChild(el("div", "band-note", state.qr_text || ""));
            row.appendChild(shot(piece.qr, "band-qr"));
            over.appendChild(row);
        }
        band.appendChild(over);
        return band;
    }

    function renderMosaicSingle(piece, panels, state) {
        var frag = document.createDocumentFragment();
        if (panels >= 2) { frag.appendChild(goldBand(piece, state)); }
        frag.appendChild(paperBand(piece, state));
        if (panels >= 3) { frag.appendChild(photoBand(piece, state)); }
        return frag;
    }

    /* --------------------------------------------------------------
       COMPARAR DE 2 A 6 PIEZAS

       Regla que manda sobre todo lo demás: **una celda nunca cruza un
       bisel**. El muro siempre se divide en tres columnas iguales (una por
       pantalla) y, cuando hay más de tres piezas, la pantalla se parte en
       mitades. Así ninguna joya aparece cortada por el marco de dos
       monitores, que es lo que pasaba al repartir dos piezas en 2880 px.

         2 piezas → pieza · diferencias · pieza
         3 piezas → una por pantalla
         4 piezas → dos mitades · diferencias · dos mitades
         5 piezas → dos mitades · pieza · dos mitades
         6 piezas → dos mitades · dos mitades · dos mitades
       -------------------------------------------------------------- */
    function comparePanel(piece, state, compact) {
        var band = el("section", "band band-compare" + (compact ? " half" : ""));
        if (piece.bg) { band.style.background = piece.bg; }

        var stage = el("div", "band-stage");
        stage.appendChild(media(piece, state));
        band.appendChild(stage);
        band.appendChild(el("div", "band-corner-veil"));

        /* La referencia distingue y es corta; el nombre de categoría haría
           que todas las piezas se llamaran igual. */
        band.appendChild(titleBlock(piece, "band-corner",
            piece.short || piece.reference || piece.product_name || piece.name));

        if (!compact) {
            var shots = piece.shots || {};
            var thumbs = el("div", "band-thumbs");
            [shots.case, shots.hand].forEach(function (url) {
                if (url) { thumbs.appendChild(shot(url, "thumb")); }
            });
            if (thumbs.childNodes.length) { band.appendChild(thumbs); }
        }
        return band;
    }

    function halfScreen(pieces, state) {
        var holder = el("section", "band band-split");
        pieces.forEach(function (piece) {
            holder.appendChild(comparePanel(piece, state, true));
        });
        return holder;
    }

    /* La pantalla del medio cuando hay número par: en qué se diferencian.
       Una columna por pieza y una fila por dato. Lo que cambia entre ellas
       va en oro y lo que comparten se apaga: justo la pregunta del cliente
       frente a dos anillos parecidos. */
    function differencesPanel(pieces, state) {
        var band = el("section", "band band-diff");
        band.appendChild(el("div", "diff-title", state.diff_text || ""));

        // Todas las filas que tenga cualquiera de las piezas, en su orden.
        var labels = [];
        // The second line is the metal only while the piece has no commercial
        // description; when it has one, the metal is already among the specs.
        if (pieces.some(function (p) { return p.subtitle && !p.metal_in_specs; })) {
            labels.push("__metal");
        }
        pieces.forEach(function (piece) {
            (piece.specs || []).forEach(function (spec) {
                if (labels.indexOf(spec.label) < 0) { labels.push(spec.label); }
            });
        });
        if (pieces.some(function (p) { return p.price; })) { labels.push("__price"); }

        var table = el("div", "diff-table");
        table.style.setProperty("--n", String(pieces.length));
        table.dataset.n = String(pieces.length);
        var head = el("div", "diff-row head");
        head.appendChild(el("div", "diff-label", ""));
        pieces.forEach(function (piece) {
            head.appendChild(el("div", "diff-cell",
                piece.short || piece.reference || piece.product_name || piece.name));
        });
        table.appendChild(head);

        labels.forEach(function (label) {
            var values = pieces.map(function (piece) {
                if (label === "__price") { return piece.price || "—"; }
                if (label === "__metal") { return piece.subtitle || "—"; }
                var found = (piece.specs || []).filter(function (spec) {
                    return spec.label === label;
                })[0];
                return found ? found.value : "—";
            });
            var differs = values.some(function (v) { return v !== values[0]; });
            var row = el("div", "diff-row" + (differs ? " differs" : " same"));
            var text = label === "__price" ? (state.price_text || "")
                : label === "__metal" ? (state.metal_text || "") : label;
            row.appendChild(el("div", "diff-label", text));
            values.forEach(function (value) {
                row.appendChild(el("div", "diff-cell", value));
            });
            table.appendChild(row);
        });
        band.appendChild(table);
        if (logo) { band.appendChild(shot(logo, "diff-logo")); }
        return band;
    }

    function renderMosaicCompare(pieces, state) {
        var frag = document.createDocumentFragment();
        var n = pieces.length;

        if (n <= 1) {
            frag.appendChild(renderMosaicSingle(pieces[0], 3, state));
            return frag;
        }
        if (n === 2) {
            frag.appendChild(comparePanel(pieces[0], state));
            frag.appendChild(differencesPanel(pieces, state));
            frag.appendChild(comparePanel(pieces[1], state));
            return frag;
        }
        if (n === 3) {
            pieces.forEach(function (piece) {
                frag.appendChild(comparePanel(piece, state));
            });
            return frag;
        }
        if (n === 4) {
            frag.appendChild(halfScreen(pieces.slice(0, 2), state));
            frag.appendChild(differencesPanel(pieces, state));
            frag.appendChild(halfScreen(pieces.slice(2, 4), state));
            return frag;
        }
        if (n === 5) {
            frag.appendChild(halfScreen(pieces.slice(0, 2), state));
            frag.appendChild(comparePanel(pieces[2], state));
            frag.appendChild(halfScreen(pieces.slice(3, 5), state));
            return frag;
        }
        frag.appendChild(halfScreen(pieces.slice(0, 2), state));
        frag.appendChild(halfScreen(pieces.slice(2, 4), state));
        frag.appendChild(halfScreen(pieces.slice(4, 6), state));
        return frag;
    }

    function renderSingle(piece, panels, state) {
        var frag = document.createDocumentFragment();
        var shots = piece.shots || {};

        var stage = el("div", "piece");
        stage.appendChild(media(piece, state));

        if (panels === 1) {
            frag.appendChild(stage);
            frag.appendChild(facts(piece));
            return frag;
        }

        var left = el("div", "cell side");
        if (shots.case) { left.appendChild(shot(shots.case, "side-shot")); }
        var row = el("div", "facts-row");
        if (shots.case && piece.ring) { row.appendChild(shot(piece.ring, "chip")); }
        row.appendChild(facts(piece));
        left.appendChild(row);

        frag.appendChild(left);
        frag.appendChild(stage);

        if (panels >= 3) {
            var right = el("div", "cell side right");
            if (shots.hand) { right.appendChild(shot(shots.hand, "side-shot")); }
            right.appendChild(invite(piece, state));
            frag.appendChild(right);
        }
        return frag;
    }

    /* Comparing: one piece per panel, each with its own small set of shots so
       the customer still sees how it sits in the case and on a hand. */
    function renderCompare(pieces, state) {
        var frag = document.createDocumentFragment();
        pieces.forEach(function (piece) {
            var card = el("div", "card");
            card.appendChild(media(piece));

            var shots = piece.shots || {};
            var thumbs = el("div", "thumbs");
            [piece.ring, shots.case, shots.hand].forEach(function (url) {
                if (url) { thumbs.appendChild(shot(url, "thumb")); }
            });
            if (thumbs.childNodes.length) { card.appendChild(thumbs); }

            card.appendChild(el("div", "name", piece.name));
            (piece.specs || []).slice(0, 2).forEach(function (spec) {
                card.appendChild(specLine(spec));
            });
            if (piece.price) { card.appendChild(el("div", "price", piece.price)); }
            frag.appendChild(card);
        });
        return frag;
    }

    function showPlain(heading) {
        if (!plain) {
            plain = el("div", "plain");
            if (logo) {
                var brand = el("img", "brand");
                brand.src = logo;
                plain.appendChild(brand);
            }
            plain.appendChild(el("div", "heading", heading || ""));
            document.body.appendChild(plain);
        }
        plain.style.opacity = "1";
    }

    function hidePlain() {
        if (plain) { plain.style.opacity = "0"; }
    }

    /* Rotating shop window, drawn with the same three-panel layout as a
       pushed piece: on a multi-panel wall the jewel has to stay on the
       centre panel, which a page built for one screen cannot do. */
    function stopShopWindow() {
        if (shopWindow && shopWindow.timer) { clearInterval(shopWindow.timer); }
        shopWindow = null;
    }

    /* The next piece's photographs are fetched while this one is on screen:
       they weigh a megabyte each and a shop player that starts downloading
       them at the moment of the change shows the change happening. */
    function precargar(piece) {
        if (!piece) { return; }
        var shots = piece.shots || {};
        [shots.case, shots.hand, piece.image, piece.ring].forEach(function (url) {
            if (url) { var img = new Image(); img.src = url; }
        });
    }

    function paintShopWindow() {
        if (!shopWindow || !shopWindow.pieces.length) { return; }
        var piece = shopWindow.pieces[shopWindow.index % shopWindow.pieces.length];
        precargar(shopWindow.pieces[(shopWindow.index + 1) % shopWindow.pieces.length]);
        wall.classList.remove("on");
        window.setTimeout(function () {
            if (!shopWindow) { return; }
            if ((cfg.style || "mosaic") !== "mosaic") { applyBackground(piece.bg); }
            wall.dataset.panels = String(Math.max(Math.min(cfg.panels || 3, 3), 1));
            wall.dataset.mode = "single";
            wall.textContent = "";
            var panels = Math.max(Math.min(cfg.panels || 3, 3), 1);
            wall.appendChild((cfg.style || "mosaic") === "mosaic"
                ? renderMosaicSingle(piece, panels, shopWindow.state)
                : renderSingle(piece, panels, shopWindow.state));
            wall.classList.add("on");
        }, 420);
    }

    function goShopWindow(state) {
        hidePlain();
        idle.classList.remove("on");
        var same = shopWindow
            && shopWindow.pieces.length === state.pieces.length
            && shopWindow.pieces.every(function (piece, i) {
                return piece.id === state.pieces[i].id;
            });
        if (same) { return; }          // same rotation, let it keep running
        stopShopWindow();
        shopWindow = {
            pieces: state.pieces,
            state: state,
            interval: Math.max(state.interval || 9, 2) * 1000,
            index: 0,
            timer: null,
        };
        paintShopWindow();
        shopWindow.timer = setInterval(function () {
            shopWindow.index += 1;
            paintShopWindow();
        }, shopWindow.interval);
    }

    function goIdle(state) {
        if (state.idle_mode === "own" && (state.pieces || []).length) {
            return goShopWindow(state);
        }
        stopShopWindow();
        applyBackground("");
        wall.classList.remove("on");
        wall.textContent = "";
        if (state.idle_url) {
            hidePlain();
            if (idleLoaded !== state.idle_url) {
                idle.src = state.idle_url;
                idleLoaded = state.idle_url;
            }
            idle.classList.add("on");
        } else {
            idle.classList.remove("on");
            showPlain(state.heading);
        }
    }

    /* Blend the wall into the photo's own backdrop when the server sends one. */
    function applyBackground(colour) {
        if (colour) {
            root.style.setProperty("--bg", colour);
            document.body.style.background = colour;
        } else if (!cfg.background) {
            root.style.removeProperty("--bg");
            document.body.style.background = "";
        }
    }

    function goLive(state) {
        stopShopWindow();
        var panels = Math.max(Math.min(cfg.panels || 3, 3), 1);
        var pieces = state.pieces || [];
        if (!pieces.length) { return goIdle(state); }
        hidePlain();
        idle.classList.remove("on");
        if ((cfg.style || "mosaic") !== "mosaic") { applyBackground(pieces[0].bg); }
        wall.dataset.panels = String(panels);
        wall.dataset.mode = state.mode === "compare" ? "compare" : "single";
        wall.style.setProperty("--cols", String(panels));
        wall.textContent = "";
        var mosaic = (cfg.style || "mosaic") === "mosaic";
        if (state.mode === "compare") {
            wall.appendChild(mosaic
                ? renderMosaicCompare(pieces, state)
                : renderCompare(pieces.slice(0, panels), state));
        } else {
            wall.appendChild(mosaic
                ? renderMosaicSingle(pieces[0], panels, state)
                : renderSingle(pieces[0], panels, state));
        }
        wall.classList.add("on");
    }

    /* A screen hanging in a shop is never reloaded by hand, and a player
       keeps the script for days. When the server answers with a newer
       version than the one this page is running, the wall reloads itself. */
    function checkVersion(state) {
        if (state.stamp && cfg.stamp && String(state.stamp) !== String(cfg.stamp)) {
            window.location.reload();
            return true;
        }
        return false;
    }

    function paint(state) {
        if (checkVersion(state)) { return; }
        if (state.rev === rev) { return; }
        rev = state.rev;
        if (state.live) { goLive(state); } else { goIdle(state); }
    }

    function poll() {
        fetch("/showroom/wall/" + encodeURIComponent(cfg.token) + "/state",
              { cache: "no-store", credentials: "omit" })
            .then(function (response) {
                if (!response.ok) { throw new Error("http " + response.status); }
                return response.json();
            })
            .then(function (state) {
                failures = 0;
                paint(state);
            })
            .catch(function (error) {
                // Keep the current piece on screen: a hiccup in the shop's
                // wifi must never turn the wall black in front of a customer.
                failures += 1;
                if (failures === 1 || failures % 30 === 0) {
                    console.warn("[showroom] state unreachable", error);
                }
            });
    }

    poll();
    setInterval(poll, Math.max(cfg.poll || 2, 1) * 1000);
})();
