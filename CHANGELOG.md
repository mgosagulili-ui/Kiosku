## 14 October 2026 — Order history and sales report oversized-card fix

- Removed expanding controls nested inside wrapping rows in the Order History, Sales Report product-performance, daily totals and order-details views. On affected Flet web clients, this combination produced oversized gray/blank blocks instead of readable content.
- Kept order records and product/daily sales figures in compact, auto-height cards with responsive label widths and the existing page margins.
- Added three Flet-control regression tests for saved order display, product/daily report display, narrow viewport sizing and absence of expanding children in wrapped rows.
- No database migration or changes to inventory, checkout, report arithmetic, or order persistence. The update ZIPs do not contain a database file.
- 125 automated tests pass using the project Flet 0.28.3 package libraries; Windows/browser visual verification remains pending.

## 14 October 2026 — Responsive page spacing, inventory product grid and bulk stock editing

- Added consistent 28-pixel left/right margins to the POS header, navigation,
  product grid, cart area and all three operator pages.
- Replaced narrow, vertically stacked inventory product entries with compact
  320-pixel cards that wrap horizontally to use the available screen width.
- Added product checkboxes, Select all, Clear selection, and an editable
  multi-product restock dialog. Each selected product can receive a different
  quantity, or Fill all can copy a shared amount into every selected field.
- Added quick +1 / +5 / +10 buttons for previously counted products.
  Uncounted products must receive a physical opening count before adding stock.
- Added a repository/controller bulk-restock operation: validates all selected
  products, applies updates in one SQLite transaction and logs stock movements.
  A failed update does not partially commit other selected changes.
- Kept SQLite schema version 2 unchanged. No migration or database replacement.
- Added regression tests for GUI layout/selection/bulk editing, restart
  persistence, transactional rollback, and stock-history entries.
- Verified: 122 automated tests pass using Flet 0.28.3 package libraries in a
  Linux environment; no live Windows browser layout test was performed.
- Full source archive deliberately **excludes data/orders.sqlite3** to prevent
  accidental replacement of a user's live stock/order records.

# Changes from the supplied Kiosku archive

## 14 October 2026 — Windows migration-test file-lock fix

- Corrected `tests/test_business_features.py`: the legacy-v1 SQLite fixture now uses
  `with closing(sqlite3.connect(old)) as db, db:` so the connection is closed before
  the temporary directory is removed on Windows.
- Added `test_legacy_migration_releases_connections` to the existing SQLite
  resource regression tests. It verifies the connection is closed before cleanup,
  including on systems where deleting an open SQLite file would otherwise work.
- No application code, database schema, or real order/inventory records were changed.
- Full test run: 113 tests, all passed, none skipped in a Linux environment with
  Flet package code extracted from the original upload. Windows Python 3.14
  execution still needs verification on the target machine.
- For an existing installation, copy only the two modified files under `tests/`;
  do not overwrite your working `data/orders.sqlite3` or `.venv`.


## 14 October 2026 — Cash/QR checkout, inventory, order history and reports

- Added a payment-method choice inside the order-review dialog. Cash checkout
  validates entered whole pesos, rejects underpayment and calculates change;
  QR payment is marked complete only when the operator confirms externally.
- Upgraded the existing SQLite order database from v1 to v2 in place, keeping
  earlier orders and introducing payment details, categories, products,
  stock-movement audit history and item-ID references.
- Added inventory create/edit/archive/restore, user-defined categories, stock
  balances, stock adjustment reasons and historical end-of-day comparisons.
- Added separate operator pages for orders by date and sales reports by date:
  product performance, most-sold, revenue leader, units, average ticket,
  cash/QR breakdowns, daily totals, and CSV clipboard output.
- Stock deduction and order/payment commit happen together in one SQLite
  transaction, with retry deduplication and multi-session oversell protection.
- Preserved original menu item names, order numbers, MVC components and
  backwards compatibility for reading older unpaid tickets.
- Added and updated automated tests. 112 tests passed when the uploaded
  Windows Flet package library was made available to the test interpreter;
  a live Windows/browser visual check has not been performed.

## 13 October 2026 — Blank menu-card rendering workaround

- For the reported Windows browser symptom (four blank gray Non Coffee tiles),
  remove the optional `ft.Semantics` wrapper from each interactive card.
- Preserve `ft.Container` as the immediate `ft.GridView` child; give it a
  tooltip that retains the drink action label.
- Add two tests: one source structure check that runs without Flet, and one
  Flet-control check for the four Non Coffee drink cards when Flet is installed.
- The menu data, cart, controller, SQLite storage, launch commands, and
  dependency pins are unchanged. Live Windows browser verification is pending.

## 13 October 2026 — SQLite test-cleanup correction

- Explicitly close five test-owned SQLite connections after transaction handling.
- Add three regression checks that detect the resource leak on Linux as well as Windows.
- Keep every application source file, dependency, launcher and database schema unchanged.
- Record current verification and preserve the original handover evidence.

## Implemented

- Retained the original MVC layout, Priceable abstraction, menu inheritance,
  café brand, 17 menu items, categories and price values.
- Fixed invalid quantities accepted through CartItem construction and Cart.add;
  rejected boolean/fractional input, conflicting item IDs and invalid totals.
- Added a 99-per-drink limit and detached cart snapshots.
- Replaced session-local numbering with atomic SQLite order records and lines,
  an application/schema ID, persistent numbering and idempotent retries.
- Added controller locking, observer deduplication/unbinding, stale-review
  checking and save-before-clear semantics; rendering failures do not reverse
  a committed order.
- Added review/confirmation, clear confirmation, payment-pending tickets, ticket
  copying, per-line removal and fallback styling for custom categories.
- Retained wide/narrow layouts, corrected sheet resize cleanup and made tickets
  scrollable. Removed the remote custom font URL. Non-coffee descriptions no
  longer assert that every drink is caffeine-free.
- Added explicit local launch options, native kiosk-mode selection, dependency
  diagnostics, matching Flet web dependency, and setup/run/test scripts.
- Added local order retrieval, CSV export and safe database backup commands.
- Added automated tests, handover notes and an on-device acceptance checklist.
- Omitted stale compiled caches and excluded real databases from the package.

## Verification limits

Flet was unavailable in the development environment and dependency downloads
failed. The graphical interface and native/fullscreen modes are implemented but
not runtime-verified in this handover. Test counts and specific gaps are recorded
in docs/VERIFICATION.md. No claim of production readiness or payment completion
is made.
