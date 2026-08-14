# HTTP client for talking to Inventory Service.
#
# Every cross-service call from Order Service to Inventory Service goes
# through this file. This is deliberate — isolating the network layer in
# one module means:
#   - Business logic (OrderManager) never sees requests/URLs/JSON parsing
#   - If Inventory Service moves or its API changes, only this file updates
#   - Tests can replace this module with a mock without touching order code
#
# This is a small example of the "anti-corruption layer" pattern from
# domain-driven design — a wall between our domain and another service's
# API shape.
#
# NOTE: This code is not runnable as-is — no Inventory Service is actually
# listening. The point is for CodeAtlas to index the shape of the cross-
# service calls, not to execute them.

import requests


# Base URL of the Inventory Service.
# In a real deployment this would come from an environment variable or a
# service discovery lookup. Hardcoded here for the sample.
INVENTORY_SERVICE_URL = "http://inventory-service:8000"

# Timeout for every HTTP call to Inventory Service, in seconds.
# Set low because Inventory is a fast local service — a slow response
# means something is wrong and we should fail rather than block the user.
HTTP_TIMEOUT_SECONDS = 2


def get_stock(product_id: str) -> dict:
    """
    Fetches the current stock level for a product from Inventory Service.

    HTTP call: GET /stock/{product_id}
    Returns the parsed JSON body — a dict with product_id, available,
    and reserved counts. Raises on HTTP error so callers know the read
    failed rather than getting silent stale data.
    """
    url = f"{INVENTORY_SERVICE_URL}/stock/{product_id}"
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def reserve_stock(product_id: str, quantity: int) -> bool:
    """
    Asks Inventory Service to reserve N units of a product.

    HTTP call: POST /stock/{product_id}/reserve  {"quantity": N}
    Called during order creation — one call per line item in the order.
    Returns True if the reservation succeeded, False if Inventory
    reported insufficient stock. The caller is responsible for rolling
    back any earlier successful reservations if a later one fails.
    """
    url  = f"{INVENTORY_SERVICE_URL}/stock/{product_id}/reserve"
    body = {"quantity": quantity}

    response = requests.post(url, json=body, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()

    return response.json().get("success", False)


def release_stock(product_id: str, quantity: int) -> None:
    """
    Asks Inventory Service to release a previous reservation.

    HTTP call: POST /stock/{product_id}/release  {"quantity": N}
    Called during order cancellation — one call per line item. Also
    called by create_order to roll back partial reservations when a
    later reservation in the same order fails.

    Does not return a value — release is fire-and-forget from the
    caller's perspective. If Inventory rejects the release we raise
    rather than silently swallowing, because that indicates a bug
    (releasing what was never reserved).
    """
    url  = f"{INVENTORY_SERVICE_URL}/stock/{product_id}/release"
    body = {"quantity": quantity}

    response = requests.post(url, json=body, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
