#!/usr/bin/env bash
# Run by nested.sh on the private bus before the nested Shell starts: installs the drawer in the PRIVATE data folder
# and makes the demo daemon (demo_daemon.py) D-Bus activatable on the private bus, under the real daemon's name.
set -eu
[[ $XDG_DATA_HOME == "${GOOGLE_HUB_BENCH_TMP:?}"/* ]] || { echo "prepare.sh: XDG_DATA_HOME is not private" >&2; exit 1; }
REPO=${GOOGLE_HUB_REPO:?}
mkdir -p "$XDG_DATA_HOME/google-hub/panel" "$XDG_DATA_HOME/google-hub/daemon" "$XDG_DATA_HOME/dbus-1/services"
cp -r "$REPO/panel/google_hub_panel" "$XDG_DATA_HOME/google-hub/panel/"
cp -r "$REPO/daemon/google_hub" "$XDG_DATA_HOME/google-hub/daemon/"
for po in "$REPO"/po/*.po; do
    lang=$(basename "$po" .po)
    mkdir -p "$XDG_DATA_HOME/google-hub/locale/$lang/LC_MESSAGES"
    msgfmt -o "$XDG_DATA_HOME/google-hub/locale/$lang/LC_MESSAGES/google-hub.mo" "$po"
done
cat >"$XDG_DATA_HOME/dbus-1/services/io.github.maximeallanic.GoogleHub.service" <<S
[D-BUS Service]
Name=io.github.maximeallanic.GoogleHub
Exec=/usr/bin/python3 $REPO/dev/screenshots/demo_daemon.py
S
