# Would-be HTTP entry points for Order Service.
#
# Same pattern as Inventory Service's main.py — thin handlers that parse
# inputs, call into OrderManager, and format the response. Any real HTTP
# framework (FastAPI, Flask) would wrap these into routes.

from models import Order, OrderItem
from order_manager import OrderManager


# Single OrderManager instance shared across all handlers.
# Same reasoning as Inventory Service — module-level state means every
# request in the same process sees the same orders.
order_manager = OrderManager()


def order_item_from_dict(raw: dict) -> OrderItem:
    """
    Builds an OrderItem from a JSON dict.

    Used when a create_order request comes in — the items in the request
    body are dicts, and we need OrderItem dataclasses to pass to
    OrderManager. Kept as a helper so the conversion happens in one place.
    """
    return OrderItem(
        product_id=raw["product_id"],
        quantity=raw["quantity"],
    )


def order_to_dict(order: Order) -> dict:
    """
    Converts an Order dataclass into a JSON-serialisable dict.

    Same idea as inventory_service's stock_level_to_dict — every response
    that returns an order goes through this so the wire format is defined
    in one place.
    """
    return {
        "order_id":    order.order_id,
        "customer_id": order.customer_id,
        "status":      order.status.value,
        "created_at":  order.created_at,
        "items": [
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in order.items
        ],
    }


def handle_create_order(customer_id: str, items: list[dict]) -> dict:
    """
    Handles an order creation request.

    In HTTP terms: POST /orders  {"customer_id": ..., "items": [...]}

    Converts raw dict items into OrderItem objects, then calls
    OrderManager.create_order which reserves stock via Inventory Service
    and creates the order. Any reservation failure comes back as a
    ValueError which we translate into an error response.
    """
    if not items:
        return {"success": False, "error": "Cannot create order with empty cart"}

    order_items = [order_item_from_dict(item) for item in items]

    try:
        order = order_manager.create_order(customer_id, order_items)
    except ValueError as error:
        return {"success": False, "error": str(error)}

    return {"success": True, "order": order_to_dict(order)}


def handle_get_order(order_id: str) -> dict:
    """
    Handles an order lookup request.

    In HTTP terms: GET /orders/{order_id}
    Returns the order if found, or an error response if not.
    """
    try:
        order = order_manager.get_order(order_id)
    except KeyError as error:
        return {"success": False, "error": str(error)}

    return {"success": True, "order": order_to_dict(order)}


def handle_cancel_order(order_id: str) -> dict:
    """
    Handles an order cancellation request.

    In HTTP terms: POST /orders/{order_id}/cancel
    Releases the reserved stock via Inventory Service and marks the
    order as CANCELLED. Fails if the order was already cancelled or
    completed — those states are terminal.
    """
    try:
        order = order_manager.cancel_order(order_id)
    except (KeyError, ValueError) as error:
        return {"success": False, "error": str(error)}

    return {"success": True, "order": order_to_dict(order)}


# New validation function to check item quantities

def validate_order_items(items: list[dict]) -> None:
    for item in items:
        if item["quantity"] < 1:
            raise ValueError(f"Item {item["product_id"]} has invalid quantity: {item["quantity"]}")
