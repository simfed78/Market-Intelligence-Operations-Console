"""Generate Simons-style quantitative research JSON from validated local snapshots.

Usage:
    python -m scripts.simons_quant_research --root . --symbols SPY QQQ XLV XLE
The market cache is populated separately by src.intelligence.refresh.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.intelligence.simons_quant import evaluate_cached, write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--symbols", nargs="+", default=["SPY", "QQQ", "XLV", "XLE"])
    parser.add_argument("--as-of", help="UTC timezone-aware ISO timestamp (default: now)")
    parser.add_argument("--fee-bps", type=float, default=10.0,
                        help="Assumed one-way cost in basis points (default 10)")
    parser.add_argument("--output", type=Path,
                        default=Path("outputs/research/simons_quant_v1.json"))
    args = parser.parse_args()
    report = evaluate_cached(args.root, args.symbols, as_of=args.as_of,
                             fee_bps=args.fee_bps)
    path = write_report(report, args.output)
    print(f"Research report: {path}")
    for r in report["results"]:
        label = r.get("reason") or (
            f"{len(r['folds'])} folds, net OOS {r['oos_return_net']:.2%}, "
            f"benchmark {r['buy_hold_return_net']:.2%}"
        )
        print(f"{r['symbol']}: {r['status']} — {label}")


if __name__ == "__main__":
    main()
