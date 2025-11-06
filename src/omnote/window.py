# src/omnote/window.py
from __future__ import annotations

from typing import Optional, Tuple

from gi import require_version
require_version("Gtk", "4.0")
require_version("Adw", "1")
require_version("Gdk", "4.0")

from gi.repository import Gtk, Gdk, Gio, Adw, GLib  # type: ignore

from .state import State


class MicroPadWindow(Adw.ApplicationWindow):  # type: ignore
    """Main window with a TextView, inline Find/Replace, file ops, and a status bar (animated Stack)."""

    def __init__(self, app: Adw.Application, state: State) -> None:  # type: ignore
        super().__init__(application=app)
        self.set_title("OmNote")
        self.set_default_size(900, 700)

        self.state = state
        self._file: Optional[Gio.File] = None
        self._changed = False
        self._closing = False

        # timers / signal ids
        self._status_tid: Optional[int] = None
        self._search_tid: Optional[int] = None
        self._sid_changed = None
        self._sid_mark = None

        # ---------- layout ----------
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_content(root)

        # header
        self.header = Adw.HeaderBar()

        new_btn  = Gtk.Button.new_from_icon_name("document-new-symbolic")
        open_btn = Gtk.Button.new_from_icon_name("document-open-symbolic")
        save_btn = Gtk.Button.new_from_icon_name("document-save-symbolic")
        find_btn = Gtk.Button.new_from_icon_name("edit-find-symbolic")
        repl_btn = Gtk.Button.new_from_icon_name("edit-find-replace-symbolic")

        new_btn.set_tooltip_text("New (Ctrl+N)")
        open_btn.set_tooltip_text("Open… (Ctrl+O)")
        save_btn.set_tooltip_text("Save (Ctrl+S)")
        find_btn.set_tooltip_text("Find (Ctrl+F)")
        repl_btn.set_tooltip_text("Replace (Ctrl+H)")

        new_btn.connect("clicked", lambda *_: self._new_file())
        open_btn.connect("clicked", lambda *_: self._open_dialog())
        save_btn.connect("clicked", lambda *_: self._save_file())
        find_btn.connect("clicked", lambda *_: self._show_find())
        repl_btn.connect("clicked", lambda *_: self._show_replace())

        self.header.pack_start(new_btn)
        self.header.pack_start(open_btn)
        self.header.pack_start(save_btn)
        self.header.pack_end(find_btn)
        self.header.pack_end(repl_btn)

        root.append(self.header)

        # top bar stack container (hidden when idle; animates when shown)
        self.top_stack = Gtk.Stack()
        self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_DOWN)
        self.top_stack.set_hexpand(True)
        self.top_stack.set_vexpand(False)
        self.top_stack.set_visible(False)  # collapse when no bar is shown
        self.top_stack.connect("notify::transition-running", self._on_stack_transition)

        # find bar
        self.find_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.find_entry = Gtk.SearchEntry()
        self.find_entry.set_placeholder_text("Find…")
        self.find_entry.set_focusable(True)
        self.find_entry.connect("search-changed", self._on_find_changed)
        self.find_entry.connect("activate", self._on_find_activate)

        self.find_prev_btn = Gtk.Button.new_with_mnemonic("_Prev")
        self.find_prev_btn.connect("clicked", lambda *_: self.find_next(forward=False))
        self.find_next_btn = Gtk.Button.new_with_mnemonic("_Next")
        self.find_next_btn.connect("clicked", lambda *_: self.find_next(forward=True))
        self.find_close_btn = Gtk.Button.new_with_mnemonic("_Close")
        self.find_close_btn.connect("clicked", lambda *_: self._hide_find())

        for w in (self.find_entry, self.find_prev_btn, self.find_next_btn, self.find_close_btn):
            self.find_box.append(w)

        # replace bar
        self.replace_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=6, margin_bottom=6, margin_start=8, margin_end=8
        )
        self.replace_find_entry = Gtk.Entry()
        self.replace_find_entry.set_placeholder_text("Find…")
        self.replace_find_entry.set_focusable(True)
        self.replace_with_entry = Gtk.Entry()
        self.replace_with_entry.set_placeholder_text("Replace with…")
        self.replace_with_entry.set_focusable(True)

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
            self.replace_box.append(w)

        # stack pages
        self.top_stack.add_named(self.find_box, "find")
        self.top_stack.add_named(self.replace_box, "replace")

        # empty placeholder (used during hide animation)
        self.empty_bar = Gtk.Box()
        self.top_stack.add_named(self.empty_bar, "empty")
        self.top_stack.set_visible_child_name("empty")

        root.append(self.top_stack)

        # editor
        self.view = Gtk.TextView()
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_top_margin(12)
        self.view.set_bottom_margin(12)
        self.view.set_left_margin(14)
        self.view.set_right_margin(14)

        self.buffer = self.view.get_buffer()
        self._sid_changed = self.buffer.connect("changed", self._on_buffer_changed)
        self._sid_mark = self.buffer.connect("mark-set", self._on_mark_set)

        scroller = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        scroller.set_child(self.view)
        scroller.set_margin_top(6)
        scroller.set_margin_bottom(6)
        scroller.set_margin_start(8)
        scroller.set_margin_end(8)

        root.append(scroller)

        # footer / status
        self.status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=4, margin_bottom=4, margin_start=10, margin_end=10
        )
        self.status_label = Gtk.Label(label="Ln: 1  Col: 1  |  Length: 0")
        self.status_label.set_xalign(0.0)
        self.status_box.append(self.status_label)
        root.append(self.status_box)

        # actions + shortcuts
        self._install_file_accels()
        self._install_shortcuts()

        # session restore
        if getattr(self.state, "last_file", None):
            f = Gio.File.new_for_path(self.state.last_file)  # type: ignore[attr-defined]
            self._open_file_gfile(f)

        GLib.idle_add(self.view.grab_focus)
        GLib.idle_add(self._update_status)

        # clean shutdown
        self.connect("close-request", self._on_close_request)

    # ---------- helper: bar visibility / focus coordination with animation ----------

    def _set_bar(self, name: Optional[str]) -> None:
        """
        Show given bar ('find' or 'replace') with slide-down, or hide with slide-up.
        We collapse the stack (set_visible(False)) only after the hide animation finishes.
        """
        if name is None:
            # hide with slide-up transition
            self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_UP)
            self.top_stack.set_visible_child_name("empty")
            self.view.set_focusable(True)
            # actual set_visible(False) happens in _on_stack_transition when animation ends
            return

        # show specific bar with slide-down
        self.top_stack.set_visible(True)  # make space so animation is visible
        self.top_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_DOWN)
        self.top_stack.set_visible_child_name(name)
        self.view.set_focusable(False)  # keep TextView from stealing focus

    def _on_stack_transition(self, *_args) -> None:
        """
        After a transition completes, if we're on 'empty', collapse the stack's height.
        """
        try:
            # Gtk.Stack.get_transition_running() exists in GTK4; be defensive
            running = getattr(self.top_stack, "get_transition_running", lambda: False)()
            if running:
                return
        except Exception:
            # if property missing, just proceed
            pass

        if self.top_stack.get_visible_child_name() == "empty":
            self.top_stack.set_visible(False)
            # make sure the editor regains focus after collapse
            GLib.idle_add(self.view.grab_focus)

    # ---------- actions, shortcuts ----------

    def _install_file_accels(self) -> None:
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
        ctrl = Gtk.ShortcutController()
        ctrl.set_scope(Gtk.ShortcutScope.GLOBAL)
        ctrl.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def _idle(fn):
            if self._closing:
                return
            GLib.idle_add(lambda: (not self._closing and fn() is None, False)[1])

        trig_f = Gtk.ShortcutTrigger.parse_string("<Control>F")
        act_f = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_find), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_f, act_f))

        trig_h = Gtk.ShortcutTrigger.parse_string("<Control>H")
        act_h = Gtk.CallbackAction.new(lambda *_: (_idle(self._show_replace), True)[1])
        ctrl.add_shortcut(Gtk.Shortcut.new(trig_h, act_h))

        self.add_controller(ctrl)

    # ---------- file ops ----------

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
        if self._closing:
            return
        try:
            f = dlg.open_finish(res)
        except GLib.Error:
            return
        if f:
            self._open_file_gfile(f)

    def _open_file_gfile(self, f: Gio.File) -> None:
        def _finish(obj: Gio.File, res: Gio.AsyncResult) -> None:
            if self._closing:
                return
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
            if self._closing:
                return
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
        if self._closing:
            return
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
        # TODO: real dialog
        return True

    # ---------- buffer / status ----------

    def _get_text(self) -> str:
        start = self.buffer.get_start_iter()
        end = self.buffer.get_end_iter()
        return self.buffer.get_text(start, end, True)

    def _set_text(self, text: str) -> None:
        self.buffer.set_text(text)

    def _on_buffer_changed(self, *_args) -> None:
        if self._closing:
            return
        self._changed = True
        self._update_title()
        self._queue_status(30)

    def _on_mark_set(self, *_args) -> None:
        if self._closing:
            return
        self._queue_status(20)

    def _queue_status(self, delay_ms: int) -> None:
        if self._status_tid:
            GLib.source_remove(self._status_tid)
        self._status_tid = GLib.timeout_add(delay_ms, self._update_status)

    def _update_status(self) -> bool:
        self._status_tid = None
        if self._closing:
            return False
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
        self.set_title(f"OmNote — {name}{dirty}")

    # ---------- find / replace ----------

    def _show_find(self) -> None:
        if self._closing:
            return
        self._set_bar("find")
        GLib.timeout_add(0, self._force_focus_find)
        self._queue_search(lambda: self._highlight_first_match(False), 10)

    def _hide_find(self) -> None:
        self._set_bar(None)

    def _show_replace(self) -> None:
        if self._closing:
            return
        seed = self._current_selection_text() or self.find_entry.get_text()
        if seed:
            self.replace_find_entry.set_text(seed)
            self.replace_find_entry.set_position(-1)
        self._set_bar("replace")
        GLib.timeout_add(0, self._force_focus_replace)
        self._queue_search(lambda: self._highlight_first_match(True), 10)

    def _hide_replace(self) -> None:
        self._set_bar(None)

    def _force_focus_find(self) -> bool:
        if self._closing or not self.top_stack.get_visible() or self.top_stack.get_visible_child_name() != "find":
            return False
        try:
            self.set_focus(self.find_entry)  # type: ignore[arg-type]
            self.find_entry.grab_focus()
            self.find_entry.set_position(-1)
        except Exception:
            pass
        return False

    def _force_focus_replace(self) -> bool:
        if self._closing or not self.top_stack.get_visible() or self.top_stack.get_visible_child_name() != "replace":
            return False
        try:
            self.set_focus(self.replace_find_entry)  # type: ignore[arg-type]
            self.replace_find_entry.grab_focus()
            self.replace_find_entry.set_position(-1)
        except Exception:
            pass
        return False

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
        if self._closing:
            return False
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
        if self._closing:
            return
        try:
            buf = self.buffer
            needle = self.replace_find_entry.get_text() if use_replace_field else self.find_entry.get_text()
            if not needle:
                return

            insert_mark = buf.get_insert()
            cur = buf.get_iter_at_mark(insert_mark)

            if buf.get_has_selection() and forward:
                _s, cur = buf.get_selection_bounds()

            match = self._buffer_search(needle, cur, forward)
            if not match:
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
        if self._closing:
            return
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
        if self._closing:
            return
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

        self.find_next(forward=True, use_replace_field=True)

    def _replace_all(self) -> None:
        if self._closing:
            return
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

    # ---------- teardown ----------

    def _on_close_request(self, *_args):
        self._closing = True

        for tid in (self._status_tid, self._search_tid):
            if tid:
                try:
                    GLib.source_remove(tid)
                except Exception:
                    pass
        self._status_tid = None
        self._search_tid = None

        for sid in (self._sid_changed, self._sid_mark):
            if sid:
                try:
                    self.buffer.disconnect(sid)
                except Exception:
                    pass
        self._sid_changed = None
        self._sid_mark = None

        self.top_stack.set_visible_child_name("empty")
        # collapse after any residual transition callback
        GLib.idle_add(lambda: (self.top_stack.set_visible(False), False)[1])

        app = self.get_application()
        if app is not None:
            GLib.idle_add(app.quit)

        return False
