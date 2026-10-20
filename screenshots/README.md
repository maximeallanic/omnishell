# Screenshots

Every picture here is a real capture of this repository's code running in GNOME Shell 51, taken through
`org.gnome.Shell.Screenshot`. None is a mock-up and none shows a real account: the data is invented.

## How they were made

All but `gemini-drawer.png` come from `dev/screenshots/run.sh` ([development](../docs/development.md#screenshots)):

- a nested, headless GNOME Shell 51 (1920×1080 virtual monitor) on a private D-Bus with private XDG folders, the
  distribution's original Shell theme, dark style;
- this repository's extension and drawer;
- the **demo daemon** (`dev/screenshots/demo_daemon.py`): the real daemon code fed by a local fake of the Google APIs
  with invented tasks ("Renew passport", "Buy flowers"…) and events ("Team meeting"…), a generated browser profile with
  public sites (gitlab.gnome.org, github.com, docs.gtk.org…), canned suggestions ("… tutorial", "… documentation",
  "… release date", which is why they do not read like real Google suggestions) and a pretend microphone.

The full-screen captures were then cropped with ffmpeg to the area of interest; `search-typing.gif` is assembled by
`run.sh` from nine frames typed one character at a time.

| File | What | Locale |
|---|---|---|
| `search.png` | Search for "gnome": applications, Google group, Chrome bookmarks and history | en_US |
| `search-calendar.png` | Search for "meeting": a calendar event | en_US |
| `search-add-task.png`, `search-add-task.fr.png` | `t Call the plumber tomorrow` / `t Appeler le plombier demain`: task creation with its due date | en_US / fr_FR |
| `clock-menu-tasks.png`, `clock-menu-tasks.fr.png` | Tasks in the clock menu (the task titles are fixture data, in English in both) | en_US / fr_FR |
| `voice-pill.png` | The "Listening…" pill | en_US |
| `search-typing.gif` | Typing "gtk docs" in the search | en_US |

## gemini-drawer.png

The drawer showing the real gemini.google.com, captured with an earlier revision of the same bench (nested Shell,
private bus, a fresh empty WebKit profile created for the run): Gemini **signed out**, on Google's cookie consent
page as served to a visitor from the European Union. Nothing in it is personal. Two differences with the other
pictures: the top bar corner uses the author's Shell theme (m3e-gnome) instead of the original one, and the picture
is cropped to the drawer to leave out the bench's "unsafe mode" notification.

The bench no longer loads Gemini (it uses `about:blank`): repeated automated loads of gemini.google.com are answered
with Google's "unusual traffic" page, which prints the network's public IP address. A picture of a signed-in drawer
needs a real account and was not taken.
