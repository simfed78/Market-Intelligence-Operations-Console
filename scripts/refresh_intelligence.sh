#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -n "${INTELLIGENCE_PYTHON:-}" ]]; then
  RESEARCH_PYTHON="$INTELLIGENCE_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  RESEARCH_PYTHON="$ROOT/.venv/bin/python"
elif [[ -f "$ROOT/.runtime-python" ]]; then
  IFS= read -r RESEARCH_PYTHON < "$ROOT/.runtime-python"
else
  RESEARCH_PYTHON="python3"
fi
cd "$ROOT"
exec "$RESEARCH_PYTHON" -m src.intelligence.refresh --root "$ROOT" "$@"
