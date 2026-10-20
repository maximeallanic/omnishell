# Troubleshooting

Start with the checker. It changes nothing and prints a hint for every problem:

```sh
~/.local/share/google-hub/source/verify.sh          # --quick skips the real dictation test
```

## Installation

| Symptom | What to do |
|---|---|
| `error: run this as your normal user, not as root` | Run the command without `sudo`; the installer asks for `sudo` itself when it installs packages. |
| `no graphical session found` | Run it from a terminal inside your GNOME session, or pass `--no-session-check` (everything starts at next login). |
| `GNOME Shell NN: this release is tested with 50 and 51 only` | The extension declares GNOME Shell 50 and 51 and will not load elsewhere. |
| `no package list for this distribution` | Install the [dependencies](installation.md#dependencies) with your package manager, then run the installer again. |
| `has no whisper-server package` | Build it: [dictation without a whisper-server package](installation.md#dictation-without-a-whisper-server-package). Everything else works without it. |
| `checksum mismatch` for the model | The download was corrupted or changed upstream; the file is deleted. Run the installer again. |
| The extension is "not loaded yet" after installing | Log out and back in: on Wayland GNOME Shell loads new extensions only at login. |
| "all user extensions are switched off" | Open the Extensions app and turn on the switch at the top. |

## Search

| Symptom | What to do |
|---|---|
| No Google group at all | Type at least three letters (one CJK character). Check that the extension is enabled (`gnome-extensions info google-hub@maximeallanic.github.io`) and the daemon runs (`systemctl --user status google-hub-daemon`). |
| Only "Search on Google" and "Ask Gemini", no suggestions | The daemon is not answering: `journalctl --user -u google-hub-daemon -b`. Offline, there are no suggestions. |
| Calendar & Tasks group says "Connect your Google account" | Settings > Online Accounts > Google, with Calendar enabled. |
| No Chrome group | No Chrome or Chromium profile was found; set `chrome_dir` in `config.json` ([configuration](configuration.md)). |
| A date in `t …` is not recognised | It must end the text, in your session language or one of `date_languages`. |

## Gemini

| Symptom | What to do |
|---|---|
| verify.sh: "Gemini prompt not found" | Press Super+G and sign in once in the drawer. If you are signed in, Google has changed Gemini's page: the prompt and send button selectors live in `panel/google_hub_panel/selectors.js`; please open an issue. |
| "Question copied — paste it into Gemini" | Same cause: the question could not be typed in; it is on the clipboard. |
| The drawer opens on an error page | Offline, or Gemini failed to load; it retries when the network returns and each time you open it. |
| The drawer is slow to open the first time after login | Gemini is still loading; the icon is selected and the drawer slides in when the page is drawn. `journalctl --user -b \| grep google-hub-panel` shows `SHOW: ready`, `offline`, `failed`, `stalled` or `unresponsive`. |
| Super+G does nothing | Another application may use the shortcut; change it ([configuration](configuration.md)). |

## Voice

| Symptom | What to do |
|---|---|
| Pill says "Microphone unavailable" | Choose a working input in Settings > Sound > Input. Some laptops expose several microphones of which only one records sound. `wpctl status` lists them. |
| Pill says "Nothing heard" | The microphone records silence or very low sound: raise the input volume, or choose another input. |
| Pill says "Transcription failed" | `journalctl --user -u google-hub-daemon -b`: usually `whisper-server` missing, or the model file. `verify.sh` names the cause. |
| Dictation is slow | Use a smaller model (`ggml-base.bin`), set `whisper_language`, or give whisper.cpp a GPU backend (`--vulkan` on Debian/Ubuntu). The first sentence after 15 idle minutes also loads the model. |
| Wrong language transcribed | Set `whisper_language` to the language you speak. |

## Logs and state

```sh
journalctl --user -u google-hub-daemon -b                  # daemon
journalctl --user -b | grep -E 'google-hub|JS ERROR'       # drawer and extension
gdbus call --session -d io.github.maximeallanic.GoogleHubShell -o /io/github/maximeallanic/GoogleHubShell \
    -m io.github.maximeallanic.GoogleHubShell.GetState     # extension state (drawer phase, last Show)
```

When you paste logs in an issue, remove event titles, task titles, URLs and anything else personal.
