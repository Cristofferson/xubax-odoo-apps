/**
 * XUBAX - Virtual seller: notices someone standing in front of the kiosk.
 * Other apps that already watch the camera (Analitix) announce it with the window event
 * "xb-va-presence" ({detail: {present: true|false}}). Without them, a simple movement detector
 * reads the camera small and in memory: no picture is kept or sent.
 */
const TICK_MS = 400;
const ARRIVE_MS = 1500; // standing this long counts (not someone walking past)
const LEAVE_MS = 4000;

export class XbVaPresence {
    constructor(onChange) {
        this.onChange = onChange;
        this.present = false;
        this.external = false;
        this.onEvent = (ev) => {
            this.external = true;
            this.stopCamera();
            this.set(Boolean(ev.detail && ev.detail.present));
        };
    }

    start() {
        window.addEventListener("xb-va-presence", this.onEvent);
        // Give the other apps a moment to announce themselves before using the camera here.
        this.wait = setTimeout(() => !this.external && !window.xbVaPresenceExternal && this.startCamera(), 8000);
    }

    stop() {
        clearTimeout(this.wait);
        window.removeEventListener("xb-va-presence", this.onEvent);
        this.stopCamera();
    }

    set(present) {
        if (present !== this.present) {
            this.present = present;
            this.onChange(present);
        }
    }

    async startCamera() {
        if (!navigator.mediaDevices) {
            return;
        }
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 160, height: 120, facingMode: "user" },
                audio: false,
            });
        } catch {
            return; // no camera or no permission: no greeting, nothing else changes
        }
        const video = document.createElement("video");
        video.muted = true;
        video.playsInline = true;
        video.srcObject = this.stream;
        await video.play().catch(() => {});
        const canvas = document.createElement("canvas");
        canvas.width = 64;
        canvas.height = 48;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        let background = null;
        let since = 0;
        let quiet = 0;
        this.timer = setInterval(() => {
            ctx.drawImage(video, 0, 0, 64, 48);
            const data = ctx.getImageData(0, 0, 64, 48).data;
            const grey = new Float32Array(64 * 48);
            for (let i = 0; i < grey.length; i++) {
                grey[i] = (data[i * 4] + data[i * 4 + 1] + data[i * 4 + 2]) / 3;
            }
            if (!background) {
                background = grey;
                return;
            }
            // How different the middle of the picture is from the empty scene.
            let diff = 0;
            let count = 0;
            for (let y = 8; y < 44; y++) {
                for (let x = 12; x < 52; x++) {
                    const i = y * 64 + x;
                    diff += Math.abs(grey[i] - background[i]);
                    count++;
                }
            }
            diff /= count;
            const now = Date.now();
            if (diff > 22) {
                since = since || now;
                quiet = 0;
                if (now - since > ARRIVE_MS) {
                    this.set(true);
                }
            } else {
                since = 0;
                quiet = quiet || now;
                if (now - quiet > LEAVE_MS) {
                    this.set(false);
                }
                // The empty scene changes with the light: it learns slowly while nobody is there.
                for (let i = 0; i < grey.length; i++) {
                    background[i] = background[i] * 0.95 + grey[i] * 0.05;
                }
            }
        }, TICK_MS);
    }

    stopCamera() {
        clearInterval(this.timer);
        if (this.stream) {
            this.stream.getTracks().forEach((t) => t.stop());
            this.stream = null;
        }
    }
}
