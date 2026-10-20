# Security policy

## Reporting a vulnerability

Please report security issues **privately** through GitHub: *Security* tab, *Report a vulnerability*
(private vulnerability reporting). Do not open a public issue. Include the version (`./install.sh --version`), your
distribution and what an attacker can do. You will get an answer within a week; fixes are released as soon as
they are verified.

## What is in scope

Omnishell handles a Google access token, your calendar and tasks, your browser history and the microphone. What we
promise about them:

- **No root.** The installer and every component run as your user and change only your home directory. `sudo` is
  used only to install missing distribution packages, after showing the exact command and asking (or with
  `--install-deps`).
- **No stored credentials.** The Google access token comes from GNOME Online Accounts and is kept in memory only,
  until it expires. The Gemini sign-in lives in the drawer's own WebKit profile (`~/.local/share/omnishell/webkit`).
- **Local speech.** Audio is captured only while the listening pill is shown or Gemini's microphone button is
  active, sent to a `whisper-server` bound to `127.0.0.1` and never written to disk.
- **Verified downloads.** The one-line install downloads its release over HTTPS only and checks it against the sha256
  pinned in `install.sh` before unpacking it. The speech model is checked against a SHA-1 before use; a mismatch
  deletes it and stops.
- **Exact removal.** `uninstall.sh` removes a fixed list of paths and never expands a pattern.
- **Local D-Bus only.** The daemon and the extension talk over the session bus; nothing listens on the network.

Reports about a way to reach the token, the microphone or the history from another user or a web page, to make the
installer write outside `$HOME`, or to run unverified downloaded code are especially welcome.

## Out of scope

Vulnerabilities in Gemini, Google services, GNOME Online Accounts, WebKitGTK or whisper.cpp: report them to those
projects.

## Supported versions

Only the latest release.
