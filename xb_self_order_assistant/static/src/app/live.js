/**
 * XUBAX - Virtual seller, live voice: the kiosk talks directly with the live voice model
 * (WebRTC). Odoo gives a short-lived key, and does what the model asks (search products,
 * show them, call a person...).
 */
const CALLS_URL = "https://api.openai.com/v1/realtime/calls";

export class XbLiveVoice {
    /**
     * @param {Object} hooks
     *   onSpeaking(bool), onListening(bool), onCustomer(text), onSeller(text),
     *   onTool(name, args) -> Promise<string>, onUsage(usage), onError(error), onEnd()
     */
    constructor(hooks, { textMode = false } = {}) {
        this.hooks = hooks;
        // Text mode: the model answers in text, said by another voice (hooks.onSentence).
        this.textMode = textMode;
        this.pending = "";
        this.pc = null;
        this.dc = null;
        this.stream = null;
        this.audio = null;
        this.muted = false;
    }

    get active() {
        return Boolean(this.pc);
    }

    async start({ key, model }) {
        this.stream = await navigator.mediaDevices.getUserMedia({
            audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        const pc = new RTCPeerConnection();
        this.pc = pc;
        this.audio = new Audio();
        this.audio.autoplay = true;
        pc.ontrack = (ev) => (this.audio.srcObject = ev.streams[0]);
        pc.onconnectionstatechange = () => {
            if (["failed", "closed", "disconnected"].includes(pc.connectionState)) {
                this.stop();
            }
        };
        for (const track of this.stream.getTracks()) {
            pc.addTrack(track, this.stream);
        }
        const dc = pc.createDataChannel("oai-events");
        this.dc = dc;
        dc.onmessage = (ev) => this.onEvent(JSON.parse(ev.data));
        const opened = new Promise((resolve) => (dc.onopen = resolve));
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        const resp = await fetch(`${CALLS_URL}?model=${encodeURIComponent(model)}`, {
            method: "POST",
            body: offer.sdp,
            headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/sdp" },
        });
        if (!resp.ok) {
            this.stop();
            throw new Error(`Live voice refused (${resp.status})`);
        }
        await pc.setRemoteDescription({ type: "answer", sdp: await resp.text() });
        await opened;
        this.hooks.onListening(true);
        // The seller greets first.
        this.send({ type: "response.create" });
    }

    send(event) {
        if (this.dc && this.dc.readyState === "open") {
            this.dc.send(JSON.stringify(event));
        }
    }

    /** A typed message, as if the customer had said it. */
    say(text) {
        this.send({
            type: "conversation.item.create",
            item: { type: "message", role: "user", content: [{ type: "input_text", text }] },
        });
        this.send({ type: "response.create" });
    }

    /** Pauses the microphone (the seller keeps talking). */
    mute(muted) {
        this.muted = muted;
        for (const track of this.stream ? this.stream.getAudioTracks() : []) {
            track.enabled = !muted;
        }
        this.hooks.onListening(!muted);
    }

    async onEvent(ev) {
        const h = this.hooks;
        switch (ev.type) {
            case "input_audio_buffer.speech_started":
            case "response.created":
                if (h.onActivity) {
                    h.onActivity();
                }
                break;
            case "output_audio_buffer.started":
                h.onSpeaking(true);
                break;
            case "output_audio_buffer.stopped":
            case "output_audio_buffer.cleared":
                h.onSpeaking(false);
                break;
            case "conversation.item.input_audio_transcription.completed":
                if (ev.transcript && ev.transcript.trim()) {
                    h.onCustomer(ev.transcript.trim());
                }
                break;
            case "response.output_text.delta":
                if (this.textMode) {
                    this.pending += ev.delta || "";
                    // Whole sentences go out at once, so the voice starts before the answer ends.
                    let match;
                    while ((match = this.pending.match(/^([\s\S]*?[.!?…:;])\s+/))) {
                        this.pending = this.pending.slice(match[0].length);
                        if (match[1].trim()) {
                            h.onSentence(match[1].trim());
                        }
                    }
                }
                break;
            case "response.output_text.done":
                if (this.textMode) {
                    if (this.pending.trim()) {
                        h.onSentence(this.pending.trim());
                    }
                    this.pending = "";
                    if (ev.text && ev.text.trim()) {
                        h.onSeller(ev.text.trim());
                    }
                }
                break;
            case "response.output_audio_transcript.done":
                if (ev.transcript && ev.transcript.trim()) {
                    h.onSeller(ev.transcript.trim());
                }
                break;
            case "response.function_call_arguments.done": {
                let args = {};
                try {
                    args = JSON.parse(ev.arguments || "{}");
                } catch {
                    args = {};
                }
                let output;
                try {
                    output = await h.onTool(ev.name, args);
                } catch {
                    output = "Error al hacerlo.";
                }
                this.send({
                    type: "conversation.item.create",
                    item: { type: "function_call_output", call_id: ev.call_id, output: String(output) },
                });
                this.send({ type: "response.create" });
                break;
            }
            case "response.done":
                if (ev.response && ev.response.usage) {
                    h.onUsage(ev.response.usage);
                }
                break;
            case "error":
                h.onError(ev.error);
                break;
        }
    }

    stop() {
        const wasActive = this.active;
        if (this.dc) {
            this.dc.close();
        }
        if (this.pc) {
            this.pc.close();
        }
        for (const track of this.stream ? this.stream.getTracks() : []) {
            track.stop();
        }
        if (this.audio) {
            this.audio.srcObject = null;
        }
        this.pc = this.dc = this.stream = this.audio = null;
        if (wasActive) {
            this.hooks.onSpeaking(false);
            this.hooks.onListening(false);
            this.hooks.onEnd();
        }
    }
}
