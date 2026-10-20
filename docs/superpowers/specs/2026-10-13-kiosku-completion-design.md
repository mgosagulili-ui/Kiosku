# Kiosku completion design

## Request and assumptions
The supplied archive contains a Python/Flet Lumah Caf kiosk, a 17-drink menu,
and an MVC/OOP structure, but no separate requirements or tests. The requested
outcome is to finish this existing application, not replace its technology.
Assumption: deliver a local, browser-based, pay-at-counter ordering application.
Preserve the 17 original drinks, categories and whole-peso prices. No claim is
made that a saved order is paid, dispatched to staff or an official receipt.

## Architecture
Retain models.py, controllers.py, views.py and main.py. Add storage.py for SQLite
order persistence and manage_orders.py for local operator list, ticket, export
and backup commands. Keep business rules independent of Flet. Each browser
session has its own cart; all sessions on this server share one order database.
Use the original Flet 0.28.3 API with its matching web extra, not an unverified
upgrade. No remote cloud services or payment-provider connections.

## Behaviour and controls
- Strict integer prices and quantities; reject booleans, negatives and fractions.
- Quantities range from 1 to 99 per item; decrementing below 1 removes the line.
- Reject duplicate menu IDs; external cart snapshots cannot change its state.
- Review/confirm before ordering and confirm before clearing a nonempty cart.
- Save order and lines atomically before clearing the cart. On storage failure,
  retain the cart and give a retry message. Order numbers survive restarts.
- Lock controller state; prevent repeat checkout from saving the same cart twice.
- Use an idempotency key and immutable item/price snapshots for saved orders.
- Display payment pending and a scrollable order ticket, with optional copy.
- Responsive wide cart and narrow bottom sheet; no remote custom font dependency.
- Default server binding is loopback only. Database remains outside served assets.
- Provide setup/launch scripts, operator commands, tests, and clear limitations.

## Acceptance and boundaries
Test models, persistence, multiple sessions, concurrent submissions, save failure,
controller notifications, view event flows and actual browser startup. Verify a
wide and phone-sized viewport. Deliver a clean source ZIP without environments,
font files, compiled caches, or live order data. Document any browser/platform
checks that could not be executed. Native installers, real payments, tax logic,
stock management, kitchen dispatch and authenticated internet hosting are outside
this completion scope. Unsaved carts are session-only, not persisted.
