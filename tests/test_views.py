"""Real Flet controls with a page test double. These are not browser E2E tests."""
import ast
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

HAS_FLET = importlib.util.find_spec('flet') is not None
if HAS_FLET:
    import flet as ft
    from views import KioskView, WIDE
    from controllers import KioskController
    from storage import SQLiteOrderStore, OrderStoreError
    from models import Coffee, Menu, Receipt


class ViewSourceContractTests(unittest.TestCase):
    def test_confirmation_handlers_exist(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'views.py').read_text())
        methods = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        self.assertTrue({'_review_order', '_confirm_order', '_request_clear'} <= methods,
                        'Explicit order and clear confirmation handlers are missing')


    def test_menu_card_root_is_direct_container_for_web_grid(self):
        """Regression: avoid accessibility wrapper hiding entire grid tiles.

        The Python structural check runs even without Flet; a live browser
        check is still required to validate the deployed Flutter web client.
        """
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'views.py').read_text())
        view_cls = next(node for node in tree.body
                        if isinstance(node, ast.ClassDef) and node.name == 'KioskView')
        card_method = next(node for node in view_cls.body
                           if isinstance(node, ast.FunctionDef) and node.name == '_card')
        last_return = next(node for node in reversed(card_method.body)
                           if isinstance(node, ast.Return))
        self.assertIsInstance(last_return.value, ast.Name)
        self.assertEqual(last_return.value.id, 'card',
                         'GridView children must directly expose the interactive card.')


class FakePage:
    def __init__(self, width=1280, height=900):
        self.width, self.height = width, height
        self.fonts = {}
        self.window = SimpleNamespace(full_screen=False)
        self.controls, self.dialogs = [], []
        self.updates = 0
        self.clipboard = ''

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        self.updates += 1

    def open(self, control):
        control.open = True
        self.dialogs.append(control)

    def close(self, control):
        control.open = False

    def set_clipboard(self, value):
        self.clipboard = value


@unittest.skipUnless(HAS_FLET, 'Flet must be installed to test actual UI controls')
class ViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SQLiteOrderStore(Path(self.temp.name) / 'orders.sqlite3')
        self.ctl = KioskController(store=self.store)
        self.page = FakePage()
        self.view = KioskView(self.page, self.ctl)
        self.view.mount()
        self.iid = self.ctl.items_in('Coffee')[0].id

    def add_and_review(self):
        self.ctl.add_item(self.iid)
        self.view._review_order()
        return self.view._review_dialog

    def select_cash(self, view=None, received='100'):
        view = view or self.view
        view._payment_radio.value = 'CASH'
        view._cash_field.value = received

    def test_non_coffee_grid_shows_four_named_drink_cards(self):
        self.view._select('Non Coffee')
        grid = self.view._grid()
        self.assertEqual(len(grid.controls), 4)
        for card, name in zip(grid.controls,
                              ('Chocoberry', 'Strawberry', 'Milo Dino', 'Choco')):
            self.assertIsInstance(card, ft.Container)
            self.assertTrue(callable(card.on_click))
            self.assertIn(name, [control.value for row in card.content.controls
                                 if isinstance(row, ft.Column)
                                 for control in row.controls
                                 if isinstance(control, ft.Text)])

    def test_wide_layout(self):
        self.assertIsInstance(self.view.body.content, ft.Row)
        self.assertEqual(self.page.fonts, {})

    def test_narrow_layout(self):
        self.page.width = 390
        self.view.refresh()
        self.assertIsInstance(self.view.body.content, ft.Column)

    def test_review_does_not_save(self):
        dialog = self.add_and_review()
        self.assertTrue(dialog.open)
        self.assertEqual(self.store.all(), ())
        self.assertEqual(self.ctl.cart_count(), 1)

    def test_cancel_review_keeps_cart(self):
        dialog = self.add_and_review()
        dialog.actions[0].on_click(None)
        self.assertFalse(dialog.open)
        self.assertIsNone(self.view._review_dialog)
        self.assertEqual(self.ctl.cart_count(), 1)

    def test_confirmation_saves_ticket(self):
        dialog = self.add_and_review()
        self.select_cash()
        dialog.actions[1].on_click(None)
        self.assertEqual(self.store.get(1).total, 79)
        self.assertEqual(self.store.get(1).change_due, 21)
        self.assertEqual(self.ctl.cart_count(), 0)
        self.assertTrue(self.view._receipt_dialog.open)
        self.assertIn('001', self.view._receipt_dialog.title.value)

    def test_payment_method_is_required(self):
        dialog = self.add_and_review()
        dialog.actions[1].on_click(None)
        self.assertEqual(self.store.all(), ())
        self.assertTrue(dialog.open)

    def test_insufficient_cash_does_not_save(self):
        dialog = self.add_and_review()
        self.select_cash(received='50')
        dialog.actions[1].on_click(None)
        self.assertEqual(self.store.all(), ())
        self.assertTrue(dialog.open)

    def test_qr_checkout_records_manual_confirmation(self):
        dialog = self.add_and_review()
        self.view._payment_radio.value = 'QR'
        dialog.actions[1].on_click(None)
        self.assertEqual(self.store.get(1).payment_method, 'QR')
        self.assertEqual(self.store.get(1).payment_status, 'PAID')

    def test_operator_pages_load(self):
        for page in ('inventory', 'history', 'reports'):
            self.view._navigate(page)
            self.assertEqual(self.view.section, page)
            self.assertIsInstance(self.view.body.content, ft.Column)

    def test_admin_page_uses_consistent_padding_and_scroll(self):
        for section in ('inventory', 'history', 'reports'):
            self.view._navigate(section)
            layout = self.view.body.content
            self.assertIsInstance(layout.controls[1], ft.Container)
            self.assertEqual(layout.controls[1].padding.left, 28)
            self.assertEqual(layout.controls[1].padding.right, 28)
            self.assertIsInstance(layout.controls[1].content, ft.Column)
            self.assertEqual(layout.controls[1].content.scroll, ft.ScrollMode.AUTO)

    @staticmethod
    def _descendant_controls(root):
        """Walk the real Flet control tree, including nested card containers."""
        stack = [root]
        while stack:
            control = stack.pop()
            yield control
            nested = getattr(control, 'content', None)
            if isinstance(nested, ft.Control):
                stack.append(nested)
            stack.extend(reversed(getattr(control, 'controls', []) or []))

    def test_saved_order_history_cards_have_bounded_height(self):
        self.ctl.add_item(self.iid)
        saved = self.ctl.checkout(payment_method='CASH', cash_received=100)
        self.assertIsNotNone(saved)
        history = self.view.admin._history()
        rows = [c for c in history if isinstance(c, ft.Container)
                and any(isinstance(node, ft.Text) and
                        f"Order #{saved.number:03d}" in (node.value or "")
                        for node in self._descendant_controls(c))]
        self.assertEqual(len(rows), 1, "Order history must display the saved ticket")
        card = rows[0]
        self.assertIsInstance(card.content, ft.Column)
        self.assertTrue(card.content.tight)
        wrapped_rows = [c for c in self._descendant_controls(card)
                        if isinstance(c, ft.Row) and c.wrap]
        self.assertTrue(wrapped_rows)
        for row in wrapped_rows:
            self.assertTrue(all(not c.expand for c in row.controls),
                            "An expanding child in a wrapped Row produces oversized gray cards in Flet web")
        details = next(c for c in self._descendant_controls(card)
                       if isinstance(c, ft.OutlinedButton) and c.text == "Details")
        details.on_click(None)
        self.assertEqual(self.page.dialogs[-1].title.value, f"Order #{saved.number:03d}")

    def test_history_record_width_respects_page_padding(self):
        self.page.width = 390
        self.ctl.add_item(self.iid)
        self.ctl.checkout(payment_method='CASH', cash_received=100)
        cards = [c for c in self.view.admin._history() if isinstance(c, ft.Container)]
        self.assertEqual(len(cards), 1)
        main_text = cards[0].content.controls[0].controls[0]
        self.assertIsInstance(main_text, ft.Container)
        self.assertLessEqual(main_text.width, self.page.width - 110)

    def test_sales_product_and_daily_rows_do_not_expand_in_wrap(self):
        from datetime import datetime
        from storage import LOCAL_TZ
        self.ctl.add_item(self.iid)
        saved = self.ctl.checkout(payment_method='CASH', cash_received=100)
        report_day = str(datetime.fromisoformat(saved.created_at).astimezone(LOCAL_TZ).date())
        self.view.admin.report_start = self.view.admin.report_end = report_day
        report_controls = self.view.admin._reports()
        cards = [c for c in report_controls if isinstance(c, ft.Container)]
        self.assertGreaterEqual(len(cards), 3, "Summary, product, and daily-total cards are expected")
        product = next(c for c in cards if any(isinstance(node, ft.Text) and
                       (node.value or "").startswith("1. Cafe Latte")
                       for node in self._descendant_controls(c)))
        self.assertTrue(any(isinstance(node, ft.Text) and "1 sold" in (node.value or "")
                            for node in self._descendant_controls(product)))
        self.assertTrue(any(isinstance(node, ft.Text) and report_day in (node.value or "")
                            for node in self._descendant_controls(cards[-1])))
        for card in cards:
            for row in self._descendant_controls(card):
                if isinstance(row, ft.Row) and row.wrap:
                    self.assertTrue(all(not c.expand for c in row.controls),
                                    "A wrapped report row cannot contain expanding children")

    def test_inventory_cards_are_horizontal_wrapped_with_selection(self):
        self.view._navigate('inventory')
        cards_row = next(c for c in self.view.admin._inventory()
                         if isinstance(c, ft.Row) and c.controls
                         and isinstance(c.controls[0], ft.Container)
                         and getattr(c.controls[0], 'width', None) == 320)
        self.assertTrue(cards_row.wrap)
        self.assertGreater(len(cards_row.controls), 1)
        checkbox = cards_row.controls[0].content.controls[0].controls[0]
        self.assertIsInstance(checkbox, ft.Checkbox)
        self.assertFalse(checkbox.value)
        checkbox.value = True
        checkbox.on_change(SimpleNamespace(control=checkbox))
        self.assertEqual(len(self.view.admin.selected_stock_ids), 1)

    def test_bulk_restock_dialog_applies_different_quantities(self):
        first, second = self.ctl.items_in('Coffee')[:2]
        self.view.admin.selected_stock_ids.update((first.id, second.id))
        self.view.admin._bulk_restock()
        dialog = self.page.dialogs[-1]
        self.assertIsInstance(dialog, ft.AlertDialog)
        self.assertEqual(dialog.content.controls[0].value, 'SET')
        fields = [c for c in dialog.content.controls if isinstance(c, ft.TextField)]
        for field in fields:
            if field.label.startswith(first.name):
                field.value = '14'
            elif field.label.startswith(second.name):
                field.value = '9'
        dialog.actions[-1].on_click(None)
        self.assertFalse(dialog.open)
        self.assertEqual(self.view.admin.selected_stock_ids, set())
        current = {p.id: p.stock for p in self.ctl.inventory()}
        self.assertEqual((current[first.id], current[second.id]), (14, 9))

    def test_inventory_select_all_and_quick_stock_add(self):
        products = self.ctl.items_in('Coffee')
        item = products[0]
        self.view.admin._select_all_stock()
        self.assertEqual(self.view.admin.selected_stock_ids,
                         {p.id for p in self.ctl.inventory()})
        card = self.view.admin._inventory_product_card(item)
        controls = card.content.controls
        quick = controls[3].controls
        self.assertTrue(all(button.disabled for button in quick))
        self.ctl.bulk_restock({item.id: 10}, mode='SET', reason='STOCK COUNT')
        updated = next(p for p in self.ctl.inventory() if p.id == item.id)
        card = self.view.admin._inventory_product_card(updated)
        card.content.controls[3].controls[1].on_click(None)
        self.assertEqual(next(p.stock for p in self.ctl.inventory() if p.id == item.id), 15)

    def test_bulk_dialog_fill_all_different_modes(self):
        first, second = self.ctl.items_in('Coffee')[:2]
        self.ctl.bulk_restock({first.id: 4, second.id: 8}, mode='SET')
        self.view.admin.selected_stock_ids.update((first.id, second.id))
        self.view.admin._bulk_restock()
        dialog = self.page.dialogs[-1]
        self.assertEqual(dialog.content.controls[0].value, 'ADD')
        row = next(control for control in dialog.content.controls
                   if isinstance(control, ft.Row) and control.controls
                   and isinstance(control.controls[0], ft.TextField))
        row.controls[0].value = '3'
        row.controls[1].on_click(None)
        fields = [c for c in dialog.content.controls if isinstance(c, ft.TextField)]
        self.assertEqual(sum(field.value == '3' for field in fields), 2)
        dialog.actions[-1].on_click(None)
        stock = {p.id: p.stock for p in self.ctl.inventory()}
        self.assertEqual((stock[first.id], stock[second.id]), (7, 11))

    def test_duplicate_confirm_event_is_ignored(self):
        dialog = self.add_and_review()
        self.select_cash()
        action = dialog.actions[1].on_click
        action(None)
        self.ctl.add_item(self.iid)
        action(None)
        self.assertEqual(len(self.store.all()), 1)
        self.assertEqual(self.ctl.cart_count(), 1)

    def test_stale_review_is_closed_without_saving(self):
        dialog = self.add_and_review()
        self.select_cash()
        self.ctl.add_item(self.iid)
        dialog.actions[1].on_click(None)
        self.assertEqual(self.store.all(), ())
        self.assertFalse(dialog.open)
        self.assertEqual(self.ctl.cart_count(), 2)

    def test_clear_requires_confirmation(self):
        self.ctl.add_item(self.iid)
        self.view._request_clear()
        self.assertEqual(self.ctl.cart_count(), 1)
        self.view._clear_dialog.actions[1].on_click(None)
        self.assertEqual(self.ctl.cart_count(), 0)

    def test_cancel_clear_keeps_cart(self):
        self.ctl.add_item(self.iid)
        self.view._request_clear()
        self.view._clear_dialog.actions[0].on_click(None)
        self.assertEqual(self.ctl.cart_count(), 1)

    def test_failed_save_keeps_review_and_reenables_button(self):
        class BrokenStore:
            def save(self, *args, **kwargs):
                raise OrderStoreError('Forced failure')
        ctl = KioskController(store=BrokenStore())
        view = KioskView(FakePage(), ctl)
        view.mount()
        ctl.add_item(self.iid)
        view._review_order()
        dialog = view._review_dialog
        self.select_cash(view)
        dialog.actions[1].on_click(None)
        self.assertEqual(ctl.cart_count(), 1)
        self.assertTrue(dialog.open)
        self.assertFalse(dialog.actions[1].disabled)

    def test_sheet_closes_when_resized_wide(self):
        self.page.width = 390
        self.ctl.add_item(self.iid)
        self.view._open_sheet()
        sheet = self.view._sheet
        self.page.width = WIDE + 50
        self.page.on_resized(None)
        self.assertFalse(sheet.open)
        self.assertIsNone(self.view._sheet)

    def test_ticket_scrolls_and_can_be_copied(self):
        receipt = Receipt(7, tuple((f'Item {i}',1,79) for i in range(17)), 17 * 79)
        self.view._show_receipt(receipt)
        self.assertTrue(self.view._receipt_dialog.scrollable)
        self.view._receipt_dialog.actions[0].on_click(None)
        self.assertIn('PAYMENT PENDING', self.page.clipboard)

    def test_custom_category_has_fallback_styling(self):
        class Tea(Coffee): category = 'Tea'
        view = KioskView(FakePage(), KioskController(Menu([Tea('tea','Tea',59)]), store=self.store))
        view.mount()
        self.assertEqual(view.category, 'Tea')

    def test_empty_review_does_not_open_confirmation(self):
        self.view._review_order()
        self.assertIsNone(self.view._review_dialog)
        self.assertEqual(self.store.all(), ())

    def test_start_new_order_closes_ticket(self):
        dialog = self.add_and_review()
        self.select_cash()
        dialog.actions[1].on_click(None)
        ticket = self.view._receipt_dialog
        ticket.actions[-1].on_click(None)
        self.assertFalse(ticket.open)
        self.assertIsNone(self.view._receipt_dialog)


if __name__ == '__main__':
    unittest.main()
