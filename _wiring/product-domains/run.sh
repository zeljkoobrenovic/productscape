#!/bin/sh
set -eu
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/../../productscapes.py" build --project "${PRODUCTSCAPES_PROJECT:-$SCRIPT_DIR/../..}" --all "$@"
