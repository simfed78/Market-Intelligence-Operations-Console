from pathlib import Path

from app.dashboard import load_payload


def test_dashboard_loader_reads_payload():
    root = Path(__file__).resolve().parents[1]
    payload = load_payload(root, weekly=False)
    assert isinstance(payload, dict)
    if payload:
        assert "watchlist_table" in payload
