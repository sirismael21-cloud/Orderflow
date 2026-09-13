"""
Places and manages real orders on Binance via ccxt. Every call in here can
move real money when USE_TESTNET=false — nothing in this file should be
called except through RiskManager.can_trade() gating in server.py.
"""
import ccxt

from .config import settings


class Executor:
    def __init__(self):
        self.exchange = ccxt.binance({
            "apiKey": settings.api_key,
            "secret": settings.api_secret,
            "enableRateLimit": True,
        })
        if settings.use_testnet:
            self.exchange.set_sandbox_mode(True)

        self.symbol_ccxt = self._to_ccxt_symbol(settings.symbol)
        self.open_position: dict | None = None  # {side, entry, qty, sl, tp}

    @staticmethod
    def _to_ccxt_symbol(sym: str) -> str:
        # "BTCUSDT" -> "BTC/USDT"
        for quote in ("USDT", "USDC", "BUSD", "BTC", "ETH"):
            if sym.upper().endswith(quote) and len(sym) > len(quote):
                return f"{sym[:-len(quote)].upper()}/{quote}"
        return sym.upper()

    def get_balances(self) -> dict:
        bal = self.exchange.fetch_balance()
        base, quote = self.symbol_ccxt.split("/")
        return {
            "base_free": bal.get(base, {}).get("free", 0.0),
            "quote_free": bal.get(quote, {}).get("free", 0.0),
            "base": base,
            "quote": quote,
        }

    def equity_in_quote(self, last_price: float) -> float:
        bal = self.get_balances()
        return bal["quote_free"] + bal["base_free"] * last_price

    def open_long(self, qty: float, entry_hint: float, sl: float, tp: float) -> dict:
        order = self.exchange.create_market_buy_order(self.symbol_ccxt, qty)
        self.open_position = {"side": "LONG", "entry": entry_hint, "qty": qty, "sl": sl, "tp": tp}
        return order

    def open_short(self, qty: float, entry_hint: float, sl: float, tp: float) -> dict:
        # Note: true shorting needs margin/futures enabled on the account.
        # On spot, "short" here means selling an existing base balance —
        # this call will fail with insufficient balance if you don't hold any.
        order = self.exchange.create_market_sell_order(self.symbol_ccxt, qty)
        self.open_position = {"side": "SHORT", "entry": entry_hint, "qty": qty, "sl": sl, "tp": tp}
        return order

    def close_position(self) -> dict | None:
        if not self.open_position:
            return None
        qty = self.open_position["qty"]
        side = self.open_position["side"]
        if side == "LONG":
            order = self.exchange.create_market_sell_order(self.symbol_ccxt, qty)
        else:
            order = self.exchange.create_market_buy_order(self.symbol_ccxt, qty)
        self.open_position = None
        return order

    def check_stop_or_target(self, last_price: float) -> str | None:
        """Returns 'SL', 'TP', or None. Caller is responsible for calling
        close_position() when this returns non-None."""
        if not self.open_position:
            return None
        p = self.open_position
        if p["side"] == "LONG":
            if last_price <= p["sl"]:
                return "SL"
            if last_price >= p["tp"]:
                return "TP"
        else:
            if last_price >= p["sl"]:
                return "SL"
            if last_price <= p["tp"]:
                return "TP"
        return None
