#!/usr/bin/env python3
"""Place an order directly via Binance API - no confirmation. Use to test if orders show in Binance UI."""

import os
import sys
from pathlib import Path

# Add project root for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def main():
    api_key = os.environ.get("BINANCE_API_KEY", "").strip()
    api_secret = os.environ.get("BINANCE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        print("Error: Set BINANCE_API_KEY and BINANCE_API_SECRET in .env")
        sys.exit(1)

    try:
        from binance.um_futures import UMFutures
    except ImportError:
        print("Installing binance-futures-connector...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "binance-futures-connector", "-q"])
        from binance.um_futures import UMFutures

    # Min notional is 100 USDT. 0.002 BTC * 61000 = 122 USDT
    client = UMFutures(key=api_key, secret=api_secret, base_url="https://demo-fapi.binance.com")
    print("Placing LIMIT BUY: 0.002 BTCUSDT @ 61000 (~122 USDT)...")
    response = client.new_order(
        symbol="BTCUSDT",
        side="BUY",
        type="LIMIT",
        quantity=0.002,
        price=61000,
        timeInForce="GTC",
    )
    print("Success!")
    print(f"  Order ID: {response.get('orderId')}")
    print(f"  Status: {response.get('status')}")
    print(f"  Symbol: {response.get('symbol')}")
    print(f"  Side: {response.get('side')} {response.get('origQty')} @ {response.get('price')}")
    print("\nCheck demo.binance.com → Futures → Open Orders → BTCUSDT")

if __name__ == "__main__":
    main()
