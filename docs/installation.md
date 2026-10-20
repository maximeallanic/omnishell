# Installation

## Requirements

- **GNOME Shell 50 or 51**, Wayland session. Other versions are refused by the extension (`metadata.json`).
- **Python 3.11+** with PyGObject, GTK 4, libadwaita and WebKitGTK 6.0 (for the Gemini drawer).
- **GNOME Online Accounts** with a Google account, for Calendar and Tasks (optional: search and Gemini work without).
- **whisper.cpp's `whisper-server`** and about 470 MB of disk for the speech model, for dictation (optional).
- A Chromium-family browser profile (Chrome or Chromium) if you want bookmarks and history in the search (optional).

## One-line install

From a terminal inside your GNOME session, as your normal user:

```sh
curl -fsSL https://raw.githubusercontent.com/maximeallanic/gnome-google-hub/main/install.sh | bash
```

This downloads the pinned release (`v0.1.0`) into `~/.cache/google-hub/bootstrap` and runs its installer, which:

1. checks your distribution, GNOME Shell version and session;
2. lists the missing system packages and asks before installing them with `sudo` (the only step that uses it);
3. asks before downloading the Whisper speech model (about 466 MB, SHA-1 checked);
4. copies the daemon, the drawer and the extension into your home directory, enables the background service and the
   extension;
5. runs `verify.sh`.

Then log out and back in: GNOME Shell loads new extensions only at login on Wayland.

Options go after `bash -s --`, for example `curl -fsSL …/install.sh | bash -s -- --no-model -y`.
`GOOGLE_HUB_REF=main` installs the development branch instead of the pinned release.

## From a clone

```sh
git clone https://github.com/maximeallanic/gnome-google-hub.git
cd gnome-google-hub
./install.sh            # --help for the options
```

| Option | Effect |
|---|---|
| `--dry-run` | Print what would be done, change nothing. |
| `-y`, `--yes` | Answer yes to every question. |
| `--install-deps` / `--no-deps` | Install missing packages without asking / never install them (only report). |
| `--no-model` | Skip the speech model (dictation stays off until you install it). |
| `--vulkan` | Also install whisper.cpp's Vulkan GPU backend (Debian and Ubuntu: `libggml0-backend-vulkan`). |
| `--no-session-check` | Install from outside a GNOME session (SSH, a script); everything starts at next login. |
| `--no-verify` | Do not run `verify.sh` at the end. |
| `--uninstall` | Same as `./uninstall.sh`. |

Running the installer again updates Google Hub and keeps your settings.

## Dependencies

What each part needs, and the package that provides it. `core` is required; without `panel` the Gemini drawer does
not open; without `voice` dictation is off. The installer checks each line and installs only what is missing.

| Check | Needed for | Debian, Ubuntu | Fedora | Arch |
|---|---|---|---|---|
| `python3` | core | `python3` | `python3` | `python` |
| `curl` | core | `curl` | `curl` | `curl` |
| `sha1sum` | core | `coreutils` | `coreutils` | `coreutils` |
| `gdbus`, `glib-compile-schemas` | core | `libglib2.0-bin` | `glib2` | `glib2` |
| `gnome-extensions` | core | `gnome-shell` | `gnome-shell` | `gnome-shell` |
| `msgfmt` | core | `gettext` | `gettext` | `gettext` |
| Python `gi` | core | `python3-gi` | `python3-gobject` | `python-gobject` |
| `GLibUnix-2.0` typelib | core | `gir1.2-glib-2.0` | `glib2` | `glib2` |
| Python `dateparser` | core | `python3-dateparser` | `python3-dateparser` | `python-dateparser` |
| Python `babel` | core | `python3-babel` | `python3-babel` | `python-babel` |
| `Gtk-4.0` typelib | panel | `gir1.2-gtk-4.0` | `gtk4` | `gtk4` |
| `Adw-1` typelib | panel | `gir1.2-adw-1` | `libadwaita` | `libadwaita` |
| `WebKit-6.0` typelib | panel | `gir1.2-webkit-6.0` | `webkitgtk6.0` | `webkitgtk-6.0` |
| `Gst-1.0` typelib | voice | `gir1.2-gstreamer-1.0` | `gstreamer1` | `gstreamer` |
| `GstApp-1.0` typelib, `audioconvert` | voice | `gir1.2-gst-plugins-base-1.0`, `gstreamer1.0-plugins-base` | `gstreamer1-plugins-base` | `gst-plugins-base-libs`, `gst-plugins-base` |
| `pipewiresrc` | voice | `gstreamer1.0-pipewire` | `pipewire-gstreamer` | `gst-plugin-pipewire` |
| `whisper-server` | voice | `whisper.cpp-tools` (Debian 14 "forky" and later, Ubuntu 26.10 and later) | none, see below | `whisper-cpp` |

The installer asks the package manager whether each package exists before offering it, so a release that lacks one
(an older Ubuntu without `whisper.cpp-tools`, for example) gets the build instructions instead of a failed
`apt-get install`.

**Supported distributions.** The installer knows Debian, Ubuntu and their derivatives (Linux Mint, Pop!_OS, …),
Fedora, and Arch and its derivatives (EndeavourOS, Manjaro, …), from `ID` and `ID_LIKE` in `/etc/os-release`. On any
other distribution (openSUSE, NixOS, Gentoo, …) it says so, installs no package, and goes on if what is needed is
already there: install the dependencies above with your package manager first. Only Debian testing has been run for
real; the Fedora and Arch package names are checked against the distributions' package indexes but not installed in
a test yet.

## Voice dictation

Dictation runs [whisper.cpp](https://github.com/ggml-org/whisper.cpp) on your computer: the daemon starts
`whisper-server` on `127.0.0.1` at the first dictation and stops it after 15 minutes without use. You need the
`whisper-server` program and a model file:

- **The model** is downloaded by the installer to `~/.local/share/google-hub/models/ggml-small.bin` (multilingual,
  about 466 MB). To use another one (`ggml-base.bin` is faster, `ggml-medium.bin` more accurate), download it from
  [the whisper.cpp model repository](https://huggingface.co/ggerganov/whisper.cpp) and set `whisper_model` in
  `config.json` (see [configuration](configuration.md)).
- **Speed.** On a recent laptop CPU a sentence takes one to a few seconds with `ggml-small.bin`. A GPU helps: on
  Debian and Ubuntu, `./install.sh --vulkan` adds the Vulkan backend; elsewhere build whisper.cpp with
  `-DGGML_VULKAN=1` (or CUDA, ROCm…) as below.
- **The microphone** is GNOME's default input (Settings > Sound > Input). If the pill says "Microphone unavailable"
  or dictation hears nothing, pick another input there: some laptops expose several microphones and only one works.

### Dictation without a whisper-server package

Fedora packages whisper.cpp only as a library, and some releases of other distributions lack it. Build it once
(a few minutes):

```sh
# Fedora: sudo dnf install git cmake gcc-c++     Debian/Ubuntu: sudo apt install git cmake g++
git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git ~/.local/src/whisper.cpp
cd ~/.local/src/whisper.cpp
cmake -B build -DBUILD_SHARED_LIBS=OFF        # add -DGGML_VULKAN=1 for a Vulkan GPU (needs the Vulkan headers)
cmake --build build -j --config Release --target whisper-server
install -Dm755 build/bin/whisper-server ~/.local/bin/whisper-server
```

If `~/.local/bin` is not in the service's `PATH`, put the absolute path in `config.json`:
`"whisper_server": "/home/you/.local/bin/whisper-server"`. Then run `./install.sh` again (it downloads the model if
you skipped it) or `systemctl --user restart google-hub-daemon`, and check with `verify.sh`.

## After installing

1. **Log out and back in.**
2. **Settings > Online Accounts > Google**, with *Calendar* enabled (Google Tasks uses the same permission), for
   Calendar and Tasks.
3. **Press Super+G** and sign in to Gemini in the drawer once. The session is kept in the drawer's own profile.
4. **Check**: `~/.local/share/google-hub/source/verify.sh`. It prints one line per check (`OK`, `WARN`, `FAIL`) and a
   hint for each problem; `--quick` skips the real dictation test.

## What is installed where

| Path | What |
|---|---|
| `~/.local/share/gnome-shell/extensions/google-hub@maximeallanic.github.io/` | The GNOME Shell extension |
| `~/.local/share/google-hub/daemon/`, `panel/`, `locale/` | The daemon, the Gemini drawer and their translations |
| `~/.local/share/google-hub/models/` | Speech model |
| `~/.local/share/google-hub/webkit/` | The drawer's browser profile (your Gemini sign-in) |
| `~/.local/share/google-hub/source/` | A copy of this release, for `verify.sh` and `uninstall.sh` |
| `~/.config/google-hub/config.json`, `keywords.json` | Your settings |
| `~/.config/systemd/user/google-hub-daemon.service` | The background service |
| `~/.local/share/dbus-1/services/io.github.maximeallanic.GoogleHub.service` | D-Bus activation of the daemon |
| `~/.local/share/applications/io.github.maximeallanic.GoogleHubPanel.desktop`, `~/.local/share/icons/…` | Launcher entry and icon of the drawer |
| `~/.cache/google-hub/`, `~/.local/state/google-hub/` | Browser history copy, offline task queue, summary state |

Nothing is written outside your home directory, except the packages you agree to install.

## Uninstall

```sh
~/.local/share/google-hub/source/uninstall.sh            # keeps settings, model and Gemini sign-in
~/.local/share/google-hub/source/uninstall.sh --purge    # removes them too
```

It disables the extension and the service and removes exactly the paths above (`--dry-run` lists them). System
packages are left installed: remove them with your package manager if nothing else uses them.

## extensions.gnome.org

`scripts/pack.sh` builds `dist/google-hub@maximeallanic.github.io.shell-extension.zip` with `gnome-extensions pack`
(schemas, French catalogue, icons and the motion toolkit included). The zip contains the Shell extension only: the
search results, Calendar, Tasks and dictation come from the daemon, and the drawer is a separate program, so the
zip on its own shows the "Search on Google" and "Ask Gemini" rows and nothing else works until `install.sh` has run.
See [development](development.md#extensionsgnomeorg) for what this means for a submission.
