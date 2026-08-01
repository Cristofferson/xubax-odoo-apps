# Analitix edge agent

Runs on the mini-PC in the store. Watches a camera, counts people crossing a
virtual line, posts the crossings to Odoo.

**This folder is not part of the published addon.** It ships with the
repository and is excluded from the apps.odoo.com zip on purpose: the Odoo
module has no computer-vision dependency and must never acquire one. Odoo
receives JSON. That is the whole interface.

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

## Install

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
| Backlog keeps growing | Odoo unreachable or refusing | Look at the last error in `journalctl -u analitix-agent`. Nothing is lost yet; it will be if the disk fills. |
| Counts look far too high | The line crosses a waiting area, so people drift back and forth over it | Move the line into the doorway itself. |
| Counts look far too low | Camera too low, people occluding each other | Mount overhead, use a depth camera in a busy doorway. |

## Contract

`../doc/API.md`. Read it before writing your own agent — every rule in it
exists because getting it wrong corrupts a paying customer's numbers in a way
that is very hard to notice afterwards.
