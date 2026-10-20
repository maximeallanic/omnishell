# Contributing

Thanks for helping. Omnishell is a GNOME Shell extension (GJS), a background daemon (Python) and a Gemini drawer
(Python, GTK 4 and WebKitGTK), with a shell installer.

## Ways to contribute

- **Report a bug** with the issue form: version, distribution, GNOME Shell version, session language, steps to
  reproduce and the output of `verify.sh`. Never paste personal data (events, tasks, history, Gemini conversations).
- **Try it on another setup** (Fedora, Arch, Ubuntu, another language) and say what worked and what did not. Only
  Debian testing has been run for real so far.
- **Translate it**: copy `po/omnishell.pot` to `po/<lang>.po`, translate, and run `scripts/update-po.sh --check`.
  The installer compiles every catalogue it finds; nothing else to register.
- **Fix something or add a feature**, as described below.

## How to contribute code

1. **Discuss first** for anything beyond a small fix: open an issue or a Discussion with the problem and the approach.
2. **Fork** and create a branch from `main` named `type/short-description` (`feat`, `fix`, `docs`, `refactor`,
   `test`, `ci`, `chore`).
3. **Keep the change focused**: one subject per pull request, no unrelated reformatting.
4. **Run the tests** below; add or update tests for the behaviour you changed.
5. **Commit with [Conventional Commits](https://www.conventionalcommits.org/)** messages in English
   (`fix(search): keep keyword rows above suggestions`). The pull request title follows the same format.
6. **Open the pull request** against `main`, fill in the template and link the issue. For a visual change, add
   before/after screenshots taken in the nested Shell (`dev/screenshots/run.sh`), never from your own account.

By contributing you agree that your work is released under the repository licence (MIT). You are responsible for what
you submit, including anything produced with the help of a tool: read it, run it, and be able to explain it.

## Ground rules

- **English in the code**: identifiers, comments, commit messages, log lines. User-facing strings go through
  `_()` / `ngettext()` (both the Python and the GJS side) and get a French translation in `po/fr.po`.
- **No language is hard-coded** on the path between the user and Gemini, Google or Whisper: no keyword list,
  regular expression or length threshold that only works in one language or script. Dates are parsed with
  dateparser and shown with Babel in the session's language; the speech language is detected by Whisper.
- **No source file over 500 lines** (`tests/check_sizes.py`). Split along a real seam.
- **Fix causes, not symptoms.** No retry loop that hides a failure, no swallowed error, no special case for one test.
- **Search before you build**: prefer a maintained dependency, and say in the PR why you adopted or rejected one.
- **Never leave the user's home**: no `sudo` outside the package installation step, no write outside the XDG folders
  listed in `lib/common.sh`, and uninstall removes exact paths only.

## Layout

| Path | What |
|---|---|
| `install.sh`, `uninstall.sh`, `verify.sh` | The three entry points. `lib/` holds their parts: `common`, `deps` (per-distribution packages), `steps`, `uninstall`, `bus_probe.py`. |
| `extension/omnishell@maximeallanic.github.io/` | The GNOME Shell extension: search providers, drawer placement and motion, voice pill, Tasks in the clock menu. `m3e/` is the vendored motion toolkit (see NOTICE.md). |
| `daemon/omnishell/` | `io.github.maximeallanic.Omnishell` on the session bus: search, Google APIs through GNOME Online Accounts, Whisper. |
| `panel/omnishell_panel/` | The Gemini drawer (GTK 4 + WebKitGTK 6). |
| `data/` | systemd user unit, D-Bus activation file, launcher. |
| `po/` | Translations (one domain, `omnishell`, for the three parts). |
| `dev/screenshots/` | The README pictures, taken in a nested GNOME Shell with demo data. |
| `tests/`, `daemon/tests/`, `panel/tests/`, `extension/tests/` | Tests (below). |

## Tests

```sh
tests/run.sh            # shellcheck, file sizes, translations, daemon, extension logic, drawer, installer round trip
tests/run.sh --nested   # also the real extension in a nested, headless GNOME Shell
```

- `daemon/tests/`: unittest, with a local fake of the Google APIs and of whisper-server on a private D-Bus. The real
  Whisper test runs when `whisper-server` and the model are installed.
- `panel/tests/run.sh`: the drawer against local HTML pages in a headless weston, on a private bus with private XDG
  folders.
- `extension/tests/test_*.js`: pure logic, run with `gjs -m`.
- `extension/tests/nested/run.sh`: the real extension and drawer in `gnome-shell --headless` on a private bus and
  private XDG folders; it refuses to run on your real session bus.
- `tests/roundtrip.sh`: install, reinstall, model download (checksum), one-line install from a tarball, uninstall and
  purge inside a temporary HOME, with shims for `gsettings`, `systemctl`, `gnome-shell` and `sudo`.

Heavy suites (the drawer, the nested Shell) start real compositors: on a busy machine, run them with
`systemd-run --user --scope -p MemoryMax=6G tests/run.sh --nested`.

What the tests cannot cover: signing in to Google and Gemini, Gemini's real page (its selectors live in
`panel/omnishell_panel/selectors.js` and may change at any time), a real microphone, and the Fedora and Arch
package names (checked as text only).

## Translations

```sh
scripts/update-po.sh          # regenerate po/omnishell.pot and merge it into every po/*.po
scripts/update-po.sh --check  # what CI runs: every string translated, every gettext file listed in po/POTFILES
```

A comment starting with `Translators:` right above a string reaches the translators.
