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
    parser.add_argument("--history-years", type=int, choices=[5, 10],
                        help="Separate 5y/10y research history; never touches Streamlit DB")
    parser.add_argument("--acquire", action="store_true",
                        help="Explicitly fetch current Yahoo daily bars for selected symbols (no broker data)")
    parser.add_argument("--output", type=Path,
                        default=Path("outputs/research/simons_quant_v1.json"))
    args = parser.parse_args()
    if args.history_years:
        from src.intelligence.simons_history import (
            fetch_long_snapshot, save_long_snapshot, evaluate_long_cached
        )
        if args.acquire:
            from src.intelligence.universe import load_universe
            allowed = set(load_universe(args.root).symbol)
            if not set(args.symbols).issubset(allowed):
                parser.error("Symbols must belong to the research universe")
            for symbol in dict.fromkeys(args.symbols):
                try:
                    record = fetch_long_snapshot(symbol, years=args.history_years)
                    save_long_snapshot(args.root, record)
                    print(f"{symbol}: {args.history_years}y provider history acquired")
                except Exception as exc:
                    print(f"{symbol}: long acquisition failed ({type(exc).__name__}); no fallback")
        report = evaluate_long_cached(args.root, args.symbols, as_of=args.as_of,
                                      fee_bps=args.fee_bps)
    else:
        if args.acquire:
            from src.intelligence.refresh import fetch_record, import_record
            from src.intelligence.store import Store
            from src.intelligence.universe import load_universe

            allowed = set(load_universe(args.root).symbol)
            if not set(args.symbols).issubset(allowed):
                parser.error("All symbols must belong to the existing research universe")
            store = Store(args.root)
            for symbol in dict.fromkeys(args.symbols):
                try:
                    import_record(store, fetch_record(symbol), allowed)
                    print(f"{symbol}: qualified provider snapshot acquired")
                except Exception as exc:
                    print(f"{symbol}: provider acquisition failed ({type(exc).__name__}); no fallback")
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
