# Architecture

Three processes, all running as you, talking over the D-Bus session bus.

```
GNOME Shell
└─ extension google-hub@maximeallanic.github.io (GJS)
     search.js       three search providers (Google, Chrome, Calendar & Tasks); one daemon call per typed text
     panel.js        starts the drawer, keeps it ready off screen, places it on the monitor under the pointer
     drawer-motion.js, m3e/   the drawer's spring motion (vendored M3E toolkit)
     voice-pill.js   the "Listening…" pill
     tasks-menu.js   Tasks section of the clock menu
     control.js      io.github.maximeallanic.GoogleHubShell: Ping, Toggle, Ask, Voice, GetState
     logic.js        pure logic (tested with gjs): rows, geometry, drawer life cycle
        │                                              │
        │ io.github.maximeallanic.GoogleHub            │ io.github.maximeallanic.GoogleHubPanel
        ▼                                              ▼
google-hub-daemon (Python, systemd user service)   google-hub-panel (Python, GTK 4 + WebKitGTK 6)
  Search, Activate                                    Show, Hide, Ask, Focus, ProbeComposer
  ListTasks, CompleteTask, AddTask                    gemini.google.com in its own WebKit profile
  Listen, StopListen, CancelListen                    speech-polyfill.js: SpeechRecognition → daemon Listen
  ├─ omnibox.py   Google suggestions, keywords, addresses
  ├─ chrome.py    bookmarks and history (a copy of the History database)
  ├─ goa.py       Google token from GNOME Online Accounts
  ├─ google_api.py, calendar.py, tasks.py   Calendar v3 and Tasks v1 REST, offline queue
  ├─ dates.py     dates read with dateparser, shown with Babel, in the session language
  └─ voice.py, whisper.py   GStreamer (PipeWire) capture, end-of-speech detection, whisper-server on 127.0.0.1
```

## The daemon

`daemon/google_hub/` owns the bus name `io.github.maximeallanic.GoogleHub` (interface in `introspection.xml`). It is
a systemd user service (`google-hub-daemon.service`) and is also D-Bus activatable, so the first search starts it if
it is not running. Every call is answered from a worker thread; the search waits at most a fixed budget and
returns what is ready (suggestions, history, events) so that typing never blocks.

- **Google account.** `goa.py` follows GNOME Online Accounts' object manager and asks the account for an OAuth access
  token (`GetAccessToken`). GOA's Google provider already requests the Calendar and Tasks scopes: no OAuth client of
  our own, no key in the code.
- **Tasks** are cached in `~/.cache/google-hub/tasks.json`. A change made offline is applied locally, queued and
  replayed when the network returns (GNOME's network monitor); a change Google refuses produces a notification.
- **Calendar**: the events of the next 30 days, cached five minutes.
- **Suggestions** come from Google's public suggest endpoint in the session language.
- **Voice.** `Listen()` captures the default microphone with GStreamer, detects the end of speech (energy over a
  calibrated noise floor), encodes WAV in memory and posts it to `whisper-server`, started on demand on a random port of
  127.0.0.1 and stopped after 15 minutes idle. The audio context is sized to the length of the sentence, which makes
  short sentences several times faster than whisper.cpp's default.

## The drawer

`panel/google_hub_panel/` is a separate GTK 4 program because a Shell extension cannot embed a web view. The
extension starts it with `Meta.WaylandClient`, which lets the Shell recognise its window, keep it out of Alt+Tab, the
dock and the overview, and place it.

A WebKit view that has never been shown loads its page but does not draw it, and its first showing used to take one
to two seconds of empty drawer. So as soon as the drawer is on the bus, the extension asks it to `Show` once while
the window is kept transparent and off screen, then hides it. `Show` answers only when the view has something to
show (`readiness.py`): `ready` (load finished and two animation frames drawn), `offline` or `failed` (a native status
page replaces the view), or `stalled` / `unresponsive` after 10 seconds without progress. The extension slides the
drawer in only at that answer.

`Ask` types the question into Gemini's prompt and presses send through `ask.js` with the selectors of
`selectors.js`. If Gemini changes its page and the prompt is not found, the question is copied to the clipboard and a
notification says so.

WebKitGTK has no speech recognition engine, so `speech-polyfill.js` provides `SpeechRecognition` to the page and
forwards it to the daemon's `Listen()`: Gemini's own microphone button uses local Whisper.

## The extension

Search providers are registered with GNOME Shell's internal search API; the three groups share one daemon call per
typed text. Without the daemon, the Google group still shows "Search on Google" and "Ask Gemini", built locally.

The extension runs in the `user` and `unlock-dialog` session modes: during the lock screen it removes its icon and
keybindings and stops its D-Bus interface but keeps the drawer process, so the Gemini conversation survives a lock.

## Languages

One gettext domain, `google-hub`, for the three parts (`po/`). The extension uses the Shell's gettext, the Python
side `gettext` with the languages GLib reports, so all three follow the session like GNOME does. Nothing parses text
with a language-specific list: dates go through dateparser, URL detection accepts any script, and the "long enough to
search" threshold is in UTF-8 bytes so that one Han character counts like three Latin letters.

## Files

| Path | What |
|---|---|
| `install.sh`, `uninstall.sh`, `verify.sh`, `lib/` | Installer, checks, removal |
| `extension/google-hub@maximeallanic.github.io/` | GNOME Shell extension |
| `daemon/google_hub/` | Daemon |
| `panel/google_hub_panel/` | Gemini drawer |
| `data/` | systemd unit, D-Bus activation file, desktop entry (paths filled in by the installer) |
| `po/` | Translations |
| `scripts/` | `pack.sh` (extensions.gnome.org zip), `update-po.sh` |
| `dev/screenshots/` | README pictures, taken in a nested Shell |
| `tests/` and `*/tests/` | Tests ([CONTRIBUTING](../CONTRIBUTING.md#tests)) |
