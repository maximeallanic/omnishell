"""Drawer window: gemini.google.com in WebKit, Web Speech polyfill, Ask/Focus/ProbeComposer."""
import json
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

from .bridge import SpeechBridge  # noqa: E402
from .i18n import _  # noqa: E402
from .network import NetworkWatcher  # noqa: E402
from .readiness import STALL_MS, Readiness  # noqa: E402

HERE = Path(__file__).parent
APP_ID = "io.github.maximeallanic.GoogleHubPanel"
GEMINI = "https://gemini.google.com/app"
IN_PANEL_HOSTS = {"gemini.google.com", "accounts.google.com"}
PROFILE = Path(GLib.get_user_data_dir()) / "google-hub/webkit"
SELECTORS = (HERE / "selectors.js").read_text()
ASK_JS = SELECTORS + (HERE / "ask.js").read_text()
PROBE_JS = SELECTORS + "return !!document.querySelector(COMPOSER);"


def host(uri: str) -> str:
    try:
        return GLib.Uri.parse(uri, GLib.UriFlags.NONE).get_host() or ""
    except GLib.Error:
        return ""


class PanelWindow(Adw.ApplicationWindow):
    def __init__(self, app, url, allow_origins, fake_listen, test, watcher: NetworkWatcher, log=None,
                 stall_ms=STALL_MS):
        super().__init__(application=app, title="Gemini", default_width=600, default_height=900)
        self.add_css_class("google-hub-panel")
        self.test = test
        session = (WebKit.NetworkSession.new_ephemeral() if test else
                   WebKit.NetworkSession.new(str(PROFILE / "data"), str(PROFILE / "cache")))
        if not test:
            session.get_cookie_manager().set_persistent_storage(
                str(PROFILE / "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)
        self.view = WebKit.WebView(network_session=session)
        self._setup_view(self.view)
        self.allow_origins = allow_origins
        ucm = self.view.get_user_content_manager()
        ucm.add_script(WebKit.UserScript.new(
            (HERE / "speech-polyfill.js").read_text(), WebKit.UserContentInjectedFrames.TOP_FRAME,
            WebKit.UserScriptInjectionTime.START, ["https://gemini.google.com/*", *allow_origins], None))
        ucm.register_script_message_handler("speech", None)
        self.bridge = SpeechBridge(self.view, fake_listen)
        ucm.connect("script-message-received::speech",
                    lambda _m, value: self.bridge.on_message(json.loads(value.to_json(0))))
        frame = Gtk.Box()
        frame.add_css_class("panel-frame")
        frame.set_overflow(Gtk.Overflow.HIDDEN)
        self.view.set_hexpand(True)
        self.view.set_vexpand(True)
        frame.append(self.view)
        # Nothing to show from the web (offline before the first load, failed load, web process gone): a native
        # status page, painted with the window's first frame, instead of an empty view.
        self._status_page = Adw.StatusPage()
        self._status_page.add_css_class("panel-status")
        self._stack = Gtk.Stack()
        self._stack.add_named(frame, "web")
        self._stack.add_named(self._status_page, "status")
        self.set_content(self._stack)
        # Gemini is only loaded with full connectivity, and loaded again when the network comes back if the first
        # load failed.
        self._url = url
        self._log = log or (lambda _line: None)
        self._started = False
        self.readiness = Readiness(self.view, self.get_mapped, self._log, stall_ms)
        self.connect("map", self._on_map)
        self.view.connect("load-changed", self._on_load_changed)
        self.view.connect("load-failed", self._on_load_failed)
        self.view.connect("web-process-terminated", self._on_web_process_terminated)
        self.watcher = watcher
        watcher.connect(self._on_network)
        self._log(f"NET: {'online' if watcher.online else 'offline'}")
        if watcher.online:
            self._load()
        else:
            self._set_problem("offline")

    # --- network ------------------------------------------------------------
    def _load(self):
        self._started = True
        self.readiness.problem = None  # the status page stays until the new load commits
        self._log(f"LOAD: {self._url}")
        self.view.load_uri(self._url)

    def _on_network(self, online):
        self._log(f"NET: {'online' if online else 'offline'}")
        if online and (not self._started or self.readiness.problem):
            self._load()

    def _on_load_changed(self, _view, event):
        self._log(f"LOAD-EVENT: {event.value_nick}")
        if event == WebKit.LoadEvent.COMMITTED and self._stack.get_visible_child_name() != "web":
            self._stack.set_visible_child_name("web")
            self._log("STATUS: web")

    def _on_load_failed(self, view, event, uri, error):
        # Not failures: a load cancelled by the next one, and a navigation that our own policy refused or handed to
        # the browser (WebKitPolicyError: _on_policy).
        if error.matches(WebKit.NetworkError.quark(), WebKit.NetworkError.CANCELLED) or \
                error.domain == GLib.quark_to_string(WebKit.PolicyError.quark()):
            return False
        self._log("LOADFAILED")
        # The error message comes from WebKit, libsoup or GLib, in the user's language.
        self._set_problem("failed", error.message)
        return True  # the status page replaces WebKit's own error page

    def _on_web_process_terminated(self, _view, reason):
        self._log(f"WEB-PROCESS-TERMINATED: {reason.value_nick}")
        self._set_problem("failed")

    # --- no page -------------------------------------------------------
    def _set_problem(self, kind, detail=""):
        # "Network unreachable" is GLib's own message (domain glib20, translated wherever GLib is); the failure
        # detail comes from WebKit, libsoup or GLib.
        if kind == "offline":
            icon, title = "network-offline-symbolic", GLib.dgettext("glib20", "Network unreachable")
        else:
            icon, title = "dialog-error-symbolic", detail
        self._status_page.set_icon_name(icon)
        self._status_page.set_title(title)
        self._stack.set_visible_child_name("status")
        self._log(f"STATUS: {kind}")
        self.readiness.problem = kind
        self.readiness.evaluate()

    # --- Show / Hide (D-Bus) -----------------------------------------------
    def _on_map(self, _win):
        self._log("MAP")
        self.readiness.evaluate()

    def request_show(self, done):
        """Maps the window; done(state) once the view has something to show (readiness.py)."""
        if self.readiness.problem and self.watcher.online:
            self._load()  # the user asks for the drawer: one new attempt, awaited like the first load
        self.present()

        def answered(state):
            self._log(f"SHOW: {state}")
            done(state)
        self.readiness.wait(answered)

    def request_hide(self):
        self.readiness.cancel()
        self.set_visible(False)

    # --- WebView -----------------------------------------------------------
    def _setup_view(self, view):
        s = view.get_settings()
        s.set_enable_media_stream(True)
        s.set_enable_webrtc(True)
        s.set_enable_developer_extras(True)
        view.connect("permission-request", self._on_permission)
        view.connect("decide-policy", self._on_policy)
        view.connect("create", self._on_create)

    def _on_permission(self, view, req):
        ok = isinstance(req, WebKit.UserMediaPermissionRequest) and (
            host(view.get_uri() or "") == "gemini.google.com" or (self.test and self.allow_origins))
        (req.allow if ok else req.deny)()
        return True

    def _on_policy(self, view, decision, kind):
        if kind not in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            return False
        action = decision.get_navigation_action()
        uri = action.get_request().get_uri()
        if uri.startswith("file:") or host(uri) in IN_PANEL_HOSTS:
            return False
        if kind == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION or \
                action.get_navigation_type() == WebKit.NavigationType.LINK_CLICKED:
            Gtk.UriLauncher.new(uri).launch(self, None, None, None)
            decision.ignore()
            return True
        return False

    def _on_create(self, view, action):
        uri = action.get_request().get_uri()
        if host(uri) != "accounts.google.com":
            Gtk.UriLauncher.new(uri).launch(self, None, None, None)
            return None
        child = WebKit.WebView(related_view=view)
        self._setup_view(child)
        # Translators: title of the Google sign-in window opened from the drawer.
        win = Gtk.Window(transient_for=self, default_width=500, default_height=700, title=_("Sign in"))
        win.set_child(child)
        child.connect("ready-to-show", lambda *_: win.present())
        child.connect("close", lambda *_: win.destroy())
        return child

    # --- Ask / Focus / Probe -----------------------------------------------
    def _js(self, body, args, done, convert=lambda value: value.to_boolean(), failed=False):
        def finish(view, res):
            try:
                done(convert(view.call_async_javascript_function_finish(res)))
            except GLib.Error as e:
                self._log(f"JS-ERROR: {e.message}")
                done(failed)
        self.view.call_async_javascript_function(body, -1, args, None, None, None, finish)

    def ask(self, text: str, done):
        def after(outcome):
            self._log(f"ASK-RESULT: {outcome}")
            sent = outcome == "sent"
            if not sent:
                Gdk.Display.get_default().get_clipboard().set(text)
                self.focus_composer()
                n = Gio.Notification.new("Gemini")
                n.set_body(_("Question copied — paste it into Gemini"))
                self.get_application().send_notification("ask-fallback", n)
            done(sent)
        self._js(ASK_JS, GLib.Variant("a{sv}", {"text": GLib.Variant("s", text)}), after,
                 convert=lambda value: value.to_string(), failed="js-error")

    def probe(self, done):
        self._js(PROBE_JS, None, done)

    def focus_composer(self):
        self.present()
        self.view.grab_focus()
        self.view.evaluate_javascript(SELECTORS + "document.querySelector(COMPOSER)?.focus();",
                                      -1, None, None, None, None, None)
