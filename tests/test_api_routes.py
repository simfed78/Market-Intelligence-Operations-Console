from pathlib import Path

from fastapi.testclient import TestClient

from app_api.main import create_app


def test_api_routes_read_latest_payload(tmp_path: Path) -> None:
    json_dir = tmp_path / "outputs" / "json"
    json_dir.mkdir(parents=True, exist_ok=True)
    (json_dir / "daily_payload.json").write_text(
        """
        {
          "timestamp": "2026-04-07T09:00:00-04:00",
          "risk_environment_flag": "neutral",
          "scores": {"spx_regime_score": 55.0, "sector_opportunity_score": 60.0, "cyclical_opportunity_score": 58.0},
          "top_ranked_sectors": [{"ticker": "XLI", "score": 61.0}],
          "top_ranked_cyclicals": [{"ticker": "KRE", "score": 59.0}],
          "alerts_table": [{"level": "watch", "category": "sector", "item": "XLI", "message": "improving"}],
          "basket_tables": {"top_sector": [{"ticker": "XLI", "weight": 1.0}]},
          "exposure_view": {"exposure_stance_label": "neutral"}
        }
        """,
        encoding="utf-8",
    )

    client = TestClient(create_app(tmp_path))

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/latest/regime").json()["risk_environment_flag"] == "neutral"
    assert client.get("/latest/rankings/sectors").json()["rows"][0]["ticker"] == "XLI"
    assert client.get("/latest/baskets").json()["rows"][0]["basket_name"] == "top_sector"
