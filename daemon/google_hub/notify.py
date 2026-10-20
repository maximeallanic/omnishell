"""Daily task summary and desktop notifications."""
from datetime import date, datetime, timedelta

from gi.repository import Gio, GLib

from .i18n import _, ngettext


def next_summary_time(now: datetime, last_sent: date | None, hour: int) -> datetime:
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if last_sent == now.date():
        return target + timedelta(days=1)
    return target if now < target else now


def summary_due(now: datetime, last_sent: date | None, hour: int) -> bool:
    """True if today's summary was not sent and its hour has passed (robust to suspend)."""
    return last_sent != now.date() and now >= now.replace(hour=hour, minute=0, second=0, microsecond=0)


def summary_text(tasks: list[dict]) -> str | None:
    """Body of the daily summary; plural forms and the joining of both counts come from the catalogue."""
    today = sum(1 for t in tasks if t["bucket"] == "today")
    late = sum(1 for t in tasks if t["bucket"] == "overdue")
    if today and late:
        # Translators: daily summary when there are tasks for today and overdue ones: "3 tasks today, 1 overdue".
        return _("{today}, {overdue}").format(
            today=ngettext("{n} task today", "{n} tasks today", today).format(n=today),
            # Translators: second part of "3 tasks today, 1 overdue": the word "task" is not repeated.
            overdue=ngettext("{n} overdue", "{n} overdue", late).format(n=late))
    if today:
        return ngettext("{n} task today", "{n} tasks today", today).format(n=today)
    if late:
        return ngettext("{n} task overdue", "{n} tasks overdue", late).format(n=late)
    return None


class Notifier:
    """org.freedesktop.Notifications with an "Open" action that opens a URL."""

    def __init__(self, bus, open_uri):
        self.bus = bus
        self.open_uri = open_uri
        self.uris: dict[int, str] = {}
        bus.signal_subscribe("org.freedesktop.Notifications", "org.freedesktop.Notifications",
                             "ActionInvoked", "/org/freedesktop/Notifications", None,
                             Gio.DBusSignalFlags.NONE, self._on_action)

    def _on_action(self, _c, _s, _p, _i, _n, params):
        nid, action = params.unpack()
        uri = self.uris.pop(nid, None)
        if uri and action == "open":
            self.open_uri(uri)

    def __call__(self, title: str, body: str, uri: str | None = None):
        actions = ["open", _("Open")] if uri else []
        try:
            (nid,) = self.bus.call_sync(
                "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications", "Notify",
                GLib.Variant("(susssasa{sv}i)", ("Google Hub", 0, "google-hub-gemini-symbolic", title, body,
                                                 actions, {}, -1)),
                GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 5000, None).unpack()
        except GLib.Error:
            return
        if uri:
            self.uris[nid] = uri
