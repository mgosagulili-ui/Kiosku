# Kiosku Completion Implementation Plan

> **For agentic workers:** Execute task-by-task using executing-plans and TDD.

**Goal:** Finish the supplied local café ordering application and deliver tested source.
**Architecture:** Preserve MVC. Add a transactional SQLite repository and local
operator CLI. The browser views render controller state without payment processing.
**Tech Stack:** Python, Flet 0.28.3, sqlite3, unittest; Chromium for browser checks.
**Spec:** ../specs/2026-10-13-kiosku-completion-design.md

## Global constraints
Preserve original 17 menu items, categories and integer PHP prices. Quantities
must be integers from 1 through 99. Bind locally. No live data in the package.
Save before clearing. Orders are unpaid. Do not bundle fonts or environments.

## Review focus
Invalid quantities must not alter existing lines. Restarted and concurrent
sessions must not reuse numbers. Storage failure must preserve the cart. Stale
review/duplicate clicks must not save unintended orders. Small-screen dialogs
and long tickets must remain usable.

### Task 1: Model contracts
Files: models.py; tests/test_models.py.
Interfaces: preserve Menu, MenuItem, Cart, CartItem, Receipt and peso; extend
Receipt with created_at and request_id, and to_text().
- [x] Write validation, pricing, snapshot and catalog tests.
- [x] Run `python -m unittest tests.test_models -v`; observe regression failures.
- [x] Implement validations and immutable ticket snapshots.
- [x] Repeat command; expect all tests to pass. Commit.

### Task 2: Durable ordering
Files: storage.py, controllers.py; tests/test_storage.py, tests/test_controllers.py.
Interfaces: SQLiteOrderStore.save(lines, total, *, request_id) -> Receipt;
get(number), recent(limit), all(), backup(destination). KioskController accepts
store=, exposes preview(), and checkout(expected_lines=None) -> Receipt | None.
- [x] Write persistence, rollback, numbering, deduplication and controller tests.
- [x] Run these tests and verify the missing/incorrect features are detected.
- [x] Implement SQLite atomic saves and locked controller actions.
- [x] Run full unittest discovery; expect all tests to pass. Commit.

### Task 3: Completed views and launch
Files: views.py, main.py, requirements.txt, launch scripts; tests/test_views.py,
tests/test_main.py and docs/ACCEPTANCE_CHECKLIST.md.
Interfaces: retain KioskView.mount(); main exposes parse_args and launch options.
- [x] Write fake-page event-flow tests and CLI launch-configuration tests.
- [x] Run tests; verify missing review/clear/error-handling behaviour is detected.
- [x] Implement responsive review, unpaid ticket and safe launch paths.
- [x] Run full unit discovery: 76 passed, 15 Flet-control tests skipped.
- [ ] Install Flet, run the 15 control tests and perform real-browser/visual checks.
  Blocked in this environment; target-device acceptance checklist supplied.

### Task 4: Operator tools and handover
Files: manage_orders.py, tests/test_manage_orders.py, README.md, CHANGELOG.md,
docs/VERIFICATION.md.
Interfaces: CLI list, ticket, export, backup; no public customer-facing admin UI.
- [x] Write CLI tests including output safety and backup recovery.
- [x] Observe RED; implement; verify GREEN and full suite.
- [x] Perform separate self-review, document limits and test evidence.
- [x] Package source only, inspect ZIP, re-extract and run clean-package tests.

Handover limitation: no transitive lockfile or browser-pass evidence was fabricated;
see docs/VERIFICATION.md for the precise boundary.
