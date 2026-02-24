"""Binance Futures Testnet API client wrapper. Uses binance-futures-connector for reliable signing."""

import os
from typing import Any

from binance.um_futures import UMFutures

from trading_bot.bot.exceptions import BinanceAPIError, ConfigurationError, NetworkError
from trading_bot.bot.logging_config import setup_logging

logger = setup_logging(console_output=False)

# Official USDT-M Futures testnet (matches demo.binance.com)
BINANCE_TESTNET_BASE_URL = "https://demo-fapi.binance.com"


class BinanceFuturesClient:
    """
    Client for Binance USDT-M Futures Testnet API.
    Uses binance-futures-connector for correct HMAC signing.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str | None = None,
    ):
        api_key = (api_key or "").strip()
        api_secret = (api_secret or "").strip()
        if not api_key or not api_secret:
            raise ConfigurationError(
                "API key and API secret are required. "
                "Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables."
            )
        self.api_key = api_key
        self.api_secret = api_secret
        base = (base_url or os.environ.get("BINANCE_BASE_URL") or BINANCE_TESTNET_BASE_URL).rstrip("/")
        self._client = UMFutures(key=api_key, secret=api_secret, base_url=base)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None = None,
        time_in_force: str = "GTC",
        new_client_order_id: str | None = None,
        new_order_resp_type: str = "RESULT",
    ) -> dict[str, Any]:
        """Place a new order on Binance Futures Testnet."""
        try:
            params: dict[str, Any] = {
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": float(quantity),
                "newOrderRespType": new_order_resp_type,
            }
            if order_type == "LIMIT":
                if not price:
                    raise BinanceAPIError("Price is required for LIMIT orders")
                params["price"] = float(price)
                params["timeInForce"] = time_in_force
            if new_client_order_id:
                params["newClientOrderId"] = new_client_order_id
            result = self._client.new_order(**params)
            return result
        except Exception as e:
            err_msg = str(e)
            code = getattr(e, "code", None)
            if hasattr(e, "error_message"):
                err_msg = e.error_message
            if hasattr(e, "response") and e.response:
                try:
                    data = e.response.json() if hasattr(e.response, "json") else {}
                    err_msg = data.get("msg", err_msg)
                    code = data.get("code", code)
                    raise BinanceAPIError(err_msg, code=code, response=data) from e
                except BinanceAPIError:
                    raise
                except Exception:
                    pass
            raise BinanceAPIError(err_msg, code=code) from e

    def get_account_info(self) -> dict[str, Any]:
        """Get account information."""
        return self._client.account()

    def get_exchange_info(self) -> dict[str, Any]:
        """Get exchange info (symbols, filters, etc.)."""
        return self._client.exchange_info()

    def get_ticker_price(self, symbol: str) -> dict[str, Any]:
        """Get current price for symbol."""
        return self._client.ticker_price(symbol=symbol)

    def get_klines(
        self, symbol: str, interval: str = "15m", limit: int = 20
    ) -> list[list]:
        """Get kline/candlestick data."""
        return self._client.klines(symbol=symbol, interval=interval, limit=limit)

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Get all open orders. Optionally filter by symbol."""
        if symbol:
            return self._client.get_orders(symbol=symbol)
        return self._client.get_orders()

    def get_position_risk(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Get position information. Optionally filter by symbol."""
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        return self._client.get_position_risk(**params)
