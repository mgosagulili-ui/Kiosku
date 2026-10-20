# Kiosku — Lumah Caf POS (MVC / OOP)

Python/Flet application with a local SQLite database for **cash / QR cashier-confirmed checkout, stock inventory, order history, and sales reporting**. Designed as a readable student OOP/MVC project rather than a commercial payment platform.

## Latest UI correction (14 October 2026)

The order-history and sales-report entries now use **compact, auto-height record cards** instead of rows with expanding children. This avoids the large blank gray panels reported in the Flet web UI. Order history retains the Details action; sales report retains per-product sales and daily totals. Narrow windows use responsive record widths. Existing page margins and inventory bulk restock remain unchanged.

For existing installations, replace `admin_views.py` from the small **History and Reports UI Patch**. Stop the application first; the patch does not include or replace `data/orders.sqlite3`.

## What's new

| Page | Functions |
| --- | --- |
| Menu / POS | Add to cart, review order, **choose Cash or QR**. Cash checkout requires entered tendered amount and shows change. QR checkout requires the cashier to verify the wallet transfer outside the app. |
| Inventory | Add/edit/archive/restore products; define categories; set prices and actual stock; automatically subtract sold units; log stock counts, restocks and sales; compare stock at two Philippine-local dates. |
| Order history | Browse saved orders, filter by a day or inclusive date range, view item details, payment method, cash received and change. Older unpaid tickets remain visible. |
| Sales report | Filter by inclusive Philippine-local date range; paid orders, gross sales, units sold, average order value, most popular item, top revenue item, Cash vs QR, per-product and daily breakdowns, and CSV copy. |

All these records share one **`data/orders.sqlite3`** database. It stays on disk between app restarts. The original 17 products and four categories are preloaded on a new database. The existing SQLite v1 order database is automatically migrated to v2 and previous orders are kept.

**Opening stock:** The original menu did not include verified stock quantities, so existing products display **Stock not set**. Enter a real current count in Inventory. Until a stock count is entered for a legacy product, its orders are saved but no stock quantity can be deducted. All newly created items require an explicit opening stock number.

**Deleting products:** The Delete button archives a product from the selling menu. Historical transactions, item names, selling prices and stock movements remain in the database. Archived products can be restored.

## Windows setup

1. Extract this ZIP into a **writable** folder (do not run it inside the ZIP).
2. Install Python 3.13 if needed. Use **`SETUP_WINDOWS.bat`** to create `.venv` and install the pinned Flet 0.28.3 dependency. Internet access is required for the initial install.
3. Run **`RUN_TESTS_WINDOWS.bat`**. Zero failures/errors/skips should be required on the target PC.
   If the legacy-v1 migration test failed with WinError 32 in the 14 October build,
   use the two-file correction described in `docs/WINDOWS_LEGACY_MIGRATION_FIX_2026-10-14.md`.
4. Run **`RUN_WINDOWS.bat`** to start the app. Open `http://127.0.0.1:8550` on the same computer. Keep the terminal open; Ctrl+C stops the server.

This updated ZIP **does not contain `data/orders.sqlite3`** (so it cannot replace existing saved orders/stock); on a fresh installation Kiosku creates that file at first launch. The ZIP also **does not include a portable Python environment**. Setup recreates it on your computer.

## macOS / Linux

```bash
bash setup.sh
bash run-tests.sh
bash run.sh
```

Or install with `python -m pip install -r requirements.txt` and start with `python main.py`. Python 3.10+ is required; Python 3.13 is recommended for this Flet release.

## Updated inventory workflow (14 October 2026)

Products are displayed in horizontal wrapping cards, with Select, quick +1/+5/+10
buttons, and Edit / set stock. **An uncounted product has no verified starting
quantity**: first set its exact stock after a physical count. Quick-add buttons
are disabled until then.

For several products at once, check their **Select** boxes (or press **Select all**),
click **Restock selected**, and choose one of:

- **Add quantities** to existing verified counts (e.g. new deliveries).
- **Set exact stock** after counting actual inventory (required for items
  showing "Not set").

Enter a separate whole-number quantity for each selected item, or type a shared
quantity and press **Fill all**. Enter an adjustment reason and save. The
repository commits all selected changes together and logs each actual quantity
change; if any selection is invalid, **none** of the updates are committed.

## Where data is saved

The file `data/orders.sqlite3` beside the Python source contains: all orders, lines, payment method and cash details; product list; categories; archived product flags; all historical stock movements. **Do not delete or replace this file** when installing future source updates. Database access is local and file-based, not tied to the browser window.

If replacing your project folder, copy your current `data/orders.sqlite3` into the new project folder **before first launch**. Before upgrading, stop the app and save a separate copy of the database. For a consistent database backup on a running-capable installation:

```bash
python manage_orders.py backup --output kiosku-backup.sqlite3
```

Alternatively, use `python main.py --data-dir /path/to/private/data` to control the database directory; the same directory must be specified for `manage_orders.py --data-dir /path/to/private/data ...`.

Useful local commands:

```bash
python main.py --check
python -m unittest discover -v
python manage_orders.py list
python manage_orders.py ticket 1
python manage_orders.py export --output orders-export.csv
python manage_orders.py backup --output new-backup.sqlite3
```

`manage_orders.py export` includes legacy unpaid orders; use the Sales report page for paid-sales totals.

## What the sales numbers mean

- **Paid sales** are orders explicitly marked Cash or QR by an operator. An order saved by the older version without payment information stays **PAYMENT PENDING** and does not count as paid sales.
- **Gross sales** sum recorded selling prices; discounts, taxes, refunds, expenses, fees and net profit are **not tracked**.
- Date ranges and daily grouping use **Asia/Manila (UTC+08:00)**. Data timestamps are stored in UTC.
- **QR is manual confirmation**: Kiosku does not connect to GCash/Maya/banks, generate verified QR payment requests, or check transaction settlement. Only click Confirm after checking payment externally.

## Limits before real commercial deployment

This is a local educational POS, **not certified payment processing or official tax receipt software**. Operator pages do **not** currently require administrator login, so do not expose the kiosk to customers with those pages available. This version has no refunds/voids, official tax receipts, supplier purchases, unit conversions, raw-ingredient recipe depletion, kitchen ticketing, or automatic cloud backup/sync. Stock is measured per **sellable menu item** (units), not ingredients.

Changes and automated tests are in `CHANGELOG.md` and `tests/`. The handover's live Windows/browser/touch acceptance tests still need to be performed on your computer: see `docs/ACCEPTANCE_CHECKLIST.md`. The older `docs/VERIFICATION*.md` and earlier progress notes describe the predecessor version, not verification of this update.
