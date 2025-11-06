# src/micropad/app.py
from __future__ import annotations
import os, sys
from gi import require_version
require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")

from gi.repository import Adw, Gio  # type: ignore
from .window import MicroPadWindow
from .state import State
from .theme import start_theme_watcher, apply_best_theme

APP_ID = "dev.omarchy.MicroPad"

class MicroPad(Adw.Application):  # type: ignore
    def __init__(self) -> None:
        # NOTE: Adw.Application is a GApplication subclass
        Adw.Application.__init__(self, application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)  # type: ignore
        self._state: State | None = None
        self._theme_watcher = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)  # type: ignore
        apply_best_theme()  # first paint
        if not os.getenv("MICROPAD_NO_WATCH"):
            self._theme_watcher = start_theme_watcher()


    def do_activate(self) -> None:
        # (super chaining not required here; we just manage windows)
        if not self.props.active_window:  # type: ignore[attr-defined]
            self._state = State.load()
            win = MicroPadWindow(self, self._state)
            win.present()
        else:
            self.props.active_window.present()  # type: ignore[attr-defined]

def main() -> None:
    Adw.init()  # type: ignore
    app = MicroPad()
    sys.exit(app.run(sys.argv))
