# Development

See [CONTRIBUTING](../CONTRIBUTING.md) for the ground rules, the layout and the test suites. This page covers the
work loop, the benches and releases.

## Work loop

```sh
./install.sh --no-model -y      # install your working tree (keeps your settings); add --no-deps to skip the check
systemctl --user restart omnishell-daemon
~/.local/share/omnishell/source/verify.sh --quick
```

Changes to the daemon need a restart of the service; changes to the drawer take effect at its next start
(`pkill -f omnishell_panel`, the extension starts it again); changes to the extension need a new login on Wayland, or
the nested Shell below.

`verify.sh` run from a clone also compares the installed copy with your tree and says when they differ.

## Nested GNOME Shell

`extension/tests/nested/nested.sh` runs `gnome-shell --headless` with a virtual monitor on a **private** D-Bus,
with private XDG folders, a private dconf database and no audio, and loads this repository's extension in it. It
refuses to start on your real session bus and checks after the run that your dconf database and runtime folder were
not touched. A driver script talks to the nested Shell through the extension's `io.github.maximeallanic.OmnishellShell`
interface and, because the bench switches on the Shell's unsafe mode inside the nested Shell only, through
`org.gnome.Shell.Eval` and `org.gnome.Shell.Screenshot`.

```sh
extension/tests/nested/run.sh       # the drawer's life cycle: prepared off screen, slid in, hidden, respawned
```

Only one bench runs at a time (lock in `$TMPDIR`). Start it with a memory limit on a busy machine:
`systemd-run --user --scope -p MemoryMax=6G extension/tests/nested/run.sh`.

## Screenshots

The pictures in `screenshots/` are real captures of this code, never mock-ups, and never of a real account:

```sh
dev/screenshots/run.sh OUT                                   # English, every shot, and search-typing.gif
OMNISHELL_SHOT_QUERIES='{"add-task": "t Appeler le plombier demain"}' \
    dev/screenshots/run.sh OUT --locale fr_FR.UTF-8 --shots "add-task tasks"
```

It runs the nested Shell with the **demo daemon** (`dev/screenshots/demo_daemon.py`): the real `HubService` and stores
fed by a local fake of the Google APIs with invented tasks and events, a generated browser profile with public sites,
canned suggestions and a listener that pretends to hear a sentence. The demo daemon refuses to run outside the bench.
The drawer loads `about:blank`: automated loads of gemini.google.com from a bench end on Google's "unusual traffic"
page, which prints the network's public IP address, so never point the bench at Gemini for pictures. How each
picture of the README was made is in [screenshots/README.md](../screenshots/README.md).

## Translations

`scripts/update-po.sh` regenerates `po/omnishell.pot` and merges it; `--check` is what CI runs. Add a language by
copying the template to `po/<lang>.po`.

## extensions.gnome.org

`scripts/pack.sh` builds the upload zip with `gnome-extensions pack`. Before submitting, know that the
[review guidelines](https://gjs.guide/extensions/review-guidelines/review-guidelines.html) discourage external
scripts and ask for GJS unless another language is required. This extension starts the Python drawer from
`~/.local/share/omnishell/panel` and relies on the Python daemon, both installed by `install.sh`, not by the zip:
on its own the zip gives the "Search on Google" and "Ask Gemini" rows and nothing else. A submission therefore needs
the extension to explain, in its description and in the Shell (for example a notification that links to the
installer when the daemon is missing), that the companion installer is required, and a reviewer may still decline
it. The nested-bench hooks in `control.js` (unsafe mode) are only enabled by a metadata key that the bench adds to its
own copy; they are inert in the zip but a reviewer will ask about them.

## Releases

1. Give `CHANGELOG.md` its `## [X.Y.Z] - date` section and commit.
2. `scripts/release.sh X.Y.Z` sets the version in `lib/common.sh` and `install.sh`, builds the reproducible tarball
   (git archive, sorted, fixed dates, owners and modes, `gzip -n`), writes its sha256 into `install.sh` and commits
   `chore(release): X.Y.Z`.
3. Tag `vX.Y.Z` and push it with `main`. `.github/workflows/release.yml` runs the tests, rebuilds the tarball with
   `scripts/release.sh --build-only`, fails if it does not match the pin, and publishes it with its sha256 and the
   extensions.gnome.org zip. The one-line installer on `main` downloads that release asset.
