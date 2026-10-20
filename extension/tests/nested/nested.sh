#!/usr/bin/env bash
# Nested bench: runs the extension in an isolated `gnome-shell --headless --wayland` (virtual monitor, private XDG_*
# directories and XDG_RUNTIME_DIR, private D-Bus session bus without the file indexer, named Wayland socket), then
# hands over to a driver script. It never touches the real session.
#
# Usage: nested.sh --driver SCRIPT [--out DIR] [--prepare SCRIPT] [--keyfile FILE]... [--locale LOCALE]
#                  [--monitor WxH@R] [--stock-theme GRESOURCE]
#   --driver SCRIPT   bash script run once the extension answers Ping (driver OUT); its exit code is the bench's
#   --prepare SCRIPT  bash script run on the private bus before gnome-shell starts (install the panel, a demo daemon…)
#   --keyfile FILE    dconf keyfile compiled into the PRIVATE dconf database (repeatable; later files win)
#   --locale LOCALE   locale of the nested session (default C.UTF-8); the host locale is never inherited
#   --monitor WxH@R   virtual monitor (default 1920x1080@60)
#   --stock-theme F   Shell theme resource file to use instead of the system one (for a host whose theme was replaced,
#                     e.g. a dpkg diversion of gnome-shell-theme.gresource): its sheets are overlaid with G_RESOURCE_OVERLAYS
# The extension of this repository is copied with the "google-hub-bench" metadata key, which exports its *Debug
# methods and switches the nested Shell to unsafe mode (org.gnome.Shell.Eval and Screenshot for the driver).
# Exit codes: 0 ok; 1 failure; 2 refusal, usage or lock held; 3 the real dconf database changed; 4 the host runtime
# directory changed.
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
UUID=google-hub@maximeallanic.github.io
NAME=io.github.maximeallanic.GoogleHubShell
OBJ_PATH=/io/github/maximeallanic/GoogleHubShell
usage() { echo "nested.sh: $1" >&2; exit 2; }

if [[ ${1:-} != --inner ]]; then
    OUT='' DRIVER='' PREPARE='' KEYFILES=() LOCALE=C.UTF-8 MONITOR=1920x1080@60 STOCK=''
    while (($#)); do
        (($# >= 2)) || usage "$1 needs a value"
        case "$1" in
            --out) OUT=$2 ;;
            --driver) [[ -f $2 ]] || usage "--driver not found: $2"; DRIVER=$(realpath "$2") ;;
            --prepare) [[ -f $2 ]] || usage "--prepare not found: $2"; PREPARE=$(realpath "$2") ;;
            --keyfile) [[ -f $2 ]] || usage "--keyfile not found: $2"; KEYFILES+=("$(realpath "$2")") ;;
            --locale) [[ $2 =~ ^[A-Za-z0-9_.@-]+$ ]] || usage "--locale: $2"; LOCALE=$2 ;;
            --monitor) [[ $2 =~ ^[0-9]+x[0-9]+(@[0-9]+)?$ ]] || usage "--monitor WxH@R: $2"; MONITOR=$2 ;;
            --stock-theme) [[ -f $2 ]] || usage "--stock-theme not found: $2"; STOCK=$(realpath "$2") ;;
            *) usage "unknown option: $1" ;;
        esac
        shift 2
    done
    [[ -n $DRIVER ]] || usage "--driver is required"
    # One bench at a time (two nested Shells would fight over nothing, but double the load).
    exec 9>"${TMPDIR:-/tmp}/google-hub-bench.lock" || usage "cannot open the lock"
    flock -n 9 || usage "another bench session is running"
    [[ -n $OUT ]] || OUT=$(mktemp -d)
    mkdir -p "$OUT" && OUT=$(cd "$OUT" && pwd) || exit 2
    # dconf guard: modification time of the REAL dconf database, read before the XDG_* change.
    DCONF_REAL="${XDG_CONFIG_HOME:-$HOME/.config}/dconf/user"
    dconf_date() { stat -c '%y' "$DCONF_REAL" 2>/dev/null || echo absent; }
    DCONF_BEFORE=$(dconf_date)
    # Host runtime directory guard (shared with the real session; the nested Shell gets $TMP/run).
    HOST_RUN=${XDG_RUNTIME_DIR:?XDG_RUNTIME_DIR is not set}
    list_run() { find "$HOST_RUN" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | sort; }
    RUN_BEFORE=$(list_run)
    TMP=$(mktemp -d) || exit 2
    # Private XDG_RUNTIME_DIR and XDG_* exported BEFORE dbus-run-session: services activated on the private bus
    # (dconf-service first, which writes the settings) inherit the bus daemon's environment, not the Shell's.
    # Audio stays private too: the bench never records or plays through the host.
    mkdir -m 0700 "$TMP/run" "$TMP/data" || exit 2
    export XDG_RUNTIME_DIR="$TMP/run" PIPEWIRE_RUNTIME_DIR="$TMP/run" PULSE_RUNTIME_PATH="$TMP/run/pulse" \
        GOOGLE_HUB_HOST_RUN="$HOST_RUN" GVFS_DISABLE_FUSE=1
    unset WAYLAND_DISPLAY DISPLAY
    export XDG_CONFIG_HOME="$TMP/config" XDG_DATA_HOME="$TMP/data" XDG_CACHE_HOME="$TMP/cache" XDG_STATE_HOME="$TMP/state"
    export GOOGLE_HUB_BENCH_TMP="$TMP" GOOGLE_HUB_REAL_BUS="${DBUS_SESSION_BUS_ADDRESS:-}" GOOGLE_HUB_BENCH_LOCALE="$LOCALE" \
        GOOGLE_HUB_BENCH_MONITOR="$MONITOR" GOOGLE_HUB_BENCH_PREPARE="$PREPARE" GOOGLE_HUB_BENCH_DRIVER="$DRIVER" \
        GOOGLE_HUB_BENCH_STOCK="$STOCK"
    GOOGLE_HUB_BENCH_KEYFILES=$(IFS=:; echo "${KEYFILES[*]-}")
    export GOOGLE_HUB_BENCH_KEYFILES
    # Private bus without the file indexer: activated there it would crawl the real HOME (session_bus.py).
    BUS_CONF=$(python3 "$HERE/session_bus.py" "$TMP/bus") || { rm -rf -- "$TMP"; exit 2; }
    dbus-run-session --config-file="$BUS_CONF" -- bash "$HERE/nested.sh" --inner "$OUT" "$TMP" 9>&- </dev/null
    code=$?
    RUN_AFTER=$(list_run)
    pattern='^(google-hub-bench-|gnome-shell-disable-extensions$|\.mutter-Xwaylandauth\.|\.X[0-9]+-lock$)'
    created=$(comm -13 <(printf '%s\n' "$RUN_BEFORE") <(printf '%s\n' "$RUN_AFTER") | grep -E "$pattern")
    gone=$(comm -23 <(printf '%s\n' "$RUN_BEFORE") <(printf '%s\n' "$RUN_AFTER") |
        grep -E "$pattern|^(wayland-|bus$|pipewire|pulse$|dconf$|doc$)")
    if [[ $(dconf_date) != "$DCONF_BEFORE" ]]; then
        echo "nested.sh: $DCONF_REAL changed during the bench (the real session may write too): please check" >&2
        code=3
    fi
    if [[ -n $created || -n $gone ]]; then
        echo "nested.sh: $HOST_RUN changed during the bench: created [$created] gone [$gone]" >&2
        code=4
    fi
    exit "$code"
fi

# --- inner part: runs inside the private session bus ---
refuse() { echo "nested.sh --inner refused: $1" >&2; exit 2; }
OUT=$2 TMP=$3
[[ -n ${GOOGLE_HUB_BENCH_TMP:-} && $TMP == "$GOOGLE_HUB_BENCH_TMP" ]] || refuse "unexpected TMP: $TMP"
[[ $TMP == "${TMPDIR:-/tmp}"/tmp.* && -d $TMP ]] || refuse "TMP outside ${TMPDIR:-/tmp}/tmp.*: $TMP"
for v in XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME XDG_STATE_HOME; do
    [[ ${!v:-} == "$TMP"/* ]] || refuse "$v is not temporary: ${!v:-}"
done
[[ -n ${DBUS_SESSION_BUS_ADDRESS:-} && $DBUS_SESSION_BUS_ADDRESS != "${GOOGLE_HUB_REAL_BUS:-}" ]] || refuse "real session bus"
[[ ${XDG_RUNTIME_DIR:-} == "$TMP/run" && $XDG_RUNTIME_DIR != "${GOOGLE_HUB_HOST_RUN:-}" ]] ||
    refuse "XDG_RUNTIME_DIR is not private: ${XDG_RUNTIME_DIR:-}"
[[ -z ${WAYLAND_DISPLAY:-} && -z ${DISPLAY:-} ]] || refuse "WAYLAND_DISPLAY/DISPLAY of the host inherited"

SHELL_PID=''
# shellcheck disable=SC2317,SC2329  # invoked by the EXIT trap
cleanup() {
    if [[ -n $SHELL_PID ]] && kill -0 "$SHELL_PID" 2>/dev/null; then
        kill "$SHELL_PID" 2>/dev/null
        for _ in $(seq 1 50); do kill -0 "$SHELL_PID" 2>/dev/null || break; sleep 0.1; done
        kill -9 "$SHELL_PID" 2>/dev/null
    fi
    # Mounts under TMP (document portal…) are unmounted first; otherwise TMP is left alone (rm -rf would cross them).
    local m
    # shellcheck disable=SC2013  # mount points under TMP contain no spaces (mktemp)
    for m in $(awk -v t="$TMP/" 'index($2, t) == 1 { print $2 }' /proc/mounts); do
        fusermount3 -u -z "$m" 2>/dev/null || fusermount -u -z "$m" 2>/dev/null || umount -l "$m" 2>/dev/null
    done
    if awk -v t="$TMP/" 'index($2, t) == 1 { found = 1 } END { exit !found }' /proc/mounts; then
        echo "nested.sh: mount still active under $TMP: directory left in place" >&2
    else
        rm -rf -- "$TMP"
    fi
}
trap cleanup EXIT

EXT="$XDG_DATA_HOME/gnome-shell/extensions/$UUID"
mkdir -p "$XDG_CONFIG_HOME/dconf" "$(dirname "$EXT")" "$XDG_CACHE_HOME" "$XDG_STATE_HOME" "$TMP/dconf-src"
cp -r "$REPO/extension/$UUID" "$EXT" || exit 1
python3 - "$EXT/metadata.json" <<'PY' || exit 1
import json, sys
meta = json.load(open(sys.argv[1]))
meta["google-hub-bench"] = True
json.dump(meta, open(sys.argv[1], "w"))
PY
glib-compile-schemas --strict "$EXT/schemas" || exit 1
for po in "$REPO"/po/*.po; do
    lang=$(basename "$po" .po)
    mkdir -p "$EXT/locale/$lang/LC_MESSAGES"
    msgfmt --check -o "$EXT/locale/$lang/LC_MESSAGES/google-hub.mo" "$po" || exit 1
done
# External search providers off: activated on the private bus they would search the real HOME.
cat >"$TMP/dconf-src/00-bench.keyfile" <<K
[org/gnome/shell]
enabled-extensions=['$UUID']
disable-user-extensions=false
welcome-dialog-last-shown-version='999'

[org/gnome/desktop/search-providers]
disable-external=true
K
n=10
IFS=: read -ra EXTRA <<<"${GOOGLE_HUB_BENCH_KEYFILES:-}"
for k in ${EXTRA[@]+"${EXTRA[@]}"}; do cp "$k" "$TMP/dconf-src/$n.keyfile"; n=$((n + 1)); done
dconf compile "$XDG_CONFIG_HOME/dconf/user" "$TMP/dconf-src" || { echo "dconf compile failed" >&2; exit 1; }

LOCALE_ENV=()
for v in $(compgen -e); do [[ $v =~ ^(LANG|LANGUAGE|LC_[A-Z]+)$ ]] && LOCALE_ENV+=(-u "$v"); done
LOCALE_ENV+=("LANG=$GOOGLE_HUB_BENCH_LOCALE")
# Services the private bus activates (the daemon) get the bench locale too, as gnome-session arranges in a real
# session; the bus itself was started with the host environment. An empty value counts as unset for GLib.
ACTIVATION_ENV=("LANG=$GOOGLE_HUB_BENCH_LOCALE")
for v in $(compgen -e); do [[ $v =~ ^(LANGUAGE|LC_[A-Z]+)$ ]] && ACTIVATION_ENV+=("$v="); done
dbus-update-activation-environment "${ACTIVATION_ENV[@]}" || { echo "cannot set the activation environment" >&2; exit 1; }
if [[ -n ${GOOGLE_HUB_BENCH_PREPARE:-} ]]; then
    env "${LOCALE_ENV[@]}" GOOGLE_HUB_REPO="$REPO" bash "$GOOGLE_HUB_BENCH_PREPARE" "$OUT" || { echo "prepare script failed" >&2; exit 1; }
fi
THEME_ENV=()
if [[ -n ${GOOGLE_HUB_BENCH_STOCK:-} ]]; then
    mkdir -p "$TMP/stock-theme"
    for r in $(gresource list "$GOOGLE_HUB_BENCH_STOCK" /org/gnome/shell/theme); do
        gresource extract "$GOOGLE_HUB_BENCH_STOCK" "$r" >"$TMP/stock-theme/$(basename "$r")" || exit 1
    done
    THEME_ENV=("G_RESOURCE_OVERLAYS=/org/gnome/shell/theme=$TMP/stock-theme")
fi
DISPLAY_NAME="google-hub-bench-$$"
env "${LOCALE_ENV[@]}" ${THEME_ENV[@]+"${THEME_ENV[@]}"} gnome-shell --headless --virtual-monitor "$GOOGLE_HUB_BENCH_MONITOR" --wayland \
    --wayland-display "$DISPLAY_NAME" >"$OUT/shell.log" 2>&1 &
SHELL_PID=$!
ready=0
for _ in $(seq 1 240); do
    kill -0 "$SHELL_PID" 2>/dev/null || { echo "the nested Shell stopped (see $OUT/shell.log)" >&2; exit 1; }
    if gdbus call --session --dest "$NAME" --object-path "$OBJ_PATH" --method "$NAME.Ping" >/dev/null 2>&1; then
        ready=1; break
    fi
    sleep 0.5
done
((ready)) || { echo "the extension never answered Ping (see $OUT/shell.log)" >&2; exit 1; }
env "${LOCALE_ENV[@]}" WAYLAND_DISPLAY="$DISPLAY_NAME" GOOGLE_HUB_REPO="$REPO" bash "$GOOGLE_HUB_BENCH_DRIVER" "$OUT"
