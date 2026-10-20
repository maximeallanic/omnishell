#!/usr/bin/env bash
# Run by nested.sh on the private bus before the nested Shell starts: installs the drawer in the PRIVATE data folder
# and makes the demo daemon (demo_daemon.py) D-Bus activatable on the private bus, under the real daemon's name.
set -eu
[[ $XDG_DATA_HOME == "${OMNISHELL_BENCH_TMP:?}"/* ]] || { echo "prepare.sh: XDG_DATA_HOME is not private" >&2; exit 1; }
REPO=${OMNISHELL_REPO:?}
mkdir -p "$XDG_DATA_HOME/omnishell/panel" "$XDG_DATA_HOME/omnishell/daemon" "$XDG_DATA_HOME/dbus-1/services"
cp -r "$REPO/panel/omnishell_panel" "$XDG_DATA_HOME/omnishell/panel/"
cp -r "$REPO/daemon/omnishell" "$XDG_DATA_HOME/omnishell/daemon/"
for po in "$REPO"/po/*.po; do
    lang=$(basename "$po" .po)
    mkdir -p "$XDG_DATA_HOME/omnishell/locale/$lang/LC_MESSAGES"
    msgfmt -o "$XDG_DATA_HOME/omnishell/locale/$lang/LC_MESSAGES/omnishell.mo" "$po"
done
cat >"$XDG_DATA_HOME/dbus-1/services/io.github.maximeallanic.Omnishell.service" <<S
[D-BUS Service]
Name=io.github.maximeallanic.Omnishell
Exec=/usr/bin/python3 $REPO/dev/screenshots/demo_daemon.py
S
