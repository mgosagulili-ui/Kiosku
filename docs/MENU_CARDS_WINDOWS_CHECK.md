# Gray menu card troubleshooting (Windows/Flet 0.28.3)

## Observation

The supplied screenshot shows four large gray tiles in the **Non Coffee** tab,
not an empty grid. The model has the four products: Chocoberry (PHP 89),
Strawberry (PHP 89), Milo Dino (PHP 79), Choco (PHP 79). There are no drink
images or remote image dependencies in `views.py`.

## Likely mechanism and narrow workaround

In the previous package, `KioskView._card()` returned:

```python
ft.Semantics(content=card, label=..., button=True)
```

`_grid()` passed those wrapper controls as the children of `ft.GridView`.
Flet/Flutter appears to allocate tile space but not show the inner card in the
reported Windows browser. This has **not** been reproduced in a browser in this
sandbox, so the exact client-side mechanism is still unconfirmed.

The patch passes the original `ft.Container` directly to `GridView` and places
the label in `Container.tooltip` instead. This is a narrow UI-only change.

## How to apply

Option A (least disruptive): replace only `<project>\views.py` using the
included replacement file. Close the running app before replacing.

Option B: extract the full patched ZIP into a NEW folder and use its launchers.
Copy your `data/` directory from the previous project only if you want to
continue using existing saved orders; back it up before copying. Do not delete
or overwrite an existing database casually.

## Confirm on Windows

1. Stop the kiosk with Ctrl+C in its terminal; close its browser tab.
2. Replace `views.py` or launch the extracted patched full project.
3. Run `RUN_TESTS_WINDOWS.bat`; all tests should pass with zero errors or skips
   when Flet is installed. The patched suite contains 96 tests total.
4. Run `RUN_WINDOWS.bat` and hard-reload the kiosk browser (Ctrl+Shift+R).
5. Switch among all four categories. The Non Coffee tab should display four
   white, labeled price cards, each clickable and adding to the cart.
6. Confirm checkout still displays item names, total, review, and ticket.

If the rectangles remain gray, send the terminal traceback or Chrome/Edge
DevTools Console output, the exact Flet versions from `main.py --check`, and
whether the cards are clickable. That will distinguish a second rendering bug,
a stale web client, or a mismatch in the installed Flet components.

## Verification boundary

- Automated Python suite in sandbox: **80 passed, 16 skipped** (Flet not
  installable here). Source structure test failed before fix and passed after.
- A real Flet-control test is included but skipped here for lack of Flet.
- No browser, Windows, or Python 3.14 execution was performed in this sandbox.
