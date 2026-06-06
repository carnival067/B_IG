# B_IG

B_IG is an async, paper-first Smart Money Concepts trading bot scaffold for
5-minute trading with higher-timeframe confirmation.

It includes:

- SMC engine: structure, CHoCH, order blocks, fair value gaps, liquidity sweeps,
  displacement, and EMA confirmation.
- AI-style scoring engine with a 0-100 trade score.
- Paper broker with virtual balance, orders, positions, trade history, and stats.
- Backtesting engine with risk/reward, drawdown, win rate, profit factor,
  expectancy, Sharpe, and Sortino.
- FastAPI API with WebSocket status stream.
- PostgreSQL schema for trades, signals, logs, market data, scores, and screenshots.
- Docker deployment files.
- Unit tests for the core trading conditions.

## Safety

The default mode is `PAPER`. Live trading is blocked unless both conditions are
true:

```bash
MODE=LIVE
ALLOW_LIVE_TRADING=true
```

Paper mode requires no broker connection.

## Quick Start

```bash
cd B_IG
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
uvicorn b_ig.api.main:app --reload
```

If you are on Python 3.14, use the flexible requirements above. The database
driver is optional for now and can be installed separately:

```bash
pip install -r requirements-db.txt
```

Open:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/status
```

## Run A Backtest

```bash
python -m b_ig.cli.backtest examples/sample_ohlcv.csv --symbol EURUSD
```

CSV columns required:

```text
timestamp,open,high,low,close,volume
```

## Core Entry Rules

Buy requires:

- M15/H1 trend bullish
- M5 bullish CHoCH with close confirmation
- Strong/institutional bullish order block
- Fresh bullish FVG
- Sell-side liquidity sweep complete
- Price retraced into both OB and FVG
- EMA9 > EMA20
- AI score >= 80
- No active high-impact news pause
- London, New York, or overlap session

Sell is the inverse.

## Project Layout

```text
B_IG/
├── b_ig/
│   ├── ai/              # scoring and optional ML hooks
│   ├── api/             # FastAPI + WebSocket
│   ├── backtest/        # historical simulator
│   ├── broker/          # paper broker and IG live adapter
│   ├── config.py        # pydantic settings
│   ├── data/            # feeds and validation
│   ├── execution/       # async bot loop
│   ├── filters/         # news/session filters
│   ├── risk/            # position sizing and risk gates
│   ├── smc/             # SMC detection engine
│   └── storage/         # PostgreSQL schema
├── tests/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── requirements*.txt
```

## Live Trading

`b_ig.broker.ig.IGBroker` is intentionally guarded. It validates config and
exposes the async broker interface, but order placement should be exercised in
IG demo before enabling live mode. Keep `MODE=PAPER` during development.

## Render

Render deployment files are included:

- `render.yaml`
- `.python-version`
- `RENDER_DEPLOY.md`

Free Render services can sleep after inactivity, so use this for paper testing,
not always-on real trading.

## Binance Futures Demo

See `BINANCE_DEMO_SETUP.md` for the guarded Binance USD-M Futures Demo
integration. Mainnet Binance trading is blocked in this build.

## Connect IG

Create `B_IG/.env` from `.env.example` and fill your IG details:

```bash
IG_API_KEY=your_ig_api_key
IG_USERNAME=your_ig_username
IG_PASSWORD=your_ig_password
IG_ACCOUNT_TYPE=DEMO
```

Keep these safety settings while testing:

```bash
MODE=PAPER
ALLOW_LIVE_TRADING=false
```

Restart the server, then open:

```text
http://127.0.0.1:8000/broker/ig/test
```

That endpoint logs in to IG, fetches account balance details, and checks market
search access. It does not place trades.

### Web Profiles

The dashboard includes an **IG Profiles** panel. A user can enter:

- Profile name
- IG username
- IG API key
- IG password
- DEMO/LIVE account type

Then press **Save Profile** and **Test**. The page shows whether that profile is
connected, the account id, and the last error if the test failed.

For safety in this early version, profile credentials are stored only in server
memory. They disappear when the server restarts and are not written to disk.
Before using this for multiple real users on a network, add login/authentication
and encrypted credential storage.
