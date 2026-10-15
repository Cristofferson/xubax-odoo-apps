/* XUBAX - Self-Order Kiosk - USB Printer (RawBT)
 * Plain script (no imports): also used by the printer test page, outside Odoo.
 * Turns a canvas into ESC/POS raster commands and hands them to the RawBT app. */
(function () {
    "use strict";
    const PACKAGE = "ru.a402d.rawbtprinter";

    /** The canvas scaled to the paper width in dots, on white. */
    function scaleCanvas(canvas, width) {
        const height = Math.max(1, Math.round((canvas.height * width) / canvas.width));
        const scaled = document.createElement("canvas");
        scaled.width = width;
        scaled.height = height;
        const ctx = scaled.getContext("2d");
        ctx.fillStyle = "#fff";
        ctx.fillRect(0, 0, width, height);
        ctx.drawImage(canvas, 0, 0, width, height);
        return scaled;
    }

    /** Black (true) or white for each dot of the scaled canvas. */
    function dots(scaled) {
        const { width, height } = scaled;
        const px = scaled.getContext("2d").getImageData(0, 0, width, height).data;
        return (x, y) => {
            const i = (y * width + x) * 4;
            return px[i] * 0.299 + px[i + 1] * 0.587 + px[i + 2] * 0.114 < 160;
        };
    }

    /** GS v 0 raster image of rows [y0, y0 + rows). */
    function rasterBlock(out, black, width, y0, rows) {
        const bytesPerRow = Math.ceil(width / 8);
        out.push(0x1d, 0x76, 0x30, 0x00, bytesPerRow & 255, bytesPerRow >> 8, rows & 255, rows >> 8);
        for (let y = y0; y < y0 + rows; y++) {
            for (let bx = 0; bx < bytesPerRow; bx++) {
                let byte = 0;
                for (let bit = 0; bit < 8; bit++) {
                    const x = bx * 8 + bit;
                    if (x < width && black(x, y)) {
                        byte |= 0x80 >> bit;
                    }
                }
                out.push(byte);
            }
        }
    }

    /**
     * ESC/POS bytes of the canvas, scaled to the paper width in dots.
     * format: "bands" (GS v 0 in blocks of 128 rows), "single" (one GS v 0 image)
     * or "esc24" (ESC * lines of 24 dots, the oldest and most supported way).
     */
    function canvasToEscPos(canvas, width, format) {
        width = width || 576;
        const scaled = scaleCanvas(canvas, width);
        const height = scaled.height;
        const black = dots(scaled);
        const out = [0x1b, 0x40]; // ESC @: reset
        if (format === "esc24") {
            out.push(0x1b, 0x33, 24); // ESC 3 24: lines of 24 dots, no gap between them
            for (let y0 = 0; y0 < height; y0 += 24) {
                out.push(0x1b, 0x2a, 33, width & 255, width >> 8); // ESC * 33: 24-dot double density
                for (let x = 0; x < width; x++) {
                    for (let k = 0; k < 3; k++) {
                        let byte = 0;
                        for (let bit = 0; bit < 8; bit++) {
                            const y = y0 + k * 8 + bit;
                            if (y < height && black(x, y)) {
                                byte |= 0x80 >> bit;
                            }
                        }
                        out.push(byte);
                    }
                }
                out.push(0x0a);
            }
            out.push(0x1b, 0x32); // ESC 2: default line spacing
        } else if (format === "single") {
            rasterBlock(out, black, width, 0, height);
        } else {
            // Some printers cannot take a long image in one command.
            for (let y0 = 0; y0 < height; y0 += 128) {
                rasterBlock(out, black, width, y0, Math.min(128, height - y0));
            }
        }
        out.push(0x1b, 0x64, 0x04); // ESC d 4: feed
        out.push(0x1d, 0x56, 0x42, 0x00); // GS V B: cut (ignored without a cutter)
        return new Uint8Array(out);
    }

    /** PNG (base64) of the canvas at the paper width, for RawBT to print as an image. */
    function canvasToPng(canvas, width) {
        return scaleCanvas(canvas, width || 576).toDataURL("image/png").replace("data:image/png;base64,", "");
    }

    function toBase64(bytes) {
        let s = "";
        const CHUNK = 0x8000;
        for (let i = 0; i < bytes.length; i += CHUNK) {
            s += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
        }
        return btoa(s);
    }

    /** The link that hands the job to RawBT: ESC/POS bytes, or a PNG when png is set. */
    function rawbtUrl(b64, method, png) {
        const data = (png ? "data:image/png;base64," : "base64,") + b64;
        if (method === "scheme") {
            return "rawbt:" + data;
        }
        return "intent:" + data + "#Intent;scheme=rawbt;package=" + PACKAGE + ";end;";
    }

    function send(b64, method, png) {
        window.location.href = rawbtUrl(b64, method, png);
    }

    /** The job for a canvas: [base64, png] in the given format. */
    function job(canvas, width, format) {
        if (format === "image") {
            return [canvasToPng(canvas, width), true];
        }
        return [toBase64(canvasToEscPos(canvas, width, format)), false];
    }

    window.XbRawBT = { canvasToEscPos, canvasToPng, toBase64, rawbtUrl, send, job };
})();
