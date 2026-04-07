from pathlib import Path

from app.dashboard_data import load_latest_baskets, load_payload, load_what_changed


def test_dashboard_data_loads_new_fields(tmp_path: Path) -> None:
    json_dir = tmp_path / "outputs" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "daily_payload.json").write_text(
        """
        {
          "timestamp": "2026-04-07T09:00:00-04:00",
          "change_log": {"ranking_transitions": "XLI improved"},
          "transition_table": [{"item": "XLI", "current_value": "early confirmation"}],
          "basket_tables": {"top_sector": [{"ticker": "XLI", "weight": 1.0}]}
        }
        """,
        encoding="utf-8",
    )

    payload = load_payload(tmp_path)
    changed = load_what_changed(tmp_path)
    baskets = load_latest_baskets(tmp_path)

    assert payload["change_log"]["ranking_transitions"] == "XLI improved"
    assert not changed["transitions"].empty
    assert "top_sector" in baskets
