from __future__ import annotations

from dataclasses import dataclass

from b_ig.config import Settings
from b_ig.models import Order, Side, TradeSignal


@dataclass(slots=True)
class RiskManager:
    settings: Settings

    def size_signal(self, signal: TradeSignal, equity: float) -> TradeSignal:
        distance = abs(signal.entry - signal.stop_loss)
        if distance <= 0:
            signal.size = 0.0
            return signal
        risk_capital = equity * self.settings.RISK_PER_TRADE
        notional_size = risk_capital / distance
        max_levered = equity * self.settings.LEVERAGE / signal.entry
        signal.size = round(min(notional_size, max_levered), 4)
        return signal

    def validate_order(self, order: Order, equity: float) -> tuple[bool, str]:
        if order.size <= 0:
            return False, "order size must be positive"
        if order.stop_loss <= 0 or order.take_profit <= 0:
            return False, "stop loss and take profit are required"
        risk_distance = abs(order.entry - order.stop_loss)
        reward_distance = abs(order.take_profit - order.entry)
        if risk_distance <= 0:
            return False, "invalid stop distance"
        if reward_distance / risk_distance < self.settings.RISK_REWARD * 0.95:
            return False, "risk reward below configured target"
        notional = order.size * order.entry
        if notional > equity * self.settings.LEVERAGE:
            return False, "leverage cap exceeded"
        return True, "approved"

    def order_from_signal(self, signal: TradeSignal) -> Order:
        side = Side.BUY if signal.side.value == "BUY" else Side.SELL
        return Order(
            symbol=signal.symbol,
            side=side,
            size=signal.size,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            reason=signal.reason,
        )

