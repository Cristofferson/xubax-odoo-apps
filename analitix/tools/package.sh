#!/bin/bash
# Build the distributable archive for apps.odoo.com, and prove what is not in it.
#
# Two things must never reach the published package:
#
#   edge/   the reference camera agent. It is a separate product with its own
#           installer and its own dependencies (opencv, ultralytics). Shipping
#           it inside the addon would suggest Odoo runs the vision, which it
#           does not, and would drag a licence question into the listing.
#
#   tools/  this script and the translation generator. Build machinery is not
#           part of what a customer installs.
#
# The checks below are assertions, not comments: the script exits non-zero if
# any of them fails, so a packaging mistake cannot quietly ship.
#
#   usage:  tools/package.sh [output-dir]

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$(basename "$HERE")"
OUT="${1:-/tmp}"
VERSION="$(python3 - "$HERE/__manifest__.py" <<'PY'
import ast, sys
print(ast.literal_eval(open(sys.argv[1]).read())["version"])
PY
)"
ZIP="$OUT/${NAME}-${VERSION}.zip"

rm -f "$ZIP"
cd "$(dirname "$HERE")"

zip -qr "$ZIP" "$NAME" \
    -x "$NAME/edge/*" \
    -x "$NAME/tools/*" \
    -x "$NAME/.git/*" \
    -x "*/__pycache__/*" \
    -x "*.pyc" \
    -x "*.pyo" \
    -x "*/.DS_Store"

fail() { echo "PACKAGING ERROR: $1" >&2; exit 1; }

# List once into a variable rather than piping `unzip` into each check:
# `grep -q` exits the moment it matches, unzip takes a SIGPIPE for it, and with
# `pipefail` that reads as a failed pipeline even when the check passed.
LISTING="$(unzip -Z1 "$ZIP")"

# --- what must not be there ------------------------------------------------
if grep -q "^$NAME/edge/"  <<<"$LISTING"; then fail "the edge agent is in the archive"; fi
if grep -q "^$NAME/tools/" <<<"$LISTING"; then fail "build tooling is in the archive"; fi
if grep -q "__pycache__"   <<<"$LISTING"; then fail "compiled Python is in the archive"; fi

# --- what must be there ----------------------------------------------------
for required in \
    "$NAME/__manifest__.py" \
    "$NAME/static/description/index.html" \
    "$NAME/static/description/icon.png" \
    "$NAME/static/description/banner.png" \
    "$NAME/static/manual/user_es.html" \
    "$NAME/static/manual/user_en.html" \
    "$NAME/static/manual/implementer_es.html" \
    "$NAME/static/manual/implementer_en.html" \
    "$NAME/i18n/analitix.pot" \
    "$NAME/i18n/es.po" \
    "$NAME/i18n/es_MX.po" \
    "$NAME/CHANGELOG.md" \
    "$NAME/doc/API.md"
do
    grep -qx "$required" <<<"$LISTING" || fail "missing from the archive: $required"
done

# --- the addon must not claim a vision dependency --------------------------
# The whole architecture rests on Odoo receiving JSON and nothing else. An
# external_dependencies entry naming torch or insightface would make the module
# uninstallable on a plain Odoo server AND would be a lie about where the work
# happens.
python3 - "$HERE/__manifest__.py" <<'PY' || exit 1
import ast, sys
manifest = ast.literal_eval(open(sys.argv[1]).read())
deps = manifest.get("external_dependencies") or {}
banned = {"torch", "insightface", "opencv-python", "cv2", "ultralytics",
          "onnxruntime", "numpy", "tensorflow"}
found = {name for names in deps.values() for name in names} & banned
if found:
    print("PACKAGING ERROR: vision dependency declared: %s" % ", ".join(sorted(found)),
          file=sys.stderr)
    sys.exit(1)
print("manifest declares no vision dependency")
PY

echo "OK  $ZIP"
wc -l <<<"$LISTING" | xargs echo "    files:"
du -h "$ZIP" | cut -f1 | xargs echo "    size:"
