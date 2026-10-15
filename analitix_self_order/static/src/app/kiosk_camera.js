/**
 * Analitix - Self-Order Kiosk
 *
 * Reads the kiosk's front camera in the browser and turns it into "stops": one
 * row per person (or group) standing in front of the kiosk, with how long, how
 * long they faced the screen, whether they touched it, and an approximate age
 * and gender. Only those numbers are sent to Odoo. Each frame is read in memory
 * and dropped; nothing is drawn, stored or uploaded.
 */
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";

const TICK_MS = 300; // ~3 readings a second: plenty for people, light for the tablet
const GONE_MS = 4000; // nobody in front for this long: the stop is over
const TOUCH_KEEPS_MS = 2000; // a touch counts as presence even if the face is hidden
const MIN_STOP_MS = 3000; // shorter is someone walking past
const FLUSH_MS = 60000;
const QUEUE_KEY = "analitix_kiosk_queue";

function readQueue() {
    try {
        return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
    } catch {
        return [];
    }
}

function writeQueue(queue) {
    try {
        // Bounded: a kiosk offline for days keeps the latest stops, not all.
        localStorage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(-500)));
    } catch {
        // Private mode or full storage: the stops of this page load still go out.
    }
}

function median(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function stdev(values) {
    const mean = values.reduce((a, b) => a + b, 0) / values.length;
    return Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length);
}

function newUuid() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export class KioskCamera {
    constructor(selfOrder, options) {
        this.selfOrder = selfOrder;
        this.options = options;
        this.current = null;
        this.lastTick = 0;
        this.lastTouch = 0;
        this.faces = 0;
        this.fps = 0;
        this.queue = readQueue();
        this.debugEl = null;
    }

    async start() {
        if (this.options.debug) {
            this.debugEl = document.createElement("div");
            this.debugEl.style.cssText =
                "position:fixed;left:8px;bottom:8px;z-index:99999;padding:4px 8px;" +
                "border-radius:6px;background:rgba(0,0,0,.6);color:#fff;font:12px sans-serif;" +
                "pointer-events:none";
            document.body.appendChild(this.debugEl);
        }
        this.show(_t("Analitix: starting the camera…"));
        document.addEventListener("pointerdown", () => this.onTouch(), true);
        setInterval(() => this.flush(), FLUSH_MS);
        this.flush();
        try {
            await loadJS(this.options.lib);
            const faceapi = window.faceapi;
            await faceapi.tf.ready();
            await faceapi.nets.tinyFaceDetector.loadFromUri(this.options.models);
            await faceapi.nets.ageGenderNet.loadFromUri(this.options.models);
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } },
                audio: false,
            });
            this.video = document.createElement("video");
            this.video.muted = true;
            this.video.playsInline = true;
            this.video.setAttribute("playsinline", "");
            // On the page but invisible: some browsers stop decoding a detached video.
            // While setting the kiosk up, a small preview shows what the camera sees, on
            // this screen only (nothing is sent), to check its angle and rotation.
            this.video.style.cssText = this.options.debug
                ? "position:fixed;left:8px;bottom:36px;width:160px;z-index:99999;" +
                  "border:2px solid #fff;border-radius:6px;pointer-events:none"
                : "position:fixed;width:2px;height:2px;opacity:0;pointer-events:none;left:0;top:0";
            document.body.appendChild(this.video);
            this.video.srcObject = stream;
            await this.video.play();
            this.options.detector = new faceapi.TinyFaceDetectorOptions({
                inputSize: 224,
                scoreThreshold: 0.5,
            });
            this.loop();
        } catch (error) {
            console.warn("[analitix] kiosk camera unavailable:", error);
            this.show(_t("Analitix: no camera (%s)", error?.message || error));
        }
    }

    async loop() {
        const started = performance.now();
        try {
            if (document.visibilityState === "visible" && this.video.readyState >= 2) {
                await this.tick();
            }
        } catch (error) {
            console.warn("[analitix] reading failed:", error);
        }
        const spent = performance.now() - started;
        this.fps = spent ? Math.min(1000 / Math.max(spent, TICK_MS), 99) : 0;
        setTimeout(() => this.loop(), Math.max(TICK_MS - spent, 50));
    }

    async tick() {
        const faceapi = window.faceapi;
        const detections = await faceapi
            .detectAllFaces(this.video, this.options.detector)
            .withAgeAndGender();
        const width = this.video.videoWidth || 1;
        const near = detections.filter((d) => d.detection.box.width / width >= this.options.min_face);
        const now = Date.now();
        const step = this.lastTick ? Math.min(now - this.lastTick, 1000) : 0;
        this.lastTick = now;
        this.faces = near.length;
        this.seen = detections.length;
        this.largest = detections.length
            ? Math.round((100 * Math.max(...detections.map((d) => d.detection.box.width))) / width)
            : 0;

        if (near.length || now - this.lastTouch < TOUCH_KEEPS_MS) {
            const stop = this.current || this.open(now);
            stop.last = now;
            if (near.length) {
                stop.attention += step;
                stop.people = Math.max(stop.people, near.length);
                // Age and gender of the person closest to the kiosk.
                const main = near.reduce((a, b) =>
                    b.detection.box.width > a.detection.box.width ? b : a
                );
                stop.ages.push(main.age);
                stop.female.push(
                    main.gender === "female" ? main.genderProbability : 1 - main.genderProbability
                );
            }
        } else if (this.current && now - this.current.last > GONE_MS) {
            this.close();
        }
        this.show(
            _t(
                "Analitix: %(faces)s face(s) near · %(seen)s in view · largest %(largest)s% · %(size)s · %(fps)s/s · %(queue)s to send",
                {
                    faces: this.faces,
                    seen: this.seen,
                    largest: this.largest,
                    size: `${this.video.videoWidth}×${this.video.videoHeight}`,
                    fps: this.fps.toFixed(1),
                    queue: this.queue.length,
                }
            )
        );
    }

    open(now) {
        this.current = {
            uuid: newUuid(),
            start: now,
            last: now,
            attention: 0,
            people: 0,
            touches: 0,
            ages: [],
            female: [],
        };
        return this.current;
    }

    onTouch() {
        const now = Date.now();
        this.lastTouch = now;
        const stop = this.current || this.open(now);
        stop.touches += 1;
        stop.last = now;
    }

    close() {
        const stop = this.current;
        this.current = null;
        if (!stop || stop.last - stop.start < MIN_STOP_MS) {
            return;
        }
        const row = {
            uuid: stop.uuid,
            start: stop.start,
            end: stop.last,
            attention: Math.round(stop.attention / 1000),
            people: stop.people || 1,
            touches: stop.touches,
        };
        if (stop.ages.length >= 3) {
            row.age = Math.round(median(stop.ages));
            // Readings that agree are worth more than readings that jump around.
            const steadiness = Math.max(0, 1 - stdev(stop.ages) / 12);
            row.age_confidence = +(steadiness * Math.min(1, stop.ages.length / 6)).toFixed(3);
            row.female = +(
                stop.female.reduce((a, b) => a + b, 0) / stop.female.length
            ).toFixed(3);
        }
        this.queue.push(row);
        writeQueue(this.queue);
        this.flush();
    }

    async flush() {
        if (!this.queue.length || this.flushing) {
            return;
        }
        this.flushing = true;
        const batch = this.queue.slice(0, 200);
        try {
            const res = await rpc(
                "/analitix_kiosk/stops",
                { access_token: this.selfOrder.access_token, stops: batch },
                { silent: true }
            );
            if (res?.held) {
                const held = new Set(res.held);
                this.queue = this.queue.filter((row) => !held.has(row.uuid));
                writeQueue(this.queue);
            }
        } catch (error) {
            // Offline: the stops wait in the queue for the next try.
            console.warn("[analitix] sending the kiosk stops failed:", error);
        } finally {
            this.flushing = false;
        }
    }

    show(text) {
        if (this.debugEl) {
            this.debugEl.textContent = text;
        }
    }
}

patch(SelfOrder.prototype, {
    async setup(...args) {
        await super.setup(...args);
        const options = this.config?._analitix_kiosk;
        if (options && navigator.mediaDevices?.getUserMedia) {
            this.analitixCamera = new KioskCamera(this, options);
            // Not awaited: the kiosk must never wait for the camera.
            this.analitixCamera.start();
        }
    },
});
