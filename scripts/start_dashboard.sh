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
"$RESEARCH_PYTHON" -c 'import streamlit, pandas, plotly, dateutil' || {
  echo 'Dipendenze mancanti: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt'
  exit 1
}
exec "$RESEARCH_PYTHON" -m streamlit run "$ROOT/streamlit_app.py" --server.address 127.0.0.1 --server.port "${INTELLIGENCE_PORT:-8517}" --browser.gatherUsageStats false
