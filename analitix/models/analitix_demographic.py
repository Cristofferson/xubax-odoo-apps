# -*- coding: utf-8 -*-
"""Age band, gender and emotion — aggregate attributes, never an identity.

What is stored is a coarse *band*, not an age: "25-34", not "31". That is not
squeamishness, it is honesty about the estimate — a demographic model's output
is a probability distribution and reporting it to the year would dress a guess
up as a measurement. Bands are also all the business question needs: an owner
asks "is my evening crowd younger than my morning crowd", never "how old is
that man".

Confidence is stored beside every attribute, and low-confidence readings are
kept rather than dropped so the dashboards can exclude them explicitly instead
of silently treating a coin flip as a fact.
"""
from odoo import api, fields, models

#: Bands wide enough that a model's error rarely crosses two of them, and
#: recognisable to a retailer without explanation.
AGE_BANDS = [
    ("0-12", "Child (0-12)"),
    ("13-17", "Teen (13-17)"),
    ("18-24", "18-24"),
    ("25-34", "25-34"),
    ("35-44", "35-44"),
    ("45-54", "45-54"),
    ("55-64", "55-64"),
    ("65+", "65+"),
]

BAND_BOUNDS = [
    (0, 12, "0-12"), (13, 17, "13-17"), (18, 24, "18-24"), (25, 34, "25-34"),
    (35, 44, "35-44"), (45, 54, "45-54"), (55, 64, "55-64"), (65, 200, "65+"),
]


def band_for_age(age):
    """Return the band an estimated age falls in, or ``False``."""
    if age is None:
        return False
    try:
        value = float(age)
    except (TypeError, ValueError):
        return False
    for low, high, band in BAND_BOUNDS:
        if low <= value <= high:
            return band
    return False


class AnalitixDemographic(models.Model):
    _name = "analitix.demographic"
    _description = "Analitix Demographic Reading"
    _order = "captured_at desc, id desc"
    _rec_name = "age_band"

    store_id = fields.Many2one(
        "analitix.store", string="Store", required=True, index=True,
        ondelete="cascade")
    company_id = fields.Many2one(
        "res.company", related="store_id.company_id", store=True, index=True,
        readonly=True)
    door_id = fields.Many2one(
        "analitix.door", string="Door", index=True, ondelete="set null")
    captured_at = fields.Datetime(
        string="Captured", required=True, index=True,
        default=lambda self: fields.Datetime.now())

    age_band = fields.Selection(
        selection=AGE_BANDS, string="Age Band", index=True,
        help="A band, not an age. The underlying model outputs an estimate with "
             "real error; reporting it to the year would present a guess as a "
             "measurement.")
    age_confidence = fields.Float(string="Age Confidence", digits=(3, 3))
    gender = fields.Selection(
        selection=[
            ("female", "Female"),
            ("male", "Male"),
            ("unknown", "Unknown"),
        ],
        string="Gender", index=True, default="unknown",
        help="The model's estimate of presented appearance. It is not a "
             "statement about anyone's identity, and 'unknown' is a legitimate "
             "and common answer rather than a failure.")
    gender_confidence = fields.Float(string="Gender Confidence", digits=(3, 3))
    emotion = fields.Selection(
        selection=[
            ("neutral", "Neutral"),
            ("happy", "Happy"),
            ("sad", "Sad"),
            ("angry", "Angry"),
            ("surprised", "Surprised"),
            ("fearful", "Fearful"),
            ("disgusted", "Disgusted"),
        ],
        string="Emotion", index=True,
        help="Momentary expression at the moment of the reading. Phase 4 uses a "
             "sustained negative reading to prompt a discreet nudge to a "
             "salesperson — a single frame means nothing on its own.")
    emotion_confidence = fields.Float(string="Emotion Confidence", digits=(3, 3))

    liveness_score = fields.Float(
        string="Liveness", digits=(3, 3),
        help="How confident the edge is that this was a live face and not a "
             "photograph shown to the camera (task 984, point 3).")
    reliable = fields.Boolean(
        string="Reliable", compute="_compute_reliable", store=True, index=True,
        help="Every confidence clears the store's floor. Unreliable readings "
             "are kept, not discarded, so a dashboard can leave them out "
             "explicitly rather than quietly average a coin flip into the "
             "customer's numbers.")

    visitor_ids = fields.One2many(
        "analitix.visitor", "demographic_id", string="Visits")

    _store_captured_idx = models.Index("(store_id, captured_at DESC)")

    @api.depends("age_confidence", "gender_confidence", "emotion_confidence",
                 "store_id.demographic_min_confidence")
    def _compute_reliable(self):
        for reading in self:
            floor = reading.store_id.demographic_min_confidence or 0.0
            scores = [s for s in (reading.age_confidence,
                                  reading.gender_confidence) if s]
            reading.reliable = bool(scores) and all(s >= floor for s in scores)

    # ------------------------------------------------------------------
    @api.model
    def record(self, store, door, payload, liveness=None, when=None):
        """Create a reading from an inbound ``demographics`` payload.

        Returns an empty recordset when the payload carries nothing usable —
        a crossing with no readable face is normal (someone looking away) and
        must not become an error or a row full of nulls.
        """
        if not isinstance(payload, dict) or not store.demographics_enabled:
            return self.browse()
        band = payload.get("age_band") or band_for_age(payload.get("age"))
        gender = payload.get("gender")
        if gender not in ("female", "male", "unknown", None):
            gender = "unknown"
        emotion = payload.get("emotion")
        if emotion not in dict(self._fields["emotion"].selection):
            emotion = False
        if not band and not gender and not emotion:
            return self.browse()

        def score(key):
            try:
                return float(payload.get(key) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        return self.sudo().create({
            "store_id": store.id,
            "door_id": door.id if door else False,
            "captured_at": when or fields.Datetime.now(),
            "age_band": band or False,
            "age_confidence": score("age_confidence"),
            "gender": gender or "unknown",
            "gender_confidence": score("gender_confidence"),
            "emotion": emotion,
            "emotion_confidence": score("emotion_confidence"),
            "liveness_score": liveness or 0.0,
        })
