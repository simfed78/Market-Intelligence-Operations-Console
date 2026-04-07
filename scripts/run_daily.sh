#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

"$ROOT/.venv/bin/python" -m src.main --mode daily --project-root "$ROOT" >> "$LOG_DIR/daily.log" 2>&1
