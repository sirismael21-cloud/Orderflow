import asyncio
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .exchange_feed import OrderFlowState, stream_order_flow
from .strategy import evaluate, StrategyInput, Signal
from .risk import RiskManager
from .executor import Executor

app = FastAPI(title="Order Flow Bot")

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ---- shared state ----
state = OrderFlowState(settings.symbol, settings.cvd_window_seconds)
executor = Executor()
risk: RiskManager | None = None
bot_enabled = False
event_log: list[dict] = []
stop_event = asyncio.Event()


def log(msg: str):
    entry = {"ts": time.time(), "msg": msg}
    event_log.append(entry)
    if len(event_log) > 300:
        event_log.pop(0)
    print(msg)


@app.on_event("startup")
async def startup():
    global risk
    try:
        bal = executor.get_balances()
        starting_equity = bal["quote_free"]  # simple: quote-currency equity baseline
    except Exception as e:
        starting_equity = 0.0
        log(f"Could not fetch starting balance ({e}). Defaulting to 0 — trading disabled until this is fixed.")
    risk = RiskManager(starting_equity or 1.0)
    log(f"Started. Testnet={settings.use_testnet} Symbol={settings.symbol} StartingEquity={starting_equity}")
    asyncio.create_task(stream_order_flow(state, stop_event))
    asyncio.create_task(trading_loop())


@app.on_event("shutdown")
async def shutdown():
    stop_event.set()


async def trading_loop():
    while not stop_event.is_set():
        await asyncio.sleep(1)
        if not bot_enabled or risk is None:
            continue
        try:
            await evaluate_and_act()
        except Exception as e:
            log(f"trading_loop error: {e}")


async def evaluate_and_act():
    last_price = state.last_price
    if last_price is None:
        return

    # manage existing position first: check SL/TP
    hit = executor.check_stop_or_target(last_price)
    if hit:
        order = executor.close_position()
        log(f"Position closed via {hit} at ~{last_price}. order_id={order.get('id') if order else None}")
        risk.update_equity(executor.equity_in_quote(last_price))
        return

    if executor.open_position is not None:
        return  # already in a trade, wait for exit

    can, reason = risk.can_trade()
    if not can:
        return

    sig = evaluate(StrategyInput(
        obi=state.order_book_imbalance(settings.obi_levels),
        cvd=state.cumulative_volume_delta(),
        last_price=last_price,
    ))
    if sig == Signal.FLAT:
        return

    bal = executor.get_balances()
    qty = risk.position_size(bal["quote_free"], last_price)
    if qty <= 0:
        return

    side = "LONG" if sig == Signal.LONG else "SHORT"
    sl = risk.stop_loss_price(last_price, side)
    tp = risk.take_profit_price(last_price, side)

    try:
        if side == "LONG":
            order = executor.open_long(qty, last_price, sl, tp)
        else:
            order = executor.open_short(qty, last_price, sl, tp)
        risk.record_trade()
        log(f"Opened {side} qty={qty:.6f} @~{last_price:.2f} SL={sl:.2f} TP={tp:.2f} order_id={order.get('id')}")
    except Exception as e:
        log(f"Order failed ({side} qty={qty:.6f}): {e}")


# ---------------- REST API ----------------

@app.get("/")
async def index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/status")
async def status():
    bal = None
    try:
        bal = executor.get_balances()
    except Exception:
        pass
    return {
        "bot_enabled": bot_enabled,
        "testnet": settings.use_testnet,
        "symbol": settings.symbol,
        "last_price": state.last_price,
        "obi": state.order_book_imbalance(settings.obi_levels),
        "cvd": state.cumulative_volume_delta(),
        "open_position": executor.open_position,
        "balances": bal,
        "risk_halted": risk.halted if risk else False,
        "halt_reason": risk.halt_reason if risk else "",
        "log": event_log[-50:],
    }


@app.post("/api/start")
async def start():
    global bot_enabled
    bot_enabled = True
    if risk:
        risk.resume()
    log("Bot ENABLED by user.")
    return {"ok": True}


@app.post("/api/stop")
async def stop():
    global bot_enabled
    bot_enabled = False
    log("Bot DISABLED by user.")
    return {"ok": True}


@app.post("/api/close")
async def close_now():
    order = executor.close_position()
    log(f"Manual close requested. order={order}")
    return {"ok": True, "order": order}


@app.post("/api/kill")
async def kill():
    global bot_enabled
    bot_enabled = False
    if risk:
        risk.manual_halt("Kill switch pressed by user")
    log("KILL SWITCH pressed. Bot halted.")
    return {"ok": True}


# ---------------- WebSocket push for live order flow chart ----------------

@app.websocket("/ws/orderflow")
async def ws_orderflow(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    state.subscribers.append(q)
    try:
        while True:
            snap = await q.get()
            await ws.send_json(snap)
    except WebSocketDisconnect:
        pass
    finally:
        if q in state.subscribers:
            state.subscribers.remove(q)
