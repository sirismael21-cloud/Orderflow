"""
Order-flow strategy: combines Order Book Imbalance (resting liquidity skew)
with Cumulative Volume Delta (aggressive taker flow) into LONG / SHORT / FLAT
signals. Both must agree before a signal fires — this is deliberately
conservative to cut down on false entries from a single noisy source.
"""
from dataclasses import dataclass
from enum import Enum

from .config import settings


class Signal(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class StrategyInput:
    obi: float | None       # 0..1, share of resting volume on the bid
    cvd: float               # signed rolling aggressor volume
    last_price: float | None


def evaluate(inp: StrategyInput) -> Signal:
    if inp.obi is None or inp.last_price is None:
        return Signal.FLAT

    obi_long = inp.obi >= settings.obi_threshold
    obi_short = inp.obi <= (1 - settings.obi_threshold)

    cvd_long = inp.cvd > settings.cvd_threshold
    cvd_short = inp.cvd < -settings.cvd_threshold

    if obi_long and cvd_long:
        return Signal.LONG
    if obi_short and cvd_short:
        return Signal.SHORT
    return Signal.FLAT
