"""
All trading decisions pass through here before an order is ever placed.
This is the single place that can veto a trade — keep it that way.
"""
import time

from .config import settings


class RiskManager:
    def __init__(self, starting_equity: float):
        self.starting_equity = starting_equity
        self.day_start_equity = starting_equity
        self.day_start_ts = time.time()
        self.last_trade_ts = 0.0
        self.halted = False
        self.halt_reason = ""

    def _roll_day_if_needed(self):
        # simple 24h rolling reset of the daily loss counter
        if time.time() - self.day_start_ts > 86400:
            self.day_start_equity = self.starting_equity
            self.day_start_ts = time.time()
            self.halted = False
            self.halt_reason = ""

    def update_equity(self, current_equity: float):
        self._roll_day_if_needed()
        loss_pct = (self.day_start_equity - current_equity) / self.day_start_equity
        if loss_pct >= settings.max_daily_loss_pct:
            self.halted = True
            self.halt_reason = (
                f"Daily loss limit hit ({loss_pct:.2%} >= "
                f"{settings.max_daily_loss_pct:.2%}). Bot halted until reset."
            )

    def can_trade(self) -> tuple[bool, str]:
        if self.halted:
            return False, self.halt_reason
        if time.time() - self.last_trade_ts < settings.cooldown_seconds:
            remaining = settings.cooldown_seconds - (time.time() - self.last_trade_ts)
            return False, f"Cooldown active ({remaining:.0f}s left)"
        return True, ""

    def position_size(self, quote_balance: float, price: float) -> float:
        """Returns base-asset quantity to trade, capped by MAX_POSITION_PCT."""
        risk_quote = quote_balance * settings.max_position_pct
        qty = risk_quote / price
        return qty

    def stop_loss_price(self, entry: float, side: str) -> float:
        return entry * (1 - settings.stop_loss_pct) if side == "LONG" else entry * (1 + settings.stop_loss_pct)

    def take_profit_price(self, entry: float, side: str) -> float:
        return entry * (1 + settings.take_profit_pct) if side == "LONG" else entry * (1 - settings.take_profit_pct)

    def record_trade(self):
        self.last_trade_ts = time.time()

    def manual_halt(self, reason: str = "Manual stop"):
        self.halted = True
        self.halt_reason = reason

    def resume(self):
        self.halted = False
        self.halt_reason = ""
