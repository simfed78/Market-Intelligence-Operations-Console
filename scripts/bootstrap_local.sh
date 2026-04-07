#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r requirements.txt

mkdir -p logs data/db outputs/exports

if [[ ! -f ".env" ]]; then
  cp .env.example .env
fi

echo "Bootstrap complete."
