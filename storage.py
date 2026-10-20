"""SQLite persistence for orders, payments, inventory and dated reports.

Existing version-1 order databases are upgraded in place without deleting orders.
A single BEGIN IMMEDIATE transaction checks stock, records payment and deducts stock.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
import os
from pathlib import Path
import sqlite3
from typing import Iterator, Protocol
from uuid import uuid4

from inventory import InventoryItem, SalesReport, StockMovement
from models import Menu, Receipt, ReceiptLines, _integer, _text

SCHEMA_VERSION = 2
APPLICATION_ID = 0x4B494F53
LOCAL_TZ = timezone(timedelta(hours=8))  # Philippine store reporting time


class OrderStoreError(RuntimeError):
    """Recoverable persistence error: never erase the cart on this exception."""


class OrderStore(Protocol):
    def save(self, lines: ReceiptLines, total: int, *, request_id: str) -> Receipt: ...


def default_database_path(data_dir: str | Path | None = None) -> Path:
    configured = data_dir or os.environ.get("KIOSKU_DATA_DIR")
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parent / "data"
    return root.resolve() / "orders.sqlite3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _range(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("Dates must be formatted YYYY-MM-DD.") from exc
    if start.isoformat() != start_date or end.isoformat() != end_date:
        raise ValueError("Dates must be formatted YYYY-MM-DD.")
    if start > end:
        raise ValueError("Start date cannot be after end date.")
    if end == date.max:
        raise ValueError("End date is too far in the future.")
    return (datetime.combine(start, time.min, LOCAL_TZ).astimezone(timezone.utc).isoformat(timespec="seconds"),
            datetime.combine(end + timedelta(days=1), time.min, LOCAL_TZ)
            .astimezone(timezone.utc).isoformat(timespec="seconds"))


class SQLiteOrderStore:
    def __init__(self, database: str | Path) -> None:
        if str(database) == ":memory:":
            raise ValueError("Use a file-backed database so data survives restarts.")
        self.path = Path(database).expanduser().resolve()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OrderStoreError("Cannot create the data directory.") from exc
        self._initialize()
        self._seed_menu()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(self.path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
        except (sqlite3.Error, OSError, OverflowError) as exc:
            raise OrderStoreError("Database unavailable. Data was not intentionally discarded; retry.") from exc
        finally:
            if connection is not None:
                connection.close()

    def _initialize(self) -> None:
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            app_id = db.execute("PRAGMA application_id").fetchone()[0]
            if version not in (0, 1, SCHEMA_VERSION):
                raise OrderStoreError("Unsupported database version; do not overwrite this file.")
            if version and app_id != APPLICATION_ID:
                raise OrderStoreError("This is not a Kiosku order database.")
            if version == 0:
                tables = db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                    "AND name NOT LIKE 'sqlite_%'").fetchall()
                if tables or app_id not in (0, APPLICATION_ID):
                    raise OrderStoreError("Refusing to modify an unrelated database.")
                db.execute("""CREATE TABLE orders (
                    number INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    total INTEGER NOT NULL CHECK(typeof(total)='integer' AND total >= 0)
                )""")
                db.execute("""CREATE TABLE order_lines (
                    order_number INTEGER NOT NULL REFERENCES orders(number),
                    position INTEGER NOT NULL, name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(typeof(quantity)='integer' AND quantity BETWEEN 1 AND 99),
                    subtotal INTEGER NOT NULL CHECK(typeof(subtotal)='integer' AND subtotal >= 0),
                    PRIMARY KEY (order_number, position)
                )""")
            else:
                db.execute("SELECT number, request_id, created_at, total FROM orders LIMIT 0")
                db.execute("SELECT order_number, position, name, quantity, subtotal FROM order_lines LIMIT 0")
            if version in (0, 1):
                db.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT NOT NULL DEFAULT ''")
                db.execute("ALTER TABLE orders ADD COLUMN cash_received INTEGER")
                db.execute("ALTER TABLE orders ADD COLUMN change_due INTEGER")
                db.execute("ALTER TABLE order_lines ADD COLUMN item_id TEXT")
                db.execute("""CREATE TABLE categories (
                    name TEXT PRIMARY KEY COLLATE NOCASE
                )""")
                db.execute("""CREATE TABLE products (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    category TEXT NOT NULL REFERENCES categories(name),
                    price INTEGER NOT NULL CHECK(price >= 0),
                    stock INTEGER CHECK(stock IS NULL OR stock >= 0),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    created_at TEXT NOT NULL
                )""")
                db.execute("""CREATE TABLE stock_movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL REFERENCES products(id),
                    created_at TEXT NOT NULL,
                    before_stock INTEGER, after_stock INTEGER NOT NULL CHECK(after_stock >= 0),
                    reason TEXT NOT NULL, order_number INTEGER REFERENCES orders(number)
                )""")
                db.execute("CREATE INDEX stock_movements_item_time ON stock_movements(item_id, created_at)")
                db.execute("CREATE INDEX orders_created ON orders(created_at)")
                db.execute(f"PRAGMA application_id = {APPLICATION_ID}")
                db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            else:
                db.execute("SELECT name FROM categories LIMIT 0")
                db.execute("SELECT id, name, category, price, stock, active FROM products LIMIT 0")
                db.execute("SELECT id, item_id, before_stock, after_stock FROM stock_movements LIMIT 0")
                db.execute("SELECT payment_method, cash_received, change_due FROM orders LIMIT 0")

    def _seed_menu(self) -> None:
        # The initial catalogue is seeded exactly once. The old menu had no stock
        # counts: NULL means "not initialized", never an invented balance.
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM products").fetchone()[0]:
                return
            for item in Menu.lumah_default()._items.values():
                db.execute("INSERT OR IGNORE INTO categories(name) VALUES (?)", (item.category,))
                db.execute("INSERT INTO products(id, name, category, price, stock, active, created_at) "
                           "VALUES(?,?,?,?,NULL,1,?)",
                           (item.id, item.name, item.category, item.price, _now()))

    @staticmethod
    def _receipt(db: sqlite3.Connection, row: sqlite3.Row) -> Receipt:
        lines = tuple((line["name"], line["quantity"], line["subtotal"])
                      for line in db.execute("SELECT name, quantity, subtotal FROM order_lines "
                                             "WHERE order_number=? ORDER BY position", (row["number"],)))
        try:
            return Receipt(row["number"], lines, row["total"], row["created_at"], row["request_id"],
                           row["payment_method"], row["cash_received"], row["change_due"])
        except (ValueError, TypeError) as exc:
            raise OrderStoreError("Saved order failed its integrity checks.") from exc

    def save(self, lines: ReceiptLines, total: int, *, request_id: str,
             payment_method: str = "", cash_received: int | None = None,
             item_ids: tuple[str, ...] | None = None) -> Receipt:
        draft = Receipt(1, lines, total)
        if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
            raise ValueError("A nonempty request ID of at most 128 characters is required.")
        if payment_method not in ("", "CASH", "QR"):
            raise ValueError("Choose Cash or QR payment.")
        change = None
        if payment_method == "CASH":
            _integer(cash_received, "Cash received", draft.total)
            change = cash_received - draft.total
        elif cash_received is not None:
            raise ValueError("Cash received applies only to cash payments.")
        if item_ids is not None and len(item_ids) != len(draft.lines):
            raise ValueError("Cart item IDs do not match the order lines.")
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT * FROM orders WHERE request_id=?", (request_id,)).fetchone()
            if previous is not None:
                saved = self._receipt(db, previous)
                if (saved.lines != draft.lines or saved.total != draft.total
                        or saved.payment_method != payment_method or saved.cash_received != cash_received):
                    raise OrderStoreError("This request was already used for a different order.")
                return saved
            # Check every stock balance before any insert, in the same write lock.
            changes = []
            if item_ids is not None:
                # Aggregate repeated product IDs. The normal cart has only one
                # row per product, but repository callers may supply more.
                requested: dict[str, int] = {}
                products = {}
                for iid, (name, qty, subtotal) in zip(item_ids, draft.lines):
                    row = db.execute("SELECT * FROM products WHERE id=?", (iid,)).fetchone()
                    if row is None or not row["active"]:
                        raise ValueError(f"{name} is no longer on sale. Review your order.")
                    if row["name"] != name or row["price"] * qty != subtotal:
                        raise ValueError(f"{name} has changed. Review your order.")
                    requested[iid] = requested.get(iid, 0) + qty
                    products[iid] = row
                for iid, qty in requested.items():
                    row = products[iid]
                    if row["stock"] is not None:
                        if row["stock"] < qty:
                            raise ValueError(f"Insufficient stock for {row['name']}: {row['stock']} left.")
                        changes.append((iid, row["stock"], row["stock"] - qty))
            created_at = _now()
            cursor = db.execute("INSERT INTO orders(request_id, created_at, total, payment_method, "
                                "cash_received, change_due) VALUES(?,?,?,?,?,?)",
                                (request_id, created_at, draft.total, payment_method, cash_received, change))
            number = cursor.lastrowid
            db.executemany("INSERT INTO order_lines(order_number,position,name,quantity,subtotal,item_id) "
                           "VALUES(?,?,?,?,?,?)",
                           [(number, pos, name, qty, subtotal, item_ids[pos] if item_ids else None)
                            for pos, (name, qty, subtotal) in enumerate(draft.lines)])
            for iid, before, after in changes:
                db.execute("UPDATE products SET stock=? WHERE id=?", (after, iid))
                db.execute("INSERT INTO stock_movements(item_id,created_at,before_stock,after_stock,reason,order_number) "
                           "VALUES(?,?,?,?,?,?)", (iid, created_at, before, after, "SALE", number))
            return Receipt(number, draft.lines, draft.total, created_at, request_id,
                           payment_method, cash_received, change)

    def get(self, number: int) -> Receipt | None:
        _integer(number, "Order number", 1)
        with self._connection() as db, db:
            db.execute("BEGIN")
            row = db.execute("SELECT * FROM orders WHERE number=?", (number,)).fetchone()
            return self._receipt(db, row) if row else None

    def recent(self, limit: int = 20) -> tuple[Receipt, ...]:
        _integer(limit, "Limit", 1)
        with self._connection() as db, db:
            db.execute("BEGIN")
            rows = db.execute("SELECT * FROM orders ORDER BY number DESC LIMIT ?", (limit,))
            return tuple(self._receipt(db, row) for row in rows)

    def all(self) -> tuple[Receipt, ...]:
        with self._connection() as db, db:
            db.execute("BEGIN")
            return tuple(self._receipt(db, row) for row in db.execute("SELECT * FROM orders ORDER BY number"))

    def orders_between(self, start: str, end: str) -> tuple[Receipt, ...]:
        first, last = _range(start, end)
        with self._connection() as db, db:
            db.execute("BEGIN")
            rows = db.execute("SELECT * FROM orders WHERE created_at>=? AND created_at<? "
                              "ORDER BY number DESC", (first, last))
            return tuple(self._receipt(db, r) for r in rows)

    def categories(self) -> tuple[str, ...]:
        with self._connection() as db:
            return tuple(row[0] for row in db.execute("SELECT name FROM categories ORDER BY rowid"))

    def create_category(self, name: str) -> None:
        name = _text(name, "Category")
        with self._connection() as db, db:
            db.execute("INSERT INTO categories(name) VALUES(?)", (name,))

    def delete_category(self, name: str) -> None:
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM products WHERE category=? LIMIT 1", (name,)).fetchone():
                raise ValueError("Reassign every product (including archived ones) before deleting the category.")
            db.execute("DELETE FROM categories WHERE name=?", (name,))

    def products(self, include_archived: bool = False) -> tuple[InventoryItem, ...]:
        with self._connection() as db:
            rows = db.execute("SELECT * FROM products " + ("" if include_archived else "WHERE active=1 ")
                              + "ORDER BY rowid")
            return tuple(InventoryItem(r["id"], r["name"], r["price"], r["category"],
                                       r["stock"], bool(r["active"])) for r in rows)

    def create_product(self, name: str, category: str, price: int, stock: int) -> str:
        name, category = _text(name, "Product name"), _text(category, "Category")
        _integer(price, "Price")
        _integer(stock, "Stock")
        iid = uuid4().hex
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM categories WHERE name=?", (category,)).fetchone():
                raise ValueError("Create the category before adding a product.")
            db.execute("INSERT INTO products(id,name,category,price,stock,created_at) "
                       "VALUES(?,?,?,?,?,?)", (iid, name, category, price, stock, _now()))
            self._movement(db, iid, None, stock, "INITIAL STOCK")
        return iid

    @staticmethod
    def _movement(db: sqlite3.Connection, iid: str, before: int | None, after: int,
                  reason: str, order_number: int | None = None) -> None:
        db.execute("INSERT INTO stock_movements(item_id,created_at,before_stock,after_stock,reason,order_number) "
                   "VALUES(?,?,?,?,?,?)", (iid, _now(), before, after, reason, order_number))

    def update_product(self, iid: str, name: str, category: str, price: int,
                       stock: int, reason: str = "STOCK COUNT / RESTOCK") -> None:
        name, category, reason = _text(name, "Product name"), _text(category, "Category"), _text(reason, "Reason")
        _integer(price, "Price")
        _integer(stock, "Stock")
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute("SELECT * FROM products WHERE id=? AND active=1", (iid,)).fetchone()
            if old is None:
                raise ValueError("This product no longer exists or is archived.")
            if not db.execute("SELECT 1 FROM categories WHERE name=?", (category,)).fetchone():
                raise ValueError("Choose an existing category.")
            db.execute("UPDATE products SET name=?, category=?, price=?, stock=? WHERE id=?",
                       (name, category, price, stock, iid))
            if old["stock"] != stock:
                self._movement(db, iid, old["stock"], stock, reason)

    def bulk_restock(self, amounts: dict[str, int], *, mode: str = "ADD",
                     reason: str = "BULK RESTOCK") -> None:
        """Adjust several products atomically, with one audited movement per change.

        ADD uses the current stored count (never a stale UI copy). SET replaces
        counts after a physical inventory count. NULL counts cannot be added to.
        """
        if not isinstance(amounts, dict) or not amounts:
            raise ValueError("Select at least one product to restock.")
        if mode not in ("ADD", "SET"):
            raise ValueError("Choose Add or Set exact stock.")
        reason = _text(reason, "Reason")
        for iid, amount in amounts.items():
            _text(iid, "Product ID")
            _integer(amount, "Quantity", 1 if mode == "ADD" else 0)

        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            changes = []
            for iid, amount in amounts.items():
                item = db.execute("SELECT name, stock FROM products WHERE id=? AND active=1",
                                  (iid,)).fetchone()
                if item is None:
                    raise ValueError("One of the selected products is missing or archived. Refresh Inventory.")
                current = item["stock"]
                if mode == "ADD" and current is None:
                    raise ValueError(f"{item['name']} has no starting stock count. Use Set exact stock first.")
                updated = current + amount if mode == "ADD" else amount
                _integer(updated, "Resulting stock")
                changes.append((iid, current, updated))

            for iid, current, updated in changes:
                if current == updated:
                    continue
                db.execute("UPDATE products SET stock=? WHERE id=?", (updated, iid))
                self._movement(db, iid, current, updated, reason)

    def archive_product(self, iid: str) -> None:
        # Historical order lines and inventory movements must never disappear.
        with self._connection() as db, db:
            db.execute("UPDATE products SET active=0 WHERE id=? AND active=1", (iid,))

    def restore_product(self, iid: str) -> None:
        with self._connection() as db, db:
            db.execute("UPDATE products SET active=1 WHERE id=? AND active=0", (iid,))

    def movements(self, start: str | None = None, end: str | None = None,
                  limit: int = 500) -> tuple[StockMovement, ...]:
        _integer(limit, "Limit", 1)
        params: list = []
        where = ""
        if start is not None or end is not None:
            if start is None or end is None:
                raise ValueError("Enter both dates for inventory history.")
            first, last = _range(start, end)
            where = "WHERE m.created_at>=? AND m.created_at<? "
            params += [first, last]
        with self._connection() as db:
            rows = db.execute("SELECT m.*, p.name item_name FROM stock_movements m "
                              "JOIN products p ON m.item_id=p.id " + where +
                              "ORDER BY m.id DESC LIMIT ?", (*params, limit))
            return tuple(StockMovement(r["id"], r["item_id"], r["item_name"], r["created_at"],
                                       r["before_stock"], r["after_stock"], r["reason"], r["order_number"])
                         for r in rows)

    def stock_at(self, on_date: str) -> dict[str, int | None]:
        _, end = _range(on_date, on_date)
        result = {}
        with self._connection() as db:
            for product in db.execute("SELECT id, created_at FROM products"):
                if product["created_at"] >= end:
                    continue
                movement = db.execute("SELECT after_stock FROM stock_movements WHERE item_id=? "
                                      "AND created_at<? ORDER BY id DESC LIMIT 1",
                                      (product["id"], end)).fetchone()
                result[product["id"]] = movement[0] if movement else None
        return result

    def sales_report(self, start: str, end: str) -> SalesReport:
        first, last = _range(start, end)
        where = "o.payment_method IN ('CASH','QR') AND o.created_at>=? AND o.created_at<?"
        with self._connection() as db:
            totals = db.execute(f"""SELECT COUNT(*) orders, COALESCE(SUM(o.total),0) sales,
                COALESCE(SUM(CASE WHEN o.payment_method='CASH' THEN o.total ELSE 0 END),0) cash_sales,
                COALESCE(SUM(CASE WHEN o.payment_method='QR' THEN o.total ELSE 0 END),0) qr_sales,
                SUM(CASE WHEN o.payment_method='CASH' THEN 1 ELSE 0 END) cash_orders,
                SUM(CASE WHEN o.payment_method='QR' THEN 1 ELSE 0 END) qr_orders
                FROM orders o WHERE {where}""", (first, last)).fetchone()
            products = db.execute(f"""SELECT l.name, SUM(l.quantity) units, SUM(l.subtotal) sales
                FROM order_lines l JOIN orders o ON o.number=l.order_number
                WHERE {where} GROUP BY l.item_id, l.name
                ORDER BY units DESC, sales DESC, l.name""", (first, last)).fetchall()
            days = db.execute(f"""SELECT date(o.created_at,'+8 hours') day, COUNT(*) orders,
                SUM(o.total) sales FROM orders o WHERE {where} GROUP BY day ORDER BY day""",
                (first, last)).fetchall()
            return SalesReport(start, end, totals["orders"], sum(p["units"] for p in products),
                               totals["sales"], totals["cash_sales"], totals["qr_sales"],
                               totals["cash_orders"], totals["qr_orders"],
                               tuple((p["name"], p["units"], p["sales"]) for p in products),
                               tuple((d["day"], d["orders"], d["sales"]) for d in days))

    def backup(self, destination: str | Path) -> Path:
        output = Path(destination).expanduser().resolve()
        created = False
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb"):
                created = True
            with self._connection() as source:
                target = sqlite3.connect(output)
                try:
                    source.backup(target)
                finally:
                    target.close()
            return output
        except (OSError, sqlite3.Error, OrderStoreError) as exc:
            if created:
                output.unlink(missing_ok=True)
            raise OrderStoreError("Backup failed. Choose an unused, writable file path.") from exc
