# Windows: `test_legacy_v1_migrates_without_losing_orders` cleanup fix

## Observed failure

The unit test reports `PermissionError: [WinError 32]` while deleting the
**temporary** file `%TEMP%\tmp...\legacy.sqlite3`. This is separate from
Kiosku's persistent `data/orders.sqlite3`.

## Root cause

The test previously used `with sqlite3.connect(old) as db:`. Python's `sqlite3`
connection context manager ends the transaction but **does not close** the
connection. On Windows the open handle blocks file deletion in
`TemporaryDirectory.cleanup()`.

## Fix

In `tests/test_business_features.py`, import `closing` from `contextlib` and
replace that specific fixture block with:

```python
with closing(sqlite3.connect(old)) as db, db:
    # Existing schema creation, legacy-order inserts and PRAGMAs unchanged.
```

Both behaviors are necessary: `db` commits or rolls back the transaction;
`closing` closes the file handle even when the fixture raises an exception.

`tests/test_storage_resources.py` now also contains a dedicated regression test
that tracks actual SQLite connections in the legacy migration scenario and
asserts they are closed **before** temporary-directory cleanup. A regression
should therefore fail on Linux as well as Windows.

## Applying the correction to an existing Windows installation

1. Exit Kiosku and close the previous test window.
2. Back up `data/orders.sqlite3` if it contains any real records; **do not**
   delete, reset, or overwrite it.
3. Replace only `tests/test_business_features.py` and
   `tests/test_storage_resources.py` with the files from the patch ZIP.
4. Run `RUN_TESTS_WINDOWS.bat` again. You should see 113 tests and no
   errors, failures or skips in the installed Flet environment.
5. If the file-lock error remains, confirm the traceback refers to the newly
   updated test file. Also ensure no second copy of Kiosku or SQLite browser
   has the same temporary file open.

The patch requires neither dependency reinstallation nor a database migration.

## Verification and limits

- On Linux (Python 3.13), all 113 unit tests passed with the Flet package code
  from the original uploaded archive. The new resource test passed.
- The target Windows + Python 3.14 environment has not been directly executed
  here. Re-run the Windows batch launcher for final verification.
- Changes are confined to two tests, documentation and the updated manifest;
  app source modules and the SQLite database contents remain unchanged.

References:
- https://docs.python.org/3.14/library/sqlite3.html#how-to-use-the-connection-context-manager
- https://docs.python.org/3.14/library/contextlib.html#contextlib.closing
