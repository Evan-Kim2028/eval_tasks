#!/bin/bash
set -eu
root="${1:-/tmp/cdc-repro}"
rm -rf "$root"
python3 /app/warehouse/runner.py --root "$root" \
  --events /app/warehouse/repro/old-events.json \
  --peer-events /app/warehouse/repro/peer-events.json
