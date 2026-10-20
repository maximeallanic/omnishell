"""Nested check of the Gemini drawer (run by driver.sh inside the nested Shell's private bus).

The panel loads a local page whose load is held by server.py. Checked through the extension's control interface:
- the Show asked when the panel reaches the bus prepares the window out of sight, without the focus, and parks it;
- a click while the page loads checks the button at once but nothing comes in sight; a second click cancels;
- the drawer slides in only after the page is released (load finished, frame produced), with the focus;
- once prepared, the drawer opens within a frame; Ask opens it and sends the text.
Writes OUT/drawer.json; exit 0 when every check holds.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

from gi.repository import Gio, GLib

SHELL = "io.github.maximeallanic.GoogleHubShell"
SHELL_PATH = "/io/github/maximeallanic/GoogleHubShell"
PANEL = "io.github.maximeallanic.GoogleHubPanel"
HERE = os.path.dirname(os.path.abspath(__file__))

out = sys.argv[1]
port = open(os.path.join(out, "port")).read().strip()
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
checks = []
measures = {}


def call(method, params=None):
    reply = bus.call_sync(SHELL, SHELL_PATH, SHELL, method, params, None, Gio.DBusCallFlags.NONE, 5000, None)
    return reply.unpack() if reply else None


def state():
    return json.loads(call("GetState")[0])


def http(path):
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5).read()


def check(name, ok, detail=None):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f" — {detail}"), flush=True)


def until(condition, seconds, step=0.02):
    """Polls the Shell state; returns (state that met the condition or None, seconds waited, every state seen)."""
    t0 = time.monotonic()
    seen = []
    while time.monotonic() - t0 < seconds:
        s = state()
        seen.append(s)
        if condition(s):
            return s, time.monotonic() - t0, seen
        time.sleep(step)
    return None, seconds, seen


def watch(seconds):
    return until(lambda _s: False, seconds)[2]


def never_in_sight(name, seen):
    check(name, seen and not any(s["panelInSight"] for s in seen), [s["panelInSight"] for s in seen][-5:])


def brief(s):
    return s and {k: s[k] for k in ("panelVisible", "panelPhase", "panelInSight", "buttonChecked", "panelWindow",
                                    "panelLastShow", "focusTitle", "overview")}


def panel_pid():
    reply = bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                          "GetConnectionUnixProcessID", GLib.Variant("(s)", (PANEL,)), None,
                          Gio.DBusCallFlags.NONE, 5000, None)
    return reply.unpack()[0]


def main():
    # --- A. the panel reaches the bus: its window is prepared out of sight, nobody asked for the drawer
    s, _, seen = until(lambda s: s["panelPhase"] == "requested" and s["panelWindow"], 30)
    check("first Show asked when the panel reaches the bus, window mapped", s, brief(seen[-1]))
    # Longer than the 3 s after which Mutter suspends a window it does not consider visible (the Shell starts in the
    # overview, where no window actor is painted): a suspended window gets no frame.
    seen = watch(4.5)
    check("first Show pending while the page loads", all(s["panelPhase"] == "requested" for s in seen), brief(seen[-1]))
    check("still in the overview", all(s["overview"] for s in seen))
    never_in_sight("prepared window out of sight (overview)", seen)
    check("button not checked while preparing", not any(s["buttonChecked"] for s in seen))
    http("/release")
    s, t, seen = until(lambda s: s["panelPhase"] == "unmapped", 15)
    check("prepared window parked once the page is ready", s, brief(seen[-1]))
    never_in_sight("never in sight during the preparation", seen)
    check("first Show answered ready, in the overview", s and s["panelLastShow"]["answer"] == "ready", s and s["panelLastShow"])
    measures["first_show_ms_after_release"] = round(t * 1000)
    call("OverviewDebug", GLib.Variant("(b)", (False,)))
    until(lambda s: not s["overview"], 5)
    witness = subprocess.Popen([sys.executable, os.path.join(HERE, "witness.py")])
    try:
        scenario(witness)
    finally:
        witness.terminate()
        witness.wait()


def scenario(_witness):
    s, _, _ = until(lambda s: s["focusTitle"] == "witness", 10)
    check("witness window focused", s, brief(state()))

    # --- B. prepared drawer: opens within a frame
    t0 = time.monotonic()
    call("Toggle")
    s, t, seen = until(lambda s: s["panelInSight"] and s["panelPhase"] == "ready", 15)
    check("prepared drawer opens", s, brief(seen[-1]))
    measures["prepared_open_ms"] = round(t * 1000)
    measures["prepared_open_show"] = s and s["panelLastShow"]
    s, _, seen = until(lambda s: s["focusIsPanel"], 5)
    check("open drawer has the focus", s, brief(seen[-1]))
    time.sleep(1.0)  # slide-in spring at rest
    s = state()
    check("open drawer at the right edge", s["panelRect"] and s["panelRect"][0] + s["panelRect"][2] == 1920, s["panelRect"])
    call("Toggle")
    s, _, seen = until(lambda s: s["panelPhase"] == "unmapped" and not s["panelWindow"], 10)
    check("drawer closed and unmapped", s, brief(seen[-1]))
    s, _, seen = until(lambda s: s["focusTitle"] == "witness", 5)
    check("focus back to the witness", s, brief(seen[-1]))

    # --- C. new panel process, page held: clicks while it loads
    http("/hold")
    pid = panel_pid()
    os.kill(pid, 15)  # the panel of this nested Shell (owner of its name on the private bus)
    s, _, seen = until(lambda s: s["panelPhase"] == "absent", 10)
    check("panel gone: phase absent", s, brief(seen[-1]))
    s, t, seen = until(lambda s: s["panelPhase"] == "requested" and s["panelWindow"], 30)
    check("respawned panel prepared again", s, brief(seen[-1]))
    seen = watch(1.0)
    never_in_sight("prepared window out of sight (desktop)", seen)
    check("prepared window does not keep the focus", all(s["focusTitle"] == "witness" for s in seen),
          sorted({str(s["focusTitle"]) for s in seen}))
    call("Toggle")
    seen = watch(1.5)
    check("click while loading: button checked at once", seen[0]["buttonChecked"] and seen[0]["panelVisible"], brief(seen[0]))
    check("click while loading: Show still pending", all(s["panelPhase"] == "requested" for s in seen), brief(seen[-1]))
    never_in_sight("click while loading: nothing in sight", seen)
    check("click while loading: focus stays", all(s["focusTitle"] == "witness" for s in seen),
          sorted({str(s["focusTitle"]) for s in seen}))
    call("Toggle")
    seen = watch(1.0)
    check("second click cancels: button released", not any(s["buttonChecked"] or s["panelVisible"] for s in seen), brief(seen[-1]))
    never_in_sight("second click cancels: nothing in sight", seen)
    call("Toggle")
    seen = watch(0.5)
    never_in_sight("third click: still nothing in sight before the page is ready", seen)
    http("/release")
    s, t, seen = until(lambda s: s["panelInSight"], 15)
    check("drawer slides in once the page is ready", s and s["panelPhase"] == "ready", brief(seen[-1]))
    check("Show answered ready", s and s["panelLastShow"]["answer"] == "ready", s and s["panelLastShow"])
    measures["open_ms_after_release"] = round(t * 1000)
    s, _, seen = until(lambda s: s["focusIsPanel"], 5)
    check("drawer has the focus once in sight", s, brief(seen[-1]))
    call("Toggle")
    s, _, seen = until(lambda s: s["panelPhase"] == "unmapped" and not s["panelWindow"], 10)
    check("drawer closed again", s, brief(seen[-1]))

    # --- D. Ask: opens the drawer, then sends the text
    call("Ask", GLib.Variant("(s)", ("bonjour",)))
    s, _, seen = until(lambda s: s["panelInSight"], 15)
    check("Ask opens the drawer", s, brief(seen[-1]))
    deadline = time.monotonic() + 8
    sent = []
    while time.monotonic() < deadline and not sent:
        sent = json.loads(http("/log"))["sent"]
        time.sleep(0.1)
    check("Ask sends the text to the page", sent == ["bonjour"], sent)
    call("Toggle")
    until(lambda s: s["panelPhase"] == "unmapped", 10)


try:
    main()
except Exception as e:  # reported as a failed check, with what was collected so far
    check("driver ran to the end", False, repr(e))
ok = all(c["ok"] for c in checks)
json.dump({"ok": ok, "checks": checks, "measures": measures}, open(os.path.join(out, "drawer.json"), "w"), indent=1)
print(json.dumps(measures))
sys.exit(0 if ok else 1)
