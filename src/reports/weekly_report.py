"""Weekly report generator."""

from __future__ import annotations

from src.models.scoring import RunArtifacts


def build_weekly_markdown_report(artifacts: RunArtifacts) -> str:
    """Render a weekly diagnostics report."""
    validation = artifacts.validation_table.head(10)[["proxy", "target", "horizon", "proxy_quality_score", "stability_score", "predictive_usefulness_score"]]
    unstable = artifacts.unstable_proxies_table.head(10)[["proxy", "target", "horizon", "stability_score", "structural_break_flag", "recent_break_dates"]]
    val_md = validation.to_markdown(index=False) if not validation.empty else "_No validation rows._"
    unstable_md = unstable.to_markdown(index=False) if not unstable.empty else "_No unstable proxies._"
    return f"""# Weekly Validation Summary

**Timestamp:** {artifacts.timestamp}

## Macro Regime Recap
{artifacts.agent_results["macro_regime"].summary}

## Regime Change Watch
- Risk environment flag: {artifacts.fusion.risk_environment_flag}
- Technical backdrop: {artifacts.agent_results["technical_structure"].summary}
- Event context: {artifacts.agent_results["macro_event"].summary}
- Earnings tone: {artifacts.agent_results["earnings_revision"].summary}
- Options context: {artifacts.agent_results["options_proxy"].summary}
- Data quality warnings: {sum(artifacts.data_health.stale_series_flags.values()) if artifacts.data_health else 0}

## Best Proxies By Current Ranking
{val_md}

## Structural Break And Decay Watch
{unstable_md}

## Sector Rotation Map
Top sectors: {", ".join(artifacts.sector_table.head(5)["ticker"].tolist())}

## Cyclical Opportunity Map
Top cyclicals: {", ".join(artifacts.cyclical_table.head(5)["ticker"].tolist())}

## Broadening Vs Narrowing Leadership
Top internal breadth sectors: {", ".join(artifacts.sector_internals_table.head(5)["sector"].astype(str).tolist()) if not artifacts.sector_internals_table.empty else "n/a"}

## Tactical Opportunity Map
Top opportunities: {", ".join(artifacts.opportunity_table.head(5)["ticker"].astype(str).tolist()) if not artifacts.opportunity_table.empty else "n/a"}

## Validation Appendix
- Validation rows: {len(artifacts.validation_table)}
- Unstable proxies: {len(artifacts.unstable_proxies_table)}
"""
