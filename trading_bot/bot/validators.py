"""Input validation for order parameters."""

import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from trading_bot.bot.exceptions import ValidationError


# Symbol pattern: alphanumeric, typically like BTCUSDT, ETHUSDT
SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{5,20}$")
# Client order ID pattern per Binance docs
CLIENT_ORDER_ID_PATTERN = re.compile(r"^[\.A-Z\:/a-z0-9_-]{1,36}$")


def validate_symbol(symbol: str) -> str:
    """Validate trading symbol (e.g., BTCUSDT)."""
    if not symbol or not isinstance(symbol, str):
        raise ValidationError("Symbol is required and must be a non-empty string")
    s = symbol.strip().upper()
    if not SYMBOL_PATTERN.match(s):
        raise ValidationError(
            f"Invalid symbol '{symbol}'. Use format like BTCUSDT, ETHUSDT."
        )
    return s


def validate_side(side: str) -> str:
    """Validate order side (BUY or SELL)."""
    if not side or not isinstance(side, str):
        raise ValidationError("Side is required and must be BUY or SELL")
    s = side.strip().upper()
    if s not in ("BUY", "SELL"):
        raise ValidationError(f"Invalid side '{side}'. Must be BUY or SELL.")
    return s


def validate_order_type(order_type: str) -> str:
    """Validate order type (MARKET or LIMIT)."""
    if not order_type or not isinstance(order_type, str):
        raise ValidationError("Order type is required and must be MARKET or LIMIT")
    t = order_type.strip().upper()
    if t not in ("MARKET", "LIMIT"):
        raise ValidationError(f"Invalid order type '{order_type}'. Must be MARKET or LIMIT.")
    return t


def validate_quantity(quantity: str | float) -> str:
    """Validate quantity as positive decimal string."""
    try:
        q = Decimal(str(quantity))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"Invalid quantity '{quantity}'. Must be a positive number.")
    if q <= 0:
        raise ValidationError("Quantity must be greater than zero.")
    return str(q)


def validate_price(price: str | float, required: bool = False) -> Optional[str]:
    """Validate price as positive decimal string. Required for LIMIT orders."""
    if price is None or (isinstance(price, str) and not price.strip()):
        if required:
            raise ValidationError("Price is required for LIMIT orders.")
        return None
    try:
        p = Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError(f"Invalid price '{price}'. Must be a positive number.")
    if p <= 0:
        raise ValidationError("Price must be greater than zero.")
    return str(p)


def validate_time_in_force(tif: str) -> str:
    """Validate timeInForce for LIMIT orders (GTC, IOC, FOK)."""
    if not tif or not isinstance(tif, str):
        return "GTC"  # default
    t = tif.strip().upper()
    if t not in ("GTC", "IOC", "FOK"):
        raise ValidationError(
            f"Invalid timeInForce '{tif}'. Must be GTC, IOC, or FOK."
        )
    return t


def validate_client_order_id(client_order_id: Optional[str]) -> Optional[str]:
    """Validate optional client order ID per Binance rules."""
    if client_order_id is None or (isinstance(client_order_id, str) and not client_order_id.strip()):
        return None
    s = client_order_id.strip()
    if not CLIENT_ORDER_ID_PATTERN.match(s):
        raise ValidationError(
            f"Invalid clientOrderId. Must match ^[.A-Z:/a-z0-9_-]{{1,36}}$"
        )
    return s
