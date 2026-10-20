"""Application actions and observable state; deliberately independent of Flet."""
from __future__ import annotations

import logging
from threading import RLock
from typing import Callable
from uuid import uuid4

from models import Cart, CartItem, Menu, MenuItem, Receipt, ReceiptLines
from inventory import InventoryItem, SalesReport, StockMovement
from storage import OrderStore, SQLiteOrderStore, default_database_path

logger = logging.getLogger(__name__)


class KioskController:
    def __init__(self, menu: Menu | None = None, cart: Cart | None = None,
                 *, store: OrderStore | None = None) -> None:
        self._menu = menu if menu is not None else Menu.lumah_default()
        self._cart = cart if cart is not None else Cart()
        self._store = store if store is not None else SQLiteOrderStore(default_database_path())
        self._uses_inventory = menu is None and isinstance(self._store, SQLiteOrderStore)
        self._listeners: list[Callable[[], None]] = []
        self._lock = RLock()
        self._request_id: str | None = None
        self._last_receipt: Receipt | None = None

    def bind(self, listener: Callable[[], None]) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unbind(self, listener: Callable[[], None]) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify(self) -> None:
        with self._lock:
            listeners = tuple(self._listeners)
        for listener in listeners:
            try:
                listener()
            except Exception:
                # Rendering must not turn a committed order into an apparent failed save.
                logger.exception("A view refresh failed; the order state remains valid.")

    @property
    def last_receipt(self) -> Receipt | None:
        with self._lock:
            return self._last_receipt

    def categories(self) -> list[str]:
        return list(self._store.categories()) if self._uses_inventory else self._menu.categories()

    def items_in(self, category: str) -> list[MenuItem]:
        if self._uses_inventory:
            return [item for item in self._store.products() if item.category == category]
        return self._menu.in_category(category)

    def inventory(self, include_archived: bool = False) -> tuple[InventoryItem, ...]:
        return self._store.products(include_archived)

    def create_category(self, name: str) -> None:
        self._store.create_category(name)
        self._notify()

    def delete_category(self, name: str) -> None:
        self._store.delete_category(name)
        self._notify()

    def create_product(self, name: str, category: str, price: int, stock: int) -> str:
        iid = self._store.create_product(name, category, price, stock)
        self._notify()
        return iid

    def update_product(self, iid: str, name: str, category: str, price: int,
                       stock: int, reason: str = "STOCK COUNT / RESTOCK") -> None:
        self._store.update_product(iid, name, category, price, stock, reason)
        self._notify()

    def bulk_restock(self, amounts: dict[str, int], *, mode: str = "ADD",
                     reason: str = "BULK RESTOCK") -> None:
        self._store.bulk_restock(amounts, mode=mode, reason=reason)
        self._notify()

    def archive_product(self, iid: str) -> None:
        self._store.archive_product(iid)
        self._notify()

    def restore_product(self, iid: str) -> None:
        self._store.restore_product(iid)
        self._notify()

    def stock_movements(self, start: str | None = None, end: str | None = None):
        return self._store.movements(start, end)

    def stock_at(self, date_str: str) -> dict[str, int | None]:
        return self._store.stock_at(date_str)

    def order_history(self, start: str, end: str) -> tuple[Receipt, ...]:
        return self._store.orders_between(start, end)

    def sales_report(self, start: str, end: str) -> SalesReport:
        return self._store.sales_report(start, end)

    def cart_lines(self) -> tuple[CartItem, ...]:
        with self._lock:
            return self._cart.lines

    def cart_total(self) -> int:
        with self._lock:
            return self._cart.total

    def cart_count(self) -> int:
        with self._lock:
            return self._cart.count

    def quantity_of(self, item_id: str) -> int:
        with self._lock:
            return self._cart.quantity_of(item_id)

    def _change(self, action: Callable[[], None]) -> None:
        with self._lock:
            before = tuple((line.item.id, line.quantity) for line in self._cart.lines)
            action()
            after = tuple((line.item.id, line.quantity) for line in self._cart.lines)
            if before != after:
                self._request_id = None
        self._notify()

    def add_item(self, item_id: str) -> None:
        if self._uses_inventory:
            item = next((p for p in self._store.products() if p.id == item_id), None)
            if item is None:
                raise ValueError("That drink is not on the current menu.")
        else:
            try:
                item = self._menu.get(item_id)
            except KeyError as exc:
                raise ValueError("That drink is not on the current menu.") from exc
        def add():
            if isinstance(item, InventoryItem) and item.stock is not None:
                if self._cart.quantity_of(item_id) >= item.stock:
                    raise ValueError(f"Only {item.stock} of {item.name} available.")
            self._cart.add(item)
        self._change(add)

    def change_quantity(self, item_id: str, delta: int) -> None:
        def change():
            if delta > 0 and self._uses_inventory:
                item = next((p for p in self._store.products() if p.id == item_id), None)
                if item is None:
                    raise ValueError("That product is no longer available.")
                if item.stock is not None and self._cart.quantity_of(item_id) + delta > item.stock:
                    raise ValueError(f"Only {item.stock} of {item.name} available.")
            self._cart.change_quantity(item_id, delta)
        self._change(change)

    def remove_item(self, item_id: str) -> None:
        self._change(lambda: self._cart.remove(item_id))

    def clear_cart(self) -> None:
        self._change(self._cart.clear)

    def preview(self) -> Receipt | None:
        """Return a draft snapshot without saving or assigning an actual order number."""
        with self._lock:
            return None if self._cart.is_empty() else self._cart.to_receipt(1)

    def checkout(self, *, expected_lines: ReceiptLines | None = None,
                 payment_method: str = "", cash_received: int | None = None) -> Receipt | None:
        with self._lock:
            if self._cart.is_empty():
                return None
            draft = self._cart.to_receipt(1)
            if expected_lines is not None and draft.lines != expected_lines:
                raise ValueError("Your order changed. Please review it again before confirming.")
            if self._request_id is None:
                self._request_id = uuid4().hex
            options = {}
            if payment_method:
                options = {"payment_method": payment_method, "cash_received": cash_received}
            if self._uses_inventory:
                options["item_ids"] = tuple(line.item.id for line in self._cart.lines)
            receipt = self._store.save(draft.lines, draft.total,
                                       request_id=self._request_id, **options)
            self._last_receipt = receipt
            self._cart.clear()
            self._request_id = None
        self._notify()
        return receipt
