"""Inventory domain objects. Stock may be unknown for pre-existing menu items."""
from __future__ import annotations

from dataclasses import dataclass
from models import MenuItem, _integer, _text


class InventoryItem(MenuItem):
    def __init__(self, item_id: str, name: str, price: int, category: str,
                 stock: int | None, active: bool = True) -> None:
        super().__init__(item_id, name, price)
        self.category = _text(category, "Category")
        self.stock = None if stock is None else _integer(stock, "Stock")
        self.active = active

    def describe(self) -> str:
        return "Stock not set" if self.stock is None else f"{self.stock} in stock"


@dataclass(frozen=True)
class StockMovement:
    id: int
    item_id: str
    item_name: str
    created_at: str
    before: int | None
    after: int
    reason: str
    order_number: int | None = None

    @property
    def difference(self) -> int | None:
        return None if self.before is None else self.after - self.before


@dataclass(frozen=True)
class SalesReport:
    start_date: str
    end_date: str
    order_count: int
    units_sold: int
    gross_sales: int
    cash_sales: int
    qr_sales: int
    cash_orders: int
    qr_orders: int
    by_product: tuple[tuple[str, int, int], ...]  # name, units, sales
    by_day: tuple[tuple[str, int, int], ...]  # date, orders, sales
