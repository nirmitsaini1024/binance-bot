"""AI-powered trading bot using Groq LLM for trade decisions."""

import json
import re
from typing import Any

import httpx
from groq import Groq

from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.exceptions import ConfigurationError
from trading_bot.bot.logging_config import setup_logging
from trading_bot.bot.orders import place_order

logger = setup_logging(console_output=False)

CHAT_SYSTEM_PROMPT = """You are a friendly trading assistant for Binance Futures Testnet. You help users understand market data and make informed decisions.

You have access to live market data (current price, recent 15m candles). Be concise and helpful. When asked to analyze, explain what you see. When asked to trade or execute, you will place orders - but prefer HOLD when uncertain.

Keep responses conversational and under 200 words unless the user asks for detail."""

SYSTEM_PROMPT = """You are a cautious trading bot for Binance Futures Testnet. You analyze market data and decide whether to trade.

Given market data (current price, recent candles), respond with a JSON object only, no other text:
- action: "BUY" | "SELL" | "HOLD"
- order_type: "MARKET" | "LIMIT" (use MARKET for immediate execution)
- quantity: small decimal string (e.g. "0.001" for BTC)
- price: only for LIMIT orders, string or null
- reason: brief explanation

Rules:
- Prefer HOLD when uncertain. Only trade when you see a clear signal.
- Use small quantities (0.001-0.01 for BTC, 0.01-0.1 for ETH).
- For MARKET: set price to null.
- Return ONLY valid JSON, no markdown or extra text."""


def _parse_bot_response(text: str) -> dict[str, Any] | None:
    """Extract JSON from LLM response."""
    text = text.strip()
    # Try raw parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to extract from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try to find first { ... }
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def get_market_context_public(symbol: str) -> str:
    """Fetch market data via public API (no auth)."""
    base = "https://demo-fapi.binance.com"
    with httpx.Client(timeout=10.0) as c:
        r = c.get(f"{base}/fapi/v1/ticker/price", params={"symbol": symbol})
        ticker = r.json() if r.status_code == 200 else {}
        r2 = c.get(
            f"{base}/fapi/v1/klines",
            params={"symbol": symbol, "interval": "15m", "limit": 10},
        )
        klines = r2.json() if r2.status_code == 200 else []
    price = ticker.get("price", "N/A")
    candles = [
        {"open": k[1], "high": k[2], "low": k[3], "close": k[4], "volume": k[5]}
        for k in klines
    ]
    return f"""Symbol: {symbol}
Current price: {price}
Recent 15m candles (last 10):
{json.dumps(candles, indent=2)}"""


def get_market_context(client: BinanceFuturesClient, symbol: str) -> str:
    """Fetch market data and format for the LLM."""
    ticker = client.get_ticker_price(symbol)
    klines = client.get_klines(symbol, interval="15m", limit=10)
    price = ticker.get("price", "N/A")
    # klines: [open_time, open, high, low, close, volume, ...]
    candles = [
        {"open": k[1], "high": k[2], "low": k[3], "close": k[4], "volume": k[5]}
        for k in klines
    ]
    return f"""Symbol: {symbol}
Current price: {price}
Recent 15m candles (last 10):
{json.dumps(candles, indent=2)}"""


def run_bot(
    binance_client: BinanceFuturesClient,
    groq_api_key: str,
    symbol: str = "BTCUSDT",
    execute: bool = True,
) -> dict[str, Any]:
    """
    Run the AI bot: fetch market data, ask Groq for a decision.
    If execute=True and action is BUY/SELL, place order. Otherwise return decision only.
    """
    if not groq_api_key:
        raise ConfigurationError(
            "GROQ_API_KEY is required. Set it in .env or environment."
        )

    groq = Groq(api_key=groq_api_key)
    context = get_market_context(binance_client, symbol)

    user_prompt = f"""Market data:
{context}

What should we do? Respond with JSON only."""

    logger.info("Calling Groq for trading decision")
    completion = groq.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.3,
    )
    raw = completion.choices[0].message.content or ""
    logger.info("Groq response: %s", raw[:500])

    decision = _parse_bot_response(raw)
    if not decision:
        return {"action": "HOLD", "reason": "Failed to parse LLM response", "raw": raw}

    action = (decision.get("action") or "HOLD").upper()
    if action not in ("BUY", "SELL"):
        return {"action": "HOLD", "reason": decision.get("reason", "No trade"), "decision": decision}

    order_type = (decision.get("order_type") or "MARKET").upper()
    if order_type not in ("MARKET", "LIMIT"):
        order_type = "MARKET"
    quantity = str(decision.get("quantity", "0.001"))
    price = decision.get("price")

    if order_type == "LIMIT" and (not price or price == "null"):
        order_type = "MARKET"
        price = None

    if not execute:
        return {
            "action": action,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "reason": decision.get("reason", ""),
            "order_response": None,
            "decision": decision,
        }

    try:
        response = place_order(
            client=binance_client,
            symbol=symbol,
            side=action,
            order_type=order_type,
            quantity=quantity,
            price=price,
        )
        return {
            "action": action,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "reason": decision.get("reason", ""),
            "order_response": response,
        }
    except Exception as e:
        logger.exception("Order failed: %s", e)
        return {
            "action": action,
            "reason": decision.get("reason", ""),
            "error": str(e),
            "decision": decision,
        }


def chat(
    groq_api_key: str,
    user_message: str,
    symbol: str = "BTCUSDT",
    history: list[dict[str, str]] | None = None,
) -> str:
    """
    Conversational chat with the trading bot. Uses market context for informed replies.
    No Binance auth needed - uses public market data.
    """
    if not groq_api_key:
        raise ConfigurationError("GROQ_API_KEY is required.")
    context = get_market_context_public(symbol)
    groq = Groq(api_key=groq_api_key)
    system_content = f"""{CHAT_SYSTEM_PROMPT}

Current market data for {symbol}:
{context}"""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_content},
    ]
    if history:
        messages.extend(history[-10:])  # last 10 turns
    messages.append({"role": "user", "content": user_message})
    completion = groq.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=0.5,
    )
    return (completion.choices[0].message.content or "").strip()
