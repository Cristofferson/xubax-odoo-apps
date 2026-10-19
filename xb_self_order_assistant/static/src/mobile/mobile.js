/**
 * XUBAX - Virtual seller on the customer's phone: the kiosk conversation continues here,
 * by voice (live) or by writing. Plain module, no framework.
 */
import { XbLiveVoice } from "/xb_self_order_assistant/static/src/app/live.js";

const boot = JSON.parse(document.getElementById("m-boot").textContent);
const T = boot.texts;
const $ = (id) => document.getElementById(id);
const base = `/xb-va/${boot.config_id}`;
let token = boot.token;
let live = null;
let busy = false;

async function call(route, params = {}) {
    const resp = await fetch(`${base}/${route}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: { m: boot.m, token, ...params } }),
    });
    const data = await resp.json();
    if (data.error) {
        throw new Error(data.error.message || "error");
    }
    return data.result;
}

// One call after the other: in parallel they collide saving the same conversation.
let queue = Promise.resolve();
const serial = (fn) => {
    const run = queue.then(fn, fn);
    queue = run.catch(() => {});
    return run;
};

function push(who, text) {
    const el = document.createElement("div");
    el.className = `m-msg m-${who}`;
    el.textContent = text;
    $("m-list").appendChild(el);
    $("m-list").scrollTop = $("m-list").scrollHeight;
}

function status(text, cls = "") {
    $("m-status").textContent = text;
    $("m-face").className = `m-face ${cls}`;
}

async function showCards(ids) {
    if (!ids || !ids.length) {
        return;
    }
    const { cards } = await serial(() => call("cards", { ids }));
    renderCards(cards);
}

function renderCards(cards) {
    const box = $("m-cards");
    box.innerHTML = "";
    for (const c of cards) {
        const a = document.createElement(c.url ? "a" : "div");
        a.className = "m-card";
        if (c.url) {
            a.href = c.url;
            a.target = "_blank";
        }
        const img = document.createElement("img");
        img.src = c.image;
        img.alt = c.name;
        img.loading = "lazy";
        const name = document.createElement("b");
        name.textContent = c.name;
        const price = document.createElement("span");
        price.textContent = c.price;
        a.append(img, name, price);
        box.appendChild(a);
    }
}

// ------------------------------------------------------------ live voice
async function startLive() {
    status(T.thinking);
    try {
        const res = await call("live");
        if (!res.ok) {
            throw new Error("no live");
        }
        token = res.token || token;
        live = new XbLiveVoice({
            onSpeaking: (on) => status(on ? T.speaking : T.listening, on ? "talking" : "listening"),
            onListening: (on) => {
                $("m-mic").classList.toggle("on", on);
                status(on ? T.listening : T.talk, on ? "listening" : "");
            },
            onCustomer: (text) => {
                push("customer", text);
                serial(() => call("live_log", { who: "customer", text }));
            },
            onSeller: (text) => {
                push("seller", text);
                serial(() => call("live_log", { who: "seller", text }));
            },
            onTool: async (name, args) => {
                const res = await serial(() => call("tool", { name, args }));
                const ui = res.ui || {};
                if (ui.products && ui.products.length) {
                    showCards(ui.products);
                }
                return res.output;
            },
            onUsage: (usage) => serial(() => call("live_log", { usage })),
            onSentence: (text) => sayLater(text),
            onError: (error) => console.warn("live voice", error),
            onEnd: () => {
                live = null;
                $("m-mic").classList.remove("on");
                status(T.talk);
            },
        }, { textMode: boot.rt_voice === "tts" });
        await live.start(res);
    } catch {
        live = null;
        push("seller", T.error);
        status(T.talk);
    }
}

// Adjustable-accent voice: each sentence with the chosen voice, the microphone paused meanwhile.
const voiceQueue = [];
let playing = false;
async function voiceUrl(text) {
    const form = new FormData();
    form.append("m", boot.m);
    form.append("token", token);
    form.append("text", text);
    try {
        const resp = await fetch(`${base}/speak`, { method: "POST", body: form });
        const blob = await resp.blob();
        return resp.ok && blob.size ? URL.createObjectURL(blob) : null;
    } catch {
        return null;
    }
}
function sayLater(text) {
    if (!boot.speak) {
        return;
    }
    voiceQueue.push(voiceUrl(text));
    if (!playing) {
        playQueue();
    }
}
async function playQueue() {
    playing = true;
    const wasMuted = live ? live.muted : false;
    if (live) {
        live.mute(true);
    }
    status(T.speaking, "talking");
    while (voiceQueue.length) {
        const url = await voiceQueue.shift();
        if (url) {
            await new Promise((resolve) => {
                const audio = new Audio(url);
                audio.onended = audio.onerror = resolve;
                audio.play().catch(resolve);
            });
        }
    }
    playing = false;
    if (live && !wasMuted) {
        live.mute(false);
    }
}

// ------------------------------------------------------------ step by step (written, spoken answer)
async function speak(text) {
    if (!boot.speak) {
        return;
    }
    const form = new FormData();
    form.append("m", boot.m);
    form.append("token", token);
    form.append("text", text);
    const resp = await fetch(`${base}/speak`, { method: "POST", body: form });
    const blob = await resp.blob();
    if (blob.size) {
        new Audio(URL.createObjectURL(blob)).play().catch(() => {});
    }
}

async function send(text) {
    text = (text || "").trim();
    if (!text || busy) {
        return;
    }
    $("m-input").value = "";
    push("customer", text);
    if (live) {
        serial(() => call("live_log", { who: "customer", text }));
        live.say(text);
        return;
    }
    busy = true;
    status(T.thinking);
    try {
        const res = await serial(() => call("chat", { text }));
        token = res.token || token;
        push("seller", res.reply);
        if (res.products && res.products.length) {
            renderCards(await (await serial(() => call("cards", { ids: res.products.map((p) => p.id) }))).cards);
        }
        speak(res.reply);
    } catch {
        push("seller", T.error);
    } finally {
        busy = false;
        status(T.talk);
    }
}

// ------------------------------------------------------------ start
async function init() {
    $("m-name").textContent = boot.name;
    $("m-input").placeholder = T.placeholder;
    $("m-send").textContent = T.send;
    if (boot.avatar && boot.avatar.face) {
        $("m-face").src = `${base}/avatar/face?m=${boot.m}&unique=${encodeURIComponent(boot.avatar.stamp)}`;
    }
    status(T.talk);
    try {
        const history = await call("history");
        for (const msg of history.messages) {
            push(msg.who, msg.text);
        }
        renderCards(history.products);
    } catch {
        // a new conversation
    }
    push("system", T.welcome);
    $("m-send").addEventListener("click", () => send($("m-input").value));
    $("m-input").addEventListener("keydown", (ev) => ev.key === "Enter" && send($("m-input").value));
    $("m-mic").addEventListener("click", () => {
        if (boot.engine !== "realtime") {
            $("m-input").focus();
            return;
        }
        if (live) {
            live.mute(!live.muted);
        } else {
            startLive();
        }
    });
}

init();
