#!/usr/bin/env bash
# Panel tests in a private headless compositor (weston) on a private session bus, with private XDG folders: the test
# windows never open on the live session and nothing reaches its bus. Usage: tests/run.sh [unittest arguments]
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v weston >/dev/null || { echo "weston missing: sudo apt-get install weston" >&2; exit 2; }
# Private runtime folder (sockets only) next to the session's one, whose path is short: Unix socket paths are capped at
# 108 bytes and WebKitGTK puts its longest one at "$XDG_RUNTIME_DIR/webkitgtk/a11y-proxy-XXXXXX". Config, data and
# cache go under $TMPDIR, whatever its length.
SOCKET_MAX=107 LONGEST_SOCKET=/webkitgtk/a11y-proxy-XXXXXX
RT="$(mktemp -d "${XDG_RUNTIME_DIR:-/tmp}/google-hub-tests.XXXXXX")" || exit 2
RUN="$(mktemp -d "${TMPDIR:-/tmp}/google-hub-panel-tests.XXXXXX")" || { rmdir -- "$RT"; exit 2; }
chmod 700 "$RT" "$RUN"
# Services activated on the private bus mount FUSE file systems in the private runtime folder (gvfs, document portal):
# unmounted first, and a folder is left in place if one is still there (rm must not cross a mount).
remove() {
    local m
    while read -r m; do
        fusermount3 -u -z "$m" 2>/dev/null || fusermount -u -z "$m" 2>/dev/null
    done < <(awk -v t="$1/" 'index($2, t) == 1 { print $2 }' /proc/mounts)
    if awk -v t="$1/" 'index($2, t) == 1 { f = 1 } END { exit !f }' /proc/mounts; then
        echo "run.sh: mount still active under $1: folder left in place" >&2
    else
        rm -rf -- "${1:?}"
    fi
}
cleanup() { remove "$RT"; remove "$RUN"; }
trap cleanup EXIT
if (( ${#RT} + ${#LONGEST_SOCKET} > SOCKET_MAX )); then
    echo "run.sh: runtime folder $RT too long for Unix sockets (${#RT} + ${#LONGEST_SOCKET} > $SOCKET_MAX bytes):" \
        "set XDG_RUNTIME_DIR to a shorter folder" >&2
    exit 2
fi
export XDG_RUNTIME_DIR="$RT" XDG_CONFIG_HOME="$RUN/config" XDG_DATA_HOME="$RUN/data" XDG_CACHE_HOME="$RUN/cache"
mkdir "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" || exit 2
unset WAYLAND_DISPLAY DISPLAY DBUS_SESSION_BUS_ADDRESS
export GSETTINGS_BACKEND=memory GOOGLE_HUB_PANEL_DIR="$HERE/.." PYTHONDONTWRITEBYTECODE=1
[[ $# -gt 0 ]] || set -- discover -s tests -t .
# -b: unittest shows what a test wrote on stderr (the panel's own stderr, see run_panel) only when that test fails.
if [[ $1 == discover ]]; then set -- discover -b "${@:2}"; else set -- -b "$@"; fi
# shellcheck disable=SC2016  # expanded by the inner bash, on the private bus
dbus-run-session -- bash -c '
    weston --backend=headless --renderer=gl --socket=google-hub-tests --width=1920 --height=1080 --idle-time=0 \
        >"$XDG_RUNTIME_DIR/weston.log" 2>&1 &
    weston=$!
    for _ in $(seq 100); do [[ -S "$XDG_RUNTIME_DIR/google-hub-tests" ]] && break; sleep 0.1; done
    [[ -S "$XDG_RUNTIME_DIR/google-hub-tests" ]] || { cat "$XDG_RUNTIME_DIR/weston.log" >&2; exit 2; }
    export WAYLAND_DISPLAY=google-hub-tests GDK_BACKEND=wayland
    cd "$GOOGLE_HUB_PANEL_DIR" && python3 -W ignore -m unittest "$@"
    code=$?
    kill "$weston"; wait "$weston" 2>/dev/null
    exit $code' _ "$@" 2> >(grep -v -E "dbus-daemon\[|^$|xdg-desktop-portal|atspi|keyring|discover_other_daemon|Non-compatible display|cannot open display|bus can.t be made" >&2)
