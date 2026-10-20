# Addendum: gray menu card patch — 13 October 2026

Current patched package: 96 tests discovered, 80 passing, 16 skipped for
unavailable Flet. An AST regression check was observed to fail with the old
Semantics wrapper and pass after removing it. The GUI-control test for the four
Non Coffee cards is provided but **not executed** in the sandbox. The precise
Windows browser failure is still unconfirmed until the user reruns it locally.
Read `MENU_CARDS_WINDOWS_CHECK.md` for the patch and confirmation steps.

---

# Kiosku SQLite test-cleanup fix — verification

**Date:** 13 October 2026  
**Applies to:** `Kiosku_Updated.zip`, the SQLite-enabled edition. This is not a replacement for the separate `Kiosku_OOP_MVC.zip` academic edition.

## Finding

The three reported Windows errors happen during `TemporaryDirectory.cleanup()`.
Five connections opened directly in `tests/test_storage.py` were not explicitly
closed: two in the rollback test, one in the future-schema test, and two in the
unrelated-database test. The application storage class already closes its own
connections in `finally`; it has not been changed.

Python's SQLite connection context manager commits or rolls back transactions;
it does not close the connection. Windows rejects removal of a file still in use,
whereas Unix permits removal of its directory entry. These documented differences
explain why the previous Linux run did not fail at temporary-file deletion.

## Correction

Imported `closing` from `contextlib` and changed all five affected blocks to:

```python
with closing(sqlite3.connect(self.path)) as db, db:
    # Existing SQL and assertions remain here.
```

The inner `db` context retains commit/rollback behaviour. The outer `closing`
context closes the connection after transaction handling, including exceptional
exits. No cleanup errors are ignored, no tests removed, no forced garbage
collection added, and no application databases or dependencies changed.

## Recorded verification

Environment: Python 3.13.5 / SQLite 3.46.1 / Linux. Flet is not installed here.

| Check | Observed result |
|---|---|
| Original suite, with ResourceWarning visible | 91 discovered: 76 passed, 15 skipped; five unclosed-database warnings |
| New resource checks against original code | Three tests produced five failing assertions, one for each leaked connection |
| Same resource checks after the patch | Three passed, zero failures |
| The three exact user-reported test methods after the patch | Three passed, zero errors |
| Full patched suite | 94 discovered: 79 passed, 15 skipped, zero failures/errors |
| ResourceWarning in the patched full-suite log | Zero occurrences |
| Python syntax | All 14 Python source files parsed successfully |
| Change review | Only `tests/test_storage.py` changed among existing Python files; one new test module added |

The three added tests retain actual SQLite connections from the reported
scenarios and check that querying each one raises the closed-database error
BEFORE temporary-directory cleanup. They use real SQLite, not a simulated
Windows filesystem or fake database. Their own safety cleanup occurs only after
the assertions, so it does not conceal a leak.

Raw before/after output and the minimal source diff are in `docs/windows-fix/`.
The previous handover report is retained as `VERIFICATION_ORIGINAL.md` and is
historical, not a claim about this patch.

## Apply the correction to an existing installation

Close the completed test window. Replace your existing `Kiosku/tests/test_storage.py`
with the corrected file. For the additional cross-platform regression checks,
also copy `tests/test_storage_resources.py` from the full patched ZIP into the
same `tests` directory. Leave all other existing tests in place.

Run `RUN_TESTS_WINDOWS.bat` again from your existing Kiosku folder. Replacing
only the original test file keeps the original 91-test count; copying the added
regression module raises it to 94. The pass/skip totals depend on whether Flet
is installed. A full local verification should have no failures, errors or skips.

There is no need to reinstall Python, rerun dependency setup, or delete a database
for this source correction. Leave `.venv` and the `data` directory untouched.
The original distribution's `MANIFEST.sha256` describes its pre-patch files; the
full patched ZIP includes a regenerated manifest for that distribution.

## Remaining verification gaps

The connection leak was reproduced and corrected on Linux. The exact Windows
file-lock error and Python 3.14 runtime have not been executed in this environment.
The 15 Flet-dependent control tests remain skipped here; browser/native display
and Windows batch launchers are not newly verified by this patch. Review was an
author self-review, not an independent review. No production-readiness claim is made.

## Primary references

- Python 3.14 sqlite3 — connection context manager: https://docs.python.org/3.14/library/sqlite3.html#how-to-use-the-connection-context-manager
- Python 3.14 contextlib.closing: https://docs.python.org/3.14/library/contextlib.html#contextlib.closing
- Python 3.14 os.remove — Windows versus Unix file deletion: https://docs.python.org/3.14/library/os.html#os.remove
