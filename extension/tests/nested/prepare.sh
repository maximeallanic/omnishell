#!/usr/bin/env bash
# Run by nested.sh on the private bus before the nested Shell starts: installs the drawer of this repository in the
# PRIVATE data folder (the extension starts it from XDG_DATA_HOME/google-hub/panel; its WebKit profile goes to
# XDG_DATA_HOME/google-hub/webkit).
set -eu
[[ $XDG_DATA_HOME == "${GOOGLE_HUB_BENCH_TMP:?}"/* ]] || { echo "prepare.sh: XDG_DATA_HOME is not private" >&2; exit 1; }
mkdir -p "$XDG_DATA_HOME/google-hub/panel"
cp -r "${GOOGLE_HUB_REPO:?}/panel/google_hub_panel" "$XDG_DATA_HOME/google-hub/panel/"
