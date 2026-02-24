# Binance Futures Testnet Trading Bot

A Python application that places orders on **Binance Futures Testnet (USDT-M)** with a Next.js chat UI. Supports MARKET and LIMIT orders, AI-powered trade suggestions, and natural-language order parsing (e.g. "limit buy BTC at 62000 for 100 usdt").

## Features

- **AI Trading Bot** – Groq-powered analysis and trade suggestions
- **Chat UI** – Natural-language orders and account queries ("fetch my trades", "open orders", "positions")
- **User-specified orders** – Parse messages like "limit order at 62000 for 100 dollar btcusdt"
- **Confirmation flow** – Pending trades require explicit Confirm before execution
- **Quantity precision** – Auto-rounds to exchange step size (e.g. BTCUSDT: 0.001) and enforces min notional (100 USDT)

## Setup

### 1. Binance Futures Testnet Account

1. Register at [Binance Futures Demo](https://demo.binance.com)
2. Generate API credentials (API Key + Secret) in API Management
3. Save them for the next steps

### 2. Python Environment

```bash
cd /path/to/binance-testnet
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
|----------|-------------|
| `BINANCE_API_KEY` | Testnet API key from [demo.binance.com](https://demo.binance.com) |
| `BINANCE_API_SECRET` | Testnet API secret |
| `GROQ_API_KEY` | From [Groq Console](https://console.groq.com) — used by the AI bot |

Optional (for UI):

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | API base URL (default: `http://localhost:8000`) — set in `ui/.env.local` |

## How to Run

### Web UI (recommended)

1. Start the API server (from project root):

```bash
source venv/bin/activate
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Start the Next.js frontend:

```bash
cd ui
npm install
# Optional: echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) and chat with the bot. Example prompts:
   - "limit order at 62000 place order of 100 dollar for btcusdt"
   - "fetch my trades"
   - "open orders"
   - "positions"

### AI Trading Bot (CLI)

```bash
source venv/bin/activate
python -m trading_bot run-bot
python -m trading_bot run-bot --symbol ETHUSDT
```

### Manual Order (CLI)

```bash
# MARKET order
python -m trading_bot order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# LIMIT order
python -m trading_bot order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 50000
```

### Direct Order Script

```bash
python scripts/place_order_direct.py
```

## Project Structure

```
binance-testnet/
├── api/
│   └── main.py            # FastAPI REST API (chat, order, confirm-trade)
├── trading_bot/
│   ├── bot/
│   │   ├── ai_bot.py      # Groq chat and trade logic
│   │   ├── client.py      # Binance API client
│   │   ├── orders.py      # Order placement
│   │   ├── validators.py  # Input validation
│   │   ├── exceptions.py
│   │   └── logging_config.py
│   ├── cli.py
│   └── __main__.py
├── ui/                    # Next.js chat frontend
├── scripts/
│   └── place_order_direct.py
├── logs/                  # Log files (created on first run)
├── .env                   # Your credentials (not committed)
├── .env.example           # Template for .env
├── requirements.txt
└── README.md
```

## Log Files

Logs are written to `logs/trading_bot_YYYY-MM-DD.log`.

## Evaluation Checklist

- [x] Places MARKET and LIMIT orders on testnet
- [x] Supports BUY and SELL
- [x] CLI with argparse
- [x] Structured code, logging, exception handling
- [x] Next.js chat UI with AI bot
- [x] User-specified orders and confirmation flow

## Assumptions

- **Demo only**: Uses `https://demo-fapi.binance.com` — no real funds
- **USDT-M Futures**: One-way mode (positionSide: BOTH)
- **Min notional**: 100 USDT per order
- **Quantity precision**: BTCUSDT/ETHUSDT 3 decimals (step 0.001), BNBUSDT 2 decimals
