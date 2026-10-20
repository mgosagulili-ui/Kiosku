"""Flet 0.28.3 view layer: menu, checkout, inventory, history and reports."""
from __future__ import annotations

import logging
from threading import RLock
from typing import Callable

import flet as ft

from controllers import KioskController
from models import CartItem, MAX_QUANTITY, MenuItem, Receipt, ReceiptLines, peso
from storage import OrderStoreError

logger = logging.getLogger(__name__)
INK, ESPRESSO, MATCHA, SODA = "#2A2625", "#5C4B46", "#4A6B1F", "#2F5D8C"
PAPER, LINE, MUTED = "#F7F6F4", "#DDD8D3", "#756C66"
ACCENT = {"Coffee": ESPRESSO, "Specials": MATCHA, "Non Coffee": INK, "Soda": SODA}
ICON = {"Coffee": ft.Icons.COFFEE, "Specials": ft.Icons.AUTO_AWESOME,
        "Non Coffee": ft.Icons.LOCAL_DRINK, "Soda": ft.Icons.BUBBLE_CHART}
WIDE = 1000


class KioskView:
    def __init__(self, page: ft.Page, controller: KioskController) -> None:
        self.page, self.ctl = page, controller
        categories = controller.categories()
        self.category = categories[0] if categories else ""
        self.section = "menu"
        from admin_views import AdminPages
        self.admin = AdminPages(self)
        self._payment_radio = None
        self._cash_field = None
        self.body = ft.Container(expand=True)
        self._sheet: ft.BottomSheet | None = None
        self._review_dialog: ft.AlertDialog | None = None
        self._clear_dialog: ft.AlertDialog | None = None
        self._receipt_dialog: ft.AlertDialog | None = None
        self._placing = False
        self._mounted = False
        self._lock = RLock()
        controller.bind(self.refresh)

    def mount(self) -> None:
        p = self.page
        p.title, p.bgcolor, p.padding = "Lumah Caf | Kiosku", PAPER, 0
        p.theme = ft.Theme(color_scheme_seed=ESPRESSO, use_material3=True)
        p.theme_mode = ft.ThemeMode.LIGHT
        # Use the framework's default font, rather than fetching a custom font.
        p.on_resized = self._resized
        p.on_close = lambda e: self.ctl.unbind(self.refresh)
        self._mounted = True
        p.add(ft.SafeArea(self.body, expand=True))
        self.refresh()

    def _wide(self) -> bool:
        return (self.page.width or 0) >= WIDE

    def _resized(self, e=None) -> None:
        with self._lock:
            if self._wide():
                self._close_sheet()
            self.refresh()

    def refresh(self) -> None:
        with self._lock:
            if not self._mounted:
                return
            if self.section != "menu":
                self.body.content = ft.Column([
                    self._topnav(),
                    ft.Container(self.admin.render(self.section), expand=True,
                                 padding=ft.padding.only(left=28, top=12, right=28, bottom=28))
                ], expand=True, spacing=0)
                self.page.update()
                return
            if self.category not in self.ctl.categories():
                options = self.ctl.categories()
                self.category = options[0] if options else ""
            menu = ft.Column([self._header(), self._topnav(), self._tabs(), self._grid()],
                             expand=True, spacing=0)
            if self._wide():
                panel = ft.Container(self._cart_panel(), width=380, padding=28,
                                     bgcolor="white",
                                     border=ft.border.only(left=ft.BorderSide(1, LINE)))
                self.body.content = ft.Row([menu, panel], expand=True, spacing=0)
            else:
                self.body.content = ft.Column([menu, self._bottom_bar()], expand=True, spacing=0)
            if self._sheet is not None and self._sheet.open:
                self._sheet.content = self._sheet_body()
            self.page.update()

    def _topnav(self) -> ft.Control:
        tabs = [("menu", "Menu / POS"), ("inventory", "Inventory"),
                ("history", "Order history"), ("reports", "Sales report")]
        return ft.Container(ft.Row([
            ft.ElevatedButton(label, bgcolor=ESPRESSO if self.section == key else "white",
                              color="white" if self.section == key else INK,
                              on_click=lambda e, section=key: self._navigate(section))
            for key, label in tabs], scroll=ft.ScrollMode.AUTO, spacing=8),
            padding=ft.padding.symmetric(horizontal=28, vertical=12), bgcolor=PAPER)

    def _navigate(self, section: str) -> None:
        with self._lock:
            if section not in ("menu", "inventory", "history", "reports"):
                return
            self._close_sheet()
            self.section = section
            self.refresh()

    def _header(self) -> ft.Control:
        return ft.Container(ft.Column([
            ft.Text("KIOSKU  /  SELF-SERVICE", size=11, color=MUTED,
                    weight=ft.FontWeight.W_600),
            ft.Text("Lumah Caf", size=38, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text("Choose your drink. Review your order. Select cash or QR.",
                    size=13, color=MUTED),
        ], spacing=4), padding=ft.padding.only(left=28, top=26, right=28, bottom=12))

    def _tabs(self) -> ft.Control:
        def tab(name: str) -> ft.Control:
            active = name == self.category
            accent = ACCENT.get(name, ESPRESSO)
            return ft.Container(
                ft.Text(name, size=15, weight=ft.FontWeight.W_600,
                        color="white" if active else INK),
                padding=ft.padding.symmetric(horizontal=18, vertical=13),
                border_radius=24, ink=True,
                bgcolor=accent if active else "white",
                border=ft.border.all(1, accent if active else LINE),
                on_click=lambda e, category=name: self._select(category))
        return ft.Container(ft.Row([tab(c) for c in self.ctl.categories()], spacing=8,
                                   scroll=ft.ScrollMode.AUTO),
                            padding=ft.padding.symmetric(horizontal=28, vertical=12))

    def _select(self, name: str) -> None:
        with self._lock:
            if name in self.ctl.categories():
                self.category = name
                self.refresh()

    def _grid(self) -> ft.Control:
        return ft.GridView([self._card(i) for i in self.ctl.items_in(self.category)],
                           expand=True, max_extent=230, child_aspect_ratio=0.84,
                           spacing=12, run_spacing=12, padding=28)

    def _card(self, item: MenuItem) -> ft.Control:
        accent = ACCENT.get(item.category, ESPRESSO)
        quantity = self.ctl.quantity_of(item.id)
        badge = ft.Container(
            ft.Text(str(quantity) if quantity else "+", color="white", size=15,
                    weight=ft.FontWeight.BOLD),
            width=30, height=30, border_radius=15, alignment=ft.alignment.center,
            bgcolor=accent)
        card = ft.Container(
            ft.Column([
                ft.Row([ft.Icon(ICON.get(item.category, ft.Icons.LOCAL_DRINK), color=accent, size=34),
                        badge], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column([
                    ft.Text(item.name, size=18, color=INK, weight=ft.FontWeight.W_600, max_lines=2),
                    ft.Text(item.describe(), size=12, color=MUTED, max_lines=2),
                ], spacing=4),
                ft.Text(peso(item.price), size=27, weight=ft.FontWeight.BOLD, color=accent),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=16, bgcolor="white", border_radius=18, ink=True,
            border=ft.border.all(2 if quantity else 1, accent if quantity else LINE),
            tooltip=f"Add {item.name}, {item.price} pesos",
            on_click=lambda e, iid=item.id: self._act(lambda: self.ctl.add_item(iid)))
        # Keep Container as GridView's direct child. In the reported Windows
        # browser, the Semantics wrapper left the product cells as gray tiles.
        # The tooltip retains a readable action label without another widget.
        return card

    def _act(self, action: Callable[[], None]) -> None:
        with self._lock:
            if self._placing:
                return
            try:
                action()
            except (ValueError, TypeError) as exc:
                self._toast(str(exc))

    def _cart_panel(self) -> ft.Control:
        lines = self.ctl.cart_lines()
        content = (ft.ListView([self._line(line) for line in lines], expand=True, spacing=8)
                   if lines else ft.Container(
                       ft.Column([
                           ft.Icon(ft.Icons.SHOPPING_BAG_OUTLINED, size=42, color=MUTED),
                           ft.Text("Your order is empty", size=18, weight=ft.FontWeight.W_600,
                                   color=INK, text_align=ft.TextAlign.CENTER),
                           ft.Text("Tap a drink to get started.", color=MUTED,
                                   text_align=ft.TextAlign.CENTER),
                       ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                          alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                       alignment=ft.alignment.center, expand=True))
        return ft.Column([
            ft.Row([ft.Text("Your order", size=27, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text(f"{self.ctl.cart_count()} items", color=MUTED, size=12)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Divider(color=LINE), content, ft.Divider(color=LINE),
            ft.Row([ft.Text("Total", size=18, color=INK),
                    ft.Text(peso(self.ctl.cart_total()), size=30, weight=ft.FontWeight.BOLD, color=INK)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("Cash or cashier-confirmed QR · Philippine pesos", size=11, color=MUTED),
            ft.Row([ft.ElevatedButton("Review order", icon=ft.Icons.CHECK_CIRCLE_OUTLINE,
                                     height=54, expand=True, bgcolor=MATCHA, color="white",
                                     disabled=not lines or self._placing,
                                     on_click=self._review_order)]),
            ft.Row([ft.TextButton("Clear order", icon=ft.Icons.DELETE_OUTLINE,
                                 disabled=not lines or self._placing, on_click=self._request_clear)],
                   alignment=ft.MainAxisAlignment.CENTER),
        ], expand=True, spacing=8)

    def _line(self, line: CartItem) -> ft.Control:
        iid = line.item.id
        return ft.Container(ft.Column([
            ft.Row([
                ft.Text(line.item.name, size=15, weight=ft.FontWeight.W_600, color=INK, expand=True),
                ft.Text(peso(line.price), size=16, weight=ft.FontWeight.BOLD, color=INK),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([
                ft.Text(f"{peso(line.item.price)} each", size=12, color=MUTED, expand=True),
                ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, icon_size=27, width=40, height=40,
                              tooltip=f"Decrease {line.item.name}",
                              on_click=lambda e: self._act(lambda: self.ctl.change_quantity(iid, -1))),
                ft.Text(str(line.quantity), size=17, weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER, width=26, color=INK),
                ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_size=27, width=40, height=40,
                              disabled=line.quantity >= MAX_QUANTITY, tooltip=f"Increase {line.item.name}",
                              on_click=lambda e: self._act(lambda: self.ctl.change_quantity(iid, 1))),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=20, width=34, height=40,
                              tooltip=f"Remove {line.item.name}",
                              on_click=lambda e: self._act(lambda: self.ctl.remove_item(iid))),
            ], spacing=0),
        ], spacing=2), padding=ft.padding.only(top=8, bottom=8),
            border=ft.border.only(bottom=ft.BorderSide(1, LINE)))

    def _bottom_bar(self) -> ft.Control:
        count = self.ctl.cart_count()
        return ft.Container(ft.Row([
            ft.Column([ft.Text(f"{count} item{'s' if count != 1 else ''}", size=12, color=MUTED),
                       ft.Text(peso(self.ctl.cart_total()), size=26, weight=ft.FontWeight.BOLD, color=INK)],
                      spacing=0),
            ft.ElevatedButton("View order", icon=ft.Icons.SHOPPING_BAG_OUTLINED,
                              height=52, bgcolor=ESPRESSO, color="white", disabled=count == 0,
                              on_click=self._open_sheet),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN), padding=28, bgcolor="white",
            border=ft.border.only(top=ft.BorderSide(1, LINE)))

    def _sheet_body(self) -> ft.Control:
        return ft.Container(self._cart_panel(), padding=18, height=(self.page.height or 800) * 0.80)

    def _open_sheet(self, e=None) -> None:
        with self._lock:
            if self._sheet is not None and self._sheet.open:
                return
            sheet = ft.BottomSheet(self._sheet_body(), is_scroll_controlled=True, show_drag_handle=True)
            def dismissed(event):
                with self._lock:
                    if self._sheet is sheet:
                        self._sheet = None
            sheet.on_dismiss = dismissed
            self._sheet = sheet
            self.page.open(sheet)

    def _close_sheet(self) -> None:
        if self._sheet is not None:
            if self._sheet.open:
                self.page.close(self._sheet)
            self._sheet = None

    def _ticket_rows(self, receipt: Receipt) -> list[ft.Control]:
        return [ft.Row([
            ft.Text(f"{quantity} x {name}", expand=True, size=14, color=INK),
            ft.Text(peso(subtotal), size=14, color=INK),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, spacing=16)
            for name, quantity, subtotal in receipt.lines]

    def _summary(self, receipt: Receipt, note: str) -> ft.Control:
        return ft.Column([
            *self._ticket_rows(receipt), ft.Divider(color=LINE),
            ft.Row([ft.Text("Total", size=18, weight=ft.FontWeight.BOLD, color=INK),
                    ft.Text(peso(receipt.total), size=22, weight=ft.FontWeight.BOLD, color=INK)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text(note, size=13, color=MUTED),
        ], tight=True, width=min(380, max(220, (self.page.width or 460) - 96)), spacing=12)

    def _review_order(self, e=None) -> None:
        with self._lock:
            if self._placing or (self._review_dialog is not None and self._review_dialog.open):
                return
            if self._receipt_dialog is not None and self._receipt_dialog.open:
                return
            draft = self.ctl.preview()
            if draft is None:
                self._toast("Add a drink before reviewing your order.")
                return
            self._close_sheet()
            cash = ft.TextField(label="Cash received (whole pesos)",
                                hint_text="e.g. 500", keyboard_type=ft.KeyboardType.NUMBER,
                                visible=False, width=260)
            balance = ft.Text("Enter the cash received to calculate change.", size=12, color=MUTED,
                              visible=False)
            qr_note = ft.Text("Check the actual QR payment notification before confirming. "
                              "This app does not verify QR transfers.", color=MUTED, size=12,
                              visible=False)
            payment = ft.RadioGroup(content=ft.Row([
                ft.Radio(value="CASH", label="Cash"),
                ft.Radio(value="QR", label="QR")], spacing=20))

            def recalculate(event=None):
                if payment.value != "CASH":
                    return
                raw = (cash.value or "").strip()
                if not raw:
                    balance.value = "Enter the cash received to calculate change."
                    balance.color = MUTED
                elif not raw.isdecimal():
                    balance.value = "Enter whole pesos only."
                    balance.color = "red"
                else:
                    amount = int(raw)
                    if amount < draft.total:
                        balance.value = f"Insufficient cash: {peso(draft.total - amount)} short"
                        balance.color = "red"
                    else:
                        balance.value = f"Change due: {peso(amount - draft.total)}"
                        balance.color = MATCHA
                self.page.update()

            def switched(event=None):
                cash.visible = balance.visible = payment.value == "CASH"
                qr_note.visible = payment.value == "QR"
                recalculate()
                self.page.update()

            cash.on_change = recalculate
            payment.on_change = switched
            dialog = ft.AlertDialog(
                modal=True, scrollable=True,
                title=ft.Text("Review order & choose payment", color=INK),
                content=ft.Column([
                    self._summary(draft, "Check the items and select a payment method below."),
                    ft.Divider(color=LINE),
                    ft.Text("Payment method", weight=ft.FontWeight.BOLD, color=INK),
                    payment, cash, balance, qr_note,
                ], tight=True, spacing=10, width=390),
                actions=[
                    ft.TextButton("Keep editing", on_click=lambda e: self._cancel_review(dialog)),
                    ft.ElevatedButton("Confirm payment & save", height=48, bgcolor=MATCHA,
                                      color="white", on_click=lambda e: self._confirm_order(dialog, draft.lines)),
                ])
            self._payment_radio = payment
            self._cash_field = cash
            self._review_dialog = dialog
            self.page.open(dialog)

    def _cancel_review(self, dialog: ft.AlertDialog) -> None:
        with self._lock:
            if self._review_dialog is dialog and not self._placing:
                self.page.close(dialog)
                self._review_dialog = None

    def _confirm_order(self, dialog: ft.AlertDialog, expected: ReceiptLines) -> None:
        with self._lock:
            # Ignore stale/replayed events, even after a customer starts a new cart.
            if self._placing or self._review_dialog is not dialog or not dialog.open:
                return
            current = self.ctl.preview()
            if current is None or current.lines != expected:
                self.page.close(dialog)
                self._review_dialog = None
                self._toast("Your order changed. Please review it again before confirming.")
                return
            method = self._payment_radio.value if self._payment_radio else None
            if method not in ("CASH", "QR"):
                self._toast("Select Cash or QR before confirming.")
                return
            cash_amount = None
            if method == "CASH":
                raw = (self._cash_field.value or "").strip()
                if not raw.isdecimal():
                    self._toast("Enter the cash received in whole pesos.")
                    return
                cash_amount = int(raw)
                if cash_amount < self.ctl.cart_total():
                    self._toast("Cash received is less than the order total.")
                    return
            self._placing = True
            dialog.actions[1].disabled = True
            self.page.update()
            try:
                receipt = self.ctl.checkout(expected_lines=expected,
                                            payment_method=method, cash_received=cash_amount)
            except OrderStoreError as exc:
                logger.exception("Order save failed.")
                self._toast(str(exc))
                return
            except ValueError as exc:
                self.page.close(dialog)
                self._review_dialog = None
                self._toast(str(exc))
                return
            finally:
                self._placing = False
                dialog.actions[1].disabled = False
                self.page.update()
            self.page.close(dialog)
            self._review_dialog = None
            if receipt is not None:
                self._show_receipt(receipt)
            else:
                self._toast("Your cart is empty. Add a drink to start a new order.")

    def _request_clear(self, e=None) -> None:
        with self._lock:
            if not self.ctl.cart_count() or self._placing:
                return
            if self._clear_dialog is not None and self._clear_dialog.open:
                return
            def cancel(event):
                self.page.close(dialog)
                self._clear_dialog = None
            def clear(event):
                with self._lock:
                    if self._clear_dialog is not dialog or not dialog.open:
                        return
                    self.page.close(dialog)
                    self._clear_dialog = None
                    self.ctl.clear_cart()
                    self._close_sheet()
            dialog = ft.AlertDialog(
                modal=True, title=ft.Text("Clear this order?", color=INK),
                content=ft.Text("This removes all drinks from your current cart. Saved orders are not deleted."),
                actions=[ft.TextButton("Keep order", on_click=cancel),
                         ft.ElevatedButton("Clear order", bgcolor=ESPRESSO, color="white", on_click=clear)])
            self._clear_dialog = dialog
            self.page.open(dialog)

    def _show_receipt(self, receipt: Receipt) -> None:
        def start_new(event):
            with self._lock:
                self.page.close(dialog)
                self._receipt_dialog = None
                self.category = self.ctl.categories()[0] if self.ctl.categories() else ""
                self.refresh()
        dialog = ft.AlertDialog(
            modal=True, scrollable=True,
            title=ft.Text(f"Order #{receipt.number:03d} saved", color=INK, weight=ft.FontWeight.BOLD),
            content=ft.Column([
                ft.Container(ft.Text(f"{receipt.payment_status} — {receipt.payment_method or 'Not recorded'}",
                                     color=MATCHA, size=12, weight=ft.FontWeight.BOLD),
                             padding=10, bgcolor="#EEF2E8", border_radius=8),
                self._summary(receipt, "Payment recorded by cashier. Not an official receipt." if
                              receipt.payment_method else "Payment still pending."),
                ft.Text(f"Cash received: {peso(receipt.cash_received)}  |  Change: {peso(receipt.change_due)}"
                        if receipt.payment_method == "CASH" else "", color=INK),
                ft.Text(f"Saved: {receipt.created_at}" if receipt.created_at else "", size=10, color=MUTED),
            ], tight=True, spacing=12),
            actions=[
                ft.TextButton("Copy ticket", icon=ft.Icons.COPY,
                              on_click=lambda e: self._copy_ticket(receipt)),
                ft.ElevatedButton("Start new order", height=48, bgcolor=MATCHA,
                                  color="white", on_click=start_new),
            ])
        self._receipt_dialog = dialog
        self.page.open(dialog)

    def _copy_ticket(self, receipt: Receipt) -> None:
        try:
            self.page.set_clipboard(receipt.to_text())
            self._toast("Ticket sent to the clipboard. Keep your order number.")
        except Exception:
            logger.exception("Clipboard operation failed.")
            self._toast("Clipboard is unavailable. Please note your order number.")

    def _toast(self, message: str) -> None:
        self.page.open(ft.SnackBar(ft.Text(message, color="white"), bgcolor=INK))
