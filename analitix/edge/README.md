# Analitix edge agent

Runs on the mini-PC in the store. Watches a camera, counts people crossing a
virtual line, posts the crossings to Odoo.

**The Odoo module has no computer-vision dependency and must never acquire
one.** Everything in this folder runs on the mini-PC in the shop; Odoo receives
JSON, and that is the whole interface. The source ships inside the addon —
`package.sh` fails the build if it does not — so nobody is locked into our
agent.

---

## What it guarantees

A shop's internet is not a data centre's. It drops for ten minutes, the router
reboots at 3 a.m., someone unplugs the switch while cleaning. A counter that
loses those hours is worse than no counter, because the owner cannot tell a
quiet Tuesday from an outage.

So the agent is built to lose nothing:

| | |
|---|---|
| **Persistent uuid** | Minted before the first send attempt and kept across retries, restarts and power cuts. This is what lets Odoo deduplicate a replayed batch instead of counting it twice. |
| **Encrypted disk queue** | SQLite, so a power cut costs at most the one in-flight row. Encrypted, so a stolen mini-PC is a stolen mini-PC and not a data breach. |
| **Ordered replay with original timestamps** | A recovered outage appears as the hours it actually was, not as one impossible spike at the moment the link came back. |
| **Acknowledge-then-delete** | An event leaves the local queue only when Odoo has explicitly confirmed it holds it. |
| **Server-driven configuration** | Heartbeat interval, line coordinates and staff signatures all come from Odoo, so a fleet is retuned without visiting any store. |

## What never leaves the store

No image. No video. Not as a field, not as an attachment, not temporarily for
debugging. The frame is discarded in memory the moment the detection is done —
one line in `LineCounterSource.crossings()` — and there is no endpoint in Odoo
that would accept one.

Face vectors also stay local by default: the agent pulls its store's staff
signatures, compares in memory, and sends only the verdict. Setting
`send_embeddings: true` is for hardware too small to hold the signature set,
and it is off unless someone chooses it.

## Install — Windows

**This is how it is installed in a shop.** Download
`AnalitixAgentSetup-<version>.exe`, run it, and paste two values. Nothing else.

The installer carries the vision engine inside it, so the mini-PC does not need
internet, a Python, or anybody who knows what a wheel is. It is a large
download for that reason — the counting model and its runtime are most of it.

What it does:

| | |
|---|---|
| Program | `C:\Program Files\Analitix` |
| Configuration | `C:\ProgramData\Analitix\agent.yaml` — **not** under Program Files, because it holds the device key and the agent writes to it. Reinstalling never overwrites it. |
| Queue and state | `C:\ProgramData\Analitix\state` |
| Log | `C:\ProgramData\Analitix\logs\agent.log`, rotated. On Linux journald collects this; Windows has nobody to collect it, so the agent writes its own. |
| Autostart | A scheduled task, **Analitix Agent**, running as `SYSTEM` at boot. |

### Why a scheduled task and not a Windows service

A real service has to speak the service-control protocol, and a PyInstaller
binary that does not gets killed after thirty seconds for "not responding".
A scheduled task is native, starts before anybody logs in, restarts on its own
if the process dies, and needs no third-party wrapper. It is visible in Task
Scheduler under `Analitix Agent`.

### After installing

The installer opens `agent.yaml` for you. Fill in the two lines the
implementer was given:

```yaml
odoo_url: "https://tienda.ejemplo.com"
api_key:  "alx_..."          # from the device form in Odoo
```

Then restart the task — or the machine:

```bat
schtasks /End  /TN "Analitix Agent"
schtasks /Run  /TN "Analitix Agent"
```

Shortcuts for **Editar la configuración**, **Ver el registro** and **Probar en
esta ventana** are in the Start menu. The last one runs the agent in the
foreground with `--verbose`, which is what to use while aiming a camera.

### Building the installer

It is built by GitHub Actions on a real Windows runner
(`.github/workflows/analitix-agent-windows.yml`) — push a tag
`analitix-agent-v<version>` or run the workflow by hand. The sources are in
`windows/`: a PyInstaller spec and an Inno Setup script.

> **Pending: Authenticode signature.** Until the installer is signed, Windows
> SmartScreen shows "unrecognised app" the first time it runs — in front of the
> customer. It is a purchase, not code.

## Install — Linux

Supported and used for the machines we provision ourselves, but it is not what
a customer gets handed.

```bash
sudo useradd -r -s /usr/sbin/nologin analitix
sudo mkdir -p /opt/analitix /etc/analitix
sudo python3 -m venv /opt/analitix/venv
sudo /opt/analitix/venv/bin/pip install requests cryptography pyyaml

# Only for a real camera; a demo-source install does not need these.
sudo /opt/analitix/venv/bin/pip install ultralytics opencv-python-headless

sudo cp analitix_agent.py /opt/analitix/
sudo cp config.example.yaml /etc/analitix/agent.yaml
sudo cp analitix-agent.service /etc/systemd/system/
sudo chown -R analitix:analitix /opt/analitix /etc/analitix
sudo chmod 600 /etc/analitix/agent.yaml     # it holds the API key

sudo -e /etc/analitix/agent.yaml            # paste odoo_url and api_key
sudo systemctl enable --now analitix-agent
```

## Commissioning a site

1. **Prove the link before mounting anything.** Set `source: demo` and start
   the agent. The device turns *Online* in Odoo within one heartbeat and
   synthetic crossings appear. If this does not work, the camera was never the
   problem.
2. **Aim the camera** overhead at the door, then set `line` to the pixel
   coordinates people must cross. Odoo can push this down instead — put it in
   the device's *Edge Configuration* field and the agent picks it up on its
   next refresh.
3. **Switch to `source: line`** and watch a few real crossings land.
4. **Enrol the staff**, or the store's conversion rate will read far below the
   truth: in a small shop the team can be a third of the "visitors".

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403 tls_required` | `odoo_url` is `http://` | Use HTTPS. For a lab only, set `analitix.allow_insecure_ingest = 1` in Odoo. |
| `401 invalid_credentials` | Key is wrong, revoked, or the device was archived | Rotate the key on the device form in Odoo and paste the new one. Buffered events survive. |
| `423 capture_paused` | The store's kill switch is on | Expected. The agent keeps buffering and resumes on its own. |
| Device shows *Offline* but the agent is running | Heartbeats are not arriving | Check DNS and the firewall from the store. The backlog in the logs tells you how much is queued. |
| Backlog keeps growing | Odoo unreachable or refusing | Look at the last error — `journalctl -u analitix-agent` on Linux, `C:\ProgramData\Analitix\logs\agent.log` on Windows. Nothing is lost yet; it will be if the disk fills. |
| Counts look far too high | The line crosses a waiting area, so people drift back and forth over it | Move the line into the doorway itself. |
| Counts look far too low | Camera too low, people occluding each other | Mount overhead, use a depth camera in a busy doorway. |
| Windows: nothing happens after installing | The task never started | `schtasks /Query /TN "Analitix Agent" /V /FO LIST`. If it is not there, the installer did not finish as administrator. |
| Windows: "unrecognised app" on opening the installer | It is not signed yet | Expected until the Authenticode certificate is bought. *More info → Run anyway.* |

## Reporting zones and the till

Phase 3 adds two more endpoints the agent can use, both documented in
`../doc/API.md`:

* **`/dwell`** — how long a tracked person has been in a zone or at a display.
  Send a **running total while they are still standing there**, keyed on the
  `track` id you gave them at the door. A lost-sale nudge that arrives after
  the customer has walked out is worthless.
* **`/checkout`** — the payer's face at the till, with the POS reference, so
  the ticket can be attributed to the visit that produced it. A store without a
  till camera skips this entirely and still gets attribution through the
  purchase unit frozen at the door.

Zone and display references (`zone`, `poi`) are the *Reference* codes set in
Odoo, so the floor plan can be re-cut without touching any agent.

## Contract

`../doc/API.md`. Read it before writing your own agent — every rule in it
exists because getting it wrong corrupts a paying customer's numbers in a way
that is very hard to notice afterwards.
