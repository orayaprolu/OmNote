# src/micropad/window.py
from __future__ import annotations

from typing import Optional, Tuple

from gi import require_version
require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")

from gi.repository import Gtk, Gdk, Gio, Adw, GLib  # type: ignore

from .state import State


class MicroPadWindow(Adw.ApplicationWindow):  # type: ignore
    """Main window with a plain TextView, inline Find/Replace, file ops, and a status bar."""

    def __init__(self, app: Adw.Application, state: State) -> None:  # type: ignore
        super().__init__(application=app)
        self.set_title("MicroPad")
        self.set_default_size(900, 700)

        self.state = state
        self._file: Optional[Gio.File] = None
        self._changed = False

        # --- debounce handles for safe, crash-free updates ---
        self._status_tid: Optional[int] = None
        self._search_tid: Optional[int] = None

        # ---- text view + buffer ----
        self.view = Gtk.TextView()
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)

        # Nice readable padding in the editor
        self.view.set_top_margin(12)
        self.view.set_bottom_margin(12)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)

        self.buffer = self.view.get_buffer()
        self.buffer.connect("changed", self._on_buffer_changed)
        self.buffer.connect("mark-set", self._on_mark_set)  # cursor move

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(self.view)
        scroller.set_margin_top(6)
        scroller.set_margin_bottom(6)
        scroller.set_margin_start(8)
        scroller.set_margin_end(8)

        # ---- top header (as a top bar, not titlebar) ----
        self.header = Adw.HeaderBar()

        # ---- layout host: ToolbarView (lets us add top/bottom bars) ----
        self.toolbar_view = Adw.ToolbarView()
        self.set_content(self.toolbar_view)
        self.toolbar_view.add_top_bar(self.header)

        # ---- inline find/replace bars (top bars) ----
        self._build_find_replace_bars()

        # ---- main content ----
        self.toolbar_view.set_content(scroller)

        # ---- footer/status bar (bottom bar) ----
        self._build_status_bar()

        # ---- header actions + shortcuts ----
        self._install_header_buttons()
        self._install_file_accels()     # keep file ops on Gio actions
        self._install_shortcuts()       # bind Ctrl+F / Ctrl+H via ShortcutController (safe)

        # ---- load last file if any ----
        if getattr(self.state, "last_file", None):
            f = Gio.File.new_for_path(self.state.last_file)  # type: ignore[attr-defined]
            self._open_file_gfile(f)

        GLib.idle_add(self.view.grab_focus)
        GLib.idle_add(self._update_status)

    # ===================== UI construction =====================

    def _install_header_buttons(self) -> None:
        new_btn = Gtk.Button.new_from_icon_name("document-new-symbolic")
        new_btn.set_tooltip_text("New (Ctrl+N)")
        new_btn.connect("clicked", lambda *_: self._new_file())

        open_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        open_btn.set_tooltip_text("Open… (Ctrl+O)")
        open_btn.connect("clicked", lambda *_: self._open_dialog())

        save_btn = Gtk.Button.new_from_icon_name("document-save-symbolic")
        save_btn.set_tooltip_text("Save (Ctrl+S)")
        save_btn.connect("clicked", lambda *_: self._save_file())

        self.header.pack_start(new_btn)
        self.header.pack_start(open_btn)
        self.header.pack_start(save_btn)

        find_btn = Gtk.Button.new_from_icon_name("edit-find-symbolic")
        find_btn.set_tooltip_text("Find (Ctrl+F)")
        find_btn.connect("clicked", lambda *_: self._show_find())

        repl_btn = Gtk.Button.new_from_icon_name("edit-find-replace-symbolic")
        repl_btn.set_tooltip_text("Replace (Ctrl+H)")
        repl_btn.connect("clicked", lambda *_: self._show_replace())

        self.header.pack_end(find_btn)
        self.header.pack_end(repl_btn)

    def _build_find_replace_bars(self) -> None:
        # --- Find bar ---
        self.find_revealer = Gtk.Revealer(reveal_child=False)
        find_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.find_entry = Gtk.SearchEntry()
        self.find_entry.set_placeholder_text("Find…")
        self.find_entry.connect("search-changed", self._on_find_changed)
        self.find_entry.connect("activate", self._on_find_activate)

        self.find_prev_btn = Gtk.Button.new_with_mnemonic("_Prev")
        self.find_prev_btn.connect("clicked", lambda *_: self.find_next(forward=False))
        self.find_next_btn = Gtk.Button.new_with_mnemonic("_Next")
        self.find_next_btn.connect("clicked", lambda *_: self.find_next(forward=True))
        self.find_close_btn = Gtk.Button.new_with_mnemonic("_Close")
        self.find_close_btn.connect("clicked", lambda *_: self._hide_find())

        for w in (self.find_entry, self.find_prev_btn, self.find_next_btn, self.find_close_btn):
            find_box.append(w)
        self.find_revealer.set_child(find_box)

        # --- Replace bar ---
        self.replace_revealer = Gtk.Revealer(reveal_child=False)
        repl_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.replace_find_entry = Gtk.Entry()
        self.replace_find_entry.set_placeholder_text("Find…")
        self.replace_with_entry = Gtk.Entry()
        self.replace_with_entry.set_placeholder_text("Replace with…")

        self.replace_one_btn = Gtk.Button(label="Replace")
        self.replace_all_btn = Gtk.Button(label="Replace All")
        self.replace_close_btn = Gtk.Button(label="Close")

        self.replace_find_entry.connect("changed", self._on_replace_find_changed)
        self.replace_find_entry.connect("activate", lambda *_: self.find_next(forward=True, use_replace_field=True))
        self.replace_with_entry.connect("activate", lambda *_: self._replace_current_or_next())
        self.replace_one_btn.connect("clicked", lambda *_: self._replace_current_or_next())
        self.replace_all_btn.connect("clicked", lambda *_: self._replace_all())
        self.replace_close_btn.connect("clicked", lambda *_: self._hide_replace())

        for w in (
            self.replace_find_entry,
            self.replace_with_entry,
            self.replace_one_btn,
            self.replace_all_btn,
            self.replace_close_btn,
        ):
            repl_box.append(w)
        self.replace_revealer.set_child(repl_box)

        # mount both bars above content (after header)
        self.toolbar_view.add_top_bar(self.find_revealer)
        self.toolbar_view.add_top_bar(self.replace_revealer)

    def _build_status_bar(self) -> None:
        self.status_revealer = Gtk.Revealer(reveal_child=True)
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=4, margin_bottom=4, margin_start=10, margin_end=10
        )
        self.status_label = Gtk.Label(label="Ln: 1  Col: 1  |  Length: 0")
        self.status_label.set_xalign(0.0)
        box.append(self.status_label)
        self.status_revealer.set_child(box)
        self.toolbar_view.add_bottom_bar(self.status_revealer)

    def _install_file_accels(self) -> None:
        """Keep file/quit on Gio actions; they’re simple and safe."""
        actions: dict[str, tuple[callable, list[str]]] = {
            "new": (self._new_file, ["<Primary>n"]),
            "open": (self._open_dialog, ["<Primary>o"]),
            "save": (self._save_file, ["<Primary>s"]),
            "quit": (self._maybe_close, ["<Primary>q"]),
        }
        for name, (cb, accels) in actions.items():
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda _a, _p, cb=cb: cb())
            self.add_action(act)
            self.get_application().set_accels_for_action(f"win.{name}", accels)

    def _install_shortcuts(self) -> None:
        """Bind Ctrl+F / Ctrl+H via ShortcutController at CAPTURE phase, and run handlers on idle."""
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def _idle(fn):
            GLib.idle_add(lambda: (fn(), False)[1])

        # Ctrl+F → show find
        trig_f = Gtk.ShortcutTrigger.parse_string("<Control>F")
        act_f = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_find), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_f, act_f))

        # Ctrl+H → show replace
        trig_h = Gtk.ShortcutTrigger.parse_string("<Control>H")
        act_h = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_replace), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_h, act_h))

        self.add_controller(ctrl)

    # ===================== File ops =====================

    def _new_file(self) -> None:
        if self._changed and not self._confirm_discard():
            return
        self.buffer.set_text("")
        self._file = None
        self._changed = False
        self._update_title()
        self._queue_status(10)

    def _open_dialog(self) -> None:
        if self._changed and not self._confirm_discard():
            return
        dlg = Gtk.FileDialog()
        dlg.set_title("Open File")
        dlg.open(self, None, self._on_open_done)

    def _on_open_done(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        try:
            f = dlg.open_finish(res)
        except GLib.Error:
            return
        if f:
            self._open_file_gfile(f)

    def _open_file_gfile(self, f: Gio.File) -> None:
        def _finish(obj: Gio.File, res: Gio.AsyncResult) -> None:
            try:
                stream = obj.read_finish(res)
            except GLib.Error:
                return
            try:
                data = stream.read_bytes(10_000_000, None).get_data().decode("utf-8", errors="replace")
            except Exception:
                data = ""
            self.buffer.set_text(data)
            self._file = f
            self._changed = False
            self.state.last_file = f.get_path() or ""  # type: ignore[attr-defined]
            self.state.save()
            self._update_title()
            self._queue_status(10)

        f.read_async(GLib.PRIORITY_DEFAULT, None, _finish)

    def _save_file(self) -> None:
        if self._file is None:
            self._save_as_dialog()
            return

        text = self._get_text()
        data = text.encode("utf-8")

        def _finish(obj: Gio.File, res: Gio.AsyncResult) -> None:
            try:
                stream = obj.replace_finish(res)
            except GLib.Error:
                return
            try:
                stream.write(data)
                stream.close(None)
            except Exception:
                pass
            self._changed = False
            self._update_title()

        self._file.replace_async(
            None, False, Gio.FileCreateFlags.REPLACE_DESTINATION,
            GLib.PRIORITY_DEFAULT, None, _finish
        )

    def _save_as_dialog(self) -> None:
        dlg = Gtk.FileDialog()
        dlg.set_title("Save As")
        dlg.save(self, None, self._on_save_done)

    def _on_save_done(self, dlg: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
        try:
            f = dlg.save_finish(res)
        except GLib.Error:
            return
        if not f:
            return
        self._file = f
        self.state.last_file = f.get_path() or ""  # type: ignore[attr-defined]
        self.state.save()
        self._save_file()

    def _maybe_close(self) -> None:
        if self._changed and not self._confirm_discard():
            return
        self.close()

    def _confirm_discard(self) -> bool:
        return True

    def _get_text(self) -> str:
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        return self.buffer.get_text(start, end, True)

    def _set_text(self, text: str) -> None:
        self.buffer.set_text(text)

    def _on_buffer_changed(self, *_args) -> None:
        self._changed = True
        self._update_title()
        self._queue_status(30)

    # ===================== Status bar =====================

    def _on_mark_set(self, *_args) -> None:
        self._queue_status(20)

    def _queue_status(self, delay_ms: int) -> None:
        if self._status_tid:
            GLib.source_remove(self._status_tid)
        self._status_tid = GLib.timeout_add(delay_ms, self._update_status)

    def _update_status(self) -> bool:
        self._status_tid = None
        try:
            insert_mark = self.buffer.get_insert()
            it = self.buffer.get_iter_at_mark(insert_mark)
            line = it.get_line() + 1
            col = it.get_line_offset() + 1
            start = self.buffer.get_start_iter()
            end = self.buffer.get_end_iter()
            length = len(self.buffer.get_text(start, end, True))
            self.status_label.set_text(f"Ln: {line}  Col: {col}  |  Length: {length}")
        except Exception:
            pass
        return False

    def _update_title(self) -> None:
        name = self._file.get_basename() if self._file else "Untitled"
        dirty = " •" if self._changed else ""
        self.set_title(f"MicroPad — {name}{dirty}")

    # ===================== Find / Replace =====================

    def _show_find(self) -> None:
        # Reveal on idle to avoid re-entrancy; don’t toggle if already visible
        if not self.find_revealer.get_reveal_child():
            GLib.idle_add(lambda: (self.find_revealer.set_reveal_child(True), False)[1])
        if self.replace_revealer.get_reveal_child():
            GLib.idle_add(lambda: (self.replace_revealer.set_reveal_child(False), False)[1])
        GLib.idle_add(self.find_entry.grab_focus)
        self._queue_search(lambda: self._highlight_first_match(False), 10)

    def _hide_find(self) -> None:
        if self.find_revealer.get_reveal_child():
            self.find_revealer.set_reveal_child(False)
        GLib.idle_add(self.view.grab_focus)

    def _show_replace(self) -> None:
        if not self.replace_revealer.get_reveal_child():
            GLib.idle_add(lambda: (self.replace_revealer.set_reveal_child(True), False)[1])
        if self.find_revealer.get_reveal_child():
            GLib.idle_add(lambda: (self.find_revealer.set_reveal_child(False), False)[1])

        seed = self._current_selection_text() or self.find_entry.get_text()
        if seed:
            self.replace_find_entry.set_text(seed)
            self.replace_find_entry.set_position(-1)
        GLib.idle_add(self.replace_find_entry.grab_focus)
        self._queue_search(lambda: self._highlight_first_match(True), 10)

    def _hide_replace(self) -> None:
        if self.replace_revealer.get_reveal_child():
            self.replace_revealer.set_reveal_child(False)
        GLib.idle_add(self.view.grab_focus)

    def _on_find_changed(self, *_args) -> None:
        self._queue_search(lambda: self._highlight_first_match(False), 80)

    def _on_find_activate(self, *_args) -> None:
        self._queue_search(lambda: self.find_next(True, False), 0)

    def _on_replace_find_changed(self, *_args) -> None:
        self._queue_search(lambda: self._highlight_first_match(True), 80)

    def _queue_search(self, fn, delay_ms: int) -> None:
        if self._search_tid:
            GLib.source_remove(self._search_tid)
        self._search_tid = GLib.timeout_add(delay_ms, self._run_search, fn)

    def _run_search(self, fn) -> bool:
        self._search_tid = None
        try:
            fn()
        except Exception:
            pass
        return False

    def _current_selection_text(self) -> str:
        if self.buffer.get_has_selection():
            s, e = self.buffer.get_selection_bounds()
            return self.buffer.get_text(s, e, True)
        return ""

    def _buffer_search(
        self, needle: str, start_iter: Gtk.TextIter, forward: bool
    ) -> Optional[Tuple[Gtk.TextIter, Gtk.TextIter]]:
        if not needle:
            return None
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
        try:
            if forward:
                return start_iter.forward_search(needle, flags, None)
            return start_iter.backward_search(needle, flags, None)
        except Exception:
            return None

    def find_next(self, forward: bool = True, use_replace_field: bool = False) -> None:
        try:
            buf = self.buffer
            needle = (
                self.replace_find_entry.get_text() if use_replace_field else self.find_entry.get_text()
            )
            if not needle:
                return

            insert_mark = buf.get_insert()
            cur = buf.get_iter_at_mark(insert_mark)

            if buf.get_has_selection() and forward:
                _s, cur = buf.get_selection_bounds()

            match = self._buffer_search(needle, cur, forward)
            if not match:
                # wrap-around
                start = buf.get_start_iter() if forward else buf.get_end_iter()
                match = self._buffer_search(needle, start, forward)
                if not match:
                    return

            mstart, mend = match
            buf.select_range(mstart, mend)
            self.view.scroll_to_iter(mstart, 0.25, False, 0.0, 0.0)
        except Exception:
            pass

    def _highlight_first_match(self, from_replace: bool) -> None:
        buf = self.buffer
        needle = self.replace_find_entry.get_text() if from_replace else self.find_entry.get_text()
        if not needle:
            return
        start = buf.get_start_iter()
        match = self._buffer_search(needle, start, True)
        if match:
            mstart, mend = match
            buf.select_range(mstart, mend)

    def _replace_current_or_next(self) -> None:
        buf = self.buffer
        find_text = self.replace_find_entry.get_text()
        repl_text = self.replace_with_entry.get_text()
        if not find_text:
            return

        if buf.get_has_selection():
            s, e = buf.get_selection_bounds()
            if buf.get_text(s, e, True).lower() == find_text.lower():
                buf.delete(s, e)
                ins = buf.get_iter_at_mark(buf.get_insert())
                buf.insert(ins, repl_text)
                ns = buf.get_iter_at_mark(buf.get_insert())
                ne = ns.copy()
                ne.forward_chars(len(repl_text))
                buf.select_range(ns, ne)

        # move to next
        self.find_next(forward=True, use_replace_field=True)

    def _replace_all(self) -> None:
        buf = self.buffer
        find_text = self.replace_find_entry.get_text()
        repl_text = self.replace_with_entry.get_text()
        if not find_text:
            return

        start = buf.get_start_iter()
        while True:
            match = self._buffer_search(find_text, start, True)
            if not match:
                break
            mstart, mend = match
            buf.delete(mstart, mend)
            ins = buf.get_iter_at_mark(buf.get_insert())
            buf.insert(ins, repl_text)
            start = buf.get_iter_at_mark(buf.get_insert())
