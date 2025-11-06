# src/omnote/findbar.py
from __future__ import annotations
from gi.repository import Gtk, GLib  # type: ignore

class FindBar(Gtk.Box):
    """
    Persistent, embedded Find/Replace bar.
    - Single instance per window (caller owns it).
    - Show/hide only; never re-instantiate.
    - All actions guard against missing buffer.
    """
    def __init__(self, get_ctx):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        for m, v in (("set_margin_start",8),("set_margin_end",8),("set_margin_top",4),("set_margin_bottom",4)):
            getattr(self, m)(v)

        self._get_ctx = get_ctx  # () -> (Gtk.TextView|None, Gtk.TextBuffer|None)

        self._find = Gtk.Entry(placeholder_text="Find…")
        self._repl = Gtk.Entry(placeholder_text="Replace…"); self._repl.set_visible(False)

        self._prev = Gtk.Button.new_from_icon_name("go-up-symbolic")
        self._next = Gtk.Button.new_from_icon_name("go-down-symbolic")
        self._do1  = Gtk.Button(label="Replace");     self._do1.set_visible(False)
        self._doA  = Gtk.Button(label="Replace All"); self._doA.set_visible(False)
        self._close= Gtk.Button.new_from_icon_name("window-close-symbolic")

        for w in (self._find, self._repl, self._prev, self._next, self._do1, self._doA, self._close):
            self.append(w)

        self._find.connect("activate", self._on_next)
        self._next.connect("clicked", self._on_next)
        self._prev.connect("clicked", self._on_prev)
        self._do1.connect("clicked", self._on_replace_one)
        self._doA.connect("clicked", self._on_replace_all)
        self._close.connect("clicked", lambda *_: self.set_visible(False))

        self._find.connect("changed", lambda *_: self._refresh_sensitivity())
        self._refresh_sensitivity()

    # public
    def show_find(self) -> None:
        self._repl.set_visible(False); self._do1.set_visible(False); self._doA.set_visible(False)
        self.set_visible(True); GLib.idle_add(lambda: self._find.grab_focus() or False)
        self._refresh_sensitivity()

    def show_replace(self) -> None:
        self._repl.set_visible(True); self._do1.set_visible(True); self._doA.set_visible(True)
        self.set_visible(True); GLib.idle_add(lambda: self._find.grab_focus() or False)
        self._refresh_sensitivity()

    # internals
    def _ctx(self):
        view, buf = self._get_ctx()
        if buf is None:
            return None, None
        return view, buf

    def _refresh_sensitivity(self) -> None:
        on = bool(self._find.get_text().strip())
        for b in (self._prev, self._next, self._do1, self._doA):
            b.set_sensitive(on)

    def _search(self, forward: bool = True) -> None:
        view, buf = self._ctx()
        if buf is None: return
        needle = self._find.get_text()
        if not needle: return
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
        start, end = buf.get_bounds()
        cur = buf.get_iter_at_mark(buf.get_insert())
        found = (cur.forward_search if forward else cur.backward_search)(needle, flags, None)
        if not found:
            found = (start.forward_search if forward else end.backward_search)(needle, flags, None)
        if found:
            s, e = found
            buf.select_range(s, e)
            if view: view.scroll_to_iter(s, 0.1, False, 0.0, 0.0)

    def _replace(self, replace_all: bool = False) -> None:
        _, buf = self._ctx()
        if buf is None: return
        needle, repl = self._find.get_text(), self._repl.get_text()
        if not needle: return
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE
        if replace_all:
            s, _ = buf.get_bounds()
            it = s
            while True:
                f = it.forward_search(needle, flags, None)
                if not f: break
                a, b = f
                buf.begin_user_action(); buf.delete(a, b); buf.insert(a, repl); buf.end_user_action()
                it = a
        else:
            sel = buf.get_selection_bounds()
            if sel:
                a, b = sel
            else:
                res = buf.get_iter_at_mark(buf.get_insert()).forward_search(needle, flags, None) \
                      or buf.get_bounds()[0].forward_search(needle, flags, None)
                if not res: return
                a, b = res
            buf.begin_user_action(); buf.delete(a, b); buf.insert(a, repl); buf.end_user_action()

    # callbacks
    def _on_next(self, *_): self._search(True)
    def _on_prev(self, *_): self._search(False)
    def _on_replace_one(self, *_): self._replace(False)
    def _on_replace_all(self, *_): self._replace(True)
