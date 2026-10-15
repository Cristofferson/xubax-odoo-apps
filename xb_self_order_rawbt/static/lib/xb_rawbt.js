/* XUBAX - Self-Order Kiosk - USB Printer (RawBT)
 * Plain script (no imports): also used by the printer test page, outside Odoo.
 * Turns a canvas into ESC/POS raster commands and hands them to the RawBT app. */
(function () {
    "use strict";
    const PACKAGE = "ru.a402d.rawbtprinter";

    /** ESC/POS bytes of the canvas, scaled to the paper width in dots. */
    function canvasToEscPos(canvas, width) {
        width = width || 576;
        const height = Math.max(1, Math.round((canvas.height * width) / canvas.width));
        const scaled = document.createElement("canvas");
        scaled.width = width;
        scaled.height = height;
        const ctx = scaled.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(canvas, 0, 0, width, height);
        const px = ctx.getImageData(0, 0, width, height).data;
        const bytesPerRow = Math.ceil(width / 8);
        const out = [0x1b, 0x40]; // ESC @: reset
        // GS v 0 in bands: some printers cannot take a long image in one command.
        const BAND = 128;
        for (let y0 = 0; y0 < height; y0 += BAND) {
            const rows = Math.min(BAND, height - y0);
            out.push(0x1d, 0x76, 0x30, 0x00, bytesPerRow & 255, bytesPerRow >> 8, rows & 255, rows >> 8);
            for (let y = y0; y < y0 + rows; y++) {
                for (let bx = 0; bx < bytesPerRow; bx++) {
                    let byte = 0;
                    for (let bit = 0; bit < 8; bit++) {
                        const x = bx * 8 + bit;
                        if (x >= width) {
                            break;
                        }
                        const i = (y * width + x) * 4;
                        const lum = px[i] * 0.299 + px[i + 1] * 0.587 + px[i + 2] * 0.114;
                        if (lum < 160) {
                            byte |= 0x80 >> bit;
                        }
                    }
                    out.push(byte);
                }
            }
        }
        out.push(0x1b, 0x64, 0x04); // ESC d 4: feed
        out.push(0x1d, 0x56, 0x42, 0x00); // GS V B: cut (ignored without a cutter)
        return new Uint8Array(out);
    }

    function toBase64(bytes) {
        let s = "";
        const CHUNK = 0x8000;
        for (let i = 0; i < bytes.length; i += CHUNK) {
            s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
        }
        return btoa(s);
    }

    /** The link that hands the ESC/POS bytes (base64) to RawBT. */
    function rawbtUrl(b64, method) {
        if (method === "scheme") {
            return "rawbt:base64," + b64;
        }
        return "intent:base64," + b64 + "#Intent;scheme=rawbt;package=" + PACKAGE + ";end;";
    }

    function send(b64, method) {
        window.location.href = rawbtUrl(b64, method);
    }

    window.XbRawBT = { canvasToEscPos, toBase64, rawbtUrl, send };
})();
