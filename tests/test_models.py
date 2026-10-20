import unittest
from models import Cart, CartItem, Coffee, Menu, MenuItem, NonCoffee, Receipt, Soda, Special, peso


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.item = Coffee('coffee', 'Cafe Latte', 79)
        self.cart = Cart()

    def test_price_format(self):
        self.assertEqual(peso(1234), '₱1,234')

    def test_invalid_prices_rejected(self):
        for value in (-1, 1.5, True, '79'):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                Coffee('x', 'X', value)

    def test_empty_id_or_name_rejected(self):
        for iid, name in [('', 'X'), ('   ', 'X'), ('x', ''), ('x', '  ')]:
            with self.subTest(iid=iid, name=name), self.assertRaises(ValueError):
                Coffee(iid, name, 1)

    def test_item_properties_are_read_only(self):
        with self.assertRaises(AttributeError):
            self.item.price = 1

    def test_constructor_rejects_invalid_quantity(self):
        for value in (0, -1, 100, 1.5, True):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                CartItem(self.item, value)

    def test_add_rejects_invalid_quantity_without_mutation(self):
        self.cart.add(self.item, 2)
        for value in (0, -1, 100, 1.5, True):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.cart.add(self.item, value)
            self.assertEqual(self.cart.quantity_of('coffee'), 2)

    def test_add_merges(self):
        self.cart.add(self.item, 2)
        self.cart.add(self.item)
        self.assertEqual((self.cart.count, self.cart.total), (3, 237))
        self.assertEqual(len(self.cart.lines), 1)

    def test_combined_quantity_limit_is_atomic(self):
        self.cart.add(self.item, 99)
        with self.assertRaises(ValueError):
            self.cart.add(self.item)
        self.assertEqual(self.cart.count, 99)

    def test_decrement_removes_at_zero(self):
        self.cart.add(self.item)
        self.cart.change_quantity('coffee', -1)
        self.assertTrue(self.cart.is_empty())

    def test_delta_rejects_noninteger(self):
        self.cart.add(self.item)
        for value in (0.5, True, '1'):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.cart.change_quantity('coffee', value)
        self.assertEqual(self.cart.count, 1)

    def test_cart_lines_cannot_mutate_cart(self):
        self.cart.add(self.item)
        line = self.cart.lines[0]
        try:
            line.quantity = 7
        except (AttributeError, TypeError):
            pass
        self.assertEqual(self.cart.count, 1)

    def test_remove_missing_and_clear(self):
        self.cart.change_quantity('missing', -1)
        self.cart.remove('missing')
        self.cart.add(self.item)
        self.cart.clear()
        self.assertEqual(self.cart.total, 0)

    def test_empty_cart_cannot_produce_ticket(self):
        with self.assertRaises(ValueError):
            self.cart.to_receipt(1)

    def test_ticket_number_validation(self):
        self.cart.add(self.item)
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.cart.to_receipt(value)

    def test_ticket_snapshots_cart(self):
        self.cart.add(self.item, 2)
        ticket = self.cart.to_receipt(4)
        self.cart.clear()
        self.assertEqual(ticket.lines, (('Cafe Latte', 2, 158),))
        self.assertEqual(ticket.total, 158)

    def test_ticket_total_must_match_lines(self):
        with self.assertRaises(ValueError):
            Receipt(1, (('Cafe Latte', 1, 79),), 1)

    def test_ticket_text_explains_payment_pending(self):
        ticket = Receipt(1, (('Cafe Latte', 2, 158),), 158)
        self.assertTrue(hasattr(ticket, 'to_text'), 'Ticket text output is missing')
        text = ticket.to_text()
        self.assertIn('001', text)
        self.assertIn('2 x Cafe Latte', text)
        self.assertIn('PAYMENT PENDING', text)
        self.assertIn('not proof of payment', text.lower())

    def test_duplicate_menu_ids_rejected(self):
        with self.assertRaises(ValueError):
            Menu([self.item, Coffee('coffee', 'Other', 10)])

    def test_empty_menu_rejected(self):
        with self.assertRaises(ValueError):
            Menu([])

    def test_original_menu_preserved(self):
        menu = Menu.lumah_default()
        self.assertEqual(menu.categories(), ['Coffee', 'Specials', 'Non Coffee', 'Soda'])
        items = [i for c in menu.categories() for i in menu.in_category(c)]
        self.assertEqual(len(items), 17)
        self.assertEqual([(i.name, i.price) for i in items], [
            ('Cafe Latte',79),('Cafe Mocha',89),('Seasalt Latte',89),
            ('Spanish Latte',89),('Salted Caramel',89),('Hojicha Latte',99),
            ('Matcha Latte',109),('Seasalt Hojicha',119),('Seasalt Matcha',129),
            ('Chocoberry',89),('Strawberry',89),('Milo Dino',79),('Choco',79),
            ('Blue Lemonade',59),('Strawberry Soda',59),('Blueberry',59),('Green Apple',59)])

    def test_category_behaviour(self):
        for cls in (Coffee, Special, NonCoffee, Soda):
            self.assertTrue(cls('x', 'X', 1).describe())

    def test_cart_cannot_merge_conflicting_item_details(self):
        self.cart.add(self.item)
        with self.assertRaises(ValueError):
            self.cart.add(Coffee('coffee', 'Changed', 999))
        self.assertEqual(self.cart.total, 79)


if __name__ == '__main__':
    unittest.main()
