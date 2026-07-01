#!/usr/bin/env python3
"""XB Aforo - desktop configurator for the xb_footfall edge agent.

A single native window (Tkinter, ships with Python) that lets a non-technical
operator set up a store counter without touching config.yaml:

  * pick the DVR brand and type IP / user / password / channel -> the RTSP URL
    is assembled for you (Dahua and Hikvision templates built in);
  * "Test camera" grabs one live frame and shows it;
  * draw the counting line by CLICKING two points on that frame;
  * "Test Odoo" checks the endpoint + token reach Odoo (no events created);
  * Save writes config.yaml, and Start/Stop runs the counter with a live log;
  * "Install 24/7" registers autostart (Windows Scheduled Task / macOS
    LaunchAgent) so the counter comes back after a reboot or power cut.

The counter itself (counter.py) is unchanged: this only produces its config
and drives it. Heavy deps (OpenCV / Pillow) are imported lazily, so the form
still opens and saves on a machine where they are not installed yet.

    python configurator.py            # opens the window
    python configurator.py --config <path-to-config.yaml>
"""
import argparse
import json
import os
import platform
import re
import subprocess
import sys
import threading
import urllib.request

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import yaml
except ImportError:                       # pragma: no cover
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTER = os.path.join(HERE, "counter.py")
DEFAULT_CONFIG = os.path.join(HERE, "config.yaml")
DISP_MAX_W = 620                          # frame preview width in the window

# Keys we do NOT touch when saving are carried over from the existing file so a
# hand-tuned config.yaml keeps its advanced values.
GUI_KEYS = {"rtsp_url", "odoo_url", "device_uid", "token", "line",
            "swap_direction", "target_fps", "model", "device"}
FALLBACK_DEFAULTS = {
    "line": [0.5, 0.1, 0.5, 0.9], "swap_direction": False, "target_fps": 6,
    "model": "yolo11n.pt", "device": "cpu", "imgsz": 640, "conf": 0.35,
    "tracker": "bytetrack.yaml", "classes": [0], "flush_seconds": 30,
    "reconnect_seconds": 5, "log_level": "INFO",
}


# ---------------------------------------------------------------------------
# RTSP URL assembly / parsing (round-trips brand + parts <-> a single URL)
# ---------------------------------------------------------------------------
def build_rtsp(brand, ip, port, user, pw, channel, stream):
    """stream: 'main' or 'sub'. Returns the RTSP URL for the DVR channel."""
    port = port or "554"
    if brand == "usb":
        return str(channel or "0")
    if brand == "generic":
        return ip                          # 'ip' field holds the raw URL here
    if brand == "hikvision":
        # /Streaming/Channels/<ch><0><1=main|2=sub>, e.g. 101 ch1 main, 302 ch3 sub
        code = "%s0%s" % (channel or "1", "1" if stream == "main" else "2")
        return "rtsp://%s:%s@%s:%s/Streaming/Channels/%s" % (
            user, pw, ip, port, code)
    # dahua (default)
    subtype = "0" if stream == "main" else "1"
    return "rtsp://%s:%s@%s:%s/cam/realmonitor?channel=%s&subtype=%s" % (
        user, pw, ip, port, channel or "1", subtype)


def parse_rtsp(url):
    """Best-effort split a URL back into GUI fields for re-editing."""
    d = {"brand": "generic", "ip": url, "port": "554", "user": "", "pw": "",
         "channel": "1", "stream": "main"}
    if not url:
        d["brand"] = "dahua"
        d["ip"] = ""
        return d
    if str(url).isdigit():
        d.update(brand="usb", ip="", channel=str(url))
        return d
    m = re.match(r"rtsp://([^:]*):([^@]*)@([^:/]+):?(\d+)?(/.*)", url)
    if not m:
        return d
    user, pw, ip, port, path = m.groups()
    d.update(user=user, pw=pw, ip=ip, port=port or "554")
    mh = re.search(r"/Streaming/Channels/(\d+)0(\d)", path)
    md = re.search(r"channel=(\d+).*subtype=(\d)", path)
    if mh:
        d.update(brand="hikvision", channel=mh.group(1),
                 stream="main" if mh.group(2) == "1" else "sub")
    elif md:
        d.update(brand="dahua", channel=md.group(1),
                 stream="main" if md.group(2) == "0" else "sub")
    return d


def odoo_ingest_url(host):
    host = (host or "").strip().rstrip("/")
    if not host:
        return ""
    if not host.startswith("http"):
        host = "https://" + host
    if not host.endswith("/xb_footfall/ingest"):
        host = host + "/xb_footfall/ingest"
    return host


# ---------------------------------------------------------------------------
# The window
# ---------------------------------------------------------------------------
class App(ttk.Frame):
    def __init__(self, master, config_path):
        # The form is taller than some store screens, so host it in a scrollable
        # canvas: the Save/Start buttons are always reachable by scrolling.
        master.geometry("820x680")
        master.minsize(600, 400)
        container = ttk.Frame(master)
        container.pack(fill="both", expand=True)
        self._vcanvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=self._vcanvas.yview)
        self._vcanvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._vcanvas.pack(side="left", fill="both", expand=True)
        super().__init__(self._vcanvas, padding=10)
        self._vcanvas.create_window((0, 0), window=self, anchor="nw")
        self.bind("<Configure>", lambda e: self._vcanvas.configure(
            scrollregion=self._vcanvas.bbox("all")))
        self._vcanvas.bind_all("<MouseWheel>", lambda e: self._vcanvas.yview_scroll(
            int(-e.delta / 120), "units"))
        self.config_path = config_path
        self.cfg = self._load()
        self.proc = None                   # running counter subprocess
        self.frame_rgb = None              # last grabbed frame (numpy RGB)
        self.tkimg = None                  # keep a ref so it is not GC'd
        self.disp_scale = 1.0
        self.line_pts = []                 # up to 2 (nx, ny) normalized points
        self._build()
        self._fill_from_cfg()

    # -- config io ----------------------------------------------------------
    def _load(self):
        cfg = dict(FALLBACK_DEFAULTS)
        if yaml and os.path.exists(self.config_path):
            with open(self.config_path) as fh:
                cfg.update({k: v for k, v in (yaml.safe_load(fh) or {}).items()})
        return cfg

    def _save(self):
        if not yaml:
            messagebox.showerror("XB Aforo", "Falta PyYAML (pip install pyyaml).")
            return False
        try:
            self._collect_into_cfg()
        except ValueError as exc:
            messagebox.showerror("XB Aforo", str(exc))
            return False
        with open(self.config_path, "w") as fh:
            yaml.safe_dump(self.cfg, fh, sort_keys=False, allow_unicode=True)
        self._log("Guardado: %s" % self.config_path)
        return True

    def _collect_into_cfg(self):
        brand = self.v_brand.get()
        rtsp = build_rtsp(brand, self.v_ip.get().strip(), self.v_port.get().strip(),
                          self.v_user.get().strip(), self.v_pw.get(),
                          self.v_channel.get().strip(), self.v_stream.get())
        odoo = odoo_ingest_url(self.v_host.get())
        if not rtsp:
            raise ValueError("Falta la fuente de la camara (IP o URL).")
        if not odoo:
            raise ValueError("Falta el sitio de Odoo (ej. www.lamur.mx).")
        if not self.v_token.get().strip():
            raise ValueError("Falta el token del dispositivo.")
        self.cfg["rtsp_url"] = rtsp
        self.cfg["odoo_url"] = odoo
        self.cfg["device_uid"] = self.v_uid.get().strip() or "store-door1"
        self.cfg["token"] = self.v_token.get().strip()
        self.cfg["swap_direction"] = bool(self.v_swap.get())
        self.cfg["target_fps"] = int(self.v_fps.get() or 6)
        self.cfg["model"] = self.v_model.get().strip() or "yolo11n.pt"
        self.cfg["device"] = self.v_device.get().strip() or "cpu"
        if len(self.line_pts) == 2:
            (x1, y1), (x2, y2) = self.line_pts
            self.cfg["line"] = [round(x1, 4), round(y1, 4),
                                round(x2, 4), round(y2, 4)]

    def _fill_from_cfg(self):
        p = parse_rtsp(self.cfg.get("rtsp_url", ""))
        self.v_brand.set(p["brand"])
        self.v_ip.set(p["ip"])
        self.v_port.set(p["port"])
        self.v_user.set(p["user"])
        self.v_pw.set(p["pw"])
        self.v_channel.set(p["channel"])
        self.v_stream.set(p["stream"])
        host = re.sub(r"^https?://", "", self.cfg.get("odoo_url", ""))
        host = host.replace("/xb_footfall/ingest", "")
        self.v_host.set(host)
        self.v_uid.set(self.cfg.get("device_uid", ""))
        self.v_token.set(self.cfg.get("token", ""))
        self.v_swap.set(1 if self.cfg.get("swap_direction") else 0)
        self.v_fps.set(str(self.cfg.get("target_fps", 6)))
        self.v_model.set(self.cfg.get("model", "yolo11n.pt"))
        self.v_device.set(self.cfg.get("device", "cpu"))
        line = self.cfg.get("line") or []
        if len(line) == 4:
            self.line_pts = [(line[0], line[1]), (line[2], line[3])]
        self._on_brand()

    # -- layout -------------------------------------------------------------
    def _build(self):
        self.master.title("XB Aforo - Configurar contador")
        pad = {"padx": 4, "pady": 3}
        self.v_brand = tk.StringVar(value="dahua")
        self.v_ip = tk.StringVar()
        self.v_port = tk.StringVar(value="554")
        self.v_user = tk.StringVar(value="admin")
        self.v_pw = tk.StringVar()
        self.v_channel = tk.StringVar(value="1")
        self.v_stream = tk.StringVar(value="main")
        self.v_host = tk.StringVar()
        self.v_uid = tk.StringVar()
        self.v_token = tk.StringVar()
        self.v_swap = tk.IntVar()
        self.v_fps = tk.StringVar(value="6")
        self.v_model = tk.StringVar(value="yolo11n.pt")
        self.v_device = tk.StringVar(value="cpu")

        # --- Camera source ---
        cam = ttk.LabelFrame(self, text="Camara (DVR de la puerta)", padding=8)
        cam.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Label(cam, text="Marca").grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(cam, textvariable=self.v_brand, width=12, state="readonly",
                          values=["dahua", "hikvision", "generic", "usb"])
        cb.grid(row=0, column=1, sticky="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._on_brand())
        ttk.Label(cam, text="IP local").grid(row=0, column=2, sticky="e")
        self.e_ip = ttk.Entry(cam, textvariable=self.v_ip, width=18)
        self.e_ip.grid(row=0, column=3, sticky="w")
        ttk.Label(cam, text="Puerto").grid(row=0, column=4, sticky="e")
        self.e_port = ttk.Entry(cam, textvariable=self.v_port, width=6)
        self.e_port.grid(row=0, column=5, sticky="w")

        ttk.Label(cam, text="Usuario").grid(row=1, column=0, sticky="w")
        self.e_user = ttk.Entry(cam, textvariable=self.v_user, width=14)
        self.e_user.grid(row=1, column=1, sticky="w")
        ttk.Label(cam, text="Contrasena").grid(row=1, column=2, sticky="e")
        self.e_pw = ttk.Entry(cam, textvariable=self.v_pw, width=18, show="*")
        self.e_pw.grid(row=1, column=3, sticky="w")
        ttk.Label(cam, text="Canal").grid(row=1, column=4, sticky="e")
        self.e_channel = ttk.Entry(cam, textvariable=self.v_channel, width=6)
        self.e_channel.grid(row=1, column=5, sticky="w")
        ttk.Label(cam, text="Flujo").grid(row=2, column=4, sticky="e")
        self.cb_stream = ttk.Combobox(cam, textvariable=self.v_stream, width=6,
                                      state="readonly", values=["main", "sub"])
        self.cb_stream.grid(row=2, column=5, sticky="w")
        self.lbl_url = ttk.Label(cam, text="", foreground="#666")
        self.lbl_url.grid(row=3, column=0, columnspan=6, sticky="w", pady=(4, 0))

        # --- Odoo destination ---
        od = ttk.LabelFrame(self, text="Odoo (a donde se envia)", padding=8)
        od.grid(row=1, column=0, sticky="ew", **pad)
        ttk.Label(od, text="Sitio").grid(row=0, column=0, sticky="w")
        ttk.Entry(od, textvariable=self.v_host, width=28).grid(row=0, column=1, sticky="w")
        ttk.Label(od, text="(ej. www.lamur.mx)").grid(row=0, column=2, sticky="w")
        ttk.Label(od, text="ID dispositivo").grid(row=1, column=0, sticky="w")
        ttk.Entry(od, textvariable=self.v_uid, width=28).grid(row=1, column=1, sticky="w")
        ttk.Label(od, text="Token").grid(row=2, column=0, sticky="w")
        ttk.Entry(od, textvariable=self.v_token, width=44, show="*").grid(
            row=2, column=1, columnspan=2, sticky="w")

        # --- Test buttons ---
        btns = ttk.Frame(self)
        btns.grid(row=2, column=0, sticky="ew", **pad)
        ttk.Button(btns, text="Probar camara", command=self._test_camera).grid(row=0, column=0, padx=3)
        ttk.Button(btns, text="Probar Odoo", command=self._test_odoo).grid(row=0, column=1, padx=3)
        ttk.Button(btns, text="Reiniciar linea", command=self._reset_line).grid(row=0, column=2, padx=3)
        ttk.Checkbutton(btns, text="Invertir Entrada/Salida", variable=self.v_swap
                        ).grid(row=0, column=3, padx=10)

        # --- Frame preview + line drawing ---
        prev = ttk.LabelFrame(self, text="Vista de la puerta - clic 2 puntos para la linea", padding=6)
        prev.grid(row=3, column=0, sticky="nsew", **pad)
        self.canvas = tk.Canvas(prev, width=DISP_MAX_W, height=int(DISP_MAX_W * 9 / 16),
                                bg="#222", highlightthickness=0)
        self.canvas.grid(row=0, column=0)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.create_text(DISP_MAX_W // 2, 40, fill="#aaa",
                                text="Pulsa \"Probar camara\" para ver la puerta")

        # --- Advanced ---
        adv = ttk.LabelFrame(self, text="Avanzado", padding=8)
        adv.grid(row=4, column=0, sticky="ew", **pad)
        ttk.Label(adv, text="FPS").grid(row=0, column=0, sticky="w")
        ttk.Entry(adv, textvariable=self.v_fps, width=5).grid(row=0, column=1, sticky="w")
        ttk.Label(adv, text="Modelo").grid(row=0, column=2, sticky="e")
        ttk.Entry(adv, textvariable=self.v_model, width=14).grid(row=0, column=3, sticky="w")
        ttk.Label(adv, text="Dispositivo").grid(row=0, column=4, sticky="e")
        ttk.Entry(adv, textvariable=self.v_device, width=6).grid(row=0, column=5, sticky="w")

        # --- Actions ---
        act = ttk.Frame(self)
        act.grid(row=5, column=0, sticky="ew", **pad)
        ttk.Button(act, text="Guardar", command=self._save).grid(row=0, column=0, padx=3)
        self.btn_run = ttk.Button(act, text="Arrancar", command=self._toggle_run)
        self.btn_run.grid(row=0, column=1, padx=3)
        ttk.Button(act, text="Instalar arranque 24/7", command=self._install_autostart
                   ).grid(row=0, column=2, padx=3)

        # --- Log ---
        self.log = tk.Text(self, height=6, width=88, bg="#111", fg="#7fd", wrap="none")
        self.log.grid(row=6, column=0, sticky="nsew", **pad)

    def _on_brand(self):
        brand = self.v_brand.get()
        usb = brand == "usb"
        generic = brand == "generic"
        net = not usb and not generic
        # 'ip' doubles as the raw-URL box for generic
        for w in (self.e_port, self.e_user, self.e_pw, self.cb_stream):
            w.configure(state="normal" if net else "disabled")
        self.e_channel.configure(state="normal" if (net or usb) else "disabled")
        if generic:
            self.lbl_url.configure(text="URL RTSP completa en el campo 'IP local'")
        elif usb:
            self.lbl_url.configure(text="Camara USB: indice (0, 1, ...) en 'Canal'")
        else:
            self.lbl_url.configure(text=self._preview_url())

    def _preview_url(self):
        url = build_rtsp(self.v_brand.get(), self.v_ip.get().strip(),
                         self.v_port.get().strip(), self.v_user.get().strip(),
                         "****" if self.v_pw.get() else "", self.v_channel.get().strip(),
                         self.v_stream.get())
        return url

    # -- camera / line ------------------------------------------------------
    def _test_camera(self):
        try:
            self._collect_into_cfg()
        except ValueError:
            pass                            # partial config is fine just to preview
        url = build_rtsp(self.v_brand.get(), self.v_ip.get().strip(),
                         self.v_port.get().strip(), self.v_user.get().strip(),
                         self.v_pw.get(), self.v_channel.get().strip(),
                         self.v_stream.get())
        if not url:
            messagebox.showerror("XB Aforo", "Falta la IP o la URL de la camara.")
            return
        self._log("Conectando a la camara...")
        threading.Thread(target=self._grab, args=(url,), daemon=True).start()

    def _grab(self, url):
        try:
            import cv2
        except ImportError:
            self._ui(lambda: messagebox.showerror(
                "XB Aforo", "Falta OpenCV. Corre install (instala dependencias)."))
            return
        os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")
        src = int(url) if str(url).isdigit() else url
        cap = cv2.VideoCapture(src)
        ok, frame = (cap.read() if cap.isOpened() else (False, None))
        cap.release()
        if not ok:
            self._ui(lambda: (self._log("No se pudo abrir la camara."),
                              messagebox.showerror("XB Aforo",
                              "No se pudo abrir la camara.\nRevisa IP, usuario, "
                              "clave y canal.")))
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self.frame_rgb = rgb
        self._ui(lambda: self._show_frame(rgb))

    def _show_frame(self, rgb):
        try:
            from PIL import Image, ImageTk
        except ImportError:
            messagebox.showerror("XB Aforo", "Falta Pillow (pip install pillow).")
            return
        h, w = rgb.shape[:2]
        self.disp_scale = DISP_MAX_W / float(w)
        disp_w, disp_h = DISP_MAX_W, int(h * self.disp_scale)
        img = Image.fromarray(rgb).resize((disp_w, disp_h))
        self.tkimg = ImageTk.PhotoImage(img)
        self.canvas.configure(width=disp_w, height=disp_h)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tkimg)
        self._redraw_line()
        self._log("Camara OK (%dx%d). Haz clic en 2 puntos para la linea." % (w, h))

    def _on_click(self, ev):
        if self.frame_rgb is None:
            return
        dw = int(self.canvas["width"])
        dh = int(self.canvas["height"])
        nx, ny = ev.x / float(dw), ev.y / float(dh)
        if len(self.line_pts) >= 2:
            self.line_pts = []
        self.line_pts.append((round(nx, 4), round(ny, 4)))
        self._redraw_line()

    def _redraw_line(self):
        self.canvas.delete("line")
        dw = int(self.canvas["width"])
        dh = int(self.canvas["height"])
        pts = [(nx * dw, ny * dh) for nx, ny in self.line_pts]
        for (x, y) in pts:
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, outline="#0f0",
                                    width=2, tags="line")
        if len(pts) == 2:
            self.canvas.create_line(pts[0][0], pts[0][1], pts[1][0], pts[1][1],
                                    fill="#0f0", width=3, tags="line")
            self._log("Linea: %s" % [c for p in self.line_pts for c in p])

    def _reset_line(self):
        self.line_pts = []
        self._redraw_line()

    # -- odoo test ----------------------------------------------------------
    def _test_odoo(self):
        url = odoo_ingest_url(self.v_host.get())
        token = self.v_token.get().strip()
        if not url or not token:
            messagebox.showerror("XB Aforo", "Falta el sitio de Odoo o el token.")
            return
        self._log("Probando %s ..." % url)
        threading.Thread(target=self._ping, args=(url, token), daemon=True).start()

    def _ping(self, url, token):
        body = json.dumps({"device_uid": self.v_uid.get().strip() or "test",
                           "events": []}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Authorization": "Bearer " + token,
                     "Content-Type": "application/json",
                     "User-Agent": "xb-footfall-edge/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.load(resp)
            msg = "Odoo OK - token valido. Respuesta: %s" % data
            self._ui(lambda: (self._log(msg),
                              messagebox.showinfo("XB Aforo", msg)))
        except urllib.error.HTTPError as exc:
            hint = {401: "falta el token", 403: "token invalido"}.get(
                exc.code, "error HTTP %s" % exc.code)
            self._ui(lambda: messagebox.showerror(
                "XB Aforo", "Odoo respondio %s (%s)." % (exc.code, hint)))
        except Exception as exc:            # noqa: BLE001
            self._ui(lambda: messagebox.showerror(
                "XB Aforo", "No se pudo contactar Odoo:\n%s" % exc))

    # -- run / autostart ----------------------------------------------------
    def _toggle_run(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc = None
            self.btn_run.configure(text="Arrancar")
            self._log("Contador detenido.")
            return
        if not self._save():
            return
        self.proc = subprocess.Popen(
            [sys.executable, COUNTER, "--config", self.config_path],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            bufsize=1)
        self.btn_run.configure(text="Detener")
        self._log("Contador arrancado (PID %s)." % self.proc.pid)
        threading.Thread(target=self._pump, args=(self.proc,), daemon=True).start()

    def _pump(self, proc):
        for line in iter(proc.stdout.readline, ""):
            self._ui(lambda ln=line.rstrip(): self._log(ln))
        self._ui(lambda: self.btn_run.configure(text="Arrancar"))

    def _install_autostart(self):
        if not self._save():
            return
        sysname = platform.system()
        try:
            if sysname == "Windows":
                self._autostart_windows()
            elif sysname == "Darwin":
                self._autostart_mac()
            else:
                messagebox.showinfo("XB Aforo",
                    "Autostart automatico solo en Windows/macOS. En Linux usa "
                    "el systemd unit xb-footfall-edge.service.")
                return
        except Exception as exc:            # noqa: BLE001
            messagebox.showerror("XB Aforo", "No se pudo instalar el arranque:\n%s" % exc)

    def _autostart_windows(self):
        # pythonw runs with no console window; Scheduled Task at logon.
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        pyw = pyw if os.path.exists(pyw) else sys.executable
        cmd = '"%s" "%s" --config "%s"' % (pyw, COUNTER, self.config_path)
        subprocess.check_call(["schtasks", "/Create", "/TN", "XB Aforo Edge",
                               "/TR", cmd, "/SC", "ONLOGON", "/RL", "LIMITED", "/F"])
        messagebox.showinfo("XB Aforo",
            "Listo. El contador arrancara solo al iniciar sesion en Windows.\n"
            "Tarea: 'XB Aforo Edge' (Programador de tareas).")

    def _autostart_mac(self):
        label = "com.xubax.footfall"
        plist = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % label)
        content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>%s</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/caffeinate</string><string>-i</string>
    <string>%s</string><string>%s</string><string>--config</string><string>%s</string>
  </array>
  <key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
</dict></plist>""" % (label, sys.executable, COUNTER, self.config_path)
        with open(plist, "w") as fh:
            fh.write(content)
        subprocess.call(["launchctl", "unload", plist])
        subprocess.check_call(["launchctl", "load", plist])
        messagebox.showinfo("XB Aforo", "Listo. LaunchAgent %s instalado." % label)

    # -- helpers ------------------------------------------------------------
    def _ui(self, fn):
        self.after(0, fn)

    def _log(self, msg):
        self.log.insert("end", msg + "\n")
        self.log.see("end")


def main():
    ap = argparse.ArgumentParser(description="XB Aforo edge configurator")
    ap.add_argument("--config", default=os.environ.get("XBF_CONFIG", DEFAULT_CONFIG))
    args = ap.parse_args()
    root = tk.Tk()
    root.columnconfigure(0, weight=1)
    App(root, args.config)
    root.mainloop()


if __name__ == "__main__":
    main()
