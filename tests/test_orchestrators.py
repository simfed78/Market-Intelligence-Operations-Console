from pathlib import Path

from src.data.loaders import load_config_bundle
from src.orchestrator.run_daily_cycle import DailyCycleRunner
from src.orchestrator.run_weekly_cycle import WeeklyCycleRunner


def test_daily_and_weekly_runners():
    root = Path(__file__).resolve().parents[1]
    config = load_config_bundle(root / "config")
    daily = DailyCycleRunner(config=config, project_root=root).run(run_type="daily", persist=False)
    weekly = WeeklyCycleRunner(config=config, project_root=root).run()
    assert daily.run_type == "daily"
    assert weekly.run_type == "weekly"
    assert "technical_structure" in daily.agent_results
