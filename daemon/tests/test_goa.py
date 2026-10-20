"""GoaTokens against a fake goa-daemon exporting an ObjectManager on a private session bus."""
import threading
import time
import unittest

from gi.repository import Gio, GLib

from omnishell.goa import ACCOUNT, BUS, OAUTH2, ROOT, GoaTokens
from omnishell.google_api import NoAccountError

XML = f"""<node>
  <interface name="org.freedesktop.DBus.ObjectManager">
    <method name="GetManagedObjects"><arg type="a{{oa{{sa{{sv}}}}}}" direction="out"/></method>
    <signal name="InterfacesAdded"><arg type="o"/><arg type="a{{sa{{sv}}}}"/></signal>
    <signal name="InterfacesRemoved"><arg type="o"/><arg type="as"/></signal>
  </interface>
  <interface name="{ACCOUNT}">
    <property name="ProviderType" type="s" access="read"/>
    <property name="AttentionNeeded" type="b" access="read"/>
    <method name="EnsureCredentials"><arg type="i" direction="out"/></method>
  </interface>
  <interface name="{OAUTH2}">
    <method name="GetAccessToken"><arg type="s" direction="out"/><arg type="i" direction="out"/></method>
  </interface>
</node>"""
NODE = Gio.DBusNodeInfo.new_for_xml(XML)
IFACES = {i.name: i for i in NODE.interfaces}
PATH = ROOT + "/Accounts/account_1"


class FakeGoa:
    """Runs on its own thread and main context, like the real goa-daemon in its own process."""

    def __init__(self, address):
        self.accounts = {}  # path -> {"provider": str, "attention": bool}
        self.ensure_fails = False
        self.calls = []
        self._regs = {}
        ready = threading.Event()
        self.ctx = GLib.MainContext.new()
        self.loop = GLib.MainLoop.new(self.ctx, False)

        def run():
            self.ctx.push_thread_default()
            self.conn = Gio.DBusConnection.new_for_address_sync(
                address, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
            self.conn.register_object(ROOT, IFACES["org.freedesktop.DBus.ObjectManager"], self._on_call, None, None)
            Gio.bus_own_name_on_connection(self.conn, BUS, Gio.BusNameOwnerFlags.NONE,
                                           lambda *_: ready.set(), None)
            self.loop.run()
            self.conn.close_sync(None)
            self.ctx.pop_thread_default()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        assert ready.wait(5)

    def close(self):
        self.loop.quit()
        self.thread.join(5)

    def _in_loop(self, fn):
        done = threading.Event()
        src = GLib.idle_source_new()
        src.set_callback(lambda *_: (fn(), done.set(), False)[2])
        src.attach(self.ctx)
        assert done.wait(5)

    def _props(self, path):
        a = self.accounts[path]
        return {ACCOUNT: {"ProviderType": GLib.Variant("s", a["provider"]),
                          "AttentionNeeded": GLib.Variant("b", a["attention"])}, OAUTH2: {}}

    def add(self, path, provider="google"):
        def do():
            self.accounts[path] = {"provider": provider, "attention": False}
            self._regs[path] = [self.conn.register_object(path, IFACES[i], self._on_call, self._on_get, None)
                                for i in (ACCOUNT, OAUTH2)]
            self.conn.emit_signal(None, ROOT, "org.freedesktop.DBus.ObjectManager", "InterfacesAdded",
                                  GLib.Variant("(oa{sa{sv}})", (path, self._props(path))))
        self._in_loop(do)

    def remove(self, path):
        def do():
            del self.accounts[path]
            for r in self._regs.pop(path):
                self.conn.unregister_object(r)
            self.conn.emit_signal(None, ROOT, "org.freedesktop.DBus.ObjectManager", "InterfacesRemoved",
                                  GLib.Variant("(oas)", (path, [ACCOUNT, OAUTH2])))
        self._in_loop(do)

    def set_attention(self, path, value):
        def do():
            self.accounts[path]["attention"] = value
            self.conn.emit_signal(None, path, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                                  GLib.Variant("(sa{sv}as)", (ACCOUNT, {"AttentionNeeded": GLib.Variant("b", value)}, [])))
        self._in_loop(do)

    def _on_get(self, _conn, _sender, path, iface, prop):
        return self._props(path)[iface][prop]

    def _on_call(self, _conn, _sender, path, _iface, method, _params, inv):
        self.calls.append(method)
        if method == "GetManagedObjects":
            inv.return_value(GLib.Variant("(a{oa{sa{sv}}})", ({p: self._props(p) for p in self.accounts},)))
        elif method == "GetAccessToken":
            inv.return_value(GLib.Variant("(si)", (f"token-{path}", 3600)))
        elif method == "EnsureCredentials":
            if self.ensure_fails:
                inv.return_dbus_error("org.gnome.OnlineAccounts.Error.NotAuthorized", "renew the credentials")
            else:
                inv.return_value(GLib.Variant("(i)", (3600,)))


class TestGoaTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.testbus = Gio.TestDBus.new(Gio.TestDBusFlags.NONE)
        cls.testbus.up()

    @classmethod
    def tearDownClass(cls):
        cls.testbus.down()

    def setUp(self):
        self.goa = FakeGoa(self.testbus.get_bus_address())
        self.bus = Gio.DBusConnection.new_for_address_sync(
            self.testbus.get_bus_address(),
            Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
        self.changes = 0

    def tearDown(self):
        self.bus.close_sync(None)
        self.goa.close()

    def tokens(self):
        t = GoaTokens(self.bus)
        t.watch(lambda: setattr(self, "changes", self.changes + 1))
        return t

    def until(self, pred):
        deadline = time.monotonic() + 3
        while not pred() and time.monotonic() < deadline:
            GLib.MainContext.default().iteration(False)
            time.sleep(0.005)
        self.assertTrue(pred())

    def test_constructor_does_not_block_and_finds_existing_account(self):
        self.goa.add(PATH)
        t = self.tokens()
        self.assertFalse(t.has_account())  # nothing read from the bus yet: the manager is asynchronous
        self.until(t.has_account)
        self.assertEqual(self.changes, 1)

    def test_has_account_never_calls_goa(self):
        self.goa.add(PATH)
        t = self.tokens()
        self.until(t.has_account)
        before = list(self.goa.calls)
        for _ in range(50):
            t.has_account()
        self.assertEqual(self.goa.calls, before)

    def test_account_added_and_removed_from_signals(self):
        t = self.tokens()
        self.until(lambda: t._manager is not None)
        self.assertFalse(t.has_account())
        self.goa.add(ROOT + "/Accounts/other", provider="ms_graph")
        self.goa.add(PATH)
        self.until(t.has_account)
        self.assertEqual(t.token(), f"token-{PATH}")
        self.goa.remove(PATH)
        self.until(lambda: not t.has_account())
        with self.assertRaises(NoAccountError):
            t.token()

    def test_attention_needed_is_not_a_usable_account(self):
        self.goa.add(PATH)
        t = self.tokens()
        self.until(t.has_account)
        self.goa.set_attention(PATH, True)
        self.until(lambda: not t.has_account())
        self.goa.set_attention(PATH, False)
        self.until(t.has_account)
        self.assertEqual(self.changes, 3)

    def test_refresh_surfaces_goa_refusal(self):
        self.goa.add(PATH)
        t = self.tokens()
        self.until(t.has_account)
        t.refresh()
        self.goa.ensure_fails = True
        with self.assertRaises(GLib.Error) as cm:
            t.refresh()
        self.assertIn("NotAuthorized", cm.exception.message)


if __name__ == "__main__":
    unittest.main()
