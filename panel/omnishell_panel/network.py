"""Network state for the drawer: Gemini only loads with full connectivity (no captive portal)."""
from gi.repository import Gio, GLib

FAKE_STEP_MS = 1500


class NetworkWatcher:
    """online + callback(online) on every change. fake: sequence of states "offline,online,…" (tests)."""

    def __init__(self, fake: str | None = None):
        self._callbacks = []
        if fake:
            states = [s.strip() == "online" for s in fake.split(",")]
            self.online = states[0]
            for i, state in enumerate(states[1:], 1):
                GLib.timeout_add(i * FAKE_STEP_MS, lambda s=state: (self._set(s), False)[1])
            self.fake_duration_ms = len(states) * FAKE_STEP_MS
            return
        self.fake_duration_ms = 0
        self._monitor = Gio.NetworkMonitor.get_default()
        self.online = self._compute()
        self._monitor.connect("network-changed", lambda *_: self._set(self._compute()))
        self._monitor.connect("notify::connectivity", lambda *_: self._set(self._compute()))

    def _compute(self) -> bool:
        m = self._monitor
        return m.get_network_available() and m.get_connectivity() == Gio.NetworkConnectivity.FULL

    def _set(self, online: bool):
        if online == self.online:
            return
        self.online = online
        for cb in self._callbacks:
            cb(online)

    def connect(self, callback):
        self._callbacks.append(callback)
