#!/usr/bin/env python3
"""CLI entry point for the Binance Futures Testnet trading bot."""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from trading_bot.bot.ai_bot import run_bot as run_ai_bot
from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.exceptions import (
    BinanceAPIError,
    ConfigurationError,
    NetworkError,
    ValidationError,
)
from trading_bot.bot.logging_config import setup_logging
from trading_bot.bot.orders import (
    format_order_response,
    format_order_summary,
    place_order,
)


def cmd_run_bot(args: argparse.Namespace) -> int:
    """Run the AI trading bot."""
    logger = setup_logging(console_output=not args.no_log_console)
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        print("\nError: GROQ_API_KEY is required. Set it in .env\n")
        return 1
    try:
        client = BinanceFuturesClient(
            api_key=args.api_key or os.environ.get("BINANCE_API_KEY", ""),
            api_secret=args.api_secret or os.environ.get("BINANCE_API_SECRET", ""),
        )
    except ConfigurationError as e:
        print(f"\nError: {e}\n")
        return 1
    print(f"\n--- AI Trading Bot ---\nSymbol: {args.symbol}\n")
    try:
        result = run_ai_bot(
            binance_client=client,
            groq_api_key=groq_key,
            symbol=args.symbol,
        )
        print(json.dumps(result, indent=2))
        if "order_response" in result:
            print("\n" + format_order_response(result["order_response"]))
            print("\nSuccess: Bot placed order.\n")
        elif result.get("action") == "HOLD":
            print("\nBot decided: HOLD (no trade)\n")
        else:
            print("\nBot attempted trade but encountered an error.\n")
        return 0
    except Exception as e:
        print(f"\nError: {e}\n")
        logger.exception("Bot error")
        return 1


def cmd_order(args: argparse.Namespace) -> int:
    """Place order manually via CLI."""
    logger = setup_logging(console_output=not args.no_log_console)
    try:
        client = BinanceFuturesClient(
            api_key=args.api_key or "",
            api_secret=args.api_secret or "",
        )
    except ConfigurationError as e:
        print(f"\nError: {e}\n")
        return 1

    # Print order request summary
    print(format_order_summary(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
    ))

    try:
        response = place_order(
            client=client,
            symbol=args.symbol,
            side=args.side,
            order_type=args.order_type,
            quantity=args.quantity,
            price=args.price,
            time_in_force=args.time_in_force,
            client_order_id=args.client_order_id,
        )

        print(format_order_response(response))
        print("\nSuccess: Order placed successfully.\n")
        return 0

    except ValidationError as e:
        print(f"\nValidation Error: {e}\n")
        logger.warning("Validation error: %s", e)
        return 1
    except BinanceAPIError as e:
        print(f"\nAPI Error: {e}\n")
        logger.error("Binance API error: %s", e)
        return 1
    except NetworkError as e:
        print(f"\nNetwork Error: {e}\n")
        logger.error("Network error: %s", e)
        return 1
    except Exception as e:
        print(f"\nUnexpected Error: {e}\n")
        logger.exception("Unexpected error")
        return 1


def main() -> int:
    """Parse arguments and dispatch to subcommand."""
    parser = argparse.ArgumentParser(description="Binance Futures Testnet Trading Bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bot_parser = subparsers.add_parser("run-bot", help="Run AI bot to place trades (uses Groq)")
    bot_parser.add_argument("--symbol", "-s", default="BTCUSDT", help="Trading symbol")
    bot_parser.add_argument("--api-key", default=os.environ.get("BINANCE_API_KEY"))
    bot_parser.add_argument("--api-secret", default=os.environ.get("BINANCE_API_SECRET"))
    bot_parser.add_argument("--no-log-console", action="store_true")
    bot_parser.set_defaults(func=cmd_run_bot)

    order_parser = subparsers.add_parser("order", help="Place order manually")
    order_parser.add_argument("--symbol", "-s", required=True, help="Trading symbol (e.g., BTCUSDT)")
    order_parser.add_argument("--side", required=True, choices=["BUY", "SELL"], help="Order side")
    order_parser.add_argument("--type", dest="order_type", required=True, choices=["MARKET", "LIMIT"], help="Order type")
    order_parser.add_argument("--quantity", "-q", required=True, help="Order quantity")
    order_parser.add_argument("--price", "-p", default=None, help="Limit price (required for LIMIT)")
    order_parser.add_argument("--time-in-force", "-t", default="GTC", choices=["GTC", "IOC", "FOK"])
    order_parser.add_argument("--client-order-id", default=None)
    order_parser.add_argument("--api-key", default=os.environ.get("BINANCE_API_KEY"))
    order_parser.add_argument("--api-secret", default=os.environ.get("BINANCE_API_SECRET"))
    order_parser.add_argument("--no-log-console", action="store_true")
    order_parser.set_defaults(func=cmd_order)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
