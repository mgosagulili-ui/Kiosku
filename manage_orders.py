"""Local operator CLI. This is not exposed through the customer web interface."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
from pathlib import Path
import sys
from typing import Iterator, TextIO

from models import peso
from storage import OrderStoreError, SQLiteOrderStore, default_database_path


def _positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use a positive whole number.") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Use a positive whole number.")
    return number


@contextmanager
def _new_file(path: str | Path, *, encoding: str = "utf-8") -> Iterator[TextIO]:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with output.open("x", encoding=encoding, newline="") as file:
            created = True
            yield file
    except Exception:
        if created:
            output.unlink(missing_ok=True)
        raise


def _csv_text(value: str) -> str:
    """Prevent formula execution when an operator opens an exported text cell."""
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="View, export and back up local Kiosku orders.")
    parser.add_argument("--data-dir", type=Path, help="Same data folder used by main.py (place before the command).")
    commands = parser.add_subparsers(dest="command", required=True)
    recent = commands.add_parser("list", help="Show saved orders, newest first.")
    recent.add_argument("--limit", type=_positive, default=20)
    ticket = commands.add_parser("ticket", help="Display or save an order ticket.")
    ticket.add_argument("number", type=_positive)
    ticket.add_argument("--output", type=Path, help="New UTF-8 text file; never overwrites an existing file.")
    export = commands.add_parser("export", help="Export one CSV row per saved order (includes legacy unpaid orders).")
    export.add_argument("--output", required=True, type=Path)
    backup = commands.add_parser("backup", help="Create a consistent SQLite backup using a new filename.")
    backup.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    database = default_database_path(args.data_dir)
    if not database.is_file():
        print(f"Order database not found: {database}. Start the kiosk or check --data-dir.", file=sys.stderr)
        return 1
    try:
        store = SQLiteOrderStore(database)
        if args.command == "list":
            orders = store.recent(args.limit)
            if not orders:
                print("No saved orders.")
            for order in orders:
                print(f"#{order.number:03d} | {order.created_at} | {peso(order.total)} | {order.payment_status}")
                print("  " + "; ".join(f"{q} x {name}" for name, q, _ in order.lines))
        elif args.command == "ticket":
            order = store.get(args.number)
            if order is None:
                print(f"Order #{args.number:03d} not found.", file=sys.stderr)
                return 1
            if args.output:
                with _new_file(args.output) as file:
                    file.write(order.to_text())
                print(f"Ticket saved to {args.output.resolve()}")
            else:
                print(order.to_text(), end="")
        elif args.command == "export":
            orders = store.all()
            with _new_file(args.output, encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(["order_number", "created_at_utc", "total_php", "payment_status",
                                 "payment_method", "cash_received_php", "change_due_php", "items"])
                for order in orders:
                    items = "; ".join(f"{quantity} x {name}" for name, quantity, _ in order.lines)
                    writer.writerow([order.number, _csv_text(order.created_at), order.total,
                                     order.payment_status, order.payment_method,
                                     order.cash_received if order.cash_received is not None else "",
                                     order.change_due if order.change_due is not None else "",
                                     _csv_text(items)])
            print(f"Exported {len(orders)} order(s) to {args.output.resolve()}.")
        elif args.command == "backup":
            print(f"Backup saved to {store.backup(args.output)}")
    except (OSError, OrderStoreError, ValueError) as exc:
        print(f"Operation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(run())
