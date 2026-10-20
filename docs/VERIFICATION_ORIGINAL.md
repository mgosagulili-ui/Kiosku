# Kiosku verification and handover

**Date:** 13 October 2026  
**Input:** the supplied `Kiosku.zip` (original archive left unchanged)  
**Deliverable:** updated source for a local café-ordering prototype

## Recorded test result

```text
Command: python -m unittest discover -v
Tests discovered/run by unittest: 91
Passed: 76
Skipped: 15
Failures: 0
Errors: 0
Result: OK (skipped=15)
```

**Do not interpret this as 91 passing tests.** The 15 skipped cases are the
`ViewTests` in `tests/test_views.py`. They need the actual Flet package; they are
not tested using a substitute implementation of Flet. The separate source-contract
test only checks that confirmation handlers are defined, not that they render.
The source was also packaged, re-extracted and its test suite rerun; the same
76-pass/15-skip result was required before handover. File hashes were checked.

## Environment and checks

| Check | Result / boundary |
|---|---|
| Python | 3.13.5, Linux development environment |
| SQLite | 3.46.1 |
| Model/controller/storage tests | Passed; no Flet dependency in these layers |
| Operator commands | Listing, ticket output, export and backup tests passed |
| Launch options | Help, port validation, option conflicts and settings tests passed |
| All Python files | Syntax-parsed/compiled successfully |
| Shell scripts | `bash -n setup.sh run.sh run-tests.sh` passed |
| Patch whitespace | `git diff --check` passed before packaging |
| Flet dependency installation | Blocked: installer could not resolve PyPI; direct downloads also failed |
| `main.py --check` in this environment | Correctly reports missing Flet/flet-web and exits 1 |
| Flet control tests | 15 skipped; require an installed compatible Flet runtime |
| Browser rendering and interaction | Not run; no screenshots or visual-pass claims |
| Windows batch/native/fullscreen operation | Not run on Windows/desktop hardware |
| Code review | Separate author self-review; not an independent reviewer or security audit |

The original archive contained no tests. Before modification, checks reproduced
invalid quantities (0, -1, fractional and boolean), duplicate menu-ID overwrites,
and order number 1 being reused by independent controllers. Model regression
tests initially produced 29 failing assertions and passed after correction.

## Substantive behaviours exercised

The tests use real temporary SQLite files, not a mocked database, for persistence,
restart numbering, order retrieval and backup. They include 32 concurrent unique
orders; 16 concurrent retries of the same request; a real SQLite trigger forcing
an insert failure to test complete rollback; and reopening a backup to check both
order contents and the next order number. Controller tests exercise separate
session carts, repeat checkout, concurrent additions, stale reviews, failed saves,
an ambiguous post-commit retry, and rendering-listener failure after a saved order.

The menu preservation test compares every original name and price. Ticket tests
check totals and the payment-pending/not-proof-of-payment wording. Export tests
check one row per order and refusal to overwrite an existing file.

## Implementation decisions and remaining gaps

The task did not provide a separate requirements specification. The completion
scope was therefore the existing local Python/Flet ordering app, preserving its
MVC/OOP design and menu. Payment collection, taxes, inventory, printer/kitchen
integration and public hosting were not added. These would require additional
requirements and verification before the app could serve as a commercial POS.

Flet was retained at the uploaded project's version, 0.28.3, with its matching web
extra. The launch/dialog/semantics interfaces were checked against that release's
official source, but static API review is not a runtime test. A complete resolved
transitive-dependency lock was not invented when installation could not run.

The source includes the missing GUI behaviours and tests, but the GUI must still
be checked on the target device. The outstanding acceptance steps, including
small/landscape layouts, long tickets, touch/keyboard interaction and fullscreen,
are in `ACCEPTANCE_CHECKLIST.md`. No native executable is included.

## Before real use

Install the requirements, obtain zero failures/errors/skips in the full test run,
and complete the on-device acceptance checklist using a separate test database.
Confirm the menu with the café and define how staff receive order numbers and
collect payment. Keep backups of the actual data directory. Saved tickets are
unpaid orders, not payment or sales records.
