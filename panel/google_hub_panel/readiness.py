"""Readiness of the drawer: Show answers only when the view has something to show.

A WebKitWebView that was never mapped does load its page, but the page is hidden (visibilityState "hidden"), its
viewport is 0x0 and no frame is ever produced: the first map pays the first layout, the first paint and the set-up of
the rendering pipeline (measured: 1.5 to 2.5 s for Gemini, 5 to 30 ms for the following maps; see docs/architecture.md).
WebKitGTK 6.0 has no API to make an unmapped view visible, so the window is mapped first (the Shell keeps it out of
sight) and the answer waits for real WebKit events:

- "ready": no load in progress and two requestAnimationFrame callbacks ran after the map (the second one runs once the
  first frame has been produced);
- "offline", "failed": nothing to wait for, the window shows its status page (window.py);
- "stalled": a load or a frame is awaited and WebKit reported no progress at all for STALL_MS ("unresponsive" when
  WebKit also flags the web process as unresponsive at that moment, or when the page cannot run the frame probe);
- "cancelled": Hide arrived first.
"""
from gi.repository import GLib

# Longest silence accepted between two progress reports of WebKit (load progress, load event, frame). Measured on
# gemini.google.com (2026-10-12, WebKitGTK 2.52.6, four loads, machine load 5 to 12): 17 to 24 reports per load, largest
# gap 1.84 s; first frame after the first map: 2.5 s at most. 10 s is five times the largest gap.
STALL_MS = 10_000
WORLD = "google-hub-readiness"
FRAME_JS = "return await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => r(true))));"


class Readiness:
    def __init__(self, view, is_mapped, log, stall_ms=STALL_MS):
        self._view = view
        self._is_mapped = is_mapped
        self._log = log
        self._stall_ms = stall_ms
        self._waiters = []
        self._probing = False
        self._stall_id = 0
        self.problem = None  # None, "offline" or "failed": set by the window, which shows the matching status page
        view.connect("load-changed", lambda *_: self._progress())
        view.connect("notify::estimated-load-progress", lambda *_: self._progress())
        # Not an answer by itself: WebKit flags a starting web process as unresponsive for a moment on a busy machine
        # (seen in the nested Shell: 3.6 s after the spawn, load 5), then takes it back.
        view.connect("notify::is-web-process-responsive",
                     lambda v, _p: log(f"RESPONSIVE: {str(v.get_is_web_process_responsive()).lower()}"))

    def wait(self, done):
        """done(state) is called once, when the view has something to show or will not have."""
        self._waiters.append(done)
        self.evaluate()

    def cancel(self):
        self._resolve("cancelled")

    def evaluate(self):
        if not self._waiters:
            return
        if self.problem:
            self._resolve(self.problem)
            return
        if not self._stall_id:
            self._stall_id = GLib.timeout_add(self._stall_ms, self._on_stall)
        if not self._view.is_loading() and self._is_mapped() and not self._probing:
            self._probing = True
            self._view.call_async_javascript_function(FRAME_JS, -1, None, WORLD, None, None, self._on_frame)

    def _progress(self):
        if self._stall_id:
            GLib.source_remove(self._stall_id)
            self._stall_id = 0
        self.evaluate()

    def _on_stall(self):
        self._stall_id = 0
        self._resolve("stalled" if self._view.get_is_web_process_responsive() else "unresponsive")
        return GLib.SOURCE_REMOVE

    def _on_frame(self, view, res):
        self._probing = False
        try:
            view.call_async_javascript_function_finish(res)
        except GLib.Error as e:
            # The page went away under the probe. A new load or a problem has its own events; anything else means
            # the page cannot run a script.
            self._log(f"FRAME-ERROR: {e.message}")
            if self.problem or view.is_loading():
                self.evaluate()
            else:
                self._resolve("unresponsive")
            return
        self._log("FRAME")
        if self.problem or view.is_loading():
            self._progress()
        else:
            self._resolve("ready")

    def _resolve(self, state):
        if self._stall_id:
            GLib.source_remove(self._stall_id)
            self._stall_id = 0
        waiters, self._waiters = self._waiters, []
        for done in waiters:
            done(state)
