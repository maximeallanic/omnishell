#!/usr/bin/env bash
# Run by nested.sh on the private bus before the nested Shell starts: installs the drawer of this repository in the
# PRIVATE data folder (the extension starts it from XDG_DATA_HOME/omnishell/panel; its WebKit profile goes to
# XDG_DATA_HOME/omnishell/webkit).
set -eu
[[ $XDG_DATA_HOME == "${OMNISHELL_BENCH_TMP:?}"/* ]] || { echo "prepare.sh: XDG_DATA_HOME is not private" >&2; exit 1; }
mkdir -p "$XDG_DATA_HOME/omnishell/panel"
cp -r "${OMNISHELL_REPO:?}/panel/omnishell_panel" "$XDG_DATA_HOME/omnishell/panel/"
