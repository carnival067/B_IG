from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from b_ig.models import SignalSide
from b_ig.risk import RiskManager
from b_ig.strategy import SMCStrategy


@dataclass(slots=True)
class BacktestReport:
    metrics: dict[str, float]
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)


class BacktestEngine:
    def __init__(
        self,
        strategy: SMCStrategy,
        risk: RiskManager,
        starting_balance: float = 10_000.0,
        warmup: int = 80,
    ) -> None:
        self.strategy = strategy
        self.risk = risk
        self.starting_balance = starting_balance
        self.warmup = warmup

    def run(self, symbol: str, candles: pd.DataFrame) -> BacktestReport:
        equity = self.starting_balance
        equity_curve = [equity]
        trades: list[dict] = []
        open_trade: dict | None = None

        for i in range(self.warmup, len(candles)):
            window = candles.iloc[: i + 1]
            bar = candles.iloc[i]
            if open_trade:
                closed = self._exit(open_trade, bar)
                if closed:
                    pnl = equity * self.risk.settings.RISK_PER_TRADE * closed["r_multiple"]
                    equity += pnl
                    closed["pnl"] = pnl
                    trades.append(closed)
                    open_trade = None
            equity_curve.append(equity)
            if open_trade:
                continue
            signal = self.strategy.generate(symbol, window, {"M15": window, "H1": window})
            if signal.side is SignalSide.HOLD:
                continue
            signal = self.risk.size_signal(signal, equity)
            open_trade = {
                "side": signal.side.value,
                "entry": signal.entry,
                "stop": signal.stop_loss,
                "take": signal.take_profit,
                "score": signal.score,
            }

        return BacktestReport(
            metrics=self._metrics(equity_curve, trades),
            trades=trades,
            equity_curve=equity_curve,
        )

    def _exit(self, trade: dict, bar: pd.Series) -> dict | None:
        high = float(bar["high"])
        low = float(bar["low"])
        risk = abs(trade["entry"] - trade["stop"])
        if trade["side"] == "BUY":
            if low <= trade["stop"]:
                return {**trade, "exit": trade["stop"], "r_multiple": -1.0}
            if high >= trade["take"]:
                return {
                    **trade,
                    "exit": trade["take"],
                    "r_multiple": self.risk.settings.RISK_REWARD,
                }
        else:
            if high >= trade["stop"]:
                return {**trade, "exit": trade["stop"], "r_multiple": -1.0}
            if low <= trade["take"]:
                return {
                    **trade,
                    "exit": trade["take"],
                    "r_multiple": self.risk.settings.RISK_REWARD,
                }
        return None if risk > 0 else {**trade, "exit": trade["entry"], "r_multiple": 0.0}

    def _metrics(self, equity_curve: list[float], trades: list[dict]) -> dict[str, float]:
        returns = pd.Series(equity_curve).pct_change().dropna()
        wins = [t for t in trades if t["r_multiple"] > 0]
        losses = [t for t in trades if t["r_multiple"] < 0]
        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (peak - np.array(equity_curve)) / peak
        downside = returns[returns < 0]
        return {
            "trades": float(len(trades)),
            "win_rate": len(wins) / len(trades) if trades else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss else 0.0,
            "expectancy": float(np.mean([t["r_multiple"] for t in trades])) if trades else 0.0,
            "average_rr": self.risk.settings.RISK_REWARD,
            "max_drawdown": float(drawdown.max()) if len(drawdown) else 0.0,
            "sharpe": (
                float((returns.mean() / returns.std()) * np.sqrt(252))
                if returns.std()
                else 0.0
            ),
            "sortino": float((returns.mean() / downside.std()) * np.sqrt(252))
            if len(downside) and downside.std()
            else 0.0,
            "total_return": equity_curve[-1] / equity_curve[0] - 1 if equity_curve else 0.0,
        }
