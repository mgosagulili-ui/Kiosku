"""Kiosku entry point. Run `python main.py --help` for launch options."""
from __future__ import annotations

import argparse
from importlib import metadata
import logging
import os
from pathlib import Path
import platform
import sqlite3
import sys

from controllers import KioskController
from storage import OrderStoreError, SQLiteOrderStore, default_database_path

FLET_VERSION = "0.28.3"


def _port(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Port must be an integer from 1 to 65535.") from exc
    if not 1 <= number <= 65535:
        raise argparse.ArgumentTypeError("Port must be from 1 to 65535.")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lumah Caf POS with cash/QR, inventory and sales reports.")
    parser.add_argument("--port", type=_port, default=8550, help="Browser-server port (default: 8550).")
    parser.add_argument("--data-dir", type=Path, help="Folder for orders.sqlite3; overrides KIOSKU_DATA_DIR.")
    parser.add_argument("--desktop", action="store_true", help="Open a native window; requires the desktop extra.")
    parser.add_argument("--kiosk", action="store_true", help="Open a fullscreen native window (implies --desktop).")
    parser.add_argument("--no-browser", action="store_true", help="Start the local web server without opening a browser.")
    parser.add_argument("--check", action="store_true", help="Check Python/Flet requirements without starting the app.")
    args = parser.parse_args(argv)
    if args.no_browser and (args.desktop or args.kiosk):
        parser.error("--no-browser cannot be combined with --desktop or --kiosk.")
    return args


def launch_settings(args: argparse.Namespace) -> dict:
    return {"host": "127.0.0.1", "port": args.port, "desktop": args.desktop or args.kiosk,
            "kiosk": args.kiosk, "open_browser": not args.no_browser,
            "database": default_database_path(args.data_dir)}


def dependency_check(desktop: bool = False) -> list[str]:
    problems = []
    if sys.version_info < (3, 10):
        problems.append("Python 3.10 or newer is required; Python 3.13 is recommended for this source version.")
    packages = ["flet", "flet-desktop-light" if desktop and platform.system() == "Linux"
                else "flet-desktop" if desktop else "flet-web"]
    for package in packages:
        try:
            version = metadata.version(package)
        except metadata.PackageNotFoundError:
            problems.append(f"{package} is not installed.")
        else:
            if version != FLET_VERSION:
                problems.append(f"{package} {version} is installed; this project requires {FLET_VERSION}.")
    return problems


def main(page, *, store=None, kiosk: bool = False) -> None:
    """A new controller/cart per browser session; the repository is shared."""
    from views import KioskView
    if kiosk:
        page.window.full_screen = True
        def keyboard(event):
            if event.key == "Escape":
                page.window.full_screen = False
                page.update()
        page.on_keyboard_event = keyboard
    KioskView(page, KioskController(store=store)).mount()


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    options = launch_settings(args)
    problems = dependency_check(options["desktop"])
    if args.check:
        print(f"Python: {platform.python_version()}")
        print(f"SQLite: {sqlite3.sqlite_version}")
        print(f"Flet required: {FLET_VERSION}")
        print(f"Order database: {options['database']}")
        if problems:
            print("\n".join(problems))
        else:
            print("Dependency versions match. This is not a visual or hardware test.")
        return int(bool(problems))
    if problems:
        extra = '[desktop]' if options['desktop'] else '[web]'
        print("Cannot start Kiosku:\n- " + "\n- ".join(problems), file=sys.stderr)
        print(f'Install with: python -m pip install "flet{extra}=={FLET_VERSION}"', file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        import flet as ft
        store = SQLiteOrderStore(options["database"])
        # These overrides affect this process only. Do not accidentally expose a
        # local, unauthenticated kiosk through inherited Flet environment settings.
        os.environ["FLET_SERVER_IP"] = options["host"]
        os.environ["FLET_SERVER_PORT"] = str(options["port"])
        os.environ.pop("FLET_ASSETS_DIR", None)
        os.environ.pop("FLET_UPLOAD_DIR", None)
        view = (ft.AppView.FLET_APP if options["desktop"] else
                ft.AppView.WEB_BROWSER if options["open_browser"] else None)
        if not options["desktop"]:
            print(f"Open http://127.0.0.1:{options['port']} in a browser on this computer.")
        print(f"Orders are saved to: {store.path}")
        print("Cash/QR payments are cashier-confirmed. Press Ctrl+C to stop the server.")
        ft.app(target=lambda page: main(page, store=store, kiosk=options["kiosk"]),
               view=view, host=options["host"], port=options["port"], assets_dir=None)
    except KeyboardInterrupt:
        print("\nKiosku stopped. Saved orders remain in the database.")
    except (OrderStoreError, OSError, ImportError, RuntimeError) as exc:
        print(f"Kiosku could not start: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
