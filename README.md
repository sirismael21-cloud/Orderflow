# Order Flow Trading Bot (Binance, spot)

A cloud-hosted or self-hosted web app that reads **real, free order flow
data** from Binance (order book depth + trade tape) and trades a combined
**Order Book Imbalance + Cumulative Volume Delta** strategy, with a
mobile-friendly dashboard.

## ⚡ Quick Start (for Android users)

Want a bot running 24/7 in the cloud, controlled from your phone?

1. Get free testnet API keys: https://testnet.binance.vision/ (sign in with
   GitHub, create a key)
2. Go to https://railway.app and sign up (with GitHub)
3. Create a new Railway project, deploy this GitHub repo
4. Add your API keys as environment variables in Railway (`BINANCE_API_KEY`,
   `BINANCE_API_SECRET`, etc.)
5. Railway gives you a public URL — open it in your Android browser
6. Press **Start Bot** and watch it trade in testnet (fake money)

See **"Deploy to Railway"** section below for full details.

## ⚠️ Read this before you touch live money

- This is not financial advice, and no strategy here is validated or
  guaranteed to be profitable. Order flow signals like OBI/CVD are commonly
  used but can and do produce losing streaks, especially in choppy markets.
- **Always run on Binance Testnet first** (`USE_TESTNET=true` in `.env`,
  the default). Get free testnet API keys at https://testnet.binance.vision/
- Only go live with an amount you can afford to lose completely, and start
  small. `MAX_POSITION_PCT` and `MAX_DAILY_LOSS_PCT` in `.env` are hard caps
  enforced in `backend/risk.py` — read that file and make sure you understand
  exactly what it does before relying on it.
- When creating your real Binance API key: enable **Spot & Margin Trading
  only**. Do **not** enable withdrawals. Restrict the key to your server's IP
  if you can.
- This app has no encrypted secrets vault — `.env` sits in plaintext on
  whatever machine you run it on. Don't deploy it on a shared or public
  server without locking that down yourself.
- Spot accounts can't truly "short" — the SHORT side in this bot sells an
  existing base-asset balance. If you don't hold any, short signals will
  fail to execute (by design — it won't use margin or futures unless you
  change that).

## What it actually does

- Connects to Binance's **free public WebSocket streams**
  (`depth20@100ms` + `aggTrade`) for live order flow — no data subscription
  needed.
- Computes **Order Book Imbalance** (bid vs ask resting volume in the top N
  levels) and **Cumulative Volume Delta** (net aggressor buy/sell volume
  over a rolling window).
- Fires a LONG/SHORT signal only when both agree, to cut down on noise.
- Every trade gets an automatic stop-loss and take-profit, a per-trade
  cooldown, and a daily-loss kill switch that halts the bot for the rest of
  the day if it's tripped.
- Dashboard (works on phone or desktop browser) shows live price, OBI, CVD,
  open position, balances, and a log — with Start / Stop / Close Position /
  Kill Switch controls.

## Setup

### Option 1: Run locally (on your computer)

```bash
cd orderflow-bot
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: add your testnet API keys, leave USE_TESTNET=true
```

Get free testnet keys (fake money, real market data) at
https://testnet.binance.vision/ — log in with GitHub, generate a key.

Run it:

```bash
uvicorn backend.server:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in a browser (or from your phone, if it's on
the same network: `http://<your-computer's-LAN-IP>:8000`).

### Option 2: Deploy to the cloud (runs 24/7, control from your phone)

**Recommended for Android users.** Bot runs on a free cloud server 24/7,
you control it from anywhere via the web dashboard.

#### Deploy to Railway (easiest, free tier available)

1. **Create a Railway account**: Go to https://railway.app/, sign up with
   GitHub.

2. **Fork this repo**: (or push to your own GitHub)
   - Click the "Fork" button on the GitHub repo
   - Clone your fork locally:
     ```bash
     git clone https://github.com/YOUR-USERNAME/orderflow-bot.git
     cd orderflow-bot
     ```

3. **Create a `.env` file locally** (don't commit it):
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your Binance testnet API keys (or live keys once
   tested). Leave `.env` in your `.gitignore` — the file already has this,
   so it won't upload to GitHub.

4. **Deploy to Railway**:
   - Go to https://railway.app/dashboard
   - Click "New Project" → "Deploy from GitHub"
   - Select your forked `orderflow-bot` repo
   - Click "Deploy Now"
   - Railway will build and start your bot automatically

5. **Set environment variables on Railway**:
   - In the Railway dashboard, open your deployment
   - Click the "Variables" tab
   - Add each variable from your local `.env.example`:
     - `BINANCE_API_KEY`
     - `BINANCE_API_SECRET`
     - `USE_TESTNET=true` (start with testnet!)
     - `SYMBOL=BTCUSDT` (or whatever you want)
     - All the other risk settings from `.env.example`

6. **Find your bot's URL**:
   - Railway assigns a public URL automatically (something like
     `orderflow-bot-production.up.railway.app`)
   - Your dashboard is at `https://YOUR-RAILWAY-URL/`
   - Open this in your Android browser and you're controlling a 24/7 bot ✓

7. **Redeploy if you change code**:
   - Edit code locally, `git commit`, `git push` to GitHub
   - Railway auto-redeploys on every push (you can disable this in settings)

#### Deploy to Render (also free, alternative)

1. Go to https://render.com/, sign up
2. Click "New+" → "Web Service"
3. Connect your GitHub repo
4. Set environment to `Python 3`
5. Build command: (leave blank, auto-detected)
6. Start command: `uvicorn backend.server:app --host 0.0.0.0 --port $PORT`
7. Add environment variables (same as Railway)
8. Click "Create Web Service" — done

---

Press **Start Bot** to arm it — it will only place trades when a signal
fires; watching the dashboard without pressing Start is completely passive.

## Security (important for cloud deployment)

- **Never commit `.env` to GitHub.** It's already in `.gitignore`, but
  check before you push.
- **Restrict your Binance API key**:
  - Enable "Spot & Margin Trading" only
  - Disable withdrawals
  - (Optional) Restrict by IP, but cloud IPs change — not critical if you
    disable withdrawals
- **Environment variables on the cloud**: Railway, Render, Heroku, etc. all
  store env vars securely on their servers; they're not logged or visible
  to the public. But treat them like passwords — don't share your deployment
  URL with untrusted people.
- The `.env` file on your local machine stays private — never push it.

## Going live (only after you've tested thoroughly)

1. Create a real Binance API key with Spot & Margin Trading enabled,
   withdrawals disabled.
2. Update environment variables on your cloud deployment:
   - Set `USE_TESTNET=false`
   - Keep `MAX_POSITION_PCT` tiny (e.g. 0.01 = 1% of your balance per trade)
   - Set `MAX_DAILY_LOSS_PCT` conservatively (e.g. 0.03 = 3% max daily loss)
3. Watch the dashboard closely for the first several trading sessions.
4. Increase position size only after you're confident the strategy works
   in your market conditions.

## Tuning the strategy

All in `.env`, no code changes needed:

| Variable | What it does |
|---|---|
| `SYMBOL` | Trading pair, e.g. `BTCUSDT`, `ETHUSDT` |
| `OBI_LEVELS` | How many order book levels to average for imbalance |
| `OBI_THRESHOLD` | How skewed the book must be to count as a signal (0.5–1.0) |
| `CVD_WINDOW_SECONDS` | Rolling window for aggressor-flow calculation |
| `STOP_LOSS_PCT` / `TAKE_PROFIT_PCT` | Exit distances from entry |
| `COOLDOWN_SECONDS` | Minimum gap between trades |

## Extending to futures/indices

There's no free legitimate order-flow feed for traditional futures/indices —
you'd need a paid data subscription (e.g. a CME market data feed, or a
broker's DOM API). The architecture here separates data (`exchange_feed.py`)
from strategy (`strategy.py`) from execution (`executor.py`) specifically so
you can swap in a different data source later without touching the rest.
