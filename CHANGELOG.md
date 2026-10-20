# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-20

First published release: 0.1.0 was tagged but never released. Its tag, pushed together with the first push of the
branch, did not start the release workflow, and the CI ShellCheck job failed on the older ShellCheck of the Ubuntu
runner (a warning disabled under its 0.11 code only). The project was renamed from "Google Hub" to Omnishell before
this release.

### Added

- **Google in the GNOME search**: "Search on Google" and "Ask Gemini" rows, Google suggestions, direct addresses,
  keyword searches (`yt`, `maps`, `w`, `gh`, `drive`, your own in `keywords.json`), Chrome or Chromium bookmarks and
  history, Google Calendar events and Google Tasks, and `t <task> [date]` to create a task.
- **Google suggestions switch** in the preferences window (GSettings key `search-suggestions`, on by default): when
  off, the daemon sends no suggestion request at all.
- **Gemini drawer**: the Gemini web app in a drawer that slides in from the right edge of the screen under the
  pointer (Super+G or the top bar icon), prepared in the background so it opens already drawn, hidden from Alt+Tab,
  the dock and the overview, with an offline state.
- **Local voice dictation** with whisper.cpp: Super+Shift+G asks Gemini by voice; the microphone button inside Gemini
  uses the same local engine. Nothing is sent to a speech service.
- **Tasks in the clock menu**: overdue, today and next 7 days, tick to complete, "+ Add a task", offline queue,
  and a daily summary notification.
- Calendar and Tasks use the Google account of GNOME Online Accounts: no OAuth project or key to create.
- English and French user interface; dates read and shown in the session language.
- One-line installer that downloads a pinned release and checks its sha256, dependency detection for Debian/Ubuntu,
  Fedora and Arch, checksum-verified model download, `uninstall.sh` (keeps your settings unless `--purge`) and
  `verify.sh`.
- `scripts/pack.sh` builds the extension zip for extensions.gnome.org.

## [0.1.0] - 2026-10-20

Tagged, not released (see 0.1.1).

[Unreleased]: https://github.com/maximeallanic/omnishell/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/maximeallanic/omnishell/releases/tag/v0.1.1
[0.1.0]: https://github.com/maximeallanic/omnishell/releases/tag/v0.1.0
