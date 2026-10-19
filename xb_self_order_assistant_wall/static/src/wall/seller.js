/* XUBAX - the kiosk's virtual seller on the videowall: small, with subtitles and voice.
   Plain ES5: the wall player may run an old browser. */
(function () {
    "use strict";
    var cfg = {};
    try { cfg = JSON.parse(document.getElementById("cfg").textContent || "{}"); } catch (e) { cfg = {}; }
    if (!cfg.token) { return; }
    var base = "/xb-va/w/" + encodeURIComponent(cfg.token);
    var box, still, idle, talk, nameEl, sub, lastSeq = -1, audio = null, current = null;

    function el(tag, cls, parent) {
        var e = document.createElement(tag);
        if (cls) { e.className = cls; }
        if (parent) { parent.appendChild(e); }
        return e;
    }

    function build() {
        box = el("div", "", document.body);
        box.id = "xbva-pip";
        var media = el("div", "xbva-media", box);
        still = el("img", "xbva-still", media);
        idle = el("video", "", media);
        talk = el("video", "xbva-talk", media);
        [idle, talk].forEach(function (v) { v.muted = true; v.loop = true; v.autoplay = true; v.setAttribute("playsinline", ""); });
        nameEl = el("div", "xbva-name", box);
        sub = el("div", "xbva-sub", box);
    }

    function setSrc(node, url) {
        if (url && node.getAttribute("data-src") !== url) {
            node.setAttribute("data-src", url);
            node.src = url;
        }
        node.style.display = url ? "" : "none";
    }

    function speakingState(on) {
        if (on) { box.className += box.className.indexOf("talking") < 0 ? " talking" : ""; }
        else { box.className = box.className.replace(/\s*talking/g, ""); }
    }

    function render(state) {
        if (!box) { build(); }
        if (!state.on) {
            box.className = "";
            if (audio) { audio.pause(); audio = null; }
            lastSeq = -1;
            return;
        }
        if (box.className.indexOf("on") < 0) { box.className = "on"; }
        nameEl.textContent = state.name || "";
        setSrc(still, state.idle ? null : (state.full || state.face));
        setSrc(idle, state.idle);
        setSrc(talk, state.talk);
        if (state.seq !== lastSeq) {
            lastSeq = state.seq;
            sub.textContent = state.text || "";
            if (state.audio && state.audio !== current) {
                current = state.audio;
                if (audio) { audio.pause(); }
                audio = new Audio(state.audio);
                audio.onplay = function () { speakingState(true); };
                audio.onended = audio.onpause = function () { speakingState(false); };
                var playing = audio.play();
                if (playing && playing.catch) { playing.catch(function () { speakingState(false); }); }
            }
        }
    }

    function poll() {
        var xhr = new XMLHttpRequest();
        xhr.open("POST", base + "/state");
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.onload = function () {
            try { render(JSON.parse(xhr.responseText).result || { on: false }); } catch (e) { /* keep last */ }
        };
        xhr.send(JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }));
    }

    setInterval(poll, 1500);
    poll();
})();
