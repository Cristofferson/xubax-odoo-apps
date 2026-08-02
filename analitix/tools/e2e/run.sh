#!/bin/bash
# Run the whole end-to-end suite against a live Odoo.
#
#   tools/e2e/run.sh [database]
#
# Three suites, in the order of what they prove:
#
#   api      the documented HTTP contract, over a real socket
#   agent    the REAL edge agent as a subprocess, including an outage
#   browser  the product driven the way a person drives it
#
# None of this is part of the in-process test suite, and none of it ships in the
# published package. It exists because the in-process suite has a blind spot it
# cannot see past: its tests run as a user far more privileged than a customer's,
# in the same process as the server, without a browser. The first browser run
# found an Access Error on the main configuration screen for the role it was
# built for, and an emergency control that a half-finished configuration could
# block. Neither was visible to 263 passing tests.
set -o pipefail

ADDON="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB="${1:-${E2E_DB:-freshanalitix}}"
URL="${E2E_URL:-http://127.0.0.1:8171}"
WORK="${E2E_WORK:-/tmp/e2e}"
ODOO="${ODOO_HOME:-/odoo/odoo-server}"
CONF="${ODOO_CONF:-/etc/odoo-server.conf}"
PY="${E2E_PYTHON:-python3}"                 # needs: requests
PW_PY="${E2E_PW_PYTHON:-$PY}"               # needs: playwright + chromium

mkdir -p "$WORK"
STATE="$WORK/state.json"

echo "== preparing $DB =="
sudo -u odoo "$ODOO/env/bin/python3" "$ODOO/odoo-bin" shell \
     -c "$CONF" -d "$DB" --no-http < "$ADDON/tools/e2e/prepare.py" 2>/dev/null \
  | sed -n '/E2E_JSON_START/,/E2E_JSON_END/p' \
  | sed '1d;$d' > "$STATE"

if ! "$PY" -c "import json,sys; json.load(open('$STATE'))" 2>/dev/null; then
    echo "PREPARE FAILED — is the database '$DB' there and is analitix installed?" >&2
    exit 2
fi
echo "   store, keys and roles ready"

if ! curl -sf -o /dev/null "$URL/web/login"; then
    echo "No Odoo answering at $URL. Start one first." >&2
    exit 2
fi

export E2E_STATE="$STATE" E2E_DB="$DB" E2E_URL="$URL"
rc=0

echo
"$PY" "$ADDON/tools/e2e/test_api_e2e.py"      || rc=1
echo
"$PY" "$ADDON/tools/e2e/test_agent_e2e.py"    || rc=1
echo
"$PW_PY" "$ADDON/tools/e2e/test_browser_e2e.py" || rc=1

echo
if [ $rc -eq 0 ]; then
    echo "E2E: everything passed."
else
    echo "E2E: something failed — see above." >&2
fi
exit $rc
