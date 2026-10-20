"""google-hub-panel: the Gemini drawer (started by the google-hub@maximeallanic.github.io extension)."""
import argparse
import sys
from pathlib import Path

from .network import NetworkWatcher
from .readiness import STALL_MS
from .window import APP_ID, GEMINI, HERE, Adw, Gdk, Gio, GLib, Gtk, PanelWindow, WebKit

PANEL_PATH = "/io/github/maximeallanic/GoogleHubPanel"
NODE = Gio.DBusNodeInfo.new_for_xml((HERE / "panel.xml").read_text())


# WebKitGTK (2.52) answers the page's prefers-color-scheme from GtkSettings:gtk-application-prefer-dark-theme, which
# libadwaita leaves false: Gemini, set to follow the system theme, stayed light in dark mode. The style manager's
# effective appearance is mirrored there, live (GTK logs that the property is deprecated; WebKit reads nothing else).
def follow_dark_appearance(style_manager, settings):
    def sync(*_args):
        settings.props.gtk_application_prefer_dark_theme = style_manager.get_dark()
    style_manager.connect("notify::dark", sync)
    sync()


class PanelApp(Adw.Application):
    def __init__(self, args):
        flags = Gio.ApplicationFlags.NON_UNIQUE if args.test else Gio.ApplicationFlags.DEFAULT_FLAGS
        super().__init__(application_id=APP_ID, flags=flags)
        self.args = args
        self.win = None
        self._loaded_once = False

    def do_activate(self):
        if self.win:
            self.win.present()
            return
        css = Gtk.CssProvider()
        css.load_from_path(str(HERE / "style.css"))
        # Above USER: ~/.config/gtk-4.0/gtk.css (loaded at USER priority) imports the theme, whose
        # `window.csd { border-radius }` would otherwise round the corners against the screen edge.
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        follow_dark_appearance(Adw.StyleManager.get_default(), Gtk.Settings.get_default())
        a = self.args
        watcher = NetworkWatcher(a.fake_network)
        self.win = PanelWindow(self, a.url, a.allow_origin, a.fake_listen, a.test, watcher,
                               log=self._out if a.test else self._journal, stall_ms=a.stall_ms)
        if a.test:
            self._setup_test()
        # Outside tests the window stays unmapped until the Shell asks for it (Show): a mapped window that the
        # Shell merely hid would be shown again by Mutter on its own (monitor change, workspace switch).
        if a.test and a.show_after is None:
            self.win.present()

    # --- D-Bus -------------------------------------------------------------
    # The application id is the panel's bus name: GApplication acquires it while registering, and exports here, just
    # before. The object is therefore there as soon as the name has an owner (the Shell calls Show at that moment);
    # calls are dispatched by the main loop, which starts after do_activate has built the window.
    def do_dbus_register(self, conn, object_path):
        if not self.args.test:
            conn.register_object(PANEL_PATH, NODE.interfaces[0], self._on_call, None, None)
        return Adw.Application.do_dbus_register(self, conn, object_path)

    def _on_call(self, _conn, _sender, _path, _iface, method, params, inv):
        if method == "Ask":
            self.win.ask(params.unpack()[0], lambda ok: inv.return_value(GLib.Variant("(b)", (ok,))))
        elif method == "ProbeComposer":
            self.win.probe(lambda ok: inv.return_value(GLib.Variant("(b)", (ok,))))
        elif method == "Focus":
            self.win.focus_composer()
            inv.return_value(None)
        elif method == "Show":
            self.win.request_show(lambda state: inv.return_value(GLib.Variant("(s)", (state,))))
        elif method == "Hide":
            self.win.request_hide()
            inv.return_value(None)

    # Load and readiness events of the real panel: stderr, i.e. the journal of the Shell that started it. A handful
    # of lines per load and per Show; they tell which wait an answer of Show came from.
    def _journal(self, line):
        print(f"google-hub-panel: {line}", file=sys.stderr, flush=True)

    # --- test mode -------------------------------------------------------
    def _out(self, line):
        print(line, flush=True)

    def _setup_test(self):
        view = self.win.view
        GLib.timeout_add_seconds(25, lambda: (self.quit(), False)[1])
        if self.args.fake_network:
            GLib.timeout_add(self.win.watcher.fake_duration_ms + 1500, lambda: (self.quit(), False)[1])

        if self.args.show_after is not None:
            # Same path as the D-Bus Show of the Shell: the window stays unmapped until then.
            def shown(_state):
                GLib.timeout_add(self.args.quit_after_show, lambda: (self.quit(), False)[1])
            GLib.timeout_add(self.args.show_after, lambda: (self.win.request_show(shown), False)[1])
        if self.args.hide_after is not None:
            GLib.timeout_add(self.args.hide_after, lambda: (self.win.request_hide(), False)[1])

        def on_title(v, _p):
            t = v.get_title() or ""
            if t:
                self._out(f"TITLE: {t}")
            if t.startswith("DONE"):
                self.quit()

        view.connect("notify::title", on_title)
        view.connect("load-changed", self._on_test_load)

    def _on_test_load(self, view, event):
        if event != WebKit.LoadEvent.FINISHED or self._loaded_once:
            return
        self._loaded_once = True
        a = self.args
        if a.probe_on_load:
            self.win.probe(lambda ok: (self._out(f"PROBE: {str(ok).lower()}"), self.quit()))
        elif a.ask_on_load is not None:
            def done(ok):
                self._out(f"ASK: {str(ok).lower()}")
                if not ok:
                    clip = Gdk.Display.get_default().get_clipboard()
                    clip.read_text_async(None, lambda c, r: (self._out(f"CLIPBOARD: {c.read_text_finish(r)}"),
                                                            self.quit()))
            self.win.ask(a.ask_on_load, done)


def main(argv=None):
    p = argparse.ArgumentParser(prog="google-hub-panel")
    p.add_argument("--url", default=GEMINI)
    p.add_argument("--allow-origin", action="append", default=[])
    p.add_argument("--fake-listen")
    p.add_argument("--test", action="store_true")
    p.add_argument("--ask-on-load")
    p.add_argument("--probe-on-load", action="store_true")
    p.add_argument("--fake-network", help="tests: successive states, e.g. offline,online")
    p.add_argument("--stall-ms", type=int, default=STALL_MS, help="WebKit silence accepted before \"stalled\"")
    p.add_argument("--show-after", type=int, help="tests: Show after N ms (window unmapped until then)")
    p.add_argument("--hide-after", type=int, help="tests: Hide after N ms")
    p.add_argument("--quit-after-show", type=int, default=300, help="tests: delay between the answer of Show and the exit")
    args = p.parse_args(argv)
    return PanelApp(args).run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
