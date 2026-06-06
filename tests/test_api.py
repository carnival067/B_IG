from __future__ import annotations

from fastapi.testclient import TestClient

from b_ig.api.main import app
from b_ig.api.state import get_bot
from b_ig.config import get_settings


def test_homepage_has_trade_button() -> None:
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Paper Test Trade" in response.text
    assert "Allow All Sessions" in response.text
    assert "/trade/paper-test" in response.text


def test_paper_trade_endpoint_places_virtual_order() -> None:
    get_bot.cache_clear()
    client = TestClient(app)
    response = client.post("/trade/paper-test")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "filled"
    assert payload["mode"] == "PAPER"
    assert payload["order"]["symbol"] == "EURUSD"
    assert client.get("/status").json()["open_positions"] == 1
    get_bot.cache_clear()


def test_market_candles_and_tick_endpoint() -> None:
    get_bot.cache_clear()
    client = TestClient(app)
    candles = client.get("/market/candles").json()
    assert candles["symbol"] == "EURUSD"
    assert len(candles["candles"]) > 20
    tick = client.post("/bot/tick").json()
    assert tick["status"] == "scanned"
    assert tick["results"]
    trades = client.get("/trades").json()
    assert "signals" in trades
    get_bot.cache_clear()


def test_multiple_currency_pairs_are_available(monkeypatch) -> None:
    get_bot.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setenv("SYMBOLS", "EURUSD,GBPUSD,USDJPY")
    client = TestClient(app)
    status = client.get("/status").json()
    assert status["symbols"] == ["EURUSD", "GBPUSD", "USDJPY"]
    gbp = client.get("/market/candles", params={"symbol": "GBPUSD"}).json()
    assert gbp["symbol"] == "GBPUSD"
    tick = client.post("/bot/tick").json()
    assert len(tick["results"]) == 3
    get_bot.cache_clear()
    get_settings.cache_clear()


def test_allow_all_sessions_toggle() -> None:
    get_bot.cache_clear()
    client = TestClient(app)
    assert client.get("/status").json()["allow_all_sessions"] is False
    response = client.post("/bot/session/all")
    assert response.status_code == 200
    assert response.json()["allow_all_sessions"] is True
    assert client.get("/status").json()["allow_all_sessions"] is True
    response = client.post("/bot/session/filtered")
    assert response.status_code == 200
    assert client.get("/status").json()["allow_all_sessions"] is False
    get_bot.cache_clear()


def test_ig_connection_requires_credentials(monkeypatch) -> None:
    get_bot.cache_clear()
    get_settings.cache_clear()
    monkeypatch.setenv("IG_API_KEY", "")
    monkeypatch.setenv("IG_USERNAME", "")
    monkeypatch.setenv("IG_PASSWORD", "")
    response = TestClient(app).get("/broker/ig/test")
    assert response.status_code == 400
    assert "credentials" in response.json()["detail"].lower()
    get_bot.cache_clear()
    get_settings.cache_clear()


def test_profile_credentials_are_saved_as_masked_status() -> None:
    client = TestClient(app)
    response = client.post(
        "/profiles/ig",
        json={
            "name": "akshay",
            "api_key": "abc123456xyz",
            "username": "demo_user",
            "password": "secret-password",
            "account_type": "DEMO",
        },
    )
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["name"] == "akshay"
    assert profile["api_key_masked"] == "abc...xyz"
    assert profile["password_saved"] is True
    listed = client.get("/profiles").json()["profiles"]
    assert any(item["name"] == "akshay" for item in listed)
    assert "secret-password" not in str(listed)


def test_unknown_profile_connection_returns_404() -> None:
    response = TestClient(app).post("/profiles/missing/ig/test")
    assert response.status_code == 404
