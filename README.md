# Binance Futures Testnet Trading Bot

A Python application that places orders on **Binance Futures Testnet (USDT-M)** with a Next.js web UI. Supports MARKET and LIMIT orders for BUY and SELL.

## Setup

### 1. Binance Futures Testnet Account

1. Register at [Binance Futures Demo](https://demo.binance.com) (or testnet)
2. Generate API credentials (API Key + Secret)
3. Save them for the next steps

### 2. Python Environment

```bash
cd /path/to/binance-testnet
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the project root:

```bash
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_api_secret
GROQ_API_KEY=your_groq_api_key
```

- **BINANCE_***: From [Binance Demo](https://demo.binance.com) → API Management
- **GROQ_API_KEY**: From [Groq Console](https://console.groq.com) — used by the AI trading bot

### 4. Next.js UI (optional)

```bash
cd ui
npm install
# Create .env.local with: NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

## How to Run

### AI Trading Bot (recommended)

The bot uses Groq to analyze market data and place trades:

```bash
source venv/bin/activate
# Ensure .env has BINANCE_API_KEY, BINANCE_API_SECRET, GROQ_API_KEY

python -m trading_bot run-bot
python -m trading_bot run-bot --symbol ETHUSDT
```

### Manual Order (CLI)

Place a **MARKET** order:

```bash
python -m trading_bot order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

Place a **LIMIT** order:

```bash
python -m trading_bot order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 50000
```

### Web UI

1. Start the Python API server (from project root):

```bash
source venv/bin/activate
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

2. Start the Next.js frontend:

```bash
cd ui && npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) and place orders via the UI.

## Project Structure

```
binance-testnet/
├── trading_bot/           # Python trading bot
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── client.py      # Binance API client
│   │   ├── orders.py      # Order placement logic
│   │   ├── validators.py  # Input validation
│   │   ├── logging_config.py
│   │   └── exceptions.py
│   ├── cli.py             # CLI entry point
│   └── __main__.py
├── api/
│   └── main.py            # FastAPI REST API
├── ui/                    # Next.js frontend
│   └── src/
├── logs/                  # Log files (created on first run)
├── requirements.txt
└── README.md
```

## Log Files

Logs are written to `logs/trading_bot_YYYY-MM-DD.log`. Each run appends.

**To generate log files for submission** (with valid testnet credentials):

```bash
# MARKET order
python -m trading_bot -s BTCUSDT --side BUY --type MARKET -q 0.001

# LIMIT order
python -m trading_bot -s BTCUSDT --side SELL --type LIMIT -q 0.001 -p 95000
```

Then copy the relevant log file from `logs/`.

- API requests and responses
- Validation errors
- Network/API errors

Example log entries:

```
2025-02-24 10:00:00 | INFO     | trading_bot | API Request: POST /fapi/v1/order | params={...}
2025-02-24 10:00:01 | INFO     | trading_bot | API Response: status=200 | body={...}
```

## Assumptions

- **Demo only**: Uses `https://demo-fapi.binance.com` (matches demo.binance.com) — no real funds
- **USDT-M Futures**: One-way mode (positionSide: BOTH)
- **LIMIT default**: `timeInForce` defaults to GTC
- **Response type**: Uses `newOrderRespType=RESULT` for full order details

## Evaluation Checklist

- [x] Places MARKET and LIMIT orders on testnet
- [x] Supports BUY and SELL
- [x] CLI with argparse (symbol, side, type, quantity, price)
- [x] Clear output (request summary, response details, success/failure)
- [x] Structured code (client/API layer, CLI layer)
- [x] Logging to file
- [x] Exception handling (validation, API, network)
- [x] README with setup and run instructions
- [x] requirements.txt
- [x] Lightweight Next.js UI (bonus)
