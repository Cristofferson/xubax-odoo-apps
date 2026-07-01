# xb_footfall — edge CV agent

Counts people crossing a doorway and reports the counts (never the image) to the
Odoo module `xb_footfall`. It reads one RTSP stream — typically a **DVR
re-emitting an analog door channel** — runs **YOLOv11 + ByteTrack**, and POSTs a
crossing event each time a tracked person passes a **virtual line**.

```
[DVR/analog door cam] --RTSP--> [mini-PC: counter.py] --HTTPS POST--> /xb_footfall/ingest
   (or IP/USB cam)              YOLOv11 + ByteTrack                    (Bearer token)
```

**Privacy:** frames are decoded in memory and discarded. No image, frame or face
ever leaves the device — only `{direction, count}`. The single exception is
`calibrate.py`, run by hand at setup, which writes one local JPG you delete after.

## Fast setup (Windows, no config file by hand)
On the store PC, inside this `edge` folder:

1. Double-click **`install-windows.bat`** — it installs Python (if missing),
   creates the virtual environment, installs the dependencies, and opens the
   **desktop configurator**.
2. In the window (**XB Aforo → Configurar**):
   - pick the **DVR brand**, type **IP / user / password / channel** → the RTSP
     URL is assembled for you;
   - **Probar cámara** shows a live frame; **click two points** on it to draw the
     counting line (tick *Invertir Entrada/Salida* if in/out come out reversed);
   - type the Odoo **site** (e.g. `www.lamur.mx`) and paste the device **token**;
     **Probar Odoo** confirms the token reaches Odoo (creates no events);
   - **Guardar**, then **Arrancar** to run with a live log;
   - **Instalar arranque 24/7** registers a Windows Scheduled Task so it comes
     back after a reboot.
3. To re-open the window later: **`configure-windows.bat`**.

The configurator just writes `config.yaml` and drives `counter.py` — the manual
steps below (§1–§6) remain valid for headless / Docker / Linux installs. The same
`python configurator.py` window works on macOS too (the *Instalar arranque 24/7*
button writes a LaunchAgent there).

## 1. Provision in Odoo
First create the **Store** (Footfall → Configuration → Stores): pick *Match sales
by* (specific POS registers, or the whole company) so the conversion KPI crosses
the right tickets. Then Footfall → Configuration → Devices → create one **device
per door**, assign it to that store, and copy its **token** (Regenerate Token
shows it once). Several doors of the same shop = several devices on the same store
(their visitors are summed).

## 2. Get the door RTSP URL from the DVR
- Hikvision: `rtsp://user:pass@DVR_IP:554/Streaming/Channels/101` (ch1 main,
  `102` = substream — prefer the substream, lighter and plenty for counting).
- Dahua: `rtsp://user:pass@DVR_IP:554/cam/realmonitor?channel=1&subtype=0`.

Quick check from the mini-PC:
`ffprobe "rtsp://user:pass@DVR_IP:554/Streaming/Channels/102"`

## 3. Configure
```
cp config.example.yaml config.yaml      # then edit: rtsp_url, odoo_url, token
```

## 4. Aim the line
```
python3 calibrate.py --config config.yaml --out door.jpg
```
Open `door.jpg` (grid is 0..1 of the frame). Set `line: [x1,y1,x2,y2]` across the
doorway, **perpendicular to the walking path**. Re-run to confirm. If `in`/`out`
come out reversed, set `swap_direction: true`. Delete `door.jpg` when done.

> Angle matters: near-overhead (cenital) counts best; very oblique views where
> people overlap undercount. If the door cam is too oblique, reposition it or add
> an overhead cam (analog into the same DVR, or IP/USB straight into the mini-PC).

## 5. Run

**Docker (recommended):**
```
docker compose up -d --build
docker compose logs -f
```

**Bare metal:**
```
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python3 counter.py --config config.yaml
# or install the systemd unit (see xb-footfall-edge.service)
```

## 6. Calibrate accuracy
Run a day next to a manual clicker; compare against the Odoo `Footfall → Hourly`
view. Tune `conf`, `imgsz`, `target_fps` and the line position. Then wire the
"Analítica de Aforo" subscription line.

## Config reference
See `config.example.yaml`. Every key has an `XBF_<UPPERCASE>` env override
(e.g. `XBF_TOKEN`, `XBF_RTSP_URL`, `XBF_LINE='[0.4,0.1,0.6,0.9]'`).

| key | meaning |
|-----|---------|
| `rtsp_url` | door stream (or `0` for USB cam) |
| `odoo_url` | `https://<client>.diamane.mx/xb_footfall/ingest` |
| `token` | per-device Bearer token from Odoo |
| `line` | `[x1,y1,x2,y2]` normalized 0..1 |
| `swap_direction` | flip in/out |
| `model` | `yolo11n.pt` (fast) … `yolo11s.pt` (more accurate) |
| `target_fps` | frames/sec processed (CPU load knob) |
| `device` | `cpu`, or `0` for a CUDA GPU (Jetson) |
| `flush_seconds` | POST cadence; events queue and survive outages |
