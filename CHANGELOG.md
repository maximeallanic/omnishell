# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-10-20

First public release.

### Added

- **Google in the GNOME search**: "Search on Google" and "Ask Gemini" rows, Google suggestions, direct addresses,
  keyword searches (`yt`, `maps`, `w`, `gh`, `drive`, your own in `keywords.json`), Chrome or Chromium bookmarks and
  history, Google Calendar events and Google Tasks, and `t <task> [date]` to create a task.
- **Gemini drawer**: the Gemini web app in a drawer that slides in from the right edge of the screen under the
  pointer (Super+G or the top bar icon), prepared in the background so it opens already drawn, hidden from Alt+Tab,
  the dock and the overview, with an offline state.
- **Local voice dictation** with whisper.cpp: Super+Shift+G asks Gemini by voice; the microphone button inside Gemini
  uses the same local engine. Nothing is sent to a speech service.
- **Tasks in the clock menu**: overdue, today and next 7 days, tick to complete, "+ Add a task", offline queue,
  and a daily summary notification.
- Calendar and Tasks use the Google account of GNOME Online Accounts: no OAuth project or key to create.
- English and French user interface; dates read and shown in the session language.
- One-line installer with dependency detection for Debian/Ubuntu, Fedora and Arch, checksum-verified model download,
  `uninstall.sh` (keeps your settings unless `--purge`) and `verify.sh`.
- `scripts/pack.sh` builds the extension zip for extensions.gnome.org.

[Unreleased]: https://github.com/maximeallanic/gnome-google-hub/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maximeallanic/gnome-google-hub/releases/tag/v0.1.0
