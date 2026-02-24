"""FastAPI backend for the trading bot - exposes REST API for the Next.js UI."""

import math
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# In-memory store for pending trade confirmations (token -> trade params)
_pending_trades: dict[str, dict] = {}

# Load .env from project root (includes BINANCE_*, GROQ_API_KEY)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import from trading_bot
from trading_bot.bot.ai_bot import chat as ai_chat, run_bot as run_ai_bot
from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.exceptions import (
    BinanceAPIError,
    ConfigurationError,
    NetworkError,
    ValidationError,
)
from trading_bot.bot.orders import place_order


def extract_symbol_from_message(message: str) -> str:
    """Extract trading symbol from user message. E.g. 'analyze BTC' -> BTCUSDT."""
    text = message.upper().strip()
    # Full symbol like BTCUSDT, ETHUSDT
    m = re.search(r"\b([A-Z]{2,10}USDT)\b", text)
    if m:
        return m.group(1)
    # Short names: BTC, ETH, BNB, SOL, etc.
    tokens = ["BTC", "ETH", "BNB", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "MATIC", "UNI", "ATOM", "LTC", "NEAR", "APT", "ARB", "OP", "INJ", "SUI", "PEPE", "WIF", "BONK", "SHIB"]
    for t in tokens:
        if re.search(rf"\b{t}\b", text):
            return f"{t}USDT"
    return "BTCUSDT"


def parse_user_order(message: str) -> dict | None:
    """
    Parse user-specified order from message. E.g.:
    - "limit order at 61000 for 100 dollar btcusdt"
    - "buy btc at 61000 with 100 usdt"
    - "limit buy btcusdt 61000 100 dollars"
    Returns dict with symbol, side, order_type, price, quantity or None.
    """
    lower = message.lower()
    # Detect side
    side = "BUY"
    if re.search(r"\bsell\b", lower) or re.search(r"\bshort\b", lower):
        side = "SELL"

    # Detect limit vs market
    order_type = "MARKET"
    if re.search(r"\blimit\b", lower) or re.search(r"\bat\s+\d+", lower):
        order_type = "LIMIT"

    # Extract price (e.g. "at 61000", "61000", "price 61000")
    price_match = re.search(r"(?:at|@|price)\s*(\d+(?:\.\d+)?)|(?:^|\s)(\d{4,}\.?\d*)(?:\s|$|dollar|usdt|usd)", lower)
    price = None
    if price_match:
        price = price_match.group(1) or price_match.group(2)
    if not price and order_type == "LIMIT":
        return None

    # Extract USD amount (e.g. "100 dollar", "100 usdt", "100 usd", "for 100")
    amount_match = re.search(r"(?:for|with|of)\s*(\d+(?:\.\d+)?)\s*(?:dollar|usdt|usd)?|(\d+(?:\.\d+)?)\s*(?:dollar|usdt|usd)", lower)
    amount_usd = None
    if amount_match:
        amount_usd = float(amount_match.group(1) or amount_match.group(2))
    # Fallback: look for number before dollar/usdt
    if not amount_usd:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:dollar|usdt|usd)", lower)
        if match:
            amount_usd = float(match.group(1))

    symbol = extract_symbol_from_message(message)

    # Compute quantity: amount_usd / price = base asset amount
    # Binance precision: BTCUSDT=3 decimals (step 0.001), ETH=3, most alts 1-4
    PRECISION = {"BTCUSDT": 3, "ETHUSDT": 3, "BNBUSDT": 2}
    if amount_usd and price:
        price_f = float(price)
        if price_f <= 0:
            return None
        quantity = amount_usd / price_f
        decimals = PRECISION.get(symbol, 3)
        quantity = round(quantity, decimals)
        # Ensure min notional 100 USDT: if qty*price < 100, round up to next step
        step = 10 ** (-decimals)
        if quantity * price_f < 100:
            min_qty = 100 / price_f
            quantity = math.ceil(min_qty / step) * step
        quantity = round(quantity, decimals)
        if quantity <= 0:
            return None
        return {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "price": str(price),
            "quantity": str(quantity),
            "reason": f"User specified: {side} {quantity} {symbol} @ {price} (~{amount_usd} USDT)",
        }
    # If limit but no amount, try quantity directly
    qty_match = re.search(r"(\d+\.?\d*)\s*(?:btc|eth|bnb)", lower)
    if qty_match and price:
        return {
            "symbol": symbol,
            "side": side,
            "order_type": order_type,
            "price": str(price),
            "quantity": qty_match.group(1),
            "reason": f"User specified: {side} {qty_match.group(1)} {symbol} @ {price}",
        }
    return None


def get_client() -> BinanceFuturesClient:
    """Create Binance client from environment variables."""
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Check API credentials on startup."""
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        print("Warning: BINANCE_API_KEY and BINANCE_API_SECRET not set. Order API will fail.")
    yield


app = FastAPI(
    title="Binance Futures Testnet Trading Bot API",
    description="REST API for placing orders on Binance Futures Testnet",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response Models ---


class PlaceOrderRequest(BaseModel):
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    side: str = Field(..., description="BUY or SELL")
    order_type: str = Field(..., description="MARKET or LIMIT")
    quantity: str = Field(..., description="Order quantity")
    price: str | None = Field(None, description="Limit price (required for LIMIT)")
    time_in_force: str = Field("GTC", description="GTC, IOC, or FOK for LIMIT orders")


class PlaceOrderResponse(BaseModel):
    success: bool = True
    message: str = "Order placed successfully"
    order_id: int | None = None
    status: str | None = None
    executed_qty: str | None = None
    avg_price: str | None = None
    raw_response: dict | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    api_configured: bool = False
    groq_configured: bool = False


class RunBotRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="Trading symbol")


class RunBotResponse(BaseModel):
    action: str  # BUY, SELL, HOLD
    reason: str | None = None
    order_type: str | None = None
    quantity: str | None = None
    price: str | None = None
    order_response: dict | None = None
    error: str | None = None
    decision: dict | None = None


class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="message content")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User message (include token name, e.g. BTC, ETH)")
    history: list[ChatMessage] | None = Field(default=None, description="Chat history")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Bot reply")
    trade_result: RunBotResponse | None = Field(default=None, description="If trade was executed")
    pending_trade: dict | None = Field(default=None, description="Trade awaiting confirmation")


class ConfirmTradeRequest(BaseModel):
    token: str = Field(..., description="Confirmation token from pending_trade")


# --- Endpoints ---


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Check API health and configuration."""
    api_configured = bool(
        os.environ.get("BINANCE_API_KEY") and os.environ.get("BINANCE_API_SECRET")
    )
    groq_configured = bool(os.environ.get("GROQ_API_KEY"))
    return HealthResponse(
        api_configured=api_configured, groq_configured=groq_configured
    )


@app.post("/api/run-bot", response_model=RunBotResponse)
async def api_run_bot(req: RunBotRequest | None = Body(default=None)):
    """Run the AI trading bot. Bot analyzes market and decides BUY/SELL/HOLD."""
    symbol = req.symbol if req else "BTCUSDT"
    try:
        client = get_client()
        groq_key = os.environ.get("GROQ_API_KEY", "")
        result = run_ai_bot(
            binance_client=client,
            groq_api_key=groq_key,
            symbol=symbol,
        )
        return RunBotResponse(
            action=result.get("action", "HOLD"),
            reason=result.get("reason"),
            order_type=result.get("order_type"),
            quantity=result.get("quantity"),
            price=result.get("price"),
            order_response=result.get("order_response"),
            error=result.get("error"),
            decision=result.get("decision"),
        )
    except ConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _format_open_orders(orders: list) -> str:
    """Format open orders for display."""
    if not orders:
        return "No open orders."
    lines = []
    for o in orders:
        lines.append(
            f"  • {o.get('symbol')} {o.get('side')} {o.get('type')} "
            f"qty={o.get('origQty')} price={o.get('price', 'market')} status={o.get('status')}"
        )
    return "\n".join(lines)


def _format_positions(positions: list) -> str:
    """Format positions for display (only non-zero)."""
    active = [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    if not active:
        return "No open positions."
    lines = []
    for p in active:
        amt = float(p.get("positionAmt", 0))
        side = "LONG" if amt > 0 else "SHORT"
        lines.append(
            f"  • {p.get('symbol')} {side} {abs(amt)} "
            f"entry={p.get('entryPrice')} mark={p.get('markPrice')} "
            f"uPnL={p.get('unRealizedProfit')}"
        )
    return "\n".join(lines)


@app.post("/api/chat", response_model=ChatResponse)
async def api_chat(req: ChatRequest):
    """Chat with the AI trading bot. Bot has market context and responds conversationally."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY not configured")
    symbol = extract_symbol_from_message(req.message)
    history = (
        [{"role": m.role, "content": m.content} for m in req.history]
        if req.history
        else None
    )
    try:
        user_message = req.message
        # If user asks for trades/orders/positions, fetch and inject into context
        lower = req.message.lower()
        fetch_trades = any(
            x in lower
            for x in (
                "fetch my trades",
                "open orders",
                "my orders",
                "show orders",
                "positions",
                "my positions",
                "show positions",
                "running trades",
                "active orders",
            )
        )
        if fetch_trades:
            try:
                client = get_client()
                orders = client.get_open_orders(None)  # All symbols
                positions = client.get_position_risk(None)  # All symbols
                orders_str = _format_open_orders(orders)
                positions_str = _format_positions(positions)
                user_message = (
                    f"{req.message}\n\n[User's account data - use this to answer:]"
                    f"\nOpen orders:\n{orders_str}\n\nPositions:\n{positions_str}"
                )
            except Exception as e:
                user_message = f"{req.message}\n\n[Could not fetch account data: {e}]"
        # Check if user specified exact order (e.g. "limit buy at 61000 for 100 dollar")
        user_order = parse_user_order(req.message)
        lower = req.message.lower()
        trade_result = None
        pending_trade = None
        place_intent = any(
            x in lower
            for x in (
                "place trade", "execute", "run bot", "place order", "trade now",
                "do it", "place", "limit order", "market order", "buy ", "sell ",
            )
        )
        if place_intent and user_order:
            # User specified exact order - use it, skip AI
            reply = f"Got it. {user_order['side']} {user_order['quantity']} {user_order['symbol']} @ {user_order.get('price', 'market')} ({user_order['order_type']})."
            token = str(uuid.uuid4())
            _pending_trades[token] = {
                "symbol": user_order["symbol"],
                "action": user_order["side"],
                "order_type": user_order["order_type"],
                "quantity": user_order["quantity"],
                "price": user_order.get("price"),
                "reason": user_order.get("reason"),
            }
            pending_trade = {
                "token": token,
                "symbol": user_order["symbol"],
                "action": user_order["side"],
                "order_type": user_order["order_type"],
                "quantity": user_order["quantity"],
                "price": user_order.get("price"),
                "reason": user_order.get("reason"),
            }
            reply += f"\n\n⚠️ Confirm: {user_order['side']} {user_order['quantity']} {user_order['symbol']} @ {user_order.get('price', 'market')} ({user_order['order_type']}). Click Confirm below."
        else:
            reply = ai_chat(
                groq_api_key=groq_key,
                user_message=user_message,
                symbol=symbol,
                history=history,
            )
            if place_intent:
                # No parsed order - run AI to decide
                try:
                    client = get_client()
                    result = run_ai_bot(
                        binance_client=client,
                        groq_api_key=groq_key,
                        symbol=symbol,
                        execute=False,
                    )
                    if result.get("action") == "HOLD":
                        reply += f"\n\n⏸️ Decided to HOLD: {result.get('reason', '')}"
                    else:
                        token = str(uuid.uuid4())
                        _pending_trades[token] = {
                            "symbol": symbol,
                            "action": result.get("action"),
                            "order_type": result.get("order_type"),
                            "quantity": result.get("quantity"),
                            "price": result.get("price"),
                            "reason": result.get("reason"),
                        }
                        pending_trade = {
                            "token": token,
                            "symbol": symbol,
                            "action": result.get("action"),
                            "order_type": result.get("order_type"),
                            "quantity": result.get("quantity"),
                            "price": result.get("price"),
                            "reason": result.get("reason"),
                        }
                        reply += f"\n\n⚠️ Confirm to place: {result.get('action')} {result.get('quantity', '')} {symbol} ({result.get('order_type', 'MARKET')}). Click Confirm below."
                except Exception as e:
                    reply += f"\n\n❌ Analysis failed: {e}"
        return ChatResponse(reply=reply, trade_result=trade_result, pending_trade=pending_trade)
    except ConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/confirm-trade", response_model=RunBotResponse)
async def api_confirm_trade(req: ConfirmTradeRequest):
    """Confirm and execute a pending trade."""
    token = req.token
    if token not in _pending_trades:
        raise HTTPException(status_code=400, detail="Invalid or expired confirmation token")
    params = _pending_trades.pop(token)
    try:
        client = get_client()
        response = place_order(
            client=client,
            symbol=params["symbol"],
            side=params["action"],
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params.get("price"),
        )
        return RunBotResponse(
            action=params["action"],
            reason=params.get("reason"),
            order_type=params["order_type"],
            quantity=params["quantity"],
            price=params.get("price"),
            order_response=response,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/order", response_model=PlaceOrderResponse)
async def api_place_order(req: PlaceOrderRequest):
    """Place a MARKET or LIMIT order on Binance Futures Testnet."""
    try:
        client = get_client()
        response = place_order(
            client=client,
            symbol=req.symbol,
            side=req.side,
            order_type=req.order_type,
            quantity=req.quantity,
            price=req.price,
            time_in_force=req.time_in_force,
        )
        return PlaceOrderResponse(
            success=True,
            message="Order placed successfully",
            order_id=response.get("orderId"),
            status=response.get("status"),
            executed_qty=response.get("executedQty"),
            avg_price=response.get("avgPrice"),
            raw_response=response,
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except BinanceAPIError as e:
        raise HTTPException(
            status_code=400,
            detail=e.response.get("msg", str(e)),
        )
    except NetworkError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/symbols")
async def get_symbols():
    """Fetch available symbols from Binance (public endpoint, no auth)."""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://demo-fapi.binance.com/fapi/v1/exchangeInfo",
                timeout=10.0,
            )
        info = r.json()
        symbols = [
            s["symbol"]
            for s in info.get("symbols", [])
            if s.get("status") == "TRADING" and s.get("symbol", "").endswith("USDT")
        ]
        return {"symbols": sorted(symbols)[:50]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
