# Google Hub for GNOME

[![CI](https://github.com/maximeallanic/gnome-google-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/maximeallanic/gnome-google-hub/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![GNOME Shell 50 | 51](https://img.shields.io/badge/GNOME%20Shell-50%20%7C%2051-4a86cf.svg)](docs/installation.md#requirements)

English | [Français](README.fr.md)

Google in your GNOME desktop instead of in browser tabs: Google search and suggestions in the GNOME search, Gemini in a
drawer one shortcut away, voice dictation that runs on your computer, and your Google Calendar and Tasks where you
already look for the time.

<p align="center">
  <img src="screenshots/search-typing.gif" width="880" alt="Typing “gtk docs” in the GNOME search: Google suggestions, Ask Gemini and a matching page from the browser history appear as you type">
</p>

## Features

- **Google in the GNOME search.** Press Super and type: "Search on Google", "Ask Gemini", Google suggestions, direct
  addresses, your Chrome or Chromium bookmarks and history, your calendar events and tasks.
- **Keyword searches.** `yt`, `maps`, `w` (Wikipedia in your language), `gh`, `drive`, and your own.
- **Create a task by typing.** `t Call the plumber tomorrow` creates a Google task due tomorrow; dates are read in
  your language.
- **Gemini drawer.** Super+G slides the real Gemini web app in from the right edge, already loaded, and hides it when
  you click elsewhere. It stays out of Alt+Tab and the overview.
- **Local voice.** Super+Shift+G: speak, and the sentence goes to Gemini. Speech is transcribed on your computer by
  [whisper.cpp](https://github.com/ggml-org/whisper.cpp); Gemini's own microphone button uses it too.
- **Tasks in the clock menu.** Overdue, today and the next 7 days; tick to complete, add one, works offline, and a
  morning summary.
- **No API key.** Calendar and Tasks use the Google account of GNOME Online Accounts.
- **Your language.** Follows the session language; English and French interface, dates and dictation in any
  language the libraries know.

<table>
  <tr>
    <td><img src="screenshots/search.png" width="440" alt="Search for “gnome”: applications, then the Google group with suggestions and the Chrome group with bookmarks"></td>
    <td><img src="screenshots/clock-menu-tasks.png" width="360" alt="Clock menu with a Tasks section: overdue, today, next 7 days, and an Add a task field"></td>
  </tr>
  <tr>
    <td><img src="screenshots/search-add-task.png" width="440" alt="Typing “t Call the plumber tomorrow” offers “Create task: Call the plumber”, due Wednesday"><br><img src="screenshots/search-calendar.png" width="440" alt="Search for “meeting” finds the Team meeting event"><br><img src="screenshots/voice-pill.png" width="440" alt="The Listening pill at the top of the screen"></td>
    <td><img src="screenshots/gemini-drawer.png" width="300" alt="The Gemini drawer at the right edge of the screen, signed out, on Google's consent page"></td>
  </tr>
</table>

<sub>Real captures in a nested GNOME Shell with invented data; the drawer is shown signed out. How they were made:
[screenshots/README.md](screenshots/README.md).</sub>

## Requirements

- GNOME Shell 50 or 51 (Wayland)
- Debian testing, Ubuntu, Fedora or Arch (the installer installs the packages); other distributions work with the
  [dependencies](docs/installation.md#dependencies) installed by hand
- Optional: a Google account in Settings > Online Accounts (Calendar and Tasks), `whisper-server` and about 470 MB for
  the speech model (dictation)

## Install

From a terminal in your GNOME session, as your normal user:

```sh
curl -fsSL https://raw.githubusercontent.com/maximeallanic/gnome-google-hub/main/install.sh | bash
```

The installer shows what is missing and asks before installing packages with `sudo` and before downloading the speech
model, installs everything in your home directory, and ends with a check. Then:

1. Log out and back in.
2. Settings > Online Accounts > Google, with Calendar enabled.
3. Press Super+G and sign in to Gemini once.

From a clone: `git clone https://github.com/maximeallanic/gnome-google-hub && cd gnome-google-hub && ./install.sh`
(`--help` for the options). Details, per-distribution packages and building whisper.cpp:
[docs/installation.md](docs/installation.md).

Check or remove it at any time:

```sh
~/.local/share/google-hub/source/verify.sh
~/.local/share/google-hub/source/uninstall.sh     # --purge also removes settings, model and Gemini sign-in
```

## Usage

| Do | Get |
|---|---|
| Super, then type | Google, Chrome and Calendar & Tasks results below the applications |
| `yt …`, `maps …`, `w …`, `gh …`, `drive …` | A direct search on that site |
| `t Buy bread friday` | A Google task due Friday |
| `tomorrow`, `monday`… | That day's events |
| Super+G, or the sparkle icon | Open or close the Gemini drawer |
| Super+Shift+G | Ask Gemini by voice (again or click: stop; Escape: cancel) |
| Clock menu | Your tasks; tick to complete, "+ Add a task" |

More in [docs/usage.md](docs/usage.md).

## Configuration

Shortcuts and the drawer width are GSettings keys, the daemon reads `~/.config/google-hub/config.json` (speech model
and language, daily summary hour, browser profile, extra date languages), and `~/.config/google-hub/keywords.json`
adds search keywords. See [docs/configuration.md](docs/configuration.md).

## Privacy

What you type in the search is sent to Google's suggestion service; Calendar and Tasks talk to Google's APIs with your
account; the drawer is Gemini. Your voice, your browser history and your credentials stay on your computer. No
telemetry. Details: [docs/privacy.md](docs/privacy.md).

## Troubleshooting and FAQ

`verify.sh` names most problems and how to fix them. See [docs/troubleshooting.md](docs/troubleshooting.md) and
[docs/faq.md](docs/faq.md). Some answers:

- **Is it made by Google?** No, it is an independent project ([NOTICE](NOTICE.md)).
- **Do I need an API key?** No.
- **Fedora?** Everything works, but Fedora has no `whisper-server` package: dictation needs whisper.cpp built once
  ([how](docs/installation.md#dictation-without-a-whisper-server-package)).
- **extensions.gnome.org?** Not yet: the extension needs its companion daemon and drawer, which the installer sets up.
- **Gemini changed and "Ask" no longer types the question?** Open an issue; the page selectors are in
  `panel/google_hub_panel/selectors.js`.

## Documentation

[Installation](docs/installation.md) · [Usage](docs/usage.md) · [Configuration](docs/configuration.md) ·
[Troubleshooting](docs/troubleshooting.md) · [Privacy](docs/privacy.md) · [FAQ](docs/faq.md) ·
[Architecture](docs/architecture.md) · [Development](docs/development.md) · [Changelog](CHANGELOG.md)

## Contributing

Bug reports, tests on other distributions and translations are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md),
[SUPPORT.md](SUPPORT.md) and the [code of conduct](CODE_OF_CONDUCT.md). Security issues: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Maxime Allanic. Google, Gemini and the other Google product names are trademarks of Google
LLC; this project is not affiliated with Google. Third-party notices: [NOTICE.md](NOTICE.md).
