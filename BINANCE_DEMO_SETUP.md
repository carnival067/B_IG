# Binance Futures Demo Setup

B_IG supports Binance USD-M Futures Demo for `BTCUSDT`.

This integration intentionally blocks Binance mainnet. Demo funds have no real
value, but automated leveraged trading can still behave unexpectedly. Validate
orders, stops, take-profit behavior, quantity precision, and reconnect handling
before considering any production integration.

## 1. Create Binance Futures Demo Credentials

Use Binance's USD-M Futures demo environment and create an API key and secret.
Do not use mainnet credentials.

Demo API base URL:

```text
https://demo-fapi.binance.com
```

## 2. Add Local Environment Variables

Create `B_IG/.env` from `.env.example` and set:

```text
MODE=DEMO
BROKER=BINANCE
ALLOW_LIVE_TRADING=false

SYMBOLS=BTCUSDT
BINANCE_ENV=DEMO
BINANCE_API_KEY=your_demo_api_key
BINANCE_API_SECRET=your_demo_api_secret
BINANCE_AUTO_TRADING=false
BINANCE_LEVERAGE=5
BINANCE_MARGIN_TYPE=ISOLATED
```

Keep `BINANCE_AUTO_TRADING=false` for the connection test.

## 3. Test The Connection

Start B_IG and open:

```text
http://127.0.0.1:8000/broker/binance/test
```

The response should show:

```text
authenticated: true
environment: DEMO
balance: <demo USDT balance>
```

## 4. Enable Automatic Demo Orders

After the connection test passes, stop B_IG and change:

```text
BINANCE_AUTO_TRADING=true
```

Restart the server, open the dashboard, and press `Start`.

Automatic Binance demo orders require all of these:

```text
MODE=DEMO
BROKER=BINANCE
BINANCE_ENV=DEMO
BINANCE_AUTO_TRADING=true
valid demo API credentials
```

The bot then uses Binance demo M5/M15/H1 candles and places protected demo
futures orders only when all SMC rules and the minimum AI score pass.

## Render

Add the same values in Render Environment Variables. Mark API keys as secret.
Render Free can sleep and restart, so it is not reliable for unattended
automated trading.

