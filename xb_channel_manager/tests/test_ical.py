# -*- coding: utf-8 -*-
from datetime import date

from odoo.tests.common import BaseCase, tagged

from ..models import ical_utils


AIRBNB_FIXTURE = """BEGIN:VCALENDAR
PRODID:-//Airbnb Inc//Hosting Calendar 0.8.8//EN
CALSCALE:GREGORIAN
VERSION:2.0
BEGIN:VEVENT
DTSTAMP:20260703T120000Z
DTSTART;VALUE=DATE:20260810
DTEND;VALUE=DATE:20260813
SUMMARY:Reserved
UID:14c1a9b8f2e1-8d1a2b3c4d5e6f@airbnb.com
DESCRIPTION:Reservation URL: https://www.airbnb.com/hosting/reservations/de
 tails/HMXYZ12345\\nPhone Number (Last 4 Digits): 1707
END:VEVENT
BEGIN:VEVENT
DTSTAMP:20260703T120000Z
DTSTART;VALUE=DATE:20260901
DTEND;VALUE=DATE:20260903
SUMMARY:Airbnb (Not available)
UID:blocked-20260901@airbnb.com
END:VEVENT
END:VCALENDAR
"""

BOOKING_FIXTURE = (
    "BEGIN:VCALENDAR\r\n"
    "VERSION:2.0\r\n"
    "PRODID:-//BookingSync//Booking.com//EN\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:bkg-5566778899@booking.com\r\n"
    "DTSTART;VALUE=DATE:20261120\r\n"
    "DTEND;VALUE=DATE:20261123\r\n"
    "SUMMARY:CLOSED - Not available\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


@tagged("standard", "at_install")
class TestIcalUtils(BaseCase):

    def test_parse_airbnb(self):
        events = ical_utils.parse(AIRBNB_FIXTURE)
        self.assertEqual(len(events), 2)
        resa, block = events
        self.assertEqual(resa["start"], date(2026, 8, 10))
        self.assertEqual(resa["end"], date(2026, 8, 13))
        self.assertEqual(resa["summary"], "Reserved")
        self.assertIn("airbnb.com", resa["uid"])
        # folded DESCRIPTION got unfolded and unescaped
        self.assertIn("HMXYZ12345", resa["description"])
        self.assertIn("\n", resa["description"])
        self.assertFalse(ical_utils.is_block(resa))
        self.assertTrue(ical_utils.is_block(block))

    def test_parse_booking_block(self):
        events = ical_utils.parse(BOOKING_FIXTURE)
        self.assertEqual(len(events), 1)
        self.assertTrue(ical_utils.is_block(events[0]))
        self.assertEqual(events[0]["start"], date(2026, 11, 20))
        self.assertEqual(events[0]["end"], date(2026, 11, 23))

    def test_parse_datetime_and_defaults(self):
        text = (
            "BEGIN:VCALENDAR\nBEGIN:VEVENT\n"
            "DTSTART:20260705T140000Z\n"
            "SUMMARY:One nighter\nEND:VEVENT\nEND:VCALENDAR\n")
        events = ical_utils.parse(text)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["start"], date(2026, 7, 5))
        # missing DTEND defaults to one night
        self.assertEqual(events[0]["end"], date(2026, 7, 6))
        self.assertTrue(events[0]["uid"].startswith("no-uid-"))

    def test_parse_garbage_is_safe(self):
        self.assertEqual(ical_utils.parse(""), [])
        self.assertEqual(ical_utils.parse("hello world"), [])
        broken = ("BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:banana\n"
                  "END:VEVENT\nEND:VCALENDAR")
        self.assertEqual(ical_utils.parse(broken), [])

    def test_generate_roundtrip(self):
        events = [{
            "uid": "cm-1-20260810@example.com",
            "start": date(2026, 8, 10),
            "end": date(2026, 8, 13),
            "summary": "Reserved, with comma; and semicolon",
        }]
        text = ical_utils.generate(events, calname="Suite King")
        self.assertIn("BEGIN:VCALENDAR", text)
        self.assertIn("DTSTART;VALUE=DATE:20260810", text)
        self.assertIn("DTEND;VALUE=DATE:20260813", text)
        # escaped on write
        self.assertIn("\\, ", text.replace("\r\n ", ""))
        parsed = ical_utils.parse(text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["start"], events[0]["start"])
        self.assertEqual(parsed[0]["end"], events[0]["end"])
        self.assertEqual(parsed[0]["summary"],
                         "Reserved, with comma; and semicolon")

    def test_folding_long_lines(self):
        events = [{
            "uid": "u1",
            "start": date(2026, 8, 10),
            "end": date(2026, 8, 11),
            "summary": "x" * 300,
        }]
        text = ical_utils.generate(events)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)
        parsed = ical_utils.parse(text)
        self.assertEqual(parsed[0]["summary"], "x" * 300)
