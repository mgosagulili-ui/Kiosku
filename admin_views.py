"""Operator pages for inventory, order history and sales reporting (Flet views)."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO
from typing import Callable

import flet as ft

from inventory import InventoryItem, SalesReport
from models import Receipt, peso
from storage import LOCAL_TZ, OrderStoreError

INK, ESPRESSO, MATCHA = "#2A2625", "#5C4B46", "#4A6B1F"
PAPER, LINE, MUTED = "#F7F6F4", "#DDD8D3", "#756C66"


class AdminPages:
    def __init__(self, view):
        self.view = view
        today = datetime.now(LOCAL_TZ).date()
        self.report_start = str(today)
        self.report_end = str(today)
        self.history_start = ""
        self.history_end = ""
        self.compare_from = str(today - timedelta(days=7))
        self.compare_to = str(today)
        self.selected_stock_ids: set[str] = set()

    @property
    def ctl(self):
        return self.view.ctl

    @property
    def page(self):
        return self.view.page

    def _run(self, action: Callable[[], None]) -> None:
        try:
            action()
        except (ValueError, TypeError, OrderStoreError) as exc:
            self.view._toast(str(exc))

    def _refresh(self) -> None:
        self.view.refresh()

    def _head(self, title: str, subtitle: str) -> ft.Control:
        return ft.Column([
            ft.Text(title, size=30, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text(subtitle, size=12, color=MUTED),
        ], spacing=4)

    def _row(self, *controls) -> ft.Control:
        return ft.Row(list(controls), spacing=10, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER)

    def _box(self, *controls) -> ft.Control:
        return ft.Container(ft.Column(list(controls), spacing=8, tight=True),
                            padding=14, bgcolor="white", border_radius=12,
                            border=ft.border.all(1, LINE))

    def _record_width(self, preferred: int) -> int:
        """Keep a wrapped record column inside the padded page on narrow screens."""
        return max(140, min(preferred, int((self.page.width or 1280) - 110)))

    def render(self, section: str) -> ft.Control:
        if section == "inventory":
            content = self._inventory()
        elif section == "history":
            content = self._history()
        else:
            content = self._reports()
        return ft.Column(content, expand=True, spacing=13, scroll=ft.ScrollMode.AUTO,
                         horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    def _toggle_stock_pick(self, item_id: str, selected: bool) -> None:
        if selected:
            self.selected_stock_ids.add(item_id)
        else:
            self.selected_stock_ids.discard(item_id)
        self._refresh()

    def _select_all_stock(self) -> None:
        self.selected_stock_ids = {item.id for item in self.ctl.inventory()}
        self._refresh()

    def _restock_item(self, item: InventoryItem, amount: int) -> None:
        self._run(lambda: self.ctl.bulk_restock(
            {item.id: amount}, reason=f"QUICK RESTOCK +{amount}"))

    def _bulk_restock(self) -> None:
        chosen = [item for item in self.ctl.inventory()
                  if item.id in self.selected_stock_ids]
        if not chosen:
            self.view._toast("Select one or more products first.")
            return

        # Give each selected product its own quantity, rather than applying
        # the same number to all of them. All updates commit in one transaction.
        amounts = {item.id: ft.TextField(
            label=f"{item.name} · Current: {item.stock if item.stock is not None else 'Not set'}",
            width=390, keyboard_type=ft.KeyboardType.NUMBER, hint_text="Enter quantity",
        ) for item in chosen}
        shared = ft.TextField(label="Optional: quantity for all", width=230,
                              keyboard_type=ft.KeyboardType.NUMBER)
        reason = ft.TextField(label="Reason for restock / count",
                              width=390, value="BULK RESTOCK")
        has_unknown = any(item.stock is None for item in chosen)
        mode = ft.RadioGroup(value="SET" if has_unknown else "ADD", content=ft.Column([
            ft.Radio(value="ADD", label="Add entered quantities to existing stock"),
            ft.Radio(value="SET", label="Set stock to entered quantities (physical count)"),
        ], tight=True))

        def fill_all(event):
            entered = (shared.value or "").strip()
            if not entered.isdecimal():
                self.view._toast("Enter a whole number before using Fill all.")
                return
            for field in amounts.values():
                field.value = entered
            self.page.update()

        def apply(event):
            def work():
                values = {}
                for item in chosen:
                    raw = (amounts[item.id].value or "").strip()
                    if not raw.isdecimal():
                        raise ValueError(f"Enter a nonnegative whole-number quantity for {item.name}.")
                    values[item.id] = int(raw)
                action = mode.value or "ADD"
                note = (reason.value or "").strip() or (
                    "BULK RESTOCK" if action == "ADD" else "BULK STOCK COUNT")
                self.ctl.bulk_restock(values, mode=action, reason=note)
                self.selected_stock_ids.clear()
                self.page.close(dialog)
                self._refresh()
            self._run(work)

        dialog = ft.AlertDialog(
            modal=True, scrollable=True,
            title=ft.Text(f"Bulk restock · {len(chosen)} products"),
            content=ft.Column([
                mode,
                ft.Text("Set exact stock for items marked 'Not set'. The Add option requires an existing stock count.",
                        color=MUTED, size=12),
                self._row(shared, ft.OutlinedButton("Fill all", on_click=fill_all)),
                ft.Divider(color=LINE),
                *[amounts[item.id] for item in chosen],
                reason,
                ft.Text("Every selected product needs a quantity. Changes are logged together.",
                        color=MUTED, size=12),
            ], tight=True, spacing=10, width=430),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                ft.ElevatedButton("Save stock updates", on_click=apply),
            ],
        )
        self.page.open(dialog)

    def _inventory_product_card(self, item: InventoryItem) -> ft.Control:
        stock = "Not set" if item.stock is None else str(item.stock)
        picked = item.id in self.selected_stock_ids
        return ft.Container(
            width=320,
            padding=14,
            bgcolor="white",
            border_radius=12,
            border=ft.border.all(2 if picked else 1, ESPRESSO if picked else LINE),
            content=ft.Column([
                ft.Row([
                    ft.Checkbox(
                        value=picked,
                        label="Select",
                        on_change=lambda e, iid=item.id: self._toggle_stock_pick(iid, bool(e.control.value)),
                    ),
                    ft.Text(item.category, color=MUTED, size=11),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text(item.name, size=18, weight=ft.FontWeight.BOLD, color=INK),
                ft.Text(f"{peso(item.price)} · Stock: {stock}", color=MUTED, size=13),
                ft.Row([
                    ft.OutlinedButton("+1", disabled=item.stock is None,
                                      on_click=lambda e, i=item: self._restock_item(i, 1)),
                    ft.OutlinedButton("+5", disabled=item.stock is None,
                                      on_click=lambda e, i=item: self._restock_item(i, 5)),
                    ft.OutlinedButton("+10", disabled=item.stock is None,
                                      on_click=lambda e, i=item: self._restock_item(i, 10)),
                ], spacing=8, wrap=True),
                ft.Row([
                    ft.ElevatedButton("Edit / set stock", on_click=lambda e, i=item: self._product_form(i)),
                    ft.TextButton("Delete", tooltip="Archive without removing order history",
                                  on_click=lambda e, i=item: self._confirm_archive(i)),
                ], spacing=8, wrap=True),
            ], spacing=10, tight=True),
        )

    def _inventory(self) -> list[ft.Control]:
        items = self.ctl.inventory()
        categories = self.ctl.categories()
        tracked = sum(i.stock is not None for i in items)
        active_ids = {i.id for i in items}
        self.selected_stock_ids.intersection_update(active_ids)
        selected_count = len(self.selected_stock_ids)
        new_category = ft.TextField(label="New category", width=230, hint_text="e.g. Pastries")

        def add_category():
            self.ctl.create_category(new_category.value or "")
            self._refresh()

        controls = [
            self._head("Inventory", "Maintain products, opening stock, categories and an auditable movement history."),
            self._box(
                self._row(
                    ft.Text(f"{len(items)} active products · {tracked} with stock counts", color=INK),
                    ft.ElevatedButton("Add product", icon=ft.Icons.ADD,
                                      on_click=lambda e: self._product_form()),
                    ft.OutlinedButton(
                        f"Restock selected ({selected_count})",
                        icon=ft.Icons.INVENTORY_2_OUTLINED,
                        disabled=selected_count == 0,
                        on_click=lambda e: self._bulk_restock(),
                    ),
                    ft.TextButton("Select all", on_click=lambda e: self._select_all_stock()),
                    ft.TextButton("Clear selection", disabled=selected_count == 0,
                                  on_click=lambda e: (self.selected_stock_ids.clear(), self._refresh())),
                ),
                ft.Text(
                    "Original menu stocks start as 'Not set'. Enter a real count before treating them as accurate. "
                    "Use the quick + buttons or bulk restock to update stock faster.",
                    size=12, color=MUTED,
                ),
            ),
            self._box(
                ft.Text("Manage categories", size=18, weight=ft.FontWeight.BOLD),
                self._row(new_category, ft.ElevatedButton("Create category",
                    on_click=lambda e: self._run(add_category))),
                self._row(*[ft.OutlinedButton(cat, tooltip="Delete empty category",
                    on_click=lambda e, c=cat: self._delete_category(c)) for cat in categories]),
            ),
            ft.Text("Products", size=21, weight=ft.FontWeight.BOLD, color=INK),
        ]
        for cat in categories:
            matching = [i for i in items if i.category == cat]
            if not matching:
                continue
            controls.append(ft.Text(cat, size=16, color=ESPRESSO, weight=ft.FontWeight.BOLD))
            controls.append(ft.Row([self._inventory_product_card(item) for item in matching],
                                   wrap=True, spacing=12, run_spacing=12))
        archived = [p for p in self.ctl.inventory(include_archived=True) if not p.active]
        if archived:
            controls.append(ft.Text("Archived products", size=20, weight=ft.FontWeight.BOLD, color=INK))
            for item in archived:
                controls.append(self._box(
                    ft.Text(f"{item.name} · {item.category}", color=INK),
                    ft.Row([
                        ft.OutlinedButton("Restore", on_click=lambda e, i=item:
                            self._run(lambda: self._restore(i.id)))
                    ], spacing=10, wrap=True)
                ))
        controls += [
            ft.Divider(color=LINE),
            ft.Text("Compare historical stock", size=20, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text("Compare end-of-day quantities (Philippine local dates). 'Not tracked' means an opening count was not recorded at that point.",
                    size=12, color=MUTED),
        ]
        earlier = ft.TextField(label="Earlier date (YYYY-MM-DD)", value=self.compare_from, width=235)
        later = ft.TextField(label="Later date (YYYY-MM-DD)", value=self.compare_to, width=235)
        def compare():
            self.compare_from, self.compare_to = earlier.value, later.value
            self._compare(self.compare_from, self.compare_to)
        controls.append(self._row(earlier, later,
                                  ft.ElevatedButton("Compare", on_click=lambda e: self._run(compare))))
        controls.append(ft.Text("Stock changes (most recent 100)", size=20,
                                weight=ft.FontWeight.BOLD, color=INK))
        changes = self.ctl.stock_movements()
        for movement in changes[:100]:
            before = "Not set" if movement.before is None else str(movement.before)
            delta = "Initial count" if movement.difference is None else f"{movement.difference:+d}"
            controls.append(self._box(
                ft.Text(f"{movement.item_name} · {delta} · {before} → {movement.after}",
                        size=14, weight=ft.FontWeight.W_600),
                ft.Text(f"{movement.created_at} UTC · {movement.reason}" +
                        (f" · Order #{movement.order_number}" if movement.order_number else ""),
                        color=MUTED, size=11)))
        if not changes:
            controls.append(ft.Text("No stock changes recorded.", color=MUTED))
        return controls

    def _product_form(self, item: InventoryItem | None = None) -> None:
        name = ft.TextField(label="Name", value=item.name if item else "", width=310)
        price = ft.TextField(label="Price in whole pesos", value=str(item.price) if item else "", width=220,
                             keyboard_type=ft.KeyboardType.NUMBER)
        stock = ft.TextField(label="Current stock quantity", value=(str(item.stock) if item and
                             item.stock is not None else ""), width=230,
                             keyboard_type=ft.KeyboardType.NUMBER)
        category = ft.Dropdown(label="Category", value=item.category if item else None, width=280,
                               options=[ft.dropdown.Option(c) for c in self.ctl.categories()])
        reason = ft.TextField(label="Reason for change (if stock changes)",
                              value="STOCK COUNT / RESTOCK", width=330)

        def save(event):
            def work():
                p, q = (price.value or "").strip(), (stock.value or "").strip()
                if not p.isdecimal() or not q.isdecimal():
                    raise ValueError("Price and stock must be nonnegative whole numbers.")
                if item:
                    self.ctl.update_product(item.id, name.value, category.value,
                                            int(p), int(q), reason.value)
                else:
                    self.ctl.create_product(name.value, category.value, int(p), int(q))
                self.page.close(dialog)
                self._refresh()
            self._run(work)

        dialog = ft.AlertDialog(modal=True, scrollable=True,
            title=ft.Text("Edit product" if item else "New product"),
            content=ft.Column([name, category, price, stock, reason,
                               ft.Text("Stock edits are logged. Past orders keep their sold prices and names.",
                                       size=12, color=MUTED)], tight=True, spacing=12),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                     ft.ElevatedButton("Save", on_click=save)])
        self.page.open(dialog)

    def _restore(self, iid: str) -> None:
        self.ctl.restore_product(iid)
        self._refresh()

    def _confirm_archive(self, item: InventoryItem) -> None:
        def delete(event):
            def work():
                self.ctl.archive_product(item.id)
                self.page.close(dialog)
                self._refresh()
            self._run(work)
        dialog = ft.AlertDialog(modal=True, title=ft.Text(f"Delete {item.name}?"),
            content=ft.Text("This archives the product from the menu. Historical sales and "
                            "inventory movements are retained."),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.page.close(dialog)),
                     ft.ElevatedButton("Archive product", on_click=delete)])
        self.page.open(dialog)

    def _delete_category(self, name: str) -> None:
        def work():
            self.ctl.delete_category(name)
            self._refresh()
        self._run(work)

    def _compare(self, earlier: str, later: str) -> None:
        if earlier > later:
            raise ValueError("Earlier date must not be after the later date.")
        old, new = self.ctl.stock_at(earlier), self.ctl.stock_at(later)
        rows = []
        for item in self.ctl.inventory(include_archived=True):
            a, b = old.get(item.id), new.get(item.id)
            if item.id not in old and item.id not in new:
                continue
            difference = "N/A" if a is None or b is None else f"{b - a:+d}"
            rows.append(self._box(ft.Text(item.name, weight=ft.FontWeight.W_600),
                ft.Text(f"{a if a is not None else 'Not tracked'} → "
                        f"{b if b is not None else 'Not tracked'}  |  Change: {difference}",
                        color=MUTED, size=12)))
        dialog = ft.AlertDialog(modal=True, scrollable=True,
            title=ft.Text(f"Stock: {earlier} vs {later}"),
            content=ft.Column(rows or [ft.Text("No recorded inventory in this period.")],
                              tight=True, spacing=7, width=440),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.close(dialog))])
        self.page.open(dialog)

    def _history(self) -> list[ft.Control]:
        first = ft.TextField(label="From (YYYY-MM-DD)", value=self.history_start, width=225)
        last = ft.TextField(label="To (YYYY-MM-DD)", value=self.history_end, width=225)
        def filter_orders():
            if not first.value or not last.value:
                raise ValueError("Enter both start and end dates.")
            self.ctl.order_history(first.value, last.value)  # validate first
            self.history_start, self.history_end = first.value, last.value
            self._refresh()
        def clear():
            self.history_start = self.history_end = ""
            self._refresh()
        if self.history_start and self.history_end:
            orders = self.ctl.order_history(self.history_start, self.history_end)
        else:
            orders = self.ctl._store.recent(200)
        controls = [
            self._head("Order history", "All saved orders, including earlier unpaid orders, survive app restarts."),
            self._row(first, last, ft.ElevatedButton("Filter dates",
                       on_click=lambda e: self._run(filter_orders)),
                      ft.TextButton("Latest 200", on_click=lambda e: clear())),
            ft.Text(f"{len(orders)} orders shown" + (" · showing first 200 matching orders"
                    if len(orders) > 200 else ""), color=MUTED),
        ]
        for receipt in orders[:200]:
            # Never put an expanding child in a Row with wrap=True. On Flet
            # 0.28.3 (web) that combination can be given an enormous height,
            # hiding the record behind a large gray placeholder.
            controls.append(self._box(
                self._row(
                    ft.Container(
                        ft.Column([
                            ft.Text(f"Order #{receipt.number:03d} · {peso(receipt.total)}",
                                    color=INK, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{receipt.created_at} UTC · {receipt.payment_status}"
                                    + (f" · {receipt.payment_method}" if receipt.payment_method else ""),
                                    color=MUTED, size=12),
                        ], spacing=4, tight=True),
                        width=self._record_width(440),
                    ),
                    ft.OutlinedButton("Details", on_click=lambda e, r=receipt: self._order_detail(r)),
                ),
            ))
        if not orders:
            controls.append(ft.Text("No orders found in this period.", color=MUTED))
        return controls

    def _order_detail(self, receipt: Receipt) -> None:
        cash = (f"Cash received: {peso(receipt.cash_received)} · Change: {peso(receipt.change_due)}"
                if receipt.payment_method == "CASH" else "")
        dialog = ft.AlertDialog(modal=True, scrollable=True,
            title=ft.Text(f"Order #{receipt.number:03d}"),
            content=ft.Column([
                ft.Text(f"Saved: {receipt.created_at} UTC", color=MUTED),
                ft.Text(f"{receipt.payment_status} · {receipt.payment_method or 'Legacy unpaid'}",
                        weight=ft.FontWeight.BOLD),
                *[self._row(ft.Text(f"{quantity} × {name}"), ft.Text(peso(subtotal)))
                  for name, quantity, subtotal in receipt.lines],
                ft.Divider(),
                ft.Text(f"TOTAL: {peso(receipt.total)}", size=19, weight=ft.FontWeight.BOLD),
                ft.Text(cash, color=MUTED),
            ], spacing=10, tight=True, width=370),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.close(dialog))])
        self.page.open(dialog)

    def _reports(self) -> list[ft.Control]:
        from_field = ft.TextField(label="From (YYYY-MM-DD)", value=self.report_start, width=225)
        to_field = ft.TextField(label="To (YYYY-MM-DD)", value=self.report_end, width=225)
        def filter_report():
            self.ctl.sales_report(from_field.value, to_field.value)
            self.report_start, self.report_end = from_field.value, to_field.value
            self._refresh()
        report = self.ctl.sales_report(self.report_start, self.report_end)
        aov = report.gross_sales // report.order_count if report.order_count else 0
        best_units = report.by_product[0] if report.by_product else None
        best_revenue = max(report.by_product, key=lambda p: p[2]) if report.by_product else None
        controls = [
            self._head("Sales report", "Date range uses Philippine time (UTC+08:00). Only completed Cash / QR orders count as sales."),
            self._row(from_field, to_field, ft.ElevatedButton("Generate report",
                         icon=ft.Icons.SEARCH, on_click=lambda e: self._run(filter_report)),
                      ft.OutlinedButton("Copy CSV", on_click=lambda e: self._copy_report(report))),
            self._box(ft.Text(f"Sales summary · {report.start_date} to {report.end_date}",
                              size=18, weight=ft.FontWeight.BOLD),
                      self._row(ft.Text(f"Gross sales: {peso(report.gross_sales)}", size=18,
                                        weight=ft.FontWeight.BOLD),
                                ft.Text(f"Paid orders: {report.order_count}"),
                                ft.Text(f"Units sold: {report.units_sold}"),
                                ft.Text(f"Average order: {peso(aov)}")),
                      ft.Divider(color=LINE),
                      self._row(ft.Text(f"Cash: {peso(report.cash_sales)} ({report.cash_orders} orders)"),
                                ft.Text(f"QR: {peso(report.qr_sales)} ({report.qr_orders} orders)")),
                      ft.Text(f"Most sold (units): {best_units[0]} — {best_units[1]}"
                              if best_units else "Most sold: none", color=INK),
                      ft.Text(f"Highest sales value: {best_revenue[0]} — {peso(best_revenue[2])}"
                              if best_revenue else "Highest sales value: none", color=INK)),
            ft.Text("Product performance", size=20, weight=ft.FontWeight.BOLD, color=INK),
        ]
        for idx, (name, qty, sales) in enumerate(report.by_product, start=1):
            controls.append(self._box(self._row(
                ft.Container(ft.Text(f"{idx}. {name}", color=INK,
                                     weight=ft.FontWeight.W_600), width=self._record_width(280)),
                ft.Container(ft.Text(f"{qty} sold", color=MUTED), width=110),
                ft.Text(peso(sales), color=INK, weight=ft.FontWeight.BOLD),
            )))
        if not report.by_product:
            controls.append(ft.Text("No paid sales for this period.", color=MUTED))
        controls.append(ft.Text("Daily totals", size=20, weight=ft.FontWeight.BOLD, color=INK))
        for day, orders, sales in report.by_day:
            controls.append(self._box(self._row(
                ft.Container(ft.Text(day, color=INK), width=self._record_width(280)),
                ft.Container(ft.Text(f"{orders} orders", color=MUTED), width=110),
                ft.Text(peso(sales), color=INK, weight=ft.FontWeight.BOLD),
            )))
        controls.append(ft.Text("Figures are gross item sales only; discounts, taxes, refunds and "
                                "payment-provider settlement fees are not tracked. Historical unpaid "
                                "orders are excluded.", color=MUTED, size=12))
        return controls

    def _copy_report(self, report: SalesReport) -> None:
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["SALES REPORT", report.start_date, report.end_date])
        writer.writerow(["Gross sales", report.gross_sales])
        writer.writerow(["Paid orders", report.order_count])
        writer.writerow(["Units sold", report.units_sold])
        writer.writerow(["Cash sales", report.cash_sales])
        writer.writerow(["QR sales", report.qr_sales])
        writer.writerow([])
        writer.writerow(["Product", "Units", "Revenue PHP"])
        writer.writerows(report.by_product)
        writer.writerow([])
        writer.writerow(["Date (PHT)", "Orders", "Sales PHP"])
        writer.writerows(report.by_day)
        try:
            self.page.set_clipboard(buffer.getvalue())
            self.view._toast("Report CSV copied to clipboard. Paste into a .csv file or spreadsheet.")
        except Exception:
            self.view._toast("Clipboard unavailable. Copy the report manually.")
