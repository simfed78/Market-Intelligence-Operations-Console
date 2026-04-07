"""Main entrypoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.data.loaders import load_config_bundle
from src.orchestrator.run_daily_cycle import DailyCycleRunner
from src.orchestrator.run_weekly_cycle import WeeklyCycleRunner
from src.utils.logger import get_logger


LOGGER = get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Run the market intelligence engine.")
    parser.add_argument("--mode", choices=["daily", "weekly", "sample"], default="daily")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    return parser


def main() -> None:
    """CLI entrypoint."""
    args = build_parser().parse_args()
    project_root = Path(args.project_root)
    config = load_config_bundle(project_root / "config")
    if args.mode == "weekly":
        artifacts = WeeklyCycleRunner(config=config, project_root=project_root).run()
    else:
        artifacts = DailyCycleRunner(config=config, project_root=project_root).run(run_type=args.mode)
    LOGGER.info("Run complete. SPX regime score %.1f, risk flag %s", artifacts.fusion.spx_regime_score, artifacts.fusion.risk_environment_flag)


if __name__ == "__main__":
    main()
