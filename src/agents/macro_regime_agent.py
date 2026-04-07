"""Macro regime agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.macro_features import composite_direction, momentum_change, yoy_change
from src.models.regime_rules import classify_macro_regime
from src.models.scoring import AgentResult
from src.utils.helpers import clamp, scale_centered


@dataclass
class MacroRegimeAgent:
    """Classify the market environment using macro proxies."""

    def run(self, macro_frame: pd.DataFrame) -> AgentResult:
        """Generate macro regime output."""
        if macro_frame.empty:
            return AgentResult(
                name="macro_regime",
                scores={"growth_score": 50.0, "inflation_score": 50.0, "policy_score": 50.0},
                summary="Macro data missing, using neutral fallback.",
                details={"regime_label": "mixed_transition"},
            )

        growth_cols = [col for col in macro_frame.columns if col in {"claims", "unemployment_rate", "payrolls", "industrial_production", "retail_sales", "pmi_proxy"}]
        inflation_cols = [col for col in macro_frame.columns if col in {"cpi", "core_cpi", "ppi", "breakeven_5y"}]
        policy_cols = [col for col in macro_frame.columns if col in {"fed_funds", "reserves", "fed_balance_sheet", "nfci"}]

        growth_direction = composite_direction(macro_frame[growth_cols]) if growth_cols else pd.Series(dtype=float)
        inflation_yoy = yoy_change(macro_frame[inflation_cols]).mean(axis=1) if inflation_cols else pd.Series(dtype=float)
        policy_momentum = momentum_change(macro_frame[policy_cols]).mean(axis=1) if policy_cols else pd.Series(dtype=float)

        growth_score = scale_centered(float(growth_direction.dropna().iloc[-1]) if not growth_direction.dropna().empty else 0.0, scale=0.5)
        inflation_score = scale_centered(float(inflation_yoy.dropna().iloc[-1]) if not inflation_yoy.dropna().empty else 0.0, scale=2.0, center=2.5)
        policy_score = clamp(50 - (float(policy_momentum.dropna().iloc[-1]) if not policy_momentum.dropna().empty else 0.0) * 5)

        regime_label = classify_macro_regime(growth_score, inflation_score, policy_score)
        summary = (
            f"Macro regime is {regime_label}. Growth score {growth_score:.1f}, "
            f"inflation score {inflation_score:.1f}, policy score {policy_score:.1f}."
        )
        return AgentResult(
            name="macro_regime",
            scores={
                "growth_score": growth_score,
                "inflation_score": inflation_score,
                "policy_score": policy_score,
            },
            summary=summary,
            details={"regime_label": regime_label},
        )
