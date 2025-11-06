# src/omnote/app.py
from __future__ import annotations
import os, sys

from gi import require_version
require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")

from gi.repository import Adw, Gio  # type: ignore

from .window import MicroPadWindow
from .state import State
from .theme import start_theme_watcher, stop_theme_watcher, apply_best_theme

# Keep the existing app-id so your .desktop file keeps working
APP_ID = "dev.omarchy.MicroPad"


class MicroPad(Adw.Application):  # type: ignore
    def __init__(self) -> None:
        # NOTE: GApplication subclass
        Adw.Application.__init__(self, application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)  # type: ignore
        self._state: State | None = None
        self._theme_watcher = None

        # If the last window is removed, quit the app loop (belt-and-suspenders)
        self.connect("window-removed", self._on_window_removed)

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)  # type: ignore
        apply_best_theme()  # first paint
        if not os.getenv("MICROPAD_NO_WATCH"):
            self._theme_watcher = start_theme_watcher()

    def do_activate(self) -> None:
        # Create a window if none exists; otherwise present the current one
        if not self.props.active_window:  # type: ignore[attr-defined]
            self._state = State.load()
            win = MicroPadWindow(self, self._state)
            win.present()
        else:
            self.props.active_window.present()  # type: ignore[attr-defined]

    def do_shutdown(self) -> None:
        # Cleanly stop theme watcher so no monitors/timeouts hold the loop
        try:
            stop_theme_watcher()
        except Exception:
            pass
        Adw.Application.do_shutdown(self)  # type: ignore

    # ---- helpers ----
    def _on_window_removed(self, app: "MicroPad", _win) -> None:
        # If no more windows remain, end the app loop explicitly
        if not app.get_windows():
            app.quit()


def main() -> int:
    Adw.init()  # type: ignore
    app = MicroPad()
    return app.run(sys.argv)
