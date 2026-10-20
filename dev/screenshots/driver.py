#!/usr/bin/env python3
"""Screenshot driver (run by nested.sh inside the nested Shell's private bus): drives the real extension, the real
drawer and the demo daemon, and saves PNGs of the whole virtual monitor through org.gnome.Shell.Screenshot.

Usage: driver.py OUT [SHOT...]   (default: every shot). Writes OUT/<shot>.png.
Environment: GOOGLE_HUB_SHOT_QUERIES  JSON object overriding the search texts typed per shot (other languages)."""
import json
import os
import sys
import time

from gi.repository import Gio, GLib

SHELL = ("io.github.maximeallanic.GoogleHubShell", "/io/github/maximeallanic/GoogleHubShell",
         "io.github.maximeallanic.GoogleHubShell")
GNOME_SHELL = ("org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell")
SCREENSHOT = ("org.gnome.Shell.Screenshot", "/org/gnome/Shell/Screenshot", "org.gnome.Shell.Screenshot")
HUB = ("io.github.maximeallanic.GoogleHub", "/io/github/maximeallanic/GoogleHub", "io.github.maximeallanic.GoogleHub")
QUERIES = {"search": "gnome", "calendar": "meeting", "add-task": "t Call the plumber tomorrow", "typing": "gtk docs"}
QUERIES.update(json.loads(os.environ.get("GOOGLE_HUB_SHOT_QUERIES") or "{}"))

out = sys.argv[1]
bus = Gio.bus_get_sync(Gio.BusType.SESSION)


def call(target, method, params=None, timeout=10000):
    reply = bus.call_sync(target[0], target[1], target[2], method, params, None, Gio.DBusCallFlags.NONE, timeout, None)
    return reply.unpack() if reply else None


def ev(code):
    ok, result = call(GNOME_SHELL, "Eval", GLib.Variant("(s)", (code,)))
    if not ok:
        raise RuntimeError(f"Eval failed: {result}\n{code}")
    return result


def state():
    return json.loads(call(SHELL, "GetState")[0])


def until(condition, seconds, step=0.1):
    t0 = time.monotonic()
    while time.monotonic() - t0 < seconds:
        s = state()
        if condition(s):
            return s
        time.sleep(step)
    raise TimeoutError(f"condition not met in {seconds} s: {state()}")


def shot(name):
    path = os.path.join(out, f"{name}.png")
    ok, _used = call(SCREENSHOT, "Screenshot", GLib.Variant("(bbs)", (False, False, path)))
    if not ok:
        raise RuntimeError(f"screenshot {name} failed")
    print(f"shot: {path}", flush=True)


def overview_search(text):
    ev("Main.overview.show();")
    time.sleep(1.5)
    ev(f"Main.overview.searchEntry.set_text({json.dumps(text)});")
    time.sleep(3.0)  # search providers answer, results laid out


def close_everything():
    ev("Main.panel.statusArea.dateMenu.menu.close(); Main.overview.searchEntry.set_text(''); Main.overview.hide();")
    time.sleep(1.0)


def s_search():
    overview_search(QUERIES["search"])
    shot("search")
    close_everything()


def s_calendar():
    overview_search(QUERIES["calendar"])
    shot("search-calendar")
    close_everything()


def s_add_task():
    overview_search(QUERIES["add-task"])
    shot("search-add-task")
    close_everything()


def s_tasks():
    ev("Main.overview.hide();")
    time.sleep(1.0)
    ev("Main.panel.statusArea.dateMenu.menu.open();")
    time.sleep(2.0)
    shot("clock-menu-tasks")
    close_everything()


def s_voice():
    ev("Main.overview.hide();")
    time.sleep(1.0)
    call(SHELL, "Voice")
    time.sleep(2.0)
    shot("voice-pill")
    # Cancelled behind the extension's back, so the pill ends on "Nothing heard": this shot runs last.
    call(HUB, "CancelListen")
    time.sleep(4.0)


def s_typing():
    """Frames of a query typed one character at a time (dev/screenshots/run.sh turns them into an animation)."""
    ev("Main.overview.show();")
    time.sleep(1.5)
    text = QUERIES["typing"]
    for i in range(1, len(text) + 1):
        ev(f"Main.overview.searchEntry.set_text({json.dumps(text[:i])});")
        time.sleep(0.8)
        shot(f"typing-{i:03d}")
    time.sleep(2.0)
    shot(f"typing-{len(text) + 1:03d}")
    close_everything()


SHOTS = {"search": s_search, "calendar": s_calendar, "add-task": s_add_task, "tasks": s_tasks, "typing": s_typing,
         "voice": s_voice}


def main():
    names = sys.argv[2:] or list(SHOTS)
    # The demo daemon is D-Bus activated; the first search waits for it and fills the caches.
    call(HUB, "Search", GLib.Variant("(as)", (["warm-up"],)), timeout=30000)
    call(HUB, "ListTasks", timeout=30000)
    # Unsafe mode (switched on by the bench) announces itself with a notification: not part of the pictures.
    ev("Main.messageTray.getSources().forEach(s => s.destroy());")
    time.sleep(1.0)
    for name in names:
        SHOTS[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
