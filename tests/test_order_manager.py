# Tests for OrderManager.
#
# OrderManager calls inventory_client for stock reservation.
# inventory_client makes HTTP calls — we mock it in every test so
# tests are fast, deterministic, and require no running services.
#
# The empty-cart test is intentionally written before the validation exists.
# It will FAIL today. After the coder adds validation it will PASS.
# That is the point — tests define the expected behaviour before the code does.

import sys
import pytest
from pathlib import Path
from unittest.mock import patch

# Add the order_service folder to path so we can import its modules directly.
# Same pattern as inventory_service/tests/test_stock_manager.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from order_manager import OrderManager
from models import OrderItem, OrderStatus


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_manager():
    """Returns a fresh OrderManager for each test."""
    return OrderManager()

def make_items(n=1):
    """Returns n OrderItems for testing."""
    return [OrderItem(product_id=f"prod-{i}", quantity=i + 1) for i in range(n)]


# ── create_order ──────────────────────────────────────────────────────────────

def test_create_order_returns_pending_order():
    """A successful order is created with PENDING status."""
    manager = make_manager()
    items   = make_items(2)

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.return_value = True
        order = manager.create_order("customer-1", items)

    assert order.customer_id == "customer-1"
    assert order.status == OrderStatus.PENDING
    assert len(order.items) == 2
    assert order.order_id is not None


def test_create_order_stores_order():
    """Created order can be retrieved by its ID."""
    manager = make_manager()
    items   = make_items()

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.return_value = True
        order = manager.create_order("customer-1", items)

    retrieved = manager.get_order(order.order_id)
    assert retrieved.order_id == order.order_id


def test_create_order_rejects_empty_items():
    """
    Creating an order with no items should raise ValueError.

    This test FAILS before validation is added and PASSES after.
    The coder agent's job is to add this validation to OrderManager.create_order.
    """
    manager = make_manager()

    with pytest.raises(ValueError, match="empty"):
        manager.create_order("customer-1", [])


def test_create_order_rolls_back_on_partial_failure():
    """If one item fails to reserve, all prior reservations are released."""
    manager = make_manager()
    items   = make_items(2)

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.side_effect = [True, False]
        mock_client.release_stock.return_value = None

        with pytest.raises(ValueError):
            manager.create_order("customer-1", items)

        mock_client.release_stock.assert_called_once_with(items[0].product_id, items[0].quantity)


# ── get_order ─────────────────────────────────────────────────────────────────

def test_get_order_raises_for_unknown_id():
    """get_order raises KeyError for an ID that does not exist."""
    manager = make_manager()

    with pytest.raises(KeyError):
        manager.get_order("nonexistent-id")


# ── cancel_order ──────────────────────────────────────────────────────────────

def test_cancel_order_sets_cancelled_status():
    """Cancelling a pending order sets its status to CANCELLED."""
    manager = make_manager()
    items   = make_items()

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.return_value = True
        mock_client.release_stock.return_value = None
        order     = manager.create_order("customer-1", items)
        cancelled = manager.cancel_order(order.order_id)

    assert cancelled.status == OrderStatus.CANCELLED


def test_cancel_order_releases_stock():
    """Cancelling an order releases the reserved stock via inventory_client."""
    manager = make_manager()
    items   = make_items()

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.return_value = True
        mock_client.release_stock.return_value = None
        order = manager.create_order("customer-1", items)
        manager.cancel_order(order.order_id)

    mock_client.release_stock.assert_called_once_with(items[0].product_id, items[0].quantity)


def test_cancel_already_cancelled_order_raises():
    """Cancelling an already-cancelled order raises ValueError."""
    manager = make_manager()
    items   = make_items()

    with patch("order_manager.inventory_client") as mock_client:
        mock_client.reserve_stock.return_value = True
        mock_client.release_stock.return_value = None
        order = manager.create_order("customer-1", items)
        manager.cancel_order(order.order_id)

        with pytest.raises(ValueError):
            manager.cancel_order(order.order_id)
