/**
 * XUBAX - Virtual seller for the self-order kiosk: the customer talks (or types) to it,
 * it answers out loud, shows products from the kiosk catalog and can call a person.
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { useSelfOrder } from "@pos_self_order/app/services/self_order_service";
import { selfOrderIndex } from "@pos_self_order/app/self_order_index";
import { XbLiveVoice } from "@xb_self_order_assistant/app/live";
import { XbVaScanner } from "@xb_self_order_assistant/app/scan";
import { XbVaPresence } from "@xb_self_order_assistant/app/presence";

const MAX_RECORD_MS = 15000;
const SILENCE_MS = 1400;
// Hands-free: if nobody speaks this long after the seller listens again, the microphone closes.
const WAIT_SPEECH_MS = 8000;
const HIDDEN_ON = ["payment", "confirmation"];

/**
 * What the seller can do on the kiosk screen besides showing products. Other apps add their
 * own: ``xbVaActions.my_action = (seller, action) => {...}`` (see the wall or layaway apps).
 */
export const xbVaActions = {};

export class XbVirtualSeller extends Component {
    static template = "xb_self_order_assistant.VirtualSeller";
    static props = {};

    setup() {
        this.selfOrder = useSelfOrder();
        this.router = useService("router");
        this.dialog = useService("dialog");
        this.va = this.selfOrder.config._xb_va;
        this.selfOrder.xbVaPicks = this.selfOrder.xbVaPicks || [];
        this.list = useRef("list");
        this.state = useState({
            open: false,
            messages: [],
            busy: false,
            recording: false,
            speaking: false,
            typed: "",
            handoff: false,
            // full = the avatar fills the screen, chat = conversation panel, mini = docked bar
            mode: "chat",
            lastCustomer: "",
            // number keypad to send the selection by WhatsApp
            pad: { open: false, digits: "", sending: false, error: "" },
            waving: false,
            // QR to take the conversation to the customer's phone
            qr: { open: false, src: "", gone: false },
        });
        this.prevMode = "chat";
        this.token = null;
        this.audio = null;
        this.recorder = null;
        this.idleTimer = null;
        this.live = null;
        this.scanner = null;
        // Calls to Odoo one after the other: in parallel they collide saving the same conversation.
        this.queue = Promise.resolve();
        onMounted(() => {
            if (this.va && this.va.scan) {
                this.scanner = new XbVaScanner((code) => this.onScan(code));
                this.scanner.start();
            }
            if (this.va && this.va.greet && this.va.greet !== "off") {
                this.presence = new XbVaPresence((present) => this.onPresence(present));
                this.presence.start();
            }
        });
        onWillUnmount(() => {
            if (this.scanner) {
                this.scanner.stop();
            }
            if (this.presence) {
                this.presence.stop();
            }
            if (this.keepAlive) {
                this.keepAlive.remove();
            }
            this.stopLive();
            this.stopVoice();
            this.stopRecording(true);
            clearTimeout(this.idleTimer);
        });
    }

    get visible() {
        return this.va && this.va.available && !HIDDEN_ON.includes(this.router.activeSlot);
    }

    /** On pages with buttons at the bottom the floating button goes higher. */
    get high() {
        return ["product_list", "product", "cart", "combo_selection"].includes(this.router.activeSlot);
    }

    /** Picture or video of the seller: face (round), full (whole screen), idle and talk (videos). */
    avatarUrl(kind = "face") {
        const avatar = this.va.avatar || {};
        return avatar[kind]
            ? `${this.url}/avatar/${kind}?access_token=${this.selfOrder.access_token}&unique=${encodeURIComponent(avatar.stamp)}`
            : false;
    }

    get hasFull() {
        const avatar = this.va.avatar || {};
        return Boolean(avatar.full || avatar.idle);
    }

    get url() {
        return `/xb-va/${this.selfOrder.config.id}`;
    }

    /** Instant conversation: live voice instead of listen-think-answer. */
    get isLive() {
        return this.va.engine === "realtime" && !!(window.RTCPeerConnection && navigator.mediaDevices);
    }

    // ------------------------------------------------------------ live voice
    async startLive() {
        this.state.busy = true;
        try {
            const res = await rpc(`${this.url}/live`, { access_token: this.selfOrder.access_token, token: this.token });
            this.token = res.token || this.token;
            if (!res.ok) {
                throw new Error("no live session");
            }
            this.live = new XbLiveVoice({
                onSpeaking: (on) => {
                    this.state.speaking = on;
                    this.touch();
                },
                onListening: (on) => (this.state.recording = on),
                onCustomer: (text) => {
                    this.touch();
                    this.push("customer", text);
                    this.state.lastCustomer = text;
                    this.liveLog({ who: "customer", text });
                },
                onSeller: (text) => {
                    this.touch();
                    this.push("seller", text);
                    this.liveLog({ who: "seller", text });
                },
                onTool: (name, args) => this.liveTool(name, args),
                onActivity: () => this.touch(),
                onUsage: (usage) => this.liveLog({ usage }),
                onSentence: (text) => this.sayLater(text),
                onError: (error) => console.warn("Virtual seller live voice:", error),
                onEnd: () => (this.live = null),
            }, { textMode: this.va.rt_voice === "tts" });
            this.voiceQueue = [];
            await this.live.start(res);
        } catch {
            this.stopLive();
            this.push("seller", _t("Sorry, I can't talk right now. You can write your question."));
        } finally {
            this.state.busy = false;
        }
    }

    /**
     * Adjustable-accent voice in the instant conversation: each sentence is said with the chosen
     * voice, one after the other; the microphone pauses meanwhile so the seller does not hear itself.
     */
    sayLater(text) {
        if (this.away || !this.va.speak) {
            return;
        }
        const audio = this.fetchVoice(text);
        this.voiceQueue = this.voiceQueue || [];
        this.voiceQueue.push(audio);
        if (!this.playingQueue) {
            this.playQueue();
        }
    }

    async fetchVoice(text) {
        const form = new FormData();
        form.append("access_token", this.selfOrder.access_token);
        form.append("token", this.token || "");
        form.append("text", text);
        try {
            const resp = await fetch(`${this.url}/speak`, { method: "POST", body: form });
            const blob = await resp.blob();
            return resp.ok && blob.size ? URL.createObjectURL(blob) : null;
        } catch {
            return null;
        }
    }

    async playQueue() {
        this.playingQueue = true;
        const wasMuted = this.live ? this.live.muted : false;
        if (this.live) {
            this.live.mute(true);
        }
        this.state.speaking = true;
        while (this.voiceQueue && this.voiceQueue.length && this.state.open) {
            const url = await this.voiceQueue.shift();
            if (!url) {
                continue;
            }
            await new Promise((resolve) => {
                const audio = new Audio(url);
                this.audio = audio;
                audio.onended = audio.onerror = audio.onpause = resolve;
                audio.play().catch(resolve);
            });
            this.touch();
        }
        this.audio = null;
        this.state.speaking = false;
        this.playingQueue = false;
        if (this.live && !wasMuted) {
            this.live.mute(false);
        }
    }

    stopLive() {
        this.voiceQueue = [];
        if (this.live) {
            this.live.stop();
            this.live = null;
        }
    }

    /** Runs a call to Odoo after the previous ones finished. */
    serial(fn) {
        const run = this.queue.then(fn, fn);
        this.queue = run.catch(() => {});
        return run;
    }

    async liveLog(params) {
        try {
            const res = await this.serial(() => rpc(`${this.url}/live_log`, {
                access_token: this.selfOrder.access_token,
                token: this.token,
                ...params,
            }));
            if (res && res.available === false) {
                this.stopLive();
            }
        } catch {
            // the history is not worth interrupting the conversation
        }
    }

    /** Someone stopped in front of the kiosk: the seller greets (once per visit). */
    onPresence(present) {
        if (!present || !this.visible || this.state.open || this.router.activeSlot === "cart") {
            return;
        }
        const now = Date.now();
        if (this.lastGreet && now - this.lastGreet < 60000) {
            return;
        }
        this.lastGreet = now;
        if (this.va.greet === "open") {
            this.open();
            return;
        }
        this.state.waving = true;
        setTimeout(() => (this.state.waving = false), 8000);
        this.speakGreeting(this.va.greet_text);
    }

    async speakGreeting(text) {
        if (!this.va.speak) {
            return;
        }
        const form = new FormData();
        form.append("access_token", this.selfOrder.access_token);
        form.append("text", text);
        try {
            const resp = await fetch(`${this.url}/speak`, { method: "POST", body: form });
            const blob = await resp.blob();
            if (blob.size && !this.state.open) {
                await new Audio(URL.createObjectURL(blob)).play();
            }
        } catch {
            // a greeting is not worth an error
        }
    }

    /** A card or barcode at the reader: the seller recognizes it and talks about it. */
    async onScan(code) {
        if (!this.visible) {
            return;
        }
        if (!this.state.open) {
            this.open();
        }
        this.touch();
        let res;
        try {
            res = await rpc(`${this.url}/scan`, { access_token: this.selfOrder.access_token, token: this.token, code });
        } catch {
            return;
        }
        if (!res.ok) {
            return;
        }
        this.token = res.token || this.token;
        this.push("system", _t("Read at the kiosk"));
        if (res.open) {
            this.openProduct(res.open);
        } else if (res.products && res.products.length) {
            this.showPicks(res.products);
        }
        this.tell(res.text);
    }

    /** Something the seller must know that the customer did not say (a card, a scan...). */
    tell(text) {
        if (this.live) {
            this.liveLog({ who: "customer", text });
            this.live.say(text);
        } else if (!this.isLive) {
            this.send(text, { silent: true });
        } else {
            // the live voice is still connecting: tell it once it is ready
            setTimeout(() => this.live && this.live.say(text), 2500);
        }
    }

    /** The seller's voice is somewhere else (the wall): the kiosk stays quiet. */
    setAway(on) {
        this.away = on;
        if (this.live && this.live.audio) {
            this.live.audio.muted = on;
        }
        if (on) {
            this.stopVoice();
        }
    }

    async openQr() {
        this.touch();
        if (!this.token) {
            const res = await rpc(`${this.url}/start`, { access_token: this.selfOrder.access_token });
            this.token = res.token;
        }
        const params = new URLSearchParams({ access_token: this.selfOrder.access_token, token: this.token || "" });
        Object.assign(this.state.qr, { open: true, gone: false, src: `${this.url}/qr.png?${params}&t=${Date.now()}` });
        clearInterval(this.qrTimer);
        this.qrTimer = setInterval(() => this.checkPresence(), 2000);
    }

    closeQr() {
        clearInterval(this.qrTimer);
        this.state.qr.open = false;
    }

    async checkPresence() {
        let res;
        try {
            res = await rpc(`${this.url}/presence`, { access_token: this.selfOrder.access_token, token: this.token });
        } catch {
            return;
        }
        if (res.presence === "phone" && !this.state.qr.gone) {
            clearInterval(this.qrTimer);
            clearInterval(this.presenceTimer);
            this.state.qr.open = true;
            this.stopLive();
            this.stopVoice();
            this.state.qr.gone = true;
            // The kiosk is free for the next customer.
            setTimeout(() => this.reset(), 6000);
        }
    }

    runActions(actions) {
        for (const action of actions || []) {
            const handler = xbVaActions[action.type];
            if (handler) {
                try {
                    handler(this, action);
                } catch (error) {
                    console.warn("Virtual seller action failed:", action.type, error);
                }
            }
        }
    }

    async liveTool(name, args) {
        this.touch();
        const res = await this.serial(() => rpc(`${this.url}/tool`, {
            access_token: this.selfOrder.access_token,
            token: this.token,
            name,
            args,
        }));
        const ui = res.ui || {};
        this.runActions(ui.actions);
        if (ui.handoff) {
            this.state.handoff = true;
        }
        if (ui.ask_phone && this.canShare) {
            this.openPad();
        }
        if (ui.open) {
            this.openProduct(ui.open);
        } else if (ui.products && ui.products.length) {
            this.showPicks(ui.products);
        }
        return res.output;
    }

    get canShare() {
        return (this.va.share || []).includes("whatsapp");
    }

    // ------------------------------------------------------------ send the selection
    openPad() {
        this.touch();
        this.stopRecording(true);
        Object.assign(this.state.pad, { open: true, digits: "", sending: false, error: "" });
        if (this.live) {
            this.live.mute(true);
        }
    }

    closePad() {
        this.state.pad.open = false;
        if (this.live) {
            this.live.mute(false);
        }
    }

    padKey(key) {
        this.touch();
        const pad = this.state.pad;
        pad.error = "";
        if (key === "del") {
            pad.digits = pad.digits.slice(0, -1);
        } else if (pad.digits.length < 15) {
            pad.digits += key;
        }
    }

    async sendSelection() {
        const pad = this.state.pad;
        if (pad.digits.length < 8 || pad.sending) {
            pad.error = _t("Write your full mobile number.");
            return;
        }
        pad.sending = true;
        try {
            const res = await rpc(`${this.url}/share`, {
                access_token: this.selfOrder.access_token,
                token: this.token,
                channel: "whatsapp",
                phone: pad.digits,
            });
            if (res.ok) {
                this.closePad();
                this.say(_t("Done! I sent it to your WhatsApp, with everything we talked about."));
            } else {
                pad.error = res.error || _t("It could not be sent.");
            }
        } catch {
            pad.error = _t("It could not be sent.");
        } finally {
            pad.sending = false;
        }
    }

    get canListen() {
        return this.va.listen && !!(navigator.mediaDevices && window.MediaRecorder);
    }

    imageUrl(product) {
        return `/web/image/product.template/${product.id}/image_512`;
    }

    // ------------------------------------------------------------ open, close, idle
    open() {
        this.state.open = true;
        // The customer may take the seller to their phone (QR, NFC sticker): the kiosk lets go then.
        clearInterval(this.presenceTimer);
        this.presenceTimer = setInterval(() => this.token && this.checkPresence(), 4000);
        this.state.mode = this.va.start_full && this.hasFull ? "full" : "chat";
        this.touch();
        if (this.isLive) {
            if (!this.live) {
                this.startLive();
            }
        } else if (!this.state.messages.length) {
            this.say(this.va.greeting);
        }
    }

    close() {
        clearInterval(this.presenceTimer);
        this.state.open = false;
        this.stopLive();
        this.stopVoice();
        this.stopRecording(true);
    }

    touch() {
        // The kiosk only counts taps as activity and shows "Session inactive" after 90 s:
        // talking to the seller is activity too.
        // (A click on a hidden element of ours: other listeners expect a real element as target.)
        if (!this.keepAlive) {
            this.keepAlive = document.createElement("span");
            this.keepAlive.className = "xb-va-keepalive d-none";
            document.body.appendChild(this.keepAlive);
        }
        this.keepAlive.dispatchEvent(new MouseEvent("click", { bubbles: true }));
        clearTimeout(this.idleTimer);
        this.idleTimer = setTimeout(() => this.reset(), this.va.idle * 1000);
    }

    reset() {
        this.state.qr.gone = false;
        if (this.token) {
            rpc(`${this.url}/end`, { access_token: this.selfOrder.access_token, token: this.token }).catch(() => {});
        }
        this.setAway(false);
        this.closeQr();
        this.close();
        this.token = null;
        this.state.messages = [];
        this.state.handoff = false;
        this.state.typed = "";
        this.state.lastCustomer = "";
        this.state.mode = "chat";
        this.selfOrder.xbVaPicks = [];
    }

    get lastSellerText() {
        const last = [...this.state.messages].reverse().find((m) => m.who === "seller");
        return last ? last.text : "";
    }

    expand() {
        this.touch();
        this.state.mode = this.prevMode === "full" && this.hasFull ? "full" : "chat";
    }

    setMode(mode) {
        this.touch();
        this.state.mode = mode;
    }

    dock() {
        if (this.state.mode !== "mini") {
            this.prevMode = this.state.mode;
            this.state.mode = "mini";
        }
    }

    /** Shows the recommended products in the kiosk's own list, the chat docked below. */
    showPicks(ids) {
        this.selfOrder.xbVaPicks = ids;
        this.dock();
        if (this.router.activeSlot !== "product_list") {
            this.router.navigate("product_list");
        }
    }

    // ------------------------------------------------------------ messages
    push(who, text, products = []) {
        this.state.messages.push({ id: this.state.messages.length + 1, who, text, products });
        // Again once the product photos have loaded and the cards have their height.
        for (const wait of [0, 400, 1200]) {
            setTimeout(() => {
                const el = this.list.el;
                if (el) {
                    el.scrollTop = el.scrollHeight;
                }
            }, wait);
        }
    }

    say(text, products = []) {
        this.push("seller", text, products);
        if (!this.live) {
            this.speak(text);
        }
    }

    async send(text, { silent = false } = {}) {
        text = (text || "").trim();
        if (!text || this.state.busy) {
            return;
        }
        this.touch();
        this.stopVoice();
        this.state.typed = "";
        if (this.live) {
            this.push("customer", text);
            this.state.lastCustomer = text;
            this.liveLog({ who: "customer", text });
            this.live.say(text);
            return;
        }
        if (!silent) {
            this.push("customer", text);
            this.state.lastCustomer = text;
        }
        this.state.busy = true;
        try {
            const res = await rpc(`${this.url}/chat`, {
                access_token: this.selfOrder.access_token,
                token: this.token,
                text,
            });
            this.token = res.token || this.token;
            if (res.handoff) {
                this.state.handoff = true;
            }
            this.say(res.reply);
            if (res.ask_phone && this.canShare) {
                this.openPad();
            }
            this.runActions(res.actions);
            if (res.open) {
                this.openProduct(res.open);
            } else if (res.products && res.products.length) {
                this.showPicks(res.products.map((p) => p.id));
            }
        } catch {
            this.push("seller", _t("Sorry, I lost the connection. Can you try again?"));
        } finally {
            this.state.busy = false;
            this.touch();
        }
    }

    onKey(ev) {
        if (ev.key === "Enter") {
            this.send(this.state.typed);
        }
    }

    openProduct(id) {
        const product = this.selfOrder.models["product.template"].get(id);
        if (!product) {
            return;
        }
        this.touch();
        this.router.navigate("product", { id });
        this.dock();
    }

    async callPerson() {
        if (this.state.handoff) {
            return;
        }
        this.touch();
        this.state.handoff = true;
        try {
            const res = await rpc(`${this.url}/handoff`, {
                access_token: this.selfOrder.access_token,
                token: this.token,
            });
            this.token = res.token || this.token;
            this.say(
                res.done
                    ? _t("Done! I've let the shop know; someone will be with you in a moment.")
                    : _t("Please go to the counter, they will help you there.")
            );
        } catch {
            this.state.handoff = false;
        }
    }

    // ------------------------------------------------------------ voice out
    async speak(text) {
        if (this.away) {
            setTimeout(() => this.listenAgain(), 2500);
            return;
        }
        if (!this.va.speak || !text) {
            setTimeout(() => this.listenAgain(), 300);
            return;
        }
        this.stopVoice();
        const form = new FormData();
        form.append("access_token", this.selfOrder.access_token);
        form.append("token", this.token || "");
        form.append("text", text);
        try {
            const resp = await fetch(`${this.url}/speak`, { method: "POST", body: form });
            const blob = await resp.blob();
            if (!resp.ok || !blob.size || !this.state.open) {
                return;
            }
            const audio = new Audio(URL.createObjectURL(blob));
            this.audio = audio;
            audio.onplay = () => (this.state.speaking = true);
            audio.onpause = () => {
                if (this.audio === audio) {
                    this.state.speaking = false;
                }
            };
            audio.onended = () => {
                if (this.audio === audio) {
                    this.state.speaking = false;
                    this.audio = null;
                    this.listenAgain();
                }
            };
            await audio.play();
        } catch {
            this.state.speaking = false;
        }
    }

    /** Hands-free: once the seller is done talking, the microphone opens by itself. */
    listenAgain() {
        if (this.live) {
            return;
        }
        if (this.va.continuous && this.canListen && this.state.open && !this.state.busy && !this.state.pad.open
                && !this.state.recording && !this.state.handoff) {
            this.toggleMic(true);
        }
    }

    stopVoice() {
        if (this.audio) {
            this.audio.pause();
            this.audio = null;
        }
        this.state.speaking = false;
    }

    // ------------------------------------------------------------ voice in
    async toggleMic(auto = false) {
        if (this.live) {
            this.touch();
            this.live.mute(!this.live.muted);
            return;
        }
        if (this.isLive && this.state.open) {
            this.startLive();
            return;
        }
        if (this.state.recording) {
            this.stopRecording();
            return;
        }
        this.stopVoice();
        this.touch();
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
            // Opened by itself (hands-free) it fails quietly; asked by the customer, it says so.
            if (!auto) {
                this.push("seller", _t("I can't use the microphone. You can type your question."));
            }
            return;
        }
        const chunks = [];
        const recorder = new MediaRecorder(stream);
        this.recorder = recorder;
        this.stream = stream;
        this.recordStart = Date.now();
        recorder.ondataavailable = (ev) => ev.data.size && chunks.push(ev.data);
        recorder.onstop = () => {
            stream.getTracks().forEach((t) => t.stop());
            this.stopMeter();
            if (this.discard) {
                return;
            }
            const seconds = (Date.now() - this.recordStart) / 1000;
            this.transcribe(new Blob(chunks, { type: recorder.mimeType || "audio/webm" }), seconds);
        };
        this.discard = false;
        recorder.start();
        this.state.recording = true;
        this.maxTimer = setTimeout(() => this.stopRecording(), MAX_RECORD_MS);
        this.autoListen = auto;
        this.startMeter(stream);
    }

    stopRecording(discard = false) {
        clearTimeout(this.maxTimer);
        this.discard = discard;
        if (this.recorder && this.recorder.state !== "inactive") {
            this.recorder.stop();
        }
        this.recorder = null;
        this.state.recording = false;
    }

    /** Stops by itself after a short silence once the customer has spoken. */
    startMeter(stream) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) {
            return;
        }
        this.ctx = new Ctx();
        const analyser = this.ctx.createAnalyser();
        analyser.fftSize = 1024;
        this.ctx.createMediaStreamSource(stream).connect(analyser);
        const data = new Uint8Array(analyser.fftSize);
        let heard = false;
        const started = Date.now();
        let quietSince = started;
        this.meter = setInterval(() => {
            analyser.getByteTimeDomainData(data);
            let peak = 0;
            for (const v of data) {
                peak = Math.max(peak, Math.abs(v - 128));
            }
            if (peak > 18) {
                heard = true;
                quietSince = Date.now();
            } else if (heard && Date.now() - quietSince > SILENCE_MS) {
                this.stopRecording();
            } else if (!heard && Date.now() - started > WAIT_SPEECH_MS) {
                // Nobody spoke: close the microphone quietly, the button is there to talk again.
                this.stopRecording(true);
            }
        }, 100);
    }

    stopMeter() {
        clearInterval(this.meter);
        if (this.ctx) {
            this.ctx.close();
            this.ctx = null;
        }
    }

    async transcribe(blob, seconds) {
        if (!blob.size) {
            return;
        }
        this.state.busy = true;
        const form = new FormData();
        form.append("access_token", this.selfOrder.access_token);
        form.append("token", this.token || "");
        form.append("seconds", String(seconds));
        form.append("audio", blob, "voz." + (blob.type.includes("mp4") ? "mp4" : "webm"));
        let text = "";
        try {
            const resp = await fetch(`${this.url}/listen`, { method: "POST", body: form });
            const res = await resp.json();
            this.token = res.token || this.token;
            text = res.text || "";
        } catch {
            text = "";
        }
        this.state.busy = false;
        if (text) {
            this.send(text);
        } else if (!this.autoListen) {
            this.push("seller", _t("I didn't hear you well. Can you say it again?"));
        }
    }
}

selfOrderIndex.components = { ...selfOrderIndex.components, XbVirtualSeller };

// The seller puts a product with its options in the cart, and takes the customer to it.
xbVaActions.add_to_cart = async (seller, action) => {
    const product = seller.selfOrder.models["product.template"].get(action.template_id);
    if (product) {
        await seller.selfOrder.addToCart(product, action.qty || 1, "", action.ptav_ids || [], {});
    }
};
// The seller went to the wall (its voice comes from there) or came back.
xbVaActions.voice_away = (seller, action) => {
    seller.setAway(Boolean(action.on));
    if (action.note) {
        seller.push("system", action.note);
    }
};

// The customer takes the seller to their phone: QR, and the kiosk lets go once it is open there.
xbVaActions.show_qr = (seller) => seller.openQr();

// A short note on the conversation (an appointment booked, something done...).
xbVaActions.note = (seller, action) => {
    seller.push("system", action.text);
};
xbVaActions.go_cart = (seller) => {
    seller.router.navigate("cart");
    seller.dock();
};
