#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python scripts/live_flow_test.py "$@"
