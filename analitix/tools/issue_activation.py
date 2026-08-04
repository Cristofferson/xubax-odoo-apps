# -*- coding: utf-8 -*-
"""Issue an activation code for one shop. XUBAX side only.

    python3 issue_activation.py "<database-uuid>:<STORE-CODE>"

The argument is the *activation request* line the customer reads off the store
form and sends over. Paste the output back to them.

The signing key lives at ``/home/ubuntu/.secrets/analitix_activation.key`` and
is deliberately not in this repository — only the public half ships, inside
``models/analitix_activation.py``. ``tools/`` is excluded from the published
package by ``package.sh``, so this file never reaches a customer either.

Before signing, satisfy yourself that the shop is actually contracted. This
script is the last step of a commercial decision, not the decision.
"""
import base64
import os
import re
import sys

from cryptography.hazmat.primitives.asymmetric import ed25519

KEY_PATH = os.environ.get(
    "ANALITIX_ACTIVATION_KEY", "/home/ubuntu/.secrets/analitix_activation.key")

#: uuid:CODE — the shape the store form produces. Anything else is a typo or a
#: line that lost half of itself in a chat window, and signing it would mint a
#: code that silently never works.
REQUEST_RE = re.compile(r"^[0-9a-f-]{8,}:[^\s:]{1,32}$")


def load_key():
    with open(KEY_PATH, "rb") as fh:
        raw = base64.b64decode(fh.read())
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def issue(request):
    request = request.strip()
    if not REQUEST_RE.match(request):
        raise SystemExit(
            "That does not look like an activation request.\n"
            "Expected  <database-uuid>:<STORE-CODE>\n"
            "Got       %r" % request)
    signature = load_key().sign(request.encode())
    return base64.b64encode(signature).decode()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(issue(sys.argv[1]))
