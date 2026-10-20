# On-device acceptance checklist — Kiosku update 14 October 2026

**Status:** Needs manual verification on the actual Windows/browser device. Automated unit/control construction tests cannot verify screenshots or QR settlement.

Use a separate test directory: `python main.py --data-dir ./test-data`. Do not mix test orders with the real store database.

| Area | What to check | Result |
| --- | --- | --- |
| Setup | `SETUP_WINDOWS.bat`, `main.py --check`, all tests with no skipped tests | Pending |
| Original menu | 17 products, 4 categories, correct original prices and card labels | Pending |
| Navigation | Menu/POS, Inventory, Order history, Sales report accessible in wide and narrow layouts | Pending |
| Review and cancellation | Cancelling review leaves the cart and does not create an order | Pending |
| Required payment | Confirm without choosing Cash or QR does not save | Pending |
| Cash | ₱79 order, ₱50 tendered rejected; ₱100 accepted with ₱21 change | Pending |
| QR | Cashier verifies payment outside app; QR method recorded in saved ticket | Pending |
| Prevent duplicate | Double-click confirm: one order and one stock deduction | Pending |
| Category/product | Add new category and product; edit name, category, price and count | Pending |
| Stock | Set 2 units, sell 1, current quantity becomes 1; selling 2 more is blocked | Pending |
| Inventory history | Stock adjustment and sale show time, reason, before and after | Pending |
| Compare days | Compare stock at two distinct dates with known counts | Pending |
| Archive/restore | Archived product disappears from menu; history remains; restore reappears | Pending |
| Order history | Search old days; see item lines, tendered cash, change, QR, legacy unpaid tickets | Pending |
| Reports | Range with Cash and QR shows correct paid gross, top item, breakdown and daily totals | Pending |
| Reports exclude unpaid | Pre-migration pending order does not inflate paid-sales totals | Pending |
| Clipboard | Copy report CSV, paste into spreadsheet; check Unicode item names | Pending |
| Restart | Stop/reopen app; inventory, archived flags, stock history, orders and reports remain | Pending |
| Backups | `manage_orders.py backup` result can be opened in a separate test folder | Pending |
| Two sessions | Separate carts, no overselling if two sessions try to buy last unit | Pending |
| Small screen | 390px width: menus, forms, actions, dialogs scroll and remain reachable | Pending |
| Receipt | Ticket is marked payment recorded but is not claimed as official tax receipt | Pending |

**Known limitations:** Admin/operator pages have no login; QR transfers are not externally verified; no tax, refunds, ingredients, or automatic backups. Record the Windows, Python, Flet and browser versions with any bugs discovered during acceptance testing.


## Inventory and margins — 14 October 2026 update

- [ ] POS, Inventory, Order history, and Sales report headers have comfortable
      left/right page margins, including on a narrow browser window.
- [ ] Inventory cards flow side-by-side on a wide window and wrap on mobile.
- [ ] A checkbox selection stays visible when multiple cards are selected.
- [ ] Select all, Clear selection, and Restock selected respond correctly.
- [ ] The restock dialog allows DIFFERENT quantities per product; Fill all also works.
- [ ] Add restock on an item without opening stock is blocked, while exact stock
      is permitted after a physical count.
- [ ] A mixture of a valid and invalid restock quantity saves NONE of the changes.
- [ ] Restocked quantities and stock-movement reasons persist after app restart.
- [ ] Previously saved orders and inventory counts remain present after installing
      the source-only update, without replacing `data/orders.sqlite3`.
