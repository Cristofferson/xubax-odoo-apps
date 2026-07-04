# -*- coding: utf-8 -*-
"""Minimal RFC 5545 (iCalendar) helpers — no external dependencies.

Covers the VEVENT subset used by hospitality platforms (Airbnb,
Booking.com, Vrbo, Lodgify, ...): all-day DATE events, DATE-TIME
events (UTC or naive), line folding/unfolding and text escaping.
"""
from datetime import date, datetime, timedelta

PRODID = "-//Xubax//Odoo Hotel OTA Channel Manager//EN"


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _escape(text):
    """Escape TEXT values per RFC 5545 §3.3.11."""
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold_all(lines):
    """Fold content lines longer than 75 octets (RFC 5545 §3.1)."""
    out = []
    for line in lines:
        raw = line.encode("utf-8")
        if len(raw) <= 75:
            out.append(line)
            continue
        first = True
        while raw:
            limit = 75 if first else 74
            chunk = raw[:limit]
            while chunk and (chunk[-1] & 0xC0) == 0x80:
                chunk = chunk[:-1]
            out.append(("" if first else " ") + chunk.decode("utf-8"))
            raw = raw[len(chunk):]
            first = False
    return out


def fmt_date(d):
    return d.strftime("%Y%m%d")


def generate(events, calname=None):
    """Build an .ics text.

    :param events: list of dicts with keys:
        uid (str), start (date), end (date, EXCLUSIVE checkout),
        summary (str), description (str, optional)
    :return: str (CRLF-terminated)
    """
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:%s" % PRODID,
        "CALSCALE:GREGORIAN",
    ]
    if calname:
        lines.append("X-WR-CALNAME:%s" % _escape(calname))
    for ev in events:
        lines += [
            "BEGIN:VEVENT",
            "UID:%s" % ev["uid"],
            "DTSTAMP:%s" % now,
            "DTSTART;VALUE=DATE:%s" % fmt_date(ev["start"]),
            "DTEND;VALUE=DATE:%s" % fmt_date(ev["end"]),
            "SUMMARY:%s" % _escape(ev.get("summary") or "Reserved"),
        ]
        if ev.get("description"):
            lines.append("DESCRIPTION:%s" % _escape(ev["description"]))
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_all(lines)) + "\r\n"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _unfold(text):
    """Unfold continuation lines and normalize newlines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in text.split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _unescape(text):
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            n = text[i + 1]
            out.append({"n": "\n", "N": "\n"}.get(n, n))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _parse_dt(prop_params, value):
    """Return a date for DATE or DATE-TIME values (drops time part)."""
    value = value.strip()
    if "VALUE=DATE" in prop_params.upper() or ("T" not in value):
        return datetime.strptime(value[:8], "%Y%m%d").date()
    # DATE-TIME: 20260703T120000Z / 20260703T120000
    return datetime.strptime(value[:8], "%Y%m%d").date()


def parse(text):
    """Parse .ics text → list of event dicts.

    Keys: uid, start (date), end (date, exclusive; defaults start+1),
    summary, description, status.
    Unknown/malformed VEVENTs are skipped, never raised.
    """
    events, cur = [], None
    for line in _unfold(text or ""):
        if not line.strip():
            continue
        upper = line.upper()
        if upper.startswith("BEGIN:VEVENT"):
            cur = {}
            continue
        if upper.startswith("END:VEVENT"):
            if cur is not None and cur.get("start"):
                cur.setdefault("uid", "no-uid-%s" % fmt_date(cur["start"]))
                if not cur.get("end") or cur["end"] <= cur["start"]:
                    cur["end"] = cur["start"] + timedelta(days=1)
                cur.setdefault("summary", "")
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        prop, value = line.split(":", 1)
        name = prop.split(";", 1)[0].upper()
        params = prop[len(name):]
        try:
            if name == "UID":
                cur["uid"] = value.strip()
            elif name == "DTSTART":
                cur["start"] = _parse_dt(params, value)
            elif name == "DTEND":
                cur["end"] = _parse_dt(params, value)
            elif name == "SUMMARY":
                cur["summary"] = _unescape(value.strip())
            elif name == "DESCRIPTION":
                cur["description"] = _unescape(value.strip())
            elif name == "STATUS":
                cur["status"] = value.strip().upper()
        except (ValueError, TypeError):
            # Malformed property: skip it, keep the event best-effort
            continue
    return events


BLOCK_KEYWORDS = (
    "not available", "closed", "unavailable", "blocked", "no disponible",
)


def is_block(event):
    """Heuristic: OTA 'closed / not available' events are blocks, the
    rest are reservations. Airbnb: 'Airbnb (Not available)' vs 'Reserved'.
    Booking.com room feeds: 'CLOSED - Not available'."""
    summary = (event.get("summary") or "").lower()
    return any(k in summary for k in BLOCK_KEYWORDS)
