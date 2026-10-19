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
        if (piece.blurb) { box.appendChild(el("p", "band-blurb", piece.blurb)); }
        box.appendChild(el("div", "band-rule"));
        var strip = dataStrip(piece, 3);
        strip.classList.add("inline");
        box.appendChild(strip);
        return box;
    }

    function paperBand(piece, state, soloPieza) {
        /* El vídeo se queda a sangre completa —no se cede un pixel— y el
           título se apoya en la esquina baja, donde el cuadro sólo tiene
           fondo de estudio: nada cae sobre la joya. */
        var band = el("section", "band band-light");
        if (piece.bg) { band.style.background = piece.bg; }
        var stage = el("div", "band-stage");
        stage.appendChild(media(piece, state));
        band.appendChild(stage);
        if (soloPieza) { return band; }
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

    /* ---------------------------------------------------------------
       PIECES WITHOUT A CASE OR HAND SHOT
       Earrings, old wedding bands: the catalogue has no photo of them in
       the case or worn. Captions only go on photos that really are that;
       the empty side gets the piece's details or the shop's invitation,
       and extra angles of the piece fill the side panels when it has them.
       --------------------------------------------------------------- */
    function specRows(piece, limit) {
        var list = el("div", "pb-specs");
        (piece.specs || []).slice(0, limit).forEach(function (spec) {
            var row = el("div", "pb-spec");
            row.appendChild(el("span", null, spec.label));
            row.appendChild(el("b", null, spec.value));
            list.appendChild(row);
        });
        return list;
    }

    function detailsBand(piece, state) {
        var band = el("section", "band band-gold pb-ficha");
        var box = el("div", "pb-ficha-box");
        if (state.kicker_text) { box.appendChild(el("div", "pb-kicker", state.kicker_text)); }
        box.appendChild(el("h1", "pb-name", piece.name || ""));
        if (piece.subtitle) { box.appendChild(el("div", "pb-sub", piece.subtitle)); }
        box.appendChild(el("div", "pb-rule"));
        box.appendChild(specRows(piece, 5));
        if (piece.reference) { box.appendChild(el("div", "band-ref pb-ref", "Ref. " + piece.reference)); }
        band.appendChild(box);
        return band;
    }

    function inviteBand(piece, state) {
        var band = el("section", "band pb-marca");
        var box = el("div", "pb-marca-box");
        if (logo) { box.appendChild(shot(logo, "pb-logo")); }
        if (state.ask_text) { box.appendChild(el("div", "pb-invite", state.ask_text)); }
        if (piece.price) { box.appendChild(el("div", "band-price", piece.price)); }
        if (piece.qr) {
            box.appendChild(shot(piece.qr, "band-qr pb-qr"));
            box.appendChild(el("div", "band-note pb-note", state.qr_text || ""));
        }
        band.appendChild(box);
        return band;
    }

    function angleBand(url, piece, state, withQr) {
        var band = el("section", "band band-light pb-angulo");
        if (piece.bg) { band.style.background = piece.bg; }
        var stage = el("div", "band-stage");
        stage.appendChild(shot(url, "pb-angle"));
        band.appendChild(stage);
        if (withQr && piece.qr) {
            var row = el("div", "pb-qr-corner");
            row.appendChild(el("div", "band-note pb-note dark", state.qr_text || ""));
            row.appendChild(shot(piece.qr, "band-qr"));
            band.appendChild(row);
        }
        return band;
    }

    /* Pieces with their own painter (registered by another module in
       window.XBWallPlugins): the first painter that answers draws them. */
    function pluginSingle(piece, panels, state) {
        var painters = window.XBWallPlugins || [];
        for (var i = 0; i < painters.length; i++) {
            var drawn = painters[i](piece, panels, state, { el: el, shot: shot, logo: logo });
            if (drawn) { return drawn; }
        }
        return null;
    }

    function renderMosaicSingle(piece, panels, state) {
        var own = pluginSingle(piece, panels, state);
        if (own) { return own; }
        var frag = document.createDocumentFragment();
        var shots = piece.shots || {};
        var angles = shots.angles || [];
        if (panels >= 3 && !shots.case && !shots.hand && angles.length) {
            // Extra angles on the sides, the piece and its name in the centre.
            frag.appendChild(angleBand(angles[0], piece, state, false));
            frag.appendChild(paperBand(piece, state));
            frag.appendChild(angles[1] ? angleBand(angles[1], piece, state, true)
                                       : inviteBand(piece, state));
            return frag;
        }
        // The details panel already names the piece: the centre shows it alone.
        var alone = panels >= 2 && !shots.case;
        if (panels >= 2) {
            frag.appendChild(shots.case ? goldBand(piece, state) : detailsBand(piece, state));
        }
        frag.appendChild(paperBand(piece, state, alone));
        if (panels >= 3) {
            frag.appendChild(shots.hand ? photoBand(piece, state) : inviteBand(piece, state));
        }
        return frag;
    }

    /* --------------------------------------------------------------
       COMPARAR DE 2 A 6 PIEZAS

       Regla que manda sobre todo lo demás: **una celda nunca cruza un
       bisel**. El muro siempre se divide en tres columnas iguales (una por
       pantalla) y, cuando hay más de tres piezas, la pantalla se parte en
       mitades. Así ninguna joya aparece cortada por el marco de dos
       monitores, que es lo que pasaba al repartir dos piezas en 2880 px.

       La pantalla del centro es SIEMPRE la de diferencias (precio «Desde»,
       metal, piedras…), sea cual sea el número de piezas:
         2 piezas → pieza · diferencias · pieza
         3 piezas → dos mitades · diferencias · pieza
         4 piezas → dos mitades · diferencias · dos mitades
         5 piezas → tres tercios · diferencias · dos mitades
         6 piezas → tres tercios · diferencias · tres tercios
       -------------------------------------------------------------- */
    function comparePanel(piece, state, compact) {
        var band = el("section", "band band-compare" + (compact ? " half" : "") + (compact === "third" ? " third" : ""));
        if (piece.bg) { band.style.background = piece.bg; }

        var stage = el("div", "band-stage");
        stage.appendChild(media(piece, state));
        band.appendChild(stage);
        band.appendChild(el("div", "band-corner-veil"));

        /* La referencia distingue y es corta; el nombre de categoría haría
           que todas las piezas se llamaran igual. */
        band.appendChild(titleBlock(piece, "band-corner",
            piece.__diff ? piece.__diff : (piece.short || piece.reference || piece.product_name || piece.name)));
        if (piece.__diff) { band.classList.add("same-model"); }

        /* Las tomas extra (de lado, en estuche, en la mano) salen siempre,
           también en mitades y tercios: arriba a la derecha y más chicas,
           para no chocar con el texto de la esquina baja. */
        var shots = piece.shots || {};
        var thumbs = el("div", "band-thumbs" + (compact ? " stacked" : ""));
        var extra = [shots.side, shots.case, shots.hand].filter(Boolean);
        if (!extra.length) { extra = (shots.angles || []).filter(Boolean); }
        extra.slice(0, 3).forEach(function (url) {
            thumbs.appendChild(shot(url, "thumb"));
        });
        if (thumbs.childNodes.length) { band.appendChild(thumbs); }
        return band;
    }

    function halfScreen(pieces, state) {
        var holder = el("section", "band band-split");
        pieces.forEach(function (piece) {
            holder.appendChild(comparePanel(piece, state, true));
        });
        return holder;
    }

    function thirdScreen(pieces, state) {
        var holder = el("section", "band band-split thirds");
        pieces.forEach(function (piece) {
            holder.appendChild(comparePanel(piece, state, "third"));
        });
        return holder;
    }

    /* La pantalla del medio cuando hay número par: en qué se diferencian.
       Una columna por pieza y una fila por dato. Lo que cambia entre ellas
       va en oro y lo que comparten se apaga: justo la pregunta del cliente
       frente a dos anillos parecidos. */
    function differencesTable(pieces, state) {   // tabla 1.16 (ya no se usa)
        var band = el("section", "band band-diff");
        band.appendChild(el("div", "diff-title", state.diff_text || ""));

        // Todas las filas que tenga cualquiera de las piezas, en su orden.
        var labels = [];
        // The second line is the metal only while the piece has no commercial
        // description; when it has one, the metal is already among the specs.
        // Mixing both kinds, the metal gets one row: from the subtitle for the
        // first kind and from the specs for the second.
        var metalLabel = (state.metal_text || "Metal").toLowerCase();
        function isMetal(spec) { return (spec.label || "").toLowerCase() === metalLabel; }
        function metalOf(piece) {
            if (!piece.metal_in_specs) { return piece.subtitle || "—"; }
            var found = (piece.specs || []).filter(isMetal)[0];
            return found ? found.value : "—";
        }
        var mixed = pieces.some(function (p) { return p.subtitle && !p.metal_in_specs; });
        if (mixed) { labels.push("__metal"); }
        pieces.forEach(function (piece) {
            (piece.specs || []).forEach(function (spec) {
                if (mixed && isMetal(spec)) { return; }
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
                if (label === "__metal") { return metalOf(piece); }
                var found = (piece.specs || []).filter(function (spec) {
                    return spec.label === label;
                })[0];
                return found ? found.value : "—";
            });
            var differs = values.some(function (v) { return v !== values[0]; });
            // Lo que es igual en todas (medida 3.0 – 8.0, piedra…) no ayuda a
            // decidir: se omite. El precio «Desde» va siempre.
            if (!differs && label !== "__price") { return; }
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

    /* ---------------------------------------------------------------
       TARJETAS «COMPARA Y ELIGE» (1.17.0)
       La pantalla del centro: una tarjeta por anillo con el estilo de la
       tienda (Jost, crema, dorado). Foto principal y sus tomas en estuche y
       en la mano, precio por kilataje, sólo los datos que cambian entre los
       anillos, una etiqueta que ayuda a decidir y un QR para llevárselo.
       --------------------------------------------------------------- */
    function numberIn(text, afterPlus) {
        var t = String(text || "");
        if (afterPlus && t.indexOf("+") >= 0) { t = t.split("+")[1]; }
        var m = t.replace(/,/g, "").match(/[\d.]+/);
        return m ? parseFloat(m[0]) : null;
    }

    function specValue(piece, word) {
        // «Piedras» (conteo) antes que «Piedra» (la opción zirconia/diamante).
        var specs = piece.specs || [];
        var found = specs.filter(function (spec) {
            return (spec.label || "").toLowerCase() === word + "s";
        })[0] || specs.filter(function (spec) {
            return (spec.label || "").toLowerCase().indexOf(word) >= 0;
        })[0];
        return found ? found.value : null;
    }

    function badgesFor(pieces, state) {
        var texts = state.badge_texts || {};
        var rules = [
            ["price", function (p) {
                // Un diamante natural no trae su piedra central en el precio:
                // compararlo como «el más accesible» engañaría.
                if (isNatural(p)) { return null; }
                var c = chosenPrice(p); return c === null ? null : -c; }],
            ["stones", function (p) { return numberIn(specValue(p, "acentos")); }],
            ["gold", function (p) { return isGold(p) ? numberIn(specValue(p, "peso")) : null; }],  // el platino pesa más, pero no es oro
            ["width", function (p) { return numberIn(specValue(p, "ancho")); }]
        ];
        var given = {};
        rules.forEach(function (rule) {
            if (!texts[rule[0]]) { return; }
            var values = pieces.map(rule[1]);
            var valid = values.filter(function (v) { return v !== null && !isNaN(v); });
            if (valid.length < 2) { return; }
            var best = Math.max.apply(null, valid);
            var winners = values.reduce(function (acc, v, i) { if (v === best) { acc.push(i); } return acc; }, []);
            if (winners.length !== 1 || given[winners[0]] !== undefined) { return; }
            given[winners[0]] = texts[rule[0]];
        });
        return given;
    }

    /* MISMO MODELO: todas las piezas son el mismo diseño (mismo nombre).
       Entonces lo que importa es justo lo que el cliente cambió. */
    function sameModel(pieces) {
        return pieces.length > 1 && pieces.every(function (p) {
            return p.product_name && p.product_name === pieces[0].product_name;
        });
    }
    var OPTION_LABELS = ["piedra central", "metal", "medida"];
    function specOf(piece, label) {
        var f = (piece.specs || []).filter(function (s) { return (s.label || "").toLowerCase() === label; })[0];
        return f ? f.value : "";
    }
    function prettyMetal(v) {
        return String(v || "").replace(/(\d+)\s*kt/i, "$1K").replace(/Platino Puro \(999\)/, "Platino").replace(/Plata \(925\)/, "Plata .925");
    }
    function diffLabel(piece, pieces, state) {
        var parts = [];
        OPTION_LABELS.forEach(function (label) {
            var vals = pieces.map(function (p) { return specOf(p, label); });
            if (!vals.some(function (v) { return v !== vals[0]; })) { return; }
            var v = specOf(piece, label);
            if (label === "metal") { v = prettyMetal(v); }
            if (label === "medida") { v = (state.size_text || "Size") + " " + v; }
            parts.push(v);
        });
        return parts.join(" · ");
    }
    function isGold(piece) { return /oro/i.test(specOf(piece, "metal") || "oro"); }
    function isNatural(piece) { return /natural/i.test(specOf(piece, "piedra central") || specOf(piece, "piedra")); }
    function priceOf(piece, state) {
        var ks = piece.karats || [];
        var k = ks.filter(function (x) { return x.chosen; })[0];
        var metal = prettyMetal(specOf(piece, "metal"));
        if (isGold(piece) && ks.length) {
            if (k) { return {label: metal || k.label, price: k.price}; }
            return {label: (state.from_text || "Desde") + " " + ks[0].label, price: ks[0].price};
        }
        return {label: metal, price: piece.price};
    }
    function chosenPrice(p) { return numberIn(priceOf(p, {}).price); }

    function stoneType(piece) {
        if (!piece.stone_type) { return ""; }
        return piece.stone_type.replace(/ de /g, " ")
            .replace(/(\d+)\.00 ct/, "$1 ct").replace(/(\d+\.\d)0 ct/, "$1 ct")
            .replace(/·.*$/, "").trim().replace(/^Zirconia$/, "Zirconias")
            .replace(/^Diamante laboratorio/, "Diam. lab.").replace(/^Diamante natural/, "Diam. natural");
    }

    function isStones(label) { return (label || "").toLowerCase() === "piedras"; }

    function factLabel(piece, label) {
        // «PIEDRAS: ZIRCONIAS» arriba y cuántas abajo, en la misma columna.
        return label;
    }

    function factValue(piece, label) {
        var f = (piece.specs || []).filter(function (s) { return s.label === label; })[0];
        var value = f ? f.value : "—";
        // El quilataje de un diamante natural depende de la piedra que se elija.
        if (!f && /quilataje/i.test(label || "") && isNatural(piece)) { value = factState.quote || "A cotizar"; }
        
        return value;
    }

    function differingRows(pieces, state) {
        var metalLabel = (state.metal_text || "Metal").toLowerCase();
        var labels = [];
        if (state.__same) {
            pieces.forEach(function (piece) {
                (piece.specs || []).forEach(function (spec) {
                    var low = (spec.label || "").toLowerCase();
                    if (low === "piedra") { return; }   // «Piedra central» ya lo dice
                    if (labels.indexOf(spec.label) < 0) { labels.push(spec.label); }
                });
            });
            var differs = function (label) {
                var values = pieces.map(function (piece) { return factValue(piece, label); });
                return values.some(function (v) { return v !== values[0]; });
            };
            return labels.filter(differs);
        }
        pieces.forEach(function (piece) {
            (piece.specs || []).forEach(function (spec) {
                var low = (spec.label || "").toLowerCase();
                // Las opciones (metal, medida, piedra) ya se leen en los precios y
                // en «Con diamante…»: en la tabla sólo estorban.
                if (low === metalLabel || ["medida", "piedra", "size", "stone"].indexOf(low) >= 0) { return; }
                if (labels.indexOf(spec.label) < 0) { labels.push(spec.label); }
            });
        });
        return labels.filter(function (label) {
            var values = pieces.map(function (piece) { return factLabel(piece, label) + "|" + factValue(piece, label); });
            return values.some(function (v) { return v !== values[0]; });
        });
    }

    function compareCard(piece, state, badge, rows) {
        /* Diseño «Revista»: la foto del anillo puesto llena la tarjeta, la
           joya va en un círculo dorado y los datos sobre un velo oscuro. */
        var card = el("article", "cc-card");
        var shots = piece.shots || {};
        var fondo = shots.hand || shots.case;
        if (fondo) { card.appendChild(shot(fondo, "cc-bg")); } else { card.classList.add("plain"); }
        var box = el("div", "cc-in");
        box.appendChild(shot(piece.image, "cc-ring"));
        box.appendChild(el("div", "cc-badge" + (badge ? "" : " empty"), badge || "·"));
        if (state.__same) {
            box.appendChild(el("div", "cc-name same", piece.__diff || "—"));
            box.appendChild(el("div", "cc-sub", piece.subtitle || piece.short || piece.product_name || ""));
        } else {
            box.appendChild(el("div", "cc-name", piece.short || piece.reference || piece.product_name || piece.name));
            if (piece.subtitle) { box.appendChild(el("div", "cc-sub", piece.subtitle)); }
        }
        /* Solo el precio de lo que se eligió: comparar otros metales es
           trabajo del comparador, no de cada tarjeta. Sin combinación
           elegida (mandada desde la rejilla) va el «desde». */
        if (isNatural(piece)) { piece.stone_note = state.natural_note || ""; }
        var one = priceOf(piece, state);
        if (one.price) {
            var pr = el("div", "cc-price-one");
            if (one.label) { pr.appendChild(el("span", null, one.label)); }
            pr.appendChild(el("b", null, one.price));
            box.appendChild(pr);
            if (piece.stone_note) { box.appendChild(el("div", "cc-stone", piece.stone_note)); }
        }
        if (rows.length || piece.lead_text) {
            var facts = el("div", "cc-facts");
            rows.forEach(function (label) {
                var item = el("div", "cc-fact" + (state.__same ? " hot" : ""));
                item.appendChild(el("span", null, factLabel(piece, label)));
                var fv = factValue(piece, label);
                if ((label || "").toLowerCase() === "metal") { fv = prettyMetal(fv); }
                item.appendChild(el("b", null, fv));
                facts.appendChild(item);
            });
            // El plazo de cada anillo (Plazo de entrega al cliente) va siempre.
            if (piece.lead_text) {
                var lead = el("div", "cc-fact lead");
                lead.appendChild(el("span", null, state.lead_label || ""));
                lead.appendChild(el("b", null, piece.lead_text));
                facts.appendChild(lead);
            }
            box.appendChild(facts);
        }
        card.appendChild(box);
        // Sin QR: el cliente se lleva la selección con la base NFC del mostrador.
        return card;
    }

    var factState = {};
    function differencesPanel(pieces, state) {
        factState.quote = state.quote_text;
        var band = el("section", "band cc-panel");
        band.dataset.n = String(pieces.length);
        var head = state.__same
            ? [state.same_text, (pieces[0].short || pieces[0].product_name), state.diff_kicker]
            : [state.diff_text, state.diff_kicker];
        band.appendChild(el("header", "cc-head", head.filter(Boolean).join(" · ")));
        var grid = el("div", "cc-grid");
        var badges = badgesFor(pieces, state);
        var rows = differingRows(pieces, state);
        pieces.forEach(function (piece, i) {
            grid.appendChild(compareCard(piece, state, badges[i], rows));
        });
        band.appendChild(grid);
        if (state.diff_footer) { band.appendChild(el("footer", "cc-footer", state.diff_footer)); }
        return band;
    }

    function renderMosaicCompare(pieces, state) {
        var frag = document.createDocumentFragment();
        state.__same = sameModel(pieces);
        if (state.__same) {
            pieces.forEach(function (p) {
                p.__diff = diffLabel(p, pieces, state);
                if (p.__diff) { p.subtitle = (p.short || p.product_name) + (p.subtitle ? " · " + p.subtitle : ""); }
            });
        }
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
            frag.appendChild(halfScreen(pieces.slice(0, 2), state));
            frag.appendChild(differencesPanel(pieces, state));
            frag.appendChild(comparePanel(pieces[2], state));
            return frag;
        }
        if (n === 4) {
            frag.appendChild(halfScreen(pieces.slice(0, 2), state));
            frag.appendChild(differencesPanel(pieces, state));
            frag.appendChild(halfScreen(pieces.slice(2, 4), state));
            return frag;
        }
        if (n === 5) {
            frag.appendChild(thirdScreen(pieces.slice(0, 3), state));
            frag.appendChild(differencesPanel(pieces, state));
            frag.appendChild(halfScreen(pieces.slice(3, 5), state));
            return frag;
        }
        frag.appendChild(thirdScreen(pieces.slice(0, 3), state));
        frag.appendChild(differencesPanel(pieces, state));
        frag.appendChild(thirdScreen(pieces.slice(3, 6), state));
        return frag;
    }

    function renderSingle(piece, panels, state) {
        var own = pluginSingle(piece, panels, state);
        if (own) { return own; }
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
        if (shopWindow) { turno += 1; }
        if (shopWindow && shopWindow.timer) { clearInterval(shopWindow.timer); }
        shopWindow = null;
    }

    /* The next piece's photographs are fetched while this one is on screen:
       they weigh a megabyte each and a shop player that starts downloading
       them at the moment of the change shows the change happening. */
    // The Image objects are kept: one that is dropped may be dropped from
    // the player's memory too, and then the change downloads it again.
    var precargadas = [];

    function precargar(piece) {
        if (!piece) { return; }
        var shots = piece.shots || {};
        precargadas = [];
        [shots.case, shots.hand, piece.image, piece.ring].forEach(function (url) {
            if (url) { var img = new Image(); img.src = url; precargadas.push(img); }
        });
    }

    /* Calls ``done`` once every photo in ``node`` is downloaded and decoded,
       or after ``limit`` ms, whichever comes first. A shop player is slow:
       swapping the moment the new piece is built is what showed one screen
       with its photo and the other two blank or drawn half way. */
    var LISTA_MAX = 8000;    // shop window: nobody is waiting for the change
    var LISTA_VIVO = 700;    // a piece sent from the tablet: someone is
    function cuandoListas(node, done, limit) {
        var imgs = [].slice.call(node.querySelectorAll ? node.querySelectorAll("img") : []);
        var pendientes = imgs.length;
        var hecho = false;
        function fin() {
            if (hecho) { return; }
            hecho = true;
            done();
        }
        if (!pendientes) { return fin(); }
        var reloj = window.setTimeout(fin, limit || LISTA_MAX);
        function una() {
            pendientes -= 1;
            if (pendientes <= 0) { window.clearTimeout(reloj); fin(); }
        }
        imgs.forEach(function (img) {
            var listo = function () {
                if (img.decode) {
                    img.decode().then(una, una);
                } else {
                    una();
                }
            };
            if (img.complete && img.naturalWidth) {
                listo();
            } else {
                img.addEventListener("load", listo, { once: true });
                img.addEventListener("error", una, { once: true });
            }
        });
    }

    var turno = 0;   // a newer paint cancels one still waiting for photos

    function paintShopWindow() {
        if (!shopWindow || !shopWindow.pieces.length) { return; }
        var piece = shopWindow.pieces[shopWindow.index % shopWindow.pieces.length];
        var siguiente = shopWindow.pieces[(shopWindow.index + 1) % shopWindow.pieces.length];
        var panels = Math.max(Math.min(cfg.panels || 3, 3), 1);
        var holder = document.createElement("div");
        holder.appendChild((cfg.style || "mosaic") === "mosaic"
            ? renderMosaicSingle(piece, panels, shopWindow.state)
            : renderSingle(piece, panels, shopWindow.state));
        var mio = ++turno;
        cuandoListas(holder, function () {
            if (!shopWindow || mio !== turno) { return; }
            wall.classList.remove("on");
            window.setTimeout(function () {
                if (!shopWindow || mio !== turno) { return; }
                if ((cfg.style || "mosaic") !== "mosaic") { applyBackground(piece.bg); }
                wall.dataset.panels = String(panels);
                wall.dataset.mode = "single";
                wall.textContent = "";
                while (holder.firstChild) { wall.appendChild(holder.firstChild); }
                wall.classList.add("on");
                precargar(siguiente);
            }, 420);
        });
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
        var mosaic = (cfg.style || "mosaic") === "mosaic";
        var holder = document.createElement("div");
        if (state.mode === "compare") {
            holder.appendChild(mosaic
                ? renderMosaicCompare(pieces, state)
                : renderCompare(pieces.slice(0, panels), state));
        } else {
            holder.appendChild(mosaic
                ? renderMosaicSingle(pieces[0], panels, state)
                : renderSingle(pieces[0], panels, state));
        }
        // A sales person is waiting for this one: speed wins over a perfect
        // first frame. The photos are light and usually cached, so whatever
        // is still missing after a moment lands in place right after.
        var mio = ++turno;
        cuandoListas(holder, function () {
            if (mio !== turno) { return; }
            hidePlain();
            idle.classList.remove("on");
            if (!mosaic) { applyBackground(pieces[0].bg); }
            wall.dataset.panels = String(panels);
            wall.dataset.mode = state.mode === "compare" ? "compare" : "single";
            wall.style.setProperty("--cols", String(panels));
            wall.textContent = "";
            while (holder.firstChild) { wall.appendChild(holder.firstChild); }
            wall.classList.add("on");
        }, LISTA_VIVO);
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

    /* Someone tapped the counter's NFC stand: the wall answers on the
       middle screen for a few seconds, over whatever it is showing, so the
       customer sees that the gesture reached it. Only transforms and
       opacity move, the player has a weak GPU. */
    var lastTap = null;
    function tapNote(state) {
        var tap = state.tap || 0;
        if (lastTap === null) { lastTap = tap; return; }   // a reload is not a tap
        if (!tap || tap === lastTap) { return; }
        lastTap = tap;
        var old = document.querySelector(".tap-note");
        if (old) { old.remove(); }
        var note = el("div", "tap-note");
        var icon = el("div", "tap-icon");
        icon.appendChild(el("span", "tap-wave"));
        icon.appendChild(el("span", "tap-wave w2"));
        icon.appendChild(el("span", "tap-phone"));
        note.appendChild(icon);
        note.appendChild(el("div", "tap-title", state.tap_text || ""));
        if (state.tap_sub) { note.appendChild(el("div", "tap-sub", state.tap_sub)); }
        document.body.appendChild(note);
        window.setTimeout(function () { note.classList.add("out"); }, 6500);
        window.setTimeout(function () { note.remove(); }, 7400);
    }

    /* The piece just sent says its name (bell + name, an MP3 made on the
       server). Only once per push, never on a reload or for the pieces
       that were already there. */
    var lastVoice = null;
    function sayName(state) {
        var key = state.voice ? String(state.voice.key) : "";
        if (lastVoice === null) { lastVoice = key; return; }
        if (!key || key === lastVoice) { return; }
        lastVoice = key;
        try {
            var audio = new Audio(state.voice.url);
            audio.volume = 1;
            var playing = audio.play();
            if (playing && playing.catch) {
                playing.catch(function (error) { console.warn("[showroom] voice blocked", error); });
            }
        } catch (error) {
            console.warn("[showroom] voice failed", error);
        }
    }

    function paint(state) {
        if (checkVersion(state)) { return; }
        tapNote(state);
        sayName(state);
        if (state.rev === rev) { return; }
        rev = state.rev;
        if (state.live) { goLive(state); } else { goIdle(state); }
    }

    /* One request at a time. A shop player that stalls for a few seconds
       otherwise wakes up with twenty requests queued, all answered at once,
       and the piece it was sent waits behind them. */
    var enVuelo = false;

    function poll() {
        if (enVuelo) { return; }
        enVuelo = true;
        var control = window.AbortController ? new AbortController() : null;
        var corte = control ? window.setTimeout(function () { control.abort(); }, 8000) : null;
        fetch("/showroom/wall/" + encodeURIComponent(cfg.token) + "/state",
              { cache: "no-store", credentials: "omit", signal: control ? control.signal : undefined })
            .then(function (response) {
                if (!response.ok) { throw new Error("http " + response.status); }
                return response.json();
            })
            .then(function (state) {
                failures = 0;
                paint(state);
                // Read by the safety net in the page head.
                window.__xbWallBeat = Date.now();
            })
            .catch(function (error) {
                // Keep the current piece on screen: a hiccup in the shop's
                // wifi must never turn the wall black in front of a customer.
                failures += 1;
                if (failures === 1 || failures % 30 === 0) {
                    console.warn("[showroom] state unreachable", error);
                }
            })
            .then(function () {
                enVuelo = false;
                if (corte) { window.clearTimeout(corte); }
            });
    }

    poll();
    setInterval(poll, Math.max(cfg.poll || 2, 1) * 1000);
})();
