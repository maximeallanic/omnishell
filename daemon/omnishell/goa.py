"""Google OAuth token provided by GNOME Online Accounts (D-Bus).

The Google account is tracked from the GOA ObjectManager signals (Gio.DBusObjectManagerClient,
created asynchronously): has_account() only reads that cached state, so the daemon main loop and
every search never wait on goa-daemon. token() and refresh() make blocking GOA calls and must
only run on worker threads.
"""
import logging
import threading
import time

from gi.repository import Gio, GLib

from .google_api import NoAccountError

log = logging.getLogger(__name__)

BUS = "org.gnome.OnlineAccounts"
ROOT = "/org/gnome/OnlineAccounts"
ACCOUNT = "org.gnome.OnlineAccounts.Account"
OAUTH2 = "org.gnome.OnlineAccounts.OAuth2Based"
CALL_TIMEOUT_MS = 10000


def _prop(proxy, name):
    v = proxy.get_cached_property(name)
    return v.unpack() if v is not None else None


class GoaTokens:
    def __init__(self, bus=None):
        self.bus = bus or Gio.bus_get_sync(Gio.BusType.SESSION)
        self._lock = threading.Lock()
        self._token = None
        self._expires = 0.0
        self._path = None              # Google account usable for OAuth2, None if absent
        self._attention = False        # GOA's AttentionNeeded: credentials must be renewed
        self._watchers = []
        self._manager = None
        # Signals of the manager are delivered on the thread-default main context of this call.
        Gio.DBusObjectManagerClient.new(self.bus, Gio.DBusObjectManagerClientFlags.NONE, BUS, ROOT,
                                        None, None, None, self._on_manager)

    def watch(self, callback) -> None:
        """callback() runs on the main loop each time has_account() may have changed."""
        self._watchers.append(callback)

    def _on_manager(self, _source, result, *_):
        try:
            self._manager = Gio.DBusObjectManagerClient.new_finish(result)
        except GLib.Error as e:
            log.warning("GNOME Online Accounts unavailable, no Google account: %s", e.message)
            return
        for sig in ("object-added", "object-removed", "interface-added", "interface-removed",
                    "interface-proxy-properties-changed", "notify::name-owner"):
            self._manager.connect(sig, lambda *_: self._rescan())
        self._rescan()

    def _rescan(self) -> None:
        path, attention = None, False
        for obj in sorted(self._manager.get_objects(), key=lambda o: o.get_object_path()):
            acc = obj.get_interface(ACCOUNT)
            if acc and obj.get_interface(OAUTH2) and _prop(acc, "ProviderType") == "google":
                path, attention = obj.get_object_path(), bool(_prop(acc, "AttentionNeeded"))
                break
        with self._lock:
            if (path, attention) == (self._path, self._attention):
                return
            if path != self._path or attention:
                self._token = None
            self._path, self._attention = path, attention
        if attention:
            log.info("Google account %s needs to be signed in again (Settings → Online Accounts)", path)
        for cb in self._watchers:
            cb()

    def has_account(self) -> bool:
        """A Google account whose credentials GOA considers valid; never touches the bus."""
        with self._lock:
            return self._path is not None and not self._attention

    def _call(self, path, iface, method, sig):
        return self.bus.call_sync(BUS, path, iface, method, None, GLib.VariantType(sig),
                                  Gio.DBusCallFlags.NONE, CALL_TIMEOUT_MS, None).unpack()

    def _usable_path(self) -> str:
        with self._lock:
            if self._path is None or self._attention:
                raise NoAccountError()
            return self._path

    def token(self) -> str:
        """Blocking: worker threads only. Raises NoAccountError or GLib.Error from GOA."""
        with self._lock:
            if self._token and time.monotonic() < self._expires:
                return self._token
        path = self._usable_path()
        token, expires_in = self._call(path, OAUTH2, "GetAccessToken", "(si)")
        with self._lock:
            if path == self._path:
                self._token = token
                self._expires = time.monotonic() + max(0, (expires_in or 3600) - 60)
        return token

    def refresh(self) -> None:
        """Blocking: worker threads only. Drops the cached token and asks GOA to check the
        credentials; a GOA refusal raises GLib.Error (goa-daemon then sets AttentionNeeded)."""
        with self._lock:
            self._token = None
        self._call(self._usable_path(), ACCOUNT, "EnsureCredentials", "(i)")
