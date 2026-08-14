# order_service

Owns customer orders. Handles the lifecycle of an order from creation through cancellation.

## What this folder contains

- `models.py` — `Order` and `OrderItem` dataclasses, plus the `OrderStatus` enum
- `order_manager.py` — `OrderManager` class with the core business logic (create, get, cancel)
- `inventory_client.py` — HTTP client used to talk to Inventory Service
- `main.py` — would-be HTTP handlers (plain functions that route incoming requests to `OrderManager`)

## Why this exists

Orders are their own domain — they have status transitions, customer associations, and a history. Keeping order logic separate from stock logic means each service stays small, focused, and independently deployable.

## Operations exposed

| Operation | Purpose |
|---|---|
| `create_order(customer_id, items)` | Reserve stock for each item via Inventory Service, then create the order in `PENDING` status |
| `get_order(order_id)` | Fetch one order by ID |
| `cancel_order(order_id)` | Release the reserved stock via Inventory Service, then mark the order as `CANCELLED` |

## How it fits into the larger system

Order Service **depends on Inventory Service** — it cannot function without it. Every `create_order` and `cancel_order` triggers an HTTP call to Inventory Service. This dependency is isolated inside `inventory_client.py` so the rest of the code does not need to know Inventory's URL, endpoints, or request format.

```
create_order() ──▶ inventory_client.reserve_stock() ──HTTP──▶ Inventory Service
cancel_order() ──▶ inventory_client.release_stock() ──HTTP──▶ Inventory Service
```

## Data storage

In-memory Python dict keyed by `order_id`. Same reasoning as Inventory Service — the `OrderManager` class hides the storage detail so it can be swapped for a database later without changing the public API.

## Why the HTTP client is a separate file

Isolating all cross-service communication in `inventory_client.py` means:

- The Order Service business logic never sees HTTP details — it just calls Python functions like `reserve_stock(product_id, quantity)`.
- If Inventory's URL or API contract changes, only one file needs updating.
- The client can be replaced with a mock in tests without touching business logic.
