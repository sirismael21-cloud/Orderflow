"""
Free, real-time order flow data straight from Binance's public WebSocket
streams — no API key required for market data (keys are only needed for
execution, handled in executor.py).

Two streams per symbol:
  - depth20@100ms  -> top 20 bid/ask levels, updated 10x/sec (order book imbalance)
  - aggTrade        -> every aggressor trade, tagged buyer/seller maker (CVD)
"""
import asyncio
import json
import time
from collections import deque

import websockets

from .config import settings

BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream"


class OrderFlowState:
    """Shared, continuously-updated snapshot of order flow for one symbol."""

    def __init__(self, symbol: str, cvd_window_seconds: int):
        self.symbol = symbol.lower()
        self.cvd_window_seconds = cvd_window_seconds

        self.bids: list[tuple[float, float]] = []  # [(price, qty), ...] best first
        self.asks: list[tuple[float, float]] = []
        self.last_price: float | None = None

        # rolling trade tape for CVD: each entry (timestamp, signed_qty)
        self._tape: deque[tuple[float, float]] = deque()

        self.subscribers: list[asyncio.Queue] = []

    # ---- order book imbalance ----
    def order_book_imbalance(self, levels: int) -> float | None:
        if not self.bids or not self.asks:
            return None
        bid_vol = sum(q for _, q in self.bids[:levels])
        ask_vol = sum(q for _, q in self.asks[:levels])
        total = bid_vol + ask_vol
        if total == 0:
            return None
        return bid_vol / total  # >0.5 means more resting buy interest

    # ---- cumulative volume delta over rolling window ----
    def cumulative_volume_delta(self) -> float:
        now = time.time()
        cutoff = now - self.cvd_window_seconds
        while self._tape and self._tape[0][0] < cutoff:
            self._tape.popleft()
        return sum(qty for _, qty in self._tape)

    def _record_trade(self, qty: float, is_buyer_maker: bool):
        # if buyer is maker, the aggressor was a seller -> negative flow
        signed = -qty if is_buyer_maker else qty
        self._tape.append((time.time(), signed))

    async def push_snapshot(self):
        snap = {
            "type": "orderflow",
            "symbol": self.symbol.upper(),
            "last_price": self.last_price,
            "obi": self.order_book_imbalance(settings.obi_levels),
            "cvd": self.cumulative_volume_delta(),
            "best_bid": self.bids[0] if self.bids else None,
            "best_ask": self.asks[0] if self.asks else None,
            "ts": time.time(),
        }
        for q in self.subscribers:
            if not q.full():
                q.put_nowait(snap)
        return snap


async def stream_order_flow(state: OrderFlowState, stop_event: asyncio.Event):
    """Connects to Binance combined stream and keeps `state` updated forever
    (auto-reconnects on drop). Runs until stop_event is set."""
    sym = state.symbol
    url = f"{BINANCE_WS_BASE}?streams={sym}@depth20@100ms/{sym}@aggTrade"

    backoff = 1
    while not stop_event.is_set():
        try:
            async with websockets.connect(url, ping_interval=15, ping_timeout=10) as ws:
                backoff = 1
                async for raw in ws:
                    if stop_event.is_set():
                        break
                    msg = json.loads(raw)
                    stream = msg.get("stream", "")
                    data = msg.get("data", {})

                    if stream.endswith("depth20@100ms"):
                        state.bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
                        state.asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
                        if state.bids and state.asks:
                            state.last_price = (state.bids[0][0] + state.asks[0][0]) / 2

                    elif stream.endswith("aggTrade"):
                        qty = float(data["q"])
                        is_buyer_maker = bool(data["m"])
                        state._record_trade(qty, is_buyer_maker)

                    await state.push_snapshot()
        except (websockets.ConnectionClosed, OSError) as e:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
