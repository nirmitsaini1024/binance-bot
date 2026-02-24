"""Order placement logic."""

from typing import Any

from trading_bot.bot.client import BinanceFuturesClient
from trading_bot.bot.exceptions import BinanceAPIError, ValidationError
from trading_bot.bot.validators import (
    validate_client_order_id,
    validate_order_type,
    validate_price,
    validate_quantity,
    validate_side,
    validate_symbol,
    validate_time_in_force,
)


def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: str | float | None = None,
    time_in_force: str = "GTC",
    client_order_id: str | None = None,
) -> dict[str, Any]:
    """
    Validate inputs and place an order via the Binance client.
    Returns the order response from the API.
    """
    symbol = validate_symbol(symbol)
    side = validate_side(side)
    order_type = validate_order_type(order_type)
    quantity = validate_quantity(quantity)
    time_in_force = validate_time_in_force(time_in_force)
    client_order_id = validate_client_order_id(client_order_id)

    is_limit = order_type == "LIMIT"
    price_str = validate_price(price, required=is_limit)

    if is_limit and not price_str:
        raise ValidationError("Price is required for LIMIT orders.")

    response = client.place_order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price_str,
        time_in_force=time_in_force,
        new_client_order_id=client_order_id,
    )

    return response


def format_order_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str,
    price: str | None,
) -> str:
    """Format a human-readable order request summary."""
    lines = [
        "--- Order Request Summary ---",
        f"  Symbol:     {symbol}",
        f"  Side:       {side}",
        f"  Type:       {order_type}",
        f"  Quantity:   {quantity}",
    ]
    if price:
        lines.append(f"  Price:      {price}")
    lines.append("----------------------------")
    return "\n".join(lines)


def format_order_response(response: dict[str, Any]) -> str:
    """Format order response for display."""
    order_id = response.get("orderId", "N/A")
    status = response.get("status", "N/A")
    executed_qty = response.get("executedQty", "0")
    avg_price = response.get("avgPrice", "0.00000")
    cum_qty = response.get("cumQty", "0")
    cum_quote = response.get("cumQuote", "0")

    lines = [
        "--- Order Response ---",
        f"  Order ID:     {order_id}",
        f"  Status:       {status}",
        f"  Executed Qty: {executed_qty}",
        f"  Avg Price:    {avg_price}",
        f"  Cum Qty:      {cum_qty}",
        f"  Cum Quote:    {cum_quote}",
        "----------------------",
    ]
    return "\n".join(lines)
