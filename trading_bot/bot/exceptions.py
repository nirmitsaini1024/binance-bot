"""Custom exceptions for the trading bot."""


class TradingBotError(Exception):
    """Base exception for trading bot."""

    pass


class ValidationError(TradingBotError):
    """Raised when input validation fails."""

    pass


class BinanceAPIError(TradingBotError):
    """Raised when Binance API returns an error."""

    def __init__(self, message: str, code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.code = code
        self.response = response or {}


class NetworkError(TradingBotError):
    """Raised when a network/connection error occurs."""

    pass


class ConfigurationError(TradingBotError):
    """Raised when configuration is missing or invalid."""

    pass
