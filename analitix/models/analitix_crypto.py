# -*- coding: utf-8 -*-
"""Encryption at rest for face embeddings (see task 984, point 1).

A face embedding is not an image and cannot be turned back into one, but it is
still biometric-derived data: two embeddings can be compared to tell whether
they belong to the same person.  So it never sits in the database in the clear.

Design
------
* One symmetric key per Odoo database, generated on install and kept in
  ``ir.config_parameter`` under ``analitix.embedding_key``.  The parameter is
  readable only by ``base.group_system`` (enforced in ``data/analitix_params.xml``),
  so a plain Analitix user — or an SQL-injection-grade read of the analitix
  tables alone — gets ciphertext and nothing else.
* Fernet (AES-128-CBC + HMAC-SHA256) from ``cryptography``, which is a core
  Odoo requirement — this addon therefore declares **no** external dependency.
* Vectors are serialised compactly as ``float32`` little-endian bytes before
  encryption, so a 512-dim buffalo_l embedding costs 2 KB of ciphertext rather
  than the ~10 KB a JSON list of floats would take.

Honest limitation, worth stating rather than hiding: the key lives in the same
database it protects.  This defeats *stolen backup / stolen table dump* and
*low-privilege read*, which are the realistic threats here.  It does not defeat
an attacker who already owns the whole Odoo database **and** the system
parameters.  Deployments that need that level put the key in an external KMS
and override ``_embedding_key``.
"""
import base64
import logging
import struct

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, models

_logger = logging.getLogger(__name__)

KEY_PARAM = "analitix.embedding_key"


class AnalitixCrypto(models.AbstractModel):
    """Service model: ``self.env['analitix.crypto']``."""
    _name = "analitix.crypto"
    _description = "Analitix — Embedding Encryption Service"

    # ------------------------------------------------------------------
    # Key management
    # ------------------------------------------------------------------
    @api.model
    def _embedding_key(self):
        """Return the database's Fernet key, generating it on first use."""
        params = self.env["ir.config_parameter"].sudo()
        key = params.get_param(KEY_PARAM)
        if not key:
            key = Fernet.generate_key().decode()
            params.set_param(KEY_PARAM, key)
            _logger.info("Analitix: generated a new embedding encryption key.")
        return key.encode()

    @api.model
    def _fernet(self):
        return Fernet(self._embedding_key())

    # ------------------------------------------------------------------
    # Vector <-> encrypted text
    # ------------------------------------------------------------------
    @api.model
    def encrypt_vector(self, vector):
        """Serialise a list of floats and return the ciphertext as text.

        Returns ``False`` for an empty vector so the caller can store a plain
        falsy value in the field.
        """
        if not vector:
            return False
        raw = struct.pack("<%df" % len(vector), *(float(v) for v in vector))
        return self._fernet().encrypt(raw).decode()

    @api.model
    def decrypt_vector(self, token):
        """Return the list of floats behind ``token``, or ``[]`` if unreadable.

        An unreadable token means the key was rotated or the row was tampered
        with; we log it and degrade to "no signature" rather than raising,
        because a single corrupt row must never break a whole matching batch.
        """
        if not token:
            return []
        try:
            raw = self._fernet().decrypt(token.encode())
        except (InvalidToken, TypeError, ValueError):
            _logger.warning("Analitix: could not decrypt an embedding; ignoring it.")
            return []
        count = len(raw) // 4
        return list(struct.unpack("<%df" % count, raw[:count * 4]))

    # ------------------------------------------------------------------
    # Vector maths — deliberately dependency-free
    # ------------------------------------------------------------------
    @api.model
    def normalize(self, vector):
        """Return ``vector`` scaled to unit length (or unchanged if degenerate).

        Pre-normalising once at write time turns every later similarity check
        into a plain dot product, which is what makes pure-Python matching fast
        enough to skip numpy (not an Odoo core requirement, and the master
        instruction forbids pulling vision libraries into the addon).
        """
        norm = sum(v * v for v in vector) ** 0.5
        if not norm:
            return list(vector)
        return [v / norm for v in vector]

    @api.model
    def cosine(self, vec_a, vec_b):
        """Cosine similarity in ``[-1, 1]``; ``0.0`` when either side is empty.

        Assumes nothing about normalisation, so it stays correct if a caller
        hands it a raw vector.
        """
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = norm_a = norm_b = 0.0
        for a, b in zip(vec_a, vec_b):
            dot += a * b
            norm_a += a * a
            norm_b += b * b
        if not norm_a or not norm_b:
            return 0.0
        return dot / ((norm_a ** 0.5) * (norm_b ** 0.5))


def decode_embedding(payload):
    """Turn an inbound API embedding into a list of floats.

    The edge may send either a JSON array of numbers (readable, good for
    debugging) or base64-encoded little-endian float32 (compact, good for
    battery/bandwidth-constrained links).  Accepting both keeps third-party
    integrators from having to guess.  Returns ``[]`` on anything malformed —
    the caller decides whether that is fatal.
    """
    if not payload:
        return []
    if isinstance(payload, (list, tuple)):
        try:
            return [float(v) for v in payload]
        except (TypeError, ValueError):
            return []
    if isinstance(payload, str):
        try:
            raw = base64.b64decode(payload, validate=True)
        except (ValueError, TypeError):
            return []
        count = len(raw) // 4
        if not count:
            return []
        return list(struct.unpack("<%df" % count, raw[:count * 4]))
    return []
