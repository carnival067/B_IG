from __future__ import annotations

import argparse
import json

import pandas as pd

from b_ig.backtest import BacktestEngine
from b_ig.config import get_settings
from b_ig.risk import RiskManager
from b_ig.strategy import SMCStrategy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv")
    parser.add_argument("--symbol", default="EURUSD")
    args = parser.parse_args()
    candles = pd.read_csv(args.csv, parse_dates=["timestamp"]).set_index("timestamp")
    settings = get_settings()
    report = BacktestEngine(SMCStrategy(settings), RiskManager(settings)).run(args.symbol, candles)
    print(json.dumps({"metrics": report.metrics, "trades": report.trades[-20:]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

