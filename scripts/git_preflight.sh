#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Checking git status..."
git status --short

echo
echo "Running tests..."
"$ROOT/.venv/bin/python" -m pytest

echo
echo "Preflight complete."
