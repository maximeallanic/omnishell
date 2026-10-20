"""A plain window titled "witness": holds the keyboard focus while the drawer is prepared out of sight."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


def activate(app):
    win = Gtk.ApplicationWindow(application=app, title="witness", default_width=500, default_height=400)
    win.set_child(Gtk.Entry())
    win.present()


app = Gtk.Application()
app.connect("activate", activate)
app.run([])
