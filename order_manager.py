# Core business logic for Order Service.
#
# OrderManager owns the full lifecycle of an order  creation, retrieval,
# and cancellation. Storage is an in-memory dict for the Iteration 1 sample.
#
# All cross-service calls to Inventory go through inventory_client  this
# file never touches HTTP, URLs, or JSON. That separation keeps the
# business logic testable and readable.

import uuid
from datetime import datetime, timezone

from codeatlas.ecommerce.order_service import inventory_client
from codeatlas.ecommerce.order_service.models import Order, OrderItem, OrderStatus


class OrderManager:
    """
    Manages the lifecycle of customer orders.

    Every order created is stored in an in-memory dict keyed by order_id.
    Creation reserves stock via Inventory Service; cancellation releases it.
    A production version would persist orders to a database  the public
    method signatures would stay the same, only storage internals change.
    """

    def __init__(self) -> None:
        """
        Initialises an empty order ledger.

        Same trade-off as StockManager  in-memory storage is fine for
        the sample but resets on restart.
        """
        self._orders: dict[str, Order] = {}

    def _generate_order_id(self) -> str:
        """
        Generates a unique order ID.

        Uses uuid4 rather than a sequential counter because sequential IDs
        leak business information (how many orders exist, growth rate)
        and are trivial to guess for URL-poking attackers.
        """
        return str(uuid.uuid4())

    def _current_timestamp(self) -> str:
        """
        Returns the current UTC time as an ISO 8601 string.

        UTC because timestamps that carry a timezone are unambiguous 
        the same instant means the same string regardless of where the
        service runs. Storing as string keeps Order trivially JSON-serialisable.
        """
        return datetime.now(tz=timezone.utc).isoformat()

    def _reserve_all_items(self, items: list[OrderItem]) -> list[OrderItem]:
        """
        Reserves stock for every item in the list via Inventory Service.

        Returns the list of items that were successfully reserved. If any
        item fails to reserve, immediately rolls back all prior successful
        reservations by calling release_stock, then raises ValueError.

        The rollback is essential  without it a partial failure would
        leave stock permanently held for an order that will never exist.
        """
        reserved_items: list[OrderItem] = []

        for item in items:
            success = inventory_client.reserve_stock(item.product_id, item.quantity)

            if not success:
                # roll back everything already reserved for this order
                # This ensures that we do not leave stock allocated for a
                # non-existent order if any reservation fails.
                self._release_items(reserved_items)
                raise ValueError(
                    f"Could not reserve {item.quantity} units of {item.product_id}"
                )

            reserved_items.append(item)

        return reserved_items

    def _release_items(self, items: list[OrderItem]) -> None:
        """
        Releases stock for every item in the list via Inventory Service.

        Used for two things  rolling back partial reservations during a
        failed create_order, and freeing reserved stock during cancel_order.
        Both cases have the same shape: given a list of items, tell
        Inventory to release each one.
        """
        for item in items:
            inventory_client.release_stock(item.product_id, item.quantity)

    def create_order(self, customer_id: str, items: list[OrderItem]) -> Order:
        """
        Creates a new order for a customer.

        Steps:
        1. Reserve stock for every item via Inventory Service (with rollback on failure)
        2. Build the Order in PENDING status with a fresh ID and timestamp
        3. Store it and return it

        Reservation happens before order creation  this is deliberate.
        If we created the order first and then reserved, a stock failure
        would leave a phantom order in the ledger. Reserving first means
        no order exists until stock is safely held.
        """
        # step 1  reserve stock; raises if any item cannot be reserved
        self._reserve_all_items(items)

        # step 2  build the order record
        order = Order(
            order_id=self._generate_order_id(),
            customer_id=customer_id,
            items=list(items),
            status=OrderStatus.PENDING,
            created_at=self._current_timestamp(),
        )

        # step 3  persist and return
        self._orders[order.order_id] = order
        return order

    def get_order(self, order_id: str) -> Order:
        """
        Fetches one order by its ID.

        Raises KeyError if the order does not exist. Callers (handlers)
        translate this into a 404 response for the client.
        """
        if order_id not in self._orders:
            raise KeyError(f"Order not found: {order_id}")
        return self._orders[order_id]

    def cancel_order(self, order_id: str) -> Order:
        """
        Cancels an existing order and releases its reserved stock.

        Steps:
        1. Fetch the order (raises if not found)
        2. Reject the cancel if the order is already cancelled or completed 
           cancelling a cancelled order is a no-op, cancelling a completed
           one would incorrectly return stock that has already shipped
        3. Release the reserved stock via Inventory Service
        4. Mark the order as CANCELLED

        Stock release happens before status change  if the release call
        fails we would rather leave the order visibly PENDING (so a retry
        is possible) than mark it CANCELLED with stock still held.
        """
        order = self.get_order(order_id)

        if order.status != OrderStatus.PENDING:
            raise ValueError(
                f"Cannot cancel order {order_id}: status is {order.status.value}"
            )

        # release first, then mark cancelled  never the other way round
        self._release_items(order.items)
        order.status = OrderStatus.CANCELLED

        return order
