# Deploy B_IG To Render

Render can run B_IG as a free Python web service for paper testing.

Important limitation: Render free web services spin down after inactivity. When
the service is asleep, the bot is not scanning. Use a paid always-on instance
before relying on it for real trading.

## Option A: Manual Render Setup

1. Push this project to GitHub.
2. In Render, create a new Web Service.
3. Connect the GitHub repository.
4. Set the root directory to:

```text
B_IG
```

5. Use these settings:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: uvicorn b_ig.api.main:app --host 0.0.0.0 --port $PORT
Instance Type: Free
```

6. Add environment variables:

```text
PYTHON_VERSION=3.14.3
MODE=PAPER
ALLOW_LIVE_TRADING=false
SYMBOLS=EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,BTCUSDT
STARTING_BALANCE=10000
RISK_PER_TRADE=0.01
LEVERAGE=25
RISK_REWARD=5
STOP_BUFFER_PIPS=3
AI_MIN_SCORE=80
```

## Option B: Blueprint

If Render detects `render.yaml`, use the Blueprint flow from the `B_IG`
directory. The included `render.yaml` creates one free web service.

## After Deploy

Open the Render URL and press `Start`.

Remember: on the free plan, the app can sleep. If it sleeps, press `Start`
again after it wakes up.

