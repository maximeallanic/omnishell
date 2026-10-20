# Configuration

Omnishell works without configuration. Three places change its behaviour.

## Search, keyboard shortcuts and the drawer (GSettings)

Schema `org.gnome.shell.extensions.omnishell`. Changes apply at once. The preferences window (Extensions app, or
`gnome-extensions prefs omnishell@maximeallanic.github.io`) has the suggestions switch; the other keys are set with
`gsettings`.

| Key | Default | What |
|---|---|---|
| `search-suggestions` | `true` | Send what you type in the GNOME search to Google for suggestions. `false`: no suggestion request is made ([privacy](privacy.md)). |
| `toggle-panel` | `['<Super>g']` | Open or close the Gemini drawer |
| `voice` | `['<Super><Shift>g']` | Ask Gemini by voice |
| `panel-width` | `600` | Drawer width, in logical pixels (clamped to the monitor) |
| `panel-url` | `''` | Address loaded in the drawer; empty means Gemini. Used by the tests. |

```sh
S="gsettings --schemadir $HOME/.local/share/gnome-shell/extensions/omnishell@maximeallanic.github.io/schemas"
$S set org.gnome.shell.extensions.omnishell toggle-panel "['<Super>space']"
$S set org.gnome.shell.extensions.omnishell panel-width 720
$S reset org.gnome.shell.extensions.omnishell voice
$S set org.gnome.shell.extensions.omnishell search-suggestions false
```

## The daemon: `~/.config/omnishell/config.json`

Written by the installer with the defaults below; it keeps your version when you reinstall. Restart the daemon after
a change: `systemctl --user restart omnishell-daemon`.

| Key | Default | What |
|---|---|---|
| `summary_hour` | `9` | Hour of the daily "N tasks today, M overdue" notification (or at login, if later). |
| `whisper_model` | `""` | Speech model file. Empty: `~/.local/share/omnishell/models/ggml-small.bin`. |
| `whisper_language` | `"auto"` | Language you speak, as an ISO 639-1 code (`"en"`, `"fr"`, `"ja"`…), or `"auto"` to let Whisper detect it each time. Setting it helps short sentences. |
| `whisper_server` | `"whisper-server"` | whisper.cpp server program: a name looked up in `PATH`, or an absolute path. |
| `whisper_threads` | `0` | CPU threads for whisper-server; `0` chooses from the number of CPUs. |
| `chrome_dir` | `""` | Chromium-family profile folder for bookmarks and history. Empty: the first of `~/.config/google-chrome`, `~/.config/chromium` that exists. Brave, Vivaldi or Edge work too: give their folder (for example `~/.config/BraveSoftware/Brave-Browser`). |
| `date_languages` | `[]` | Extra languages read in task due dates and day searches, on top of your session language (dateparser codes: `["en", "de"]`). |

A malformed file is ignored with a warning in the journal (`journalctl --user -u omnishell-daemon`) and the
defaults are used.

## Search keywords: `~/.config/omnishell/keywords.json`

Type a keyword, a space and your text to search a site directly. The defaults:

```json
{
  "yt": ["YouTube", "https://www.youtube.com/results?search_query={q}"],
  "maps": ["Maps", "https://www.google.com/maps/search/{q}"],
  "w": ["Wikipedia", "https://{lang}.wikipedia.org/w/index.php?search={q}"],
  "gh": ["GitHub", "https://github.com/search?q={q}"],
  "drive": ["Drive", "https://drive.google.com/drive/search?q={q}"]
}
```

Each entry is `"keyword": ["Label", "URL"]`. In the URL, `{q}` is your text (URL-encoded) and `{lang}` the language of
your session (`en`, `fr`, `ja`…). Your file is merged over the defaults: add or replace entries, the others stay. For
example:

```json
{
  "ddg": ["DuckDuckGo", "https://duckduckgo.com/?q={q}"],
  "w": ["Wikipedia (English)", "https://en.wikipedia.org/w/index.php?search={q}"]
}
```

The keyword `t` is reserved: `t <task> [date]` creates a Google task (see [usage](usage.md)).

## Language

Omnishell follows your session language, like the rest of GNOME (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`):

- **Interface**: English and French are translated; other languages show English until a catalogue is added
  (`po/`, see [CONTRIBUTING](../CONTRIBUTING.md#translations)).
- **Dates** are shown in your locale's format (Babel) and read in your language plus `date_languages` (dateparser),
  for any language those libraries support.
- **Google suggestions** (when on) **and Wikipedia** use your session language.
- **Dictation** transcribes any language the Whisper model knows (99 for the multilingual models).
