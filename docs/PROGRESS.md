# Implementation ledger
Plan: docs/superpowers/plans/2026-10-13-kiosku-completion.md

Baseline: original archive preserved; extracted source is isolated. Original had
no tests. Reproduced acceptance of quantities 0, -1, 1.5 and True; duplicate menu
IDs silently overwritten; two sessions both assigned order number 1.

Scope decision: complete the existing local café kiosk without external services
or commercial POS claims. No separate feature specification was provided.
Pre-flight: Receipt snapshots connect model, store, controller, view and CLI;
controller actions remain Flet-independent. No shared-interface conflict found.

Task 1 complete: 22 model tests pass after 29 failing baseline assertions.
Validated constructor/setter/add paths, preserved all original menu rows, and
made cart snapshots detached. Descriptions no longer promise preparation times
or label all non-coffee drinks caffeine-free.
Environment finding: pip could not resolve PyPI; a direct download also failed.
UI-runtime verification will be explicitly distinguished from core tests.

Task 2 complete: 58 core tests pass. Tested 32 concurrent unique orders, 16 retries
of one idempotency key, rollback using a real failing SQLite trigger, restart
sequence continuity, consistent backup, and controller save-failure recovery.

Tasks 3–4 implementation completed: review/clear dialogs, unpaid ticket, local
launch diagnostics and options, operator CLI, setup scripts and handover notes.
Full suite result: 91 discovered, 76 passed, 15 Flet-control tests skipped.
GUI-runtime acceptance remains open; it is not marked passed.

Final review: self-review (no independent reviewer available). Reviewed save/clear
ordering, transaction rollback, concurrent numbering, replayed confirmation
handling, cart isolation, export overwrite protection, backup and served-data
boundaries. No further core defects identified in this pass. Visual behaviour
and platform-specific launch remain unverified, as listed in the acceptance file.

Scope decision: no payment, inventory, kitchen dispatch or public server was
invented from the archive. A commercial POS expectation would require additional
scope and acceptance work. Runtime decision: do not replace Flet merely because
this environment cannot download it; preserve the user's stack and disclose the
verification gap. Dependency decision: do not fabricate a transitive lockfile or
browser screenshots. Package source, test evidence and a target-device checklist.

Delivery mode: downloadable ZIP; preserve the local development branch and the
original upload. No repository was pushed, deployed or connected to live data.
