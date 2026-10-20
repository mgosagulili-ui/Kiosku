# Upgrade and data preservation

1. Stop Kiosku fully. Before replacing code, back up `data/orders.sqlite3` to a different location.
2. Extract the replacement project source. If you have real records, preserve **your** existing database file and do not overwrite it with the archive's sample file.
3. Run the setup script and tests. Start the program on the same data directory.
4. The first start upgrades an existing Kiosku v1 database to v2, preserving order and order-line rows. New columns for payment details on older orders are blank; those tickets still display `PAYMENT PENDING`.
5. Pre-existing products receive `Stock not set` because prior data contained no verified stock balances. Inventory edits establish opening counts, then later paid checkouts subtract inventory atomically.
6. Keep periodic SQLite backups. `manage_orders.py backup --output <new-file>` makes a consistent backup and never overwrites a file.
7. To roll back to the previous program version, restore the v1 backup and the old program files; the old program is not compatible with the new v2 schema.

This application is intended for supervised local classroom use. The admin pages are not protected by account login. QR status is a cashier declaration, not a successful provider integration.
