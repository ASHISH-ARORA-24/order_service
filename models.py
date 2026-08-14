# Data models for Order Service.
#
# Same design principle as Inventory Service's models.py — plain data
# holders, no business logic. Kept in their own file so the shape of an
# order can be understood without reading any orchestration code.

from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    """
    The possible states an order can be in.

    Inherits from str so the enum members serialise as their string values
    directly — no custom encoder needed when converting to JSON.

    - PENDING   : order created, stock reserved, awaiting payment/fulfilment
    - COMPLETED : order fulfilled — reserved stock has been shipped
    - CANCELLED : order abandoned — reserved stock has been released back
    """

    PENDING   = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    """
    A single line item within an order.

    An order can contain many items. Each item is one product and a
    quantity — the price is intentionally not stored here because prices
    can change, and an order's price should be captured at the Order level
    at the moment of creation.
    """

    product_id: str
    quantity: int


@dataclass
class Order:
    """
    A customer order.

    Uses field(default_factory=list) for items rather than items=[] because
    a bare mutable default is shared across every Order instance — a
    classic Python gotcha. default_factory calls list() fresh per instance.

    created_at is stored as an ISO 8601 string rather than a datetime
    object so the Order is trivially JSON-serialisable without a custom
    encoder.
    """

    order_id: str
    customer_id: str
    items: list[OrderItem] = field(default_factory=list)
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = ""
