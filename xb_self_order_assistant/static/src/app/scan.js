/**
 * XUBAX - Virtual seller: reads what the customer brings to the kiosk reader.
 * - USB / Bluetooth readers that "type" the code and press Enter (barcodes, many NFC readers).
 * - The tablet's own NFC (Web NFC, Chrome on Android): the card's link or its serial number.
 */
const KEY_GAP_MS = 60; // readers type much faster than people
const MIN_LENGTH = 4;

export class XbVaScanner {
    constructor(onCode) {
        this.onCode = onCode;
        this.buffer = "";
        this.last = 0;
        this.nfc = null;
        this.onKey = this.onKey.bind(this);
        this.startNfc = this.startNfc.bind(this);
    }

    start() {
        window.addEventListener("keydown", this.onKey, true);
        if ("NDEFReader" in window) {
            // Web NFC needs a first touch on the page.
            window.addEventListener("pointerdown", this.startNfc, { once: true, capture: true });
        }
    }

    stop() {
        window.removeEventListener("keydown", this.onKey, true);
        window.removeEventListener("pointerdown", this.startNfc, true);
        if (this.nfcAbort) {
            this.nfcAbort.abort();
        }
    }

    onKey(ev) {
        const target = ev.target;
        if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
            return;
        }
        const now = Date.now();
        if (now - this.last > KEY_GAP_MS) {
            this.buffer = "";
        }
        this.last = now;
        if (ev.key === "Enter") {
            if (this.buffer.length >= MIN_LENGTH) {
                const code = this.buffer;
                this.buffer = "";
                ev.preventDefault();
                this.onCode(code);
            }
            return;
        }
        if (ev.key.length === 1) {
            this.buffer += ev.key;
        }
    }

    async startNfc() {
        try {
            this.nfcAbort = new AbortController();
            const reader = new window.NDEFReader();
            await reader.scan({ signal: this.nfcAbort.signal });
            reader.onreading = (ev) => {
                const decoder = new TextDecoder();
                for (const record of ev.message.records) {
                    if (record.recordType === "url" || record.recordType === "text") {
                        this.onCode(decoder.decode(record.data));
                        return;
                    }
                }
                if (ev.serialNumber) {
                    this.onCode(ev.serialNumber);
                }
            };
        } catch (error) {
            console.info("Virtual seller: NFC not available", error);
        }
    }
}
