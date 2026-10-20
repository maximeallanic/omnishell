"""Bridge between the page's Web Speech replacement and the daemon's Listen() (or a fake one, in tests)."""
import json

from gi.repository import Gio, GLib

HUB = ("io.github.maximeallanic.Omnishell", "/io/github/maximeallanic/Omnishell", "io.github.maximeallanic.Omnishell")


class SpeechBridge:
    def __init__(self, webview, fake_listen=None):
        self.view = webview
        self.fake = fake_listen
        self.aborted = set()
        self._proxy = None
        self._listen_timeout = None  # ms, published by the daemon (ListenTimeout)

    def _hub(self):
        if self._proxy is None:
            self._proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES | Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
                None, *HUB, None)
        return self._proxy

    def dispatch(self, id_, type_, data=None):
        self.view.evaluate_javascript(
            f"window.__ghSpeech && window.__ghSpeech.dispatch({int(id_)}, {json.dumps(type_)}, {json.dumps(data)})",
            -1, None, None, None, None, None)

    def on_message(self, msg: dict):
        cmd, id_ = msg.get("cmd"), int(msg.get("id", 0))
        if cmd == "start":
            self.dispatch(id_, "start")
            self.dispatch(id_, "audiostart")
            self._listen(id_)
        elif cmd == "stop":
            self._call("StopListen")
        elif cmd == "abort":
            self.aborted.add(id_)
            self._call("CancelListen")

    def _call(self, method):
        if self.fake is not None:
            return
        try:
            self._hub().call(method, None, Gio.DBusCallFlags.NONE, 2000, None, None)
        except GLib.Error:
            pass

    def _listen(self, id_):
        if self.fake is not None:
            GLib.timeout_add(300, lambda: (self._deliver(id_, self.fake), False)[1])
            return

        def done(proxy, res):
            try:
                (text,) = proxy.call_finish(res).unpack()
            except GLib.Error as e:
                code = "audio-capture" if "Error.AudioCapture" in e.message else "network"
                text = f"error:{code}"
            self._deliver(id_, text)

        def listen():
            self._hub().call("Listen", None, Gio.DBusCallFlags.NONE, self._listen_timeout, None, done)

        def got_timeout(proxy, res):
            # The daemon's worst case for capture + transcription: waiting less would report a failure
            # while it is still transcribing.
            try:
                (value,) = proxy.call_finish(res).unpack()
            except GLib.Error:
                self._deliver(id_, "error:network")
                return
            self._listen_timeout = value
            listen()

        try:
            if self._listen_timeout is None:
                self._hub().call("org.freedesktop.DBus.Properties.Get", GLib.Variant("(ss)", (HUB[2], "ListenTimeout")),
                                 Gio.DBusCallFlags.NONE, 10000, None, got_timeout)
            else:
                listen()
        except GLib.Error:
            self._deliver(id_, "error:network")

    def _deliver(self, id_, text):
        if id_ in self.aborted:
            self.aborted.discard(id_)
            return
        if text.startswith("error:"):
            self.dispatch(id_, "error", text[6:])
        elif not text.strip():
            self.dispatch(id_, "error", "no-speech")
        else:
            for t in ("speechstart", "speechend", "audioend"):
                self.dispatch(id_, t)
            self.dispatch(id_, "result", text.strip())
        self.dispatch(id_, "end")
