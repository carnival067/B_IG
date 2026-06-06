from __future__ import annotations

import asyncio
import contextlib

from fastapi import FastAPI, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from httpx import HTTPError
from pydantic import BaseModel
from websockets.exceptions import ConnectionClosed

from b_ig.api.state import get_bot
from b_ig.broker.ig import IGAuthError, IGBroker
from b_ig.config import Mode, get_settings
from b_ig.models import SignalSide, TradeSignal
from b_ig.profiles import profile_store

app = FastAPI(title="B_IG SMC Trading Bot", version="0.1.0")


class IGProfileRequest(BaseModel):
    name: str
    api_key: str
    username: str
    password: str
    account_type: str = "DEMO"


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    status_data = await status()
    profiles = await list_profiles()
    cards = [
        ("Mode", status_data["mode"]),
        ("Live Enabled", status_data["live_trading_enabled"]),
        ("Running", status_data["running"]),
        ("Balance", status_data["balance"]),
        ("Open Positions", status_data["open_positions"]),
        ("Last Signal", status_data["last_event"]),
        ("All Sessions", status_data["allow_all_sessions"]),
        ("Symbols", ", ".join(status_data["symbols"])),
    ]
    card_html = "\n".join(
        (
            '      <div class="card">'
            f'<div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            "</div>"
        )
        for label, value in cards
    )
    symbol_options = "\n".join(
        f'        <option value="{symbol}">{symbol}</option>' for symbol in status_data["symbols"]
    )
    profile_rows = "\n".join(
        (
            "        <tr>"
            f"<td>{profile['name']}</td>"
            f"<td>{profile['username']}</td>"
            f"<td>{profile['account_type']}</td>"
            f"<td>{profile['connected']}</td>"
            f"<td>{profile['last_error'] or ''}</td>"
            f"<td><button data-profile-test=\"{profile['name']}\">Test</button></td>"
            "</tr>"
        )
        for profile in profiles["profiles"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>B_IG SMC Trading Bot</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: #f6f7f9;
      color: #171a1f;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 32px;
      letter-spacing: 0;
    }}
    .subtle {{
      color: #5d6675;
      margin: 0 0 28px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: #fff;
      border: 1px solid #dfe3ea;
      border-radius: 8px;
      padding: 16px;
    }}
    .label {{
      color: #667085;
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .value {{
      font-size: 22px;
      font-weight: 700;
      overflow-wrap: anywhere;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 20px;
    }}
    a, button {{
      border: 1px solid #1d4ed8;
      background: #1d4ed8;
      color: #fff;
      border-radius: 6px;
      padding: 10px 14px;
      text-decoration: none;
      font-size: 14px;
      cursor: pointer;
    }}
    a.secondary {{
      background: #fff;
      color: #1d4ed8;
    }}
    button.danger {{
      background: #b42318;
      border-color: #b42318;
    }}
    pre {{
      margin-top: 20px;
      padding: 16px;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      overflow: auto;
    }}
    .chart-wrap {{
      background: #fff;
      border: 1px solid #dfe3ea;
      border-radius: 8px;
      margin-top: 16px;
      padding: 14px;
    }}
    .chart-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }}
    select {{
      border: 1px solid #c7ced9;
      border-radius: 6px;
      padding: 8px 10px;
      background: #fff;
    }}
    input {{
      border: 1px solid #c7ced9;
      border-radius: 6px;
      padding: 9px 10px;
      min-width: 0;
    }}
    .profile-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #e5e7eb;
      padding: 8px;
      text-align: left;
      overflow-wrap: anywhere;
    }}
    canvas {{
      width: 100%;
      height: 360px;
      display: block;
    }}
  </style>
</head>
<body>
  <main>
    <h1>B_IG SMC Trading Bot</h1>
    <p class="subtle">Paper-first Smart Money Concepts trading system.</p>
    <section class="grid">
{card_html}
    </section>
    <div class="actions">
      <button data-action="/bot/start">Start</button>
      <button data-action="/bot/session/all">Allow All Sessions</button>
      <button data-action="/trade/paper-test">Paper Test Trade</button>
      <button class="secondary" data-action="/bot/stop">Stop</button>
      <button class="danger" data-action="/bot/emergency-stop">Emergency Stop</button>
      <a href="/docs">API Docs</a>
      <a class="secondary" href="/status">JSON Status</a>
      <a class="secondary" href="/broker/ig/test">Test IG</a>
      <a class="secondary" href="/trades">Trades</a>
    </div>
    <section class="chart-wrap">
      <div class="chart-head">
        <strong>Live Paper Chart</strong>
        <select id="symbol">
{symbol_options}
        </select>
      </div>
      <canvas id="chart" width="940" height="360"></canvas>
    </section>
    <section class="chart-wrap">
      <div class="chart-head">
        <strong>IG Profiles</strong>
        <span>Credentials are kept in server memory only.</span>
      </div>
      <form id="profileForm">
        <div class="profile-grid">
          <input name="name" placeholder="Profile name" required>
          <input name="username" placeholder="IG username" required>
          <input name="api_key" placeholder="IG API key" required>
          <input name="password" placeholder="IG password" type="password" required>
          <select name="account_type">
            <option value="DEMO">DEMO</option>
            <option value="LIVE">LIVE</option>
          </select>
          <button type="submit">Save Profile</button>
        </div>
      </form>
      <table>
        <thead>
          <tr>
            <th>Profile</th>
            <th>Username</th>
            <th>Type</th>
            <th>Connected</th>
            <th>Last Error</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody id="profiles">
{profile_rows}
        </tbody>
      </table>
    </section>
    <pre id="live"></pre>
  </main>
  <script>
    const live = document.getElementById("live");
    const chart = document.getElementById("chart");
    const symbolSelect = document.getElementById("symbol");
    const ctx = chart.getContext("2d");

    function drawChart(candles) {{
      if (!candles.length) return;
      const width = chart.width;
      const height = chart.height;
      const pad = 34;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, width, height);
      const highs = candles.map(c => c.high);
      const lows = candles.map(c => c.low);
      const max = Math.max(...highs);
      const min = Math.min(...lows);
      const span = Math.max(max - min, 0.0001);
      const xStep = (width - pad * 2) / candles.length;
      const y = price => pad + (max - price) / span * (height - pad * 2);
      ctx.strokeStyle = "#e5e7eb";
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {{
        const gy = pad + i * (height - pad * 2) / 4;
        ctx.beginPath();
        ctx.moveTo(pad, gy);
        ctx.lineTo(width - pad, gy);
        ctx.stroke();
      }}
      candles.forEach((c, i) => {{
        const x = pad + i * xStep + xStep / 2;
        const up = c.close >= c.open;
        const color = up ? "#16a34a" : "#dc2626";
        const bodyTop = y(Math.max(c.open, c.close));
        const bodyBottom = y(Math.min(c.open, c.close));
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(x, y(c.high));
        ctx.lineTo(x, y(c.low));
        ctx.stroke();
        ctx.fillRect(
          x - Math.max(2, xStep * 0.28),
          bodyTop,
          Math.max(3, xStep * 0.56),
          Math.max(2, bodyBottom - bodyTop)
        );
      }});
      ctx.fillStyle = "#374151";
      ctx.font = "12px Arial";
      ctx.fillText(max.toFixed(5), 4, pad + 4);
      ctx.fillText(min.toFixed(5), 4, height - pad);
    }}

    const ws = new WebSocket(`ws://${{location.host}}/ws/status`);
    ws.onmessage = event => {{
      const payload = JSON.parse(event.data);
      live.textContent = JSON.stringify(payload.status, null, 2);
      const selected = symbolSelect.value;
      drawChart(payload.candles[selected] || []);
    }};
    ws.onerror = () => {{
      live.textContent = "WebSocket unavailable. Refresh or use /status.";
    }};
    document.querySelectorAll("button[data-action]").forEach(button => {{
      button.addEventListener("click", async () => {{
        button.disabled = true;
        try {{
          const response = await fetch(button.dataset.action, {{ method: "POST" }});
          const payload = await response.json();
          live.textContent = JSON.stringify(payload, null, 2);
        }} catch (error) {{
          live.textContent = String(error);
        }} finally {{
          button.disabled = false;
        }}
      }});
    }});
    symbolSelect.addEventListener("change", async () => {{
      const response = await fetch(`/market/candles?symbol=${{symbolSelect.value}}`);
      const payload = await response.json();
      drawChart(payload.candles);
    }});
    async function refreshProfiles() {{
      const response = await fetch("/profiles");
      const payload = await response.json();
      document.getElementById("profiles").innerHTML = payload.profiles.map(profile => `
        <tr>
          <td>${{profile.name}}</td>
          <td>${{profile.username}}</td>
          <td>${{profile.account_type}}</td>
          <td>${{profile.connected}}</td>
          <td>${{profile.last_error || ""}}</td>
          <td><button data-profile-test="${{profile.name}}">Test</button></td>
        </tr>
      `).join("");
    }}
    document.getElementById("profileForm").addEventListener("submit", async event => {{
      event.preventDefault();
      const form = new FormData(event.target);
      const payload = Object.fromEntries(form.entries());
      const response = await fetch("/profiles/ig", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      live.textContent = JSON.stringify(await response.json(), null, 2);
      await refreshProfiles();
    }});
    document.addEventListener("click", async event => {{
      const button = event.target.closest("button[data-profile-test]");
      if (!button) return;
      button.disabled = true;
      try {{
        const name = encodeURIComponent(button.dataset.profileTest);
        const response = await fetch(`/profiles/${{name}}/ig/test`, {{ method: "POST" }});
        live.textContent = JSON.stringify(await response.json(), null, 2);
        await refreshProfiles();
      }} finally {{
        button.disabled = false;
      }}
    }});
  </script>
</body>
</html>"""


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
async def status() -> dict:
    settings = get_settings()
    bot = get_bot()
    last_event = bot.last_event or {}
    return {
        "mode": settings.MODE.value,
        "live_trading_enabled": settings.live_enabled,
        "running": bot.running,
        "symbols": bot.symbols,
        "primary_timeframe": settings.PRIMARY_TIMEFRAME,
        "htf_timeframes": settings.htf_timeframes,
        "balance": await bot.broker.balance(),
        "open_positions": len(await bot.broker.positions()),
        "last_event": last_event.get("status", "none"),
        "last_reason": last_event.get("reason", ""),
        "allow_all_sessions": bot.strategy.allow_all_sessions,
        "ig_configured": bool(
            settings.IG_API_KEY.get_secret_value()
            and settings.IG_USERNAME
            and settings.IG_PASSWORD.get_secret_value()
        ),
        "ig_account_type": settings.IG_ACCOUNT_TYPE,
    }


@app.get("/broker/ig/test")
async def test_ig_connection() -> dict:
    settings = get_settings()
    broker = IGBroker(settings)
    try:
        return await broker.test_connection()
    except (RuntimeError, IGAuthError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"IG request failed: {exc}") from exc


@app.get("/profiles")
async def list_profiles() -> dict:
    return {"profiles": profile_store.list_public()}


@app.post("/profiles/ig")
async def save_ig_profile(payload: IGProfileRequest) -> dict:
    try:
        profile = profile_store.upsert_ig(
            name=payload.name,
            api_key=payload.api_key,
            username=payload.username,
            password=payload.password,
            account_type=payload.account_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "saved", "profile": profile.public()}


@app.post("/profiles/{profile_name}/ig/test")
async def test_profile_ig(profile_name: str) -> dict:
    try:
        profile = profile_store.get(profile_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile_name}") from exc

    broker = IGBroker(profile.settings(get_settings()))
    try:
        result = await broker.test_connection()
    except (RuntimeError, IGAuthError, HTTPError) as exc:
        profile.mark_failed(str(exc))
        return {"status": "failed", "profile": profile.public()}

    profile.mark_connected(result.get("account_id"))
    return {"status": "connected", "profile": profile.public(), "ig": result}


@app.post("/bot/start")
async def start() -> dict:
    bot = get_bot()
    return bot.start_auto()


@app.post("/bot/stop")
async def stop() -> dict:
    bot = get_bot()
    bot.stop()
    return {"status": "stopped"}


@app.post("/bot/session/all")
async def allow_all_sessions() -> dict:
    settings = get_settings()
    if settings.MODE not in {Mode.PAPER, Mode.BACKTEST}:
        raise HTTPException(
            status_code=403,
            detail="session override is paper/backtest only",
        )
    bot = get_bot()
    bot.strategy.allow_all_sessions = True
    return {"status": "ok", "allow_all_sessions": True}


@app.post("/bot/session/filtered")
async def filtered_sessions() -> dict:
    bot = get_bot()
    bot.strategy.allow_all_sessions = False
    return {"status": "ok", "allow_all_sessions": False}


@app.post("/bot/tick")
async def tick(symbol: str | None = None) -> dict:
    try:
        return await get_bot().tick(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {symbol}") from exc


@app.get("/market/candles")
async def candles(symbol: str | None = Query(default=None)) -> dict:
    bot = get_bot()
    try:
        market = bot.market(symbol)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown symbol: {symbol}") from exc
    return {"symbol": market.symbol, "candles": market.candles_json()}


@app.post("/bot/emergency-stop")
async def emergency_stop() -> dict:
    bot = get_bot()
    bot.stop()
    closed = await bot.broker.close_all("emergency stop")
    return {"status": "emergency_stopped", "closed": closed}


@app.post("/trade/paper-test")
async def paper_test_trade() -> dict:
    settings = get_settings()
    if settings.MODE not in {Mode.PAPER, Mode.BACKTEST}:
        raise HTTPException(
            status_code=403,
            detail="manual dashboard trade is paper-only",
        )

    bot = get_bot()
    symbol = settings.symbols[0] if settings.symbols else "EURUSD"
    signal = TradeSignal(
        symbol=symbol,
        side=SignalSide.BUY,
        score=100,
        entry=1.1000,
        stop_loss=1.0980,
        take_profit=1.1100,
        reason="manual paper dashboard test trade",
    )
    equity = await bot.broker.balance()
    sized = bot.risk.size_signal(signal, equity)
    order = bot.risk.order_from_signal(sized)
    approved, reason = bot.risk.validate_order(order, equity)
    if not approved:
        return {"status": "rejected", "reason": reason}
    result = await bot.broker.submit(order)
    result["score"] = sized.score
    result["reason"] = sized.reason
    return result


@app.get("/trades")
async def trades() -> dict:
    bot = get_bot()
    return {
        "orders": getattr(bot.broker, "history", []),
        "signals": bot.events[-100:],
    }


@app.websocket("/ws/status")
async def ws_status(websocket: WebSocket) -> None:
    await websocket.accept()
    with contextlib.suppress(WebSocketDisconnect, ConnectionClosed, RuntimeError):
        while True:
            bot = get_bot()
            await websocket.send_json(
                {
                    "status": await status(),
                    "candles": {
                        symbol: market.candles_json()
                        for symbol, market in bot.markets.items()
                    },
                    "last_event": bot.last_event,
                }
            )
            await asyncio.sleep(2)
