import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    v = os.getenv(name)
    return float(v) if v else default


def _int(name: str, default: int) -> int:
    v = os.getenv(name)
    return int(v) if v else default


class Settings:
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    use_testnet: bool = _bool("USE_TESTNET", True)

    symbol: str = os.getenv("SYMBOL", "BTCUSDT")
    obi_levels: int = _int("OBI_LEVELS", 10)
    obi_threshold: float = _float("OBI_THRESHOLD", 0.62)
    cvd_window_seconds: int = _int("CVD_WINDOW_SECONDS", 30)
    cvd_threshold: float = _float("CVD_THRESHOLD", 0.0)

    max_position_pct: float = _float("MAX_POSITION_PCT", 0.02)
    stop_loss_pct: float = _float("STOP_LOSS_PCT", 0.006)
    take_profit_pct: float = _float("TAKE_PROFIT_PCT", 0.012)
    max_daily_loss_pct: float = _float("MAX_DAILY_LOSS_PCT", 0.03)
    cooldown_seconds: int = _int("COOLDOWN_SECONDS", 60)


settings = Settings()

if not settings.use_testnet and (not settings.api_key or not settings.api_secret):
    raise RuntimeError(
        "USE_TESTNET is false (LIVE trading) but no API key/secret is set. "
        "Refusing to start without credentials."
    )
