"""Markdown report generator."""

from __future__ import annotations

import pandas as pd

from src.models.scoring import RunArtifacts


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown-like table without extra dependencies."""
    if frame.empty:
        return "_No data available._"
    cols = list(frame.columns)
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join(["---"] * len(cols)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in frame.astype(object).values.tolist()]
    return "\n".join([header, sep, *rows])


def build_markdown_report(artifacts: RunArtifacts) -> str:
    """Render a daily Markdown report."""
    macro = artifacts.agent_results["macro_regime"]
    liquidity = artifacts.agent_results["liquidity_rates_credit"]
    sentiment = artifacts.agent_results["sentiment_internals"]
    seasonality = artifacts.agent_results["seasonality"]
    technical = artifacts.agent_results["technical_structure"]
    event = artifacts.agent_results["macro_event"]
    earnings = artifacts.agent_results["earnings_revision"]
    internals = artifacts.agent_results["sector_internals"]
    options = artifacts.agent_results["options_proxy"]
    opportunity = artifacts.agent_results["early_opportunity"]
    alerting = artifacts.agent_results["alerting"]

    top_sectors = _markdown_table(artifacts.sector_table.head(5)[["ticker", "score", "classification"]])
    top_cyclicals = _markdown_table(artifacts.cyclical_table.head(5)[["ticker", "score", "classification"]])
    top_proxies = _markdown_table(artifacts.validation_table.head(5)[["proxy", "horizon", "proxy_quality_score", "stability_score"]]) if not artifacts.validation_table.empty else "_No proxy diagnostics._"
    unstable_proxies = _markdown_table(artifacts.unstable_proxies_table.head(5)[["proxy", "horizon", "stability_score", "structural_break_flag"]]) if not artifacts.unstable_proxies_table.empty else "_No unstable proxies._"
    event_map = _markdown_table(artifacts.macro_event_table.head(8))
    earnings_watch = _markdown_table(artifacts.earnings_watch_table.head(8))
    internals_highlights = _markdown_table(artifacts.sector_internals_table.head(5)[["sector", "sector_internal_breadth_score", "concentration_risk_score", "participation_score"]]) if not artifacts.sector_internals_table.empty else "_No internals available._"
    options_context = _markdown_table(artifacts.options_context_table.head(3))
    opportunity_table = _markdown_table(artifacts.opportunity_table.head(5)[["ticker", "early_opportunity_score", "opportunity_label"]]) if not artifacts.opportunity_table.empty else "_No opportunity ranking._"
    alerts_table = _markdown_table(artifacts.alerts_table.head(8)[["level", "category", "item", "message"]]) if not artifacts.alerts_table.empty else "_No alerts._"
    basket_name = next(iter(artifacts.basket_tables.keys()), "")
    basket_table = _markdown_table(artifacts.basket_tables.get(basket_name, pd.DataFrame()).head(5)) if basket_name else "_No baskets available._"
    transition_table = _markdown_table(artifacts.transition_table.head(8)) if not artifacts.transition_table.empty else "_No transitions detected._"
    exposure = artifacts.exposure_view or {}
    exposure_block = "\n".join(
        [
            f"- Stance: {exposure.get('exposure_stance_label', 'n/a')}",
            f"- Confidence: {exposure.get('confidence_tag', 'n/a')}",
            f"- Summary: {exposure.get('exposure_summary', 'n/a')}",
        ]
    )
    warnings = []
    if sentiment.scores.get("fragility_score", 50) > 60:
        warnings.append("Fragility score is elevated.")
    if liquidity.scores.get("credit_stress_score", 50) > 60:
        warnings.append("Credit stress remains above neutral.")
    if artifacts.fusion.risk_environment_flag == "risk_off":
        warnings.append("Fused risk flag is risk-off.")
    if artifacts.data_health and any(artifacts.data_health.stale_series_flags.values()):
        warnings.append("One or more input series appear stale.")
    warning_block = "\n".join([f"- {item}" for item in warnings]) if warnings else "- No major warnings."
    changes = artifacts.change_log or {}
    changes_block = "\n".join([f"- {key}: {value}" for key, value in changes.items()]) if changes else "- No prior run comparison available."

    return f"""# Daily Market Intelligence Report

**Timestamp:** {artifacts.timestamp}

## Macro Regime Summary
{macro.summary}

## Liquidity, Rates, and Credit
{liquidity.summary}

## Sentiment and Internals
{sentiment.summary}

## Seasonality Context
{seasonality.summary}

## Technical Structure
{technical.summary}

## Macro Event Map
{event.summary}
{event_map}

## Earnings Watch
{earnings.summary}
{earnings_watch}

## Sector Internals Highlights
{internals.summary}
{internals_highlights}

## Options / Gamma Context
{options.summary}
{options_context}

## Top Sectors
{top_sectors}

## Top Cyclical Opportunities
{top_cyclicals}

## Top Emerging Opportunities
{opportunity.summary}
{opportunity_table}

## Final Fused View
- SPX regime score: {artifacts.fusion.spx_regime_score:.1f}
- Sector opportunity score: {artifacts.fusion.sector_opportunity_score:.1f}
- Cyclical opportunity score: {artifacts.fusion.cyclical_opportunity_score:.1f}
- Risk environment: {artifacts.fusion.risk_environment_flag}
- Explanation: {artifacts.fusion.explanation}

## Regime-Based Exposure View
{exposure_block}

## Candidate Basket Snapshot
{basket_name or "latest"}
{basket_table}

## What Changed Since Previous Run
{changes_block}
{transition_table}

## Top 5 Active Proxies
{top_proxies}

## Top 5 Unstable Proxies
{unstable_proxies}

## Alert Summary
{alerting.summary}
{alerts_table}

## Warnings / Fragility Notes
{warning_block}
"""
