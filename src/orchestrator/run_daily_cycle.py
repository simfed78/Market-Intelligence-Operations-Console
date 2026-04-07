"""Daily cycle orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.agents.alerting_agent import AlertingAgent
from src.agents.candidate_basket_agent import CandidateBasketAgent
from src.agents.cross_asset_leadlag_agent import CrossAssetLeadLagAgent
from src.agents.early_opportunity_agent import EarlyOpportunityAgent
from src.agents.earnings_revision_agent import EarningsRevisionAgent
from src.agents.liquidity_rates_credit_agent import LiquidityRatesCreditAgent
from src.agents.macro_event_agent import MacroEventAgent
from src.agents.macro_regime_agent import MacroRegimeAgent
from src.agents.options_proxy_agent import OptionsProxyAgent
from src.agents.seasonality_agent import SeasonalityAgent
from src.agents.sector_internals_agent import SectorInternalsAgent
from src.agents.sector_rotation_agent import SectorRotationAgent
from src.agents.sentiment_internals_agent import SentimentInternalsAgent
from src.agents.signal_fusion_agent import SignalFusionAgent
from src.agents.technical_structure_agent import TechnicalStructureAgent
from src.data.cache_manager import CacheManager
from src.data.calendar_data import CalendarDataLoader
from src.data.data_quality import DataQualityChecker
from src.data.earnings_calendar import EarningsCalendarLoader
from src.data.loaders import ConfigBundle
from src.data.macro_data import MacroDataFetcher
from src.data.macro_event_calendar import MacroEventCalendarLoader
from src.data.market_data import MarketDataFetcher
from src.data.options_proxy_loader import OptionsProxyLoader
from src.data.snapshots import SnapshotStore
from src.models.exposure_model import build_exposure_view
from src.models.portfolio_research import basket_performance
from src.models.proxy_diagnostics import build_regime_masks, evaluate_proxy
from src.models.scoring import RunArtifacts
from src.reports.change_log_report import build_change_summary
from src.reports.exporters import export_latest_outputs
from src.reports.json_payload import build_json_payload
from src.reports.markdown_report import build_markdown_report
from src.reports.ranking_tables import write_csv_table
from src.reports.watchlist_report import build_watchlist_markdown
from src.storage.run_history import RunHistoryStore
from src.storage.signal_store import persist_artifacts
from src.utils.dates import now_in_tz
from src.utils.helpers import ensure_dir, write_json


@dataclass
class DailyCycleRunner:
    """Run the full daily research cycle."""

    config: ConfigBundle
    project_root: Path

    def run(self, run_type: str = "daily", persist: bool = True) -> RunArtifacts:
        """Run a complete cycle and optionally persist outputs."""
        settings = self.config.settings
        validation_cfg = self.config.validation
        period = settings["run"]["default_market_period"]
        lead_lag_max_lag = settings["run"]["lead_lag_max_lag"]
        timezone_name = settings["project"]["timezone"]
        timestamp = now_in_tz(timezone_name).isoformat()

        cache_dir = ensure_dir(self.project_root / "data" / "cache")
        snapshots_dir = ensure_dir(self.project_root / "data" / "processed" / "snapshots")
        cache = CacheManager(cache_dir=cache_dir, ttl_hours=settings["run"]["cache_ttl_hours"])
        market_fetcher = MarketDataFetcher(cache=cache, raw_dir=self.project_root / "data" / "raw", use_sample_on_failure=settings["run"]["use_sample_data_on_failure"])
        macro_fetcher = MacroDataFetcher(cache=cache, raw_dir=self.project_root / "data" / "raw", use_sample_on_failure=settings["run"]["use_sample_data_on_failure"])
        calendar_loader = CalendarDataLoader(raw_dir=self.project_root / "data" / "raw")
        macro_event_loader = MacroEventCalendarLoader(raw_dir=self.project_root / "data" / "raw", config=self.config.macro_events)
        earnings_loader = EarningsCalendarLoader(raw_dir=self.project_root / "data" / "raw", config=self.config.earnings_map)
        options_loader = OptionsProxyLoader(raw_dir=self.project_root / "data" / "raw", config=self.config.options_proxy)
        snapshot_store = SnapshotStore(snapshot_dir=snapshots_dir)

        sector_tickers = self._build_sector_universe()
        extended_tickers = self._build_extended_universe(sector_tickers)
        prices = market_fetcher.fetch_prices(extended_tickers, period=period, interval=settings["run"]["frequency"])
        volumes = market_fetcher.fetch_volumes(extended_tickers, period=period, interval=settings["run"]["frequency"])
        sector_prices = prices[[ticker for ticker in sector_tickers if ticker in prices.columns]].copy()
        sector_volumes = volumes[[ticker for ticker in sector_tickers if ticker in volumes.columns]].copy() if not volumes.empty else pd.DataFrame(index=sector_prices.index, columns=sector_prices.columns)

        macro_frames = []
        for _, series_map in self.config.fred_series.items():
            frame = macro_fetcher.fetch_series_map(series_map)
            if not frame.empty:
                macro_frames.append(frame)
        macro_frame = pd.concat(macro_frames, axis=1).sort_index() if macro_frames else pd.DataFrame()
        calendar_frame = calendar_loader.load(self.project_root / settings["files"]["event_calendar_csv"])
        macro_event_frame = macro_event_loader.load()
        earnings_calendar = earnings_loader.load_calendar()
        revision_proxy = earnings_loader.load_revision_proxy()
        manual_options = options_loader.load_manual()

        manual_sentiment_path = self.project_root / settings["files"]["manual_sentiment_csv"]
        manual_sentiment = pd.read_csv(manual_sentiment_path, parse_dates=["date"]).set_index("date") if manual_sentiment_path.exists() else pd.DataFrame()

        data_health = DataQualityChecker().evaluate(
            frames={
                "prices": sector_prices,
                "macro": macro_frame,
                "manual_sentiment": manual_sentiment,
                "calendar": calendar_frame,
                "macro_events": macro_event_frame,
                "earnings_calendar": earnings_calendar,
                "options_manual": manual_options,
            },
            fallback_usage_flags={"market_data": market_fetcher.used_fallback, "macro_data": macro_fetcher.used_fallback},
        )

        benchmark = settings["project"]["benchmark"]
        benchmark_series = sector_prices[benchmark] if benchmark in sector_prices.columns else pd.Series(dtype=float, name=benchmark)

        macro_result = MacroRegimeAgent().run(macro_frame)
        liquidity_result = LiquidityRatesCreditAgent().run(macro_frame, sector_prices)
        cross_asset_result = CrossAssetLeadLagAgent(windows=settings["run"]["correlation_windows"], max_lag=lead_lag_max_lag).run(sector_prices, benchmark=benchmark)
        sentiment_result = SentimentInternalsAgent().run(sector_prices, manual_sentiment=manual_sentiment)
        seasonality_result = SeasonalityAgent().run(benchmark_series, calendar_frame=calendar_frame)
        technical_result = TechnicalStructureAgent(weights=self.config.weights.get("technical_structure", {})).run(sector_prices, volumes=sector_volumes, benchmark=benchmark)
        event_result = MacroEventAgent(config=self.config.macro_events).run(macro_event_frame, sector_prices, benchmark=benchmark)
        earnings_result = EarningsRevisionAgent(earnings_map=self.config.earnings_map).run(sector_prices, sector_volumes, earnings_calendar, revision_proxy=revision_proxy)
        sector_internals_result = SectorInternalsAgent(config=self.config.sector_constituents).run(prices, sector_prices)
        options_result = OptionsProxyAgent(config=self.config.options_proxy).run(sector_prices, manual_options=manual_options)

        validation_table = self._build_validation_table(sector_prices, benchmark_series, macro_result, liquidity_result)
        sector_result = SectorRotationAgent(
            sector_map=self.config.sector_map,
            ranking_weights=self.config.weights.get("sector_ranking", {}),
        ).run(
            sector_prices,
            macro_result,
            liquidity_result,
            sentiment_result,
            seasonality_result,
            cross_asset_result,
            technical_result,
            validation_table=validation_table,
            benchmark=benchmark,
        )
        early_opportunity_result = EarlyOpportunityAgent(weights=self.config.opportunity_weights).run(
            sector_result.details.get("sector_rank_table", pd.DataFrame()),
            sector_result.details.get("cyclical_opportunity_table", pd.DataFrame()),
            technical_result,
            sector_internals_result,
            macro_result,
            liquidity_result,
            event_result,
            options_result,
            earnings_result,
            sentiment_result,
            validation_table,
        )
        alert_result = AlertingAgent(config=self.config.alerts).run(
            validation_table,
            validation_table[(validation_table["decay_flag"]) | (validation_table["structural_break_flag"])] if not validation_table.empty else pd.DataFrame(),
            early_opportunity_result.details.get("sector_opportunity_table", pd.DataFrame()),
            event_result,
            options_result,
            sector_result,
        )

        agent_results = {
            "macro_regime": macro_result,
            "liquidity_rates_credit": liquidity_result,
            "cross_asset_leadlag": cross_asset_result,
            "sentiment_internals": sentiment_result,
            "seasonality": seasonality_result,
            "technical_structure": technical_result,
            "macro_event": event_result,
            "earnings_revision": earnings_result,
            "sector_internals": sector_internals_result,
            "options_proxy": options_result,
            "early_opportunity": early_opportunity_result,
            "alerting": alert_result,
            "sector_rotation": sector_result,
        }
        fusion = SignalFusionAgent(weights=self.config.weights.get("fusion", settings["scoring"]["fusion_weights"])).run(agent_results)

        sector_table = sector_result.details.get("sector_rank_table", pd.DataFrame())
        cyclical_table = sector_result.details.get("cyclical_opportunity_table", pd.DataFrame())
        risk_rotation_table = sector_result.details.get("risk_rotation_table", pd.DataFrame())
        drivers_table = cross_asset_result.details.get("active_drivers_table", pd.DataFrame())
        seasonality_table = seasonality_result.details.get("seasonality_table", pd.DataFrame())
        unstable_proxies_table = validation_table[(validation_table["decay_flag"]) | (validation_table["structural_break_flag"])].sort_values(
            ["proxy_quality_score", "stability_score"], ascending=[True, True]
        ) if not validation_table.empty else pd.DataFrame()
        opportunity_table = early_opportunity_result.details.get("sector_opportunity_table", pd.DataFrame())
        watchlist_table = alert_result.details.get("watchlist_table", pd.DataFrame())
        alerts_table = alert_result.details.get("alerts_table", pd.DataFrame())
        macro_event_table = event_result.details.get("upcoming_events", pd.DataFrame())
        earnings_watch_table = earnings_result.details.get("earnings_calendar_watchlist", pd.DataFrame())
        sector_internals_table = sector_internals_result.details.get("sector_internals_table", pd.DataFrame())
        options_context_table = options_result.details.get("options_context_table", pd.DataFrame())
        previous_opportunities = self._read_table_snapshot("opportunity_ranking.csv")
        previous_validation = self._read_table_snapshot("proxy_validation.csv")
        change_log, transition_table = build_change_summary(previous_opportunities, opportunity_table, previous_validation, validation_table)
        basket_result = CandidateBasketAgent(config=self.config.baskets).run(sector_table, cyclical_table, opportunity_table)
        basket_tables = basket_result.details.get("baskets", {})
        exposure_view = build_exposure_view(
            self.config.exposure_rules,
            fusion,
            macro_result,
            liquidity_result,
            sentiment_result,
            options_result,
            event_result,
        )
        portfolio_summary = self._build_portfolio_summary(sector_prices, basket_tables)
        run_history_table = self._load_run_history(limit=30)

        artifacts = RunArtifacts(
            timestamp=timestamp,
            agent_results=agent_results,
            fusion=fusion,
            sector_table=sector_table,
            cyclical_table=cyclical_table,
            risk_rotation_table=risk_rotation_table,
            drivers_table=drivers_table,
            seasonality_table=seasonality_table,
            validation_table=validation_table,
            unstable_proxies_table=unstable_proxies_table,
            opportunity_table=opportunity_table,
            watchlist_table=watchlist_table,
            alerts_table=alerts_table,
            macro_event_table=macro_event_table,
            earnings_watch_table=earnings_watch_table,
            sector_internals_table=sector_internals_table,
            options_context_table=options_context_table,
            basket_tables=basket_tables,
            exposure_view={
                "exposure_stance_label": exposure_view.exposure_stance_label,
                "exposure_summary": exposure_view.exposure_summary,
                "supporting_components": exposure_view.supporting_components,
                "confidence_tag": exposure_view.confidence_tag,
            },
            portfolio_summary=portfolio_summary,
            transition_table=transition_table,
            run_history_table=run_history_table,
            data_health=data_health,
            run_type=run_type,
            change_log=change_log,
        )

        if persist:
            self._persist_outputs(artifacts)
            snapshot_store.save_frame("prices", sector_prices, timestamp)
            snapshot_store.save_frame("macro", macro_frame, timestamp)
        return artifacts

    def _build_sector_universe(self) -> list[str]:
        tickers: list[str] = []
        for key, group in self.config.tickers.items():
            if key != "manual_series":
                tickers.extend(group if isinstance(group, list) else [])
        return list(dict.fromkeys(tickers))

    def _build_extended_universe(self, sector_tickers: list[str]) -> list[str]:
        tickers = list(sector_tickers)
        for members in self.config.sector_constituents.get("sector_constituents", {}).values():
            tickers.extend(members)
        for meta in self.config.earnings_map.get("sectors", {}).values():
            tickers.extend(meta.get("key_names", []))
        public_opts = self.config.options_proxy.get("public_proxies", {})
        for symbol in [public_opts.get("vix_symbol"), public_opts.get("vvix_symbol")]:
            if symbol:
                tickers.append(symbol)
        return list(dict.fromkeys(tickers))

    def _build_validation_table(self, prices: pd.DataFrame, benchmark_series: pd.Series, macro_result, liquidity_result) -> pd.DataFrame:
        """Evaluate registry proxies against benchmark."""
        proxy_rows = []
        validation_cfg = self.config.validation
        horizons = validation_cfg["targets"]["spy_forward_returns"]
        benchmark_returns = benchmark_series.pct_change()
        vol_regime = benchmark_returns.rolling(20).std() > validation_cfg["regimes"]["volatility"]["high_vol_threshold"]
        regime_masks = build_regime_masks(
            benchmark_series.index,
            macro_result.scores,
            liquidity_result.scores,
            volatility_regime=vol_regime,
            benchmark_returns=benchmark_returns,
        )
        for proxy_meta in self.config.proxy_registry.get("proxies", []):
            ticker = proxy_meta["ticker"]
            if ticker not in prices.columns:
                continue
            for horizon in horizons:
                result = evaluate_proxy(
                    proxy_name=ticker,
                    proxy_series=prices[ticker],
                    target_series=benchmark_series.rename("SPY"),
                    horizon=horizon,
                    regime_masks=regime_masks,
                    rolling_window=max(validation_cfg["windows"]["rolling"]),
                    train_window=validation_cfg["windows"]["walk_forward_train"],
                    test_window=validation_cfg["windows"]["walk_forward_test"],
                    bootstrap_samples=validation_cfg["windows"]["bootstrap_samples"],
                )
                proxy_rows.append(
                    {
                        "proxy": result.proxy,
                        "target": result.target,
                        "horizon": result.horizon,
                        "proxy_quality_score": result.proxy_quality_score,
                        "stability_score": result.stability_score,
                        "predictive_usefulness_score": result.predictive_usefulness_score,
                        "decay_flag": result.decay_flag,
                        "recommended_usage_context": result.recommended_usage_context,
                        "structural_break_flag": result.structural_break_flag,
                        "recent_break_dates": ",".join(result.recent_break_dates),
                        "stability_warning": result.stability_warning,
                    }
                )
        return pd.DataFrame(proxy_rows).sort_values(["proxy_quality_score", "stability_score"], ascending=False).reset_index(drop=True) if proxy_rows else pd.DataFrame()

    def _read_table_snapshot(self, filename: str) -> pd.DataFrame:
        """Load a prior output table when it exists."""
        path = self.project_root / "outputs" / "tables" / filename
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _load_run_history(self, limit: int = 30) -> pd.DataFrame:
        """Load stored run history if available."""
        rows = RunHistoryStore(self.project_root).runs.run_history(limit=limit)
        return pd.DataFrame([dict(row) for row in rows]) if rows else pd.DataFrame()

    def _build_portfolio_summary(self, prices: pd.DataFrame, basket_tables: dict[str, pd.DataFrame]) -> dict[str, dict[str, float]]:
        """Create a lightweight research summary for each current basket."""
        friction = self.config.portfolio_research.get("backtest", {}).get("friction_bps", 10.0)
        benchmark = self.config.portfolio_research.get("backtest", {}).get("benchmark", self.config.settings["project"]["benchmark"])
        summary: dict[str, dict[str, float]] = {}
        for name, basket in basket_tables.items():
            summary[name] = basket_performance(prices, basket, benchmark=benchmark, friction_bps=friction)
        return summary

    def _persist_outputs(self, artifacts: RunArtifacts) -> None:
        """Persist daily outputs."""
        reports_dir = ensure_dir(self.project_root / "outputs" / "reports")
        tables_dir = ensure_dir(self.project_root / "outputs" / "tables")
        json_dir = ensure_dir(self.project_root / "outputs" / "json")
        html_dir = ensure_dir(self.project_root / "outputs" / "html")

        markdown_report = build_markdown_report(artifacts)
        (reports_dir / "daily_report.md").write_text(markdown_report, encoding="utf-8")
        (reports_dir / "watchlist.md").write_text(build_watchlist_markdown(artifacts.alerts_table, artifacts.watchlist_table), encoding="utf-8")
        write_json(json_dir / "alerts.json", {"alerts": artifacts.alerts_table.to_dict(orient="records"), "watchlist": artifacts.watchlist_table.to_dict(orient="records")})
        write_csv_table(artifacts.sector_table, tables_dir / "sector_ranking.csv")
        write_csv_table(artifacts.cyclical_table, tables_dir / "cyclical_ranking.csv")
        write_csv_table(artifacts.risk_rotation_table, tables_dir / "risk_rotation.csv")
        write_csv_table(artifacts.drivers_table, tables_dir / "active_drivers.csv")
        write_csv_table(artifacts.seasonality_table, tables_dir / "seasonality_table.csv")
        write_csv_table(artifacts.validation_table, tables_dir / "proxy_validation.csv")
        write_csv_table(artifacts.unstable_proxies_table, tables_dir / "unstable_proxies.csv")
        write_csv_table(artifacts.opportunity_table, tables_dir / "opportunity_ranking.csv")
        write_csv_table(artifacts.watchlist_table, tables_dir / "watchlist.csv")
        write_csv_table(artifacts.alerts_table, tables_dir / "alerts.csv")
        write_csv_table(artifacts.macro_event_table, tables_dir / "macro_event_map.csv")
        write_csv_table(artifacts.earnings_watch_table, tables_dir / "earnings_watchlist.csv")
        write_csv_table(artifacts.sector_internals_table, tables_dir / "sector_internals.csv")
        write_csv_table(artifacts.options_context_table, tables_dir / "options_context.csv")
        write_csv_table(artifacts.transition_table, tables_dir / "rank_transitions.csv")
        write_csv_table(artifacts.run_history_table, tables_dir / "run_history.csv")
        for name, basket in artifacts.basket_tables.items():
            write_csv_table(basket, tables_dir / f"{name}_basket.csv")
        (html_dir / "daily_report.html").write_text(f"<html><body><pre>{markdown_report}</pre></body></html>", encoding="utf-8")
        payload_name = "weekly_payload.json" if artifacts.run_type == "weekly" else "daily_payload.json"
        payload_path = json_dir / payload_name
        write_json(payload_path, build_json_payload(artifacts))
        persist_artifacts(self.project_root, artifacts, str(payload_path), baskets=artifacts.basket_tables, transitions=artifacts.transition_table)
        export_latest_outputs(self.project_root, artifacts, artifacts.basket_tables, exposure_view=artifacts.exposure_view)
