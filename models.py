"""Menu, cart and ticket business rules. This module never imports Flet."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

MAX_QUANTITY = 99
ReceiptLines = tuple[tuple[str, int, int], ...]  # name, quantity, line subtotal


def _integer(value: int, label: str, minimum: int = 0) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a whole number.")
    if value < minimum:
        raise ValueError(f"{label} must be at least {minimum}.")
    return value


def _text(value: str, label: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{label} must be text.")
    value = value.strip()
    if not value or any(ord(c) < 32 for c in value):
        raise ValueError(f"{label} must be nonempty, single-line text.")
    return value


def peso(amount: int) -> str:
    """Format a nonnegative whole-peso amount without floating-point rounding."""
    return f"₱{_integer(amount, 'Amount'):,}"


class Priceable(ABC):
    @property
    @abstractmethod
    def price(self) -> int: ...

    @abstractmethod
    def describe(self) -> str: ...


class MenuItem(Priceable):
    category = "Menu"
    prep_minutes = 3

    def __init__(self, item_id: str, name: str, price: int) -> None:
        self._id = _text(item_id, "Item ID")
        self._name = _text(name, "Item name")
        self._price = _integer(price, "Price")

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def price(self) -> int:
        return self._price

    def describe(self) -> str:
        return f"Ready in about {self.prep_minutes} min"


class Coffee(MenuItem):
    category, prep_minutes = "Coffee", 4

    def describe(self) -> str:
        return "Espresso-based"


class Special(MenuItem):
    category, prep_minutes = "Specials", 5

    def describe(self) -> str:
        return "A house favourite"


class NonCoffee(MenuItem):
    category, prep_minutes = "Non Coffee", 3

    def describe(self) -> str:
        # Non-coffee does not necessarily mean caffeine-free (e.g. cocoa).
        return "Made without coffee"


class Soda(MenuItem):
    category, prep_minutes = "Soda", 2

    def describe(self) -> str:
        return "Sparkling and iced"


class CartItem(Priceable):
    def __init__(self, item: MenuItem, quantity: int = 1) -> None:
        if not isinstance(item, MenuItem):
            raise TypeError("Cart items must be menu items.")
        self._item = item
        self.quantity = quantity

    @property
    def item(self) -> MenuItem:
        return self._item

    @property
    def quantity(self) -> int:
        return self._quantity

    @quantity.setter
    def quantity(self, value: int) -> None:
        _integer(value, "Quantity", 1)
        if value > MAX_QUANTITY:
            raise ValueError(f"You can order up to {MAX_QUANTITY} of each drink.")
        self._quantity = value

    @property
    def price(self) -> int:
        return self.item.price * self.quantity

    def describe(self) -> str:
        return f"{self.quantity} x {self.item.name}"


@dataclass(frozen=True)
class Receipt:
    """Immutable order ticket, not a payment receipt or tax document."""
    number: int
    lines: ReceiptLines
    total: int
    created_at: str = ""
    request_id: str = ""
    payment_method: str = ""
    cash_received: int | None = None
    change_due: int | None = None

    def __post_init__(self) -> None:
        _integer(self.number, "Order number", 1)
        _integer(self.total, "Total")
        rows = tuple(tuple(row) for row in self.lines)
        if not rows:
            raise ValueError("An order must contain at least one item.")
        for row in rows:
            if len(row) != 3:
                raise ValueError("Invalid order line.")
            name, quantity, subtotal = row
            _text(name, "Item name")
            _integer(quantity, "Quantity", 1)
            if quantity > MAX_QUANTITY:
                raise ValueError("Order line quantity exceeds the limit.")
            _integer(subtotal, "Subtotal")
            if subtotal % quantity:
                raise ValueError("The subtotal must represent a whole-peso unit price.")
        if sum(row[2] for row in rows) != self.total:
            raise ValueError("The order total does not match its lines.")
        if self.payment_method not in ("", "CASH", "QR"):
            raise ValueError("Unsupported payment method.")
        if self.payment_method == "CASH":
            _integer(self.cash_received, "Cash received", self.total)
            if self.change_due != self.cash_received - self.total:
                raise ValueError("Incorrect cash change.")
        elif self.cash_received is not None or self.change_due is not None:
            raise ValueError("Cash details require cash payment.")
        object.__setattr__(self, "lines", rows)

    @property
    def payment_status(self) -> str:
        return "PAID" if self.payment_method else "PAYMENT PENDING"

    def to_text(self) -> str:
        lines = ["LUMAH CAF", f"Order #{self.number:03d}", self.payment_status]
        if self.created_at:
            lines.append(f"Saved: {self.created_at} (UTC)")
        lines += ["-" * 36]
        lines += [f"{q} x {name}  {peso(subtotal)}" for name, q, subtotal in self.lines]
        lines += ["-" * 36, f"TOTAL: {peso(self.total)}"]
        if self.payment_method:
            lines.append(f"Method: {self.payment_method}")
            if self.payment_method == "CASH":
                lines += [f"Cash: {peso(self.cash_received)}", f"Change: {peso(self.change_due)}"]
            lines += ["", "Payment recorded by cashier; not an official receipt."]
        else:
            lines += ["", "Pay at the counter and show this order number.",
                      "Order ticket only; not proof of payment."]
        return "\n".join(lines) + "\n"


class Cart:
    """Owns mutable lines and exposes detached snapshots to callers."""
    def __init__(self) -> None:
        self._lines: dict[str, CartItem] = {}

    def add(self, item: MenuItem, quantity: int = 1) -> None:
        candidate = CartItem(item, quantity)  # validate before changing any state
        existing = self._lines.get(item.id)
        if existing is not None:
            if (existing.item.name, existing.item.price) != (item.name, item.price):
                raise ValueError("A menu item changed. Start a new order.")
            existing.quantity += quantity
        else:
            self._lines[item.id] = candidate

    def change_quantity(self, item_id: str, delta: int) -> None:
        if type(delta) is not int:
            raise TypeError("Quantity change must be a whole number.")
        line = self._lines.get(item_id)
        if line is None:
            return
        if line.quantity + delta < 1:
            self.remove(item_id)
        else:
            line.quantity += delta

    def remove(self, item_id: str) -> None:
        self._lines.pop(item_id, None)

    def clear(self) -> None:
        self._lines.clear()

    def quantity_of(self, item_id: str) -> int:
        line = self._lines.get(item_id)
        return line.quantity if line else 0

    @property
    def lines(self) -> tuple[CartItem, ...]:
        return tuple(CartItem(line.item, line.quantity) for line in self._lines.values())

    @property
    def count(self) -> int:
        return sum(line.quantity for line in self._lines.values())

    @property
    def total(self) -> int:
        return sum(line.price for line in self._lines.values())

    def is_empty(self) -> bool:
        return not self._lines

    def to_receipt(self, number: int) -> Receipt:
        rows = tuple((line.item.name, line.quantity, line.price) for line in self.lines)
        return Receipt(number, rows, self.total)


class Menu:
    def __init__(self, items: list[MenuItem]) -> None:
        if not items:
            raise ValueError("The menu must contain at least one item.")
        self._items: dict[str, MenuItem] = {}
        for item in items:
            if not isinstance(item, MenuItem):
                raise TypeError("The menu can contain only menu items.")
            if item.id in self._items:
                raise ValueError(f"Duplicate menu item ID: {item.id}")
            self._items[item.id] = item

    def get(self, item_id: str) -> MenuItem:
        return self._items[item_id]

    def categories(self) -> list[str]:
        return list(dict.fromkeys(i.category for i in self._items.values()))

    def in_category(self, category: str) -> list[MenuItem]:
        return [i for i in self._items.values() if i.category == category]

    @classmethod
    def lumah_default(cls) -> Menu:
        rows = [
            (Coffee, "Cafe Latte", 79), (Coffee, "Cafe Mocha", 89),
            (Coffee, "Seasalt Latte", 89), (Coffee, "Spanish Latte", 89),
            (Coffee, "Salted Caramel", 89),
            (Special, "Hojicha Latte", 99), (Special, "Matcha Latte", 109),
            (Special, "Seasalt Hojicha", 119), (Special, "Seasalt Matcha", 129),
            (NonCoffee, "Chocoberry", 89), (NonCoffee, "Strawberry", 89),
            (NonCoffee, "Milo Dino", 79), (NonCoffee, "Choco", 79),
            (Soda, "Blue Lemonade", 59), (Soda, "Strawberry Soda", 59),
            (Soda, "Blueberry", 59), (Soda, "Green Apple", 59),
        ]
        return cls([kind(f"{kind.category[:2].lower()}-{name.lower().replace(' ', '-')}",
                         name, price) for kind, name, price in rows])
