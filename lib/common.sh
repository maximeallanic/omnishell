# shellcheck shell=bash disable=SC2034  # the constants below are used by the scripts that source this file
# Shared by install.sh, uninstall.sh and verify.sh: version, paths, messages, prompts.

OMNISHELL_VERSION=0.1.1
UUID=omnishell@maximeallanic.github.io
BUS_NAME=io.github.maximeallanic.Omnishell
PANEL_APP_ID=io.github.maximeallanic.OmnishellPanel
DOCS_URL=https://github.com/maximeallanic/omnishell/blob/main/docs
# Whisper model downloaded by default (whisper.cpp models/README.md gives the SHA-1).
MODEL_NAME=ggml-small.bin
MODEL_URL=https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
MODEL_SHA1=55356645c2b361a969dfd0ef2c5a50d530afd8d5

# XDG base directories, as GLib reads them. The daemon, the drawer and the extension use the same ones.
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
CACHE_HOME=${XDG_CACHE_HOME:-$HOME/.cache}
STATE_HOME=${XDG_STATE_HOME:-$HOME/.local/state}

EXT_DIR=$DATA_HOME/gnome-shell/extensions/$UUID
DATA=$DATA_HOME/omnishell                  # daemon/, panel/, locale/, models/, webkit/ (Gemini sign-in), source/
CONF=$CONFIG_HOME/omnishell                # config.json, keywords.json
CACHE=$CACHE_HOME/omnishell                # copy of the browser history, tasks.json (offline queue)
STATE=$STATE_HOME/omnishell                # summary.json
UNIT_DIR=$CONFIG_HOME/systemd/user
UNIT=omnishell-daemon.service
DBUS_SERVICE=$DATA_HOME/dbus-1/services/$BUS_NAME.service
DESKTOP_FILE=$DATA_HOME/applications/$PANEL_APP_ID.desktop
ICON_FILE=$DATA_HOME/icons/hicolor/symbolic/apps/omnishell-gemini-symbolic.svg
# What to tell the user to run again: the release copy kept by the installer works after a one-line install too.
REINSTALL=$DATA/source/install.sh

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    C_BOLD=$'\e[1m' C_DIM=$'\e[2m' C_RED=$'\e[31m' C_GREEN=$'\e[32m' C_YELLOW=$'\e[33m' C_BLUE=$'\e[34m' C_OFF=$'\e[0m'
else
    C_BOLD='' C_DIM='' C_RED='' C_GREEN='' C_YELLOW='' C_BLUE='' C_OFF=''
fi

msg_step() { printf '\n%s==>%s %s%s%s\n' "$C_BLUE" "$C_OFF" "$C_BOLD" "$*" "$C_OFF"; }
msg_info() { printf '    %s\n' "$*"; }
msg_ok() { printf '  %s✓%s %s\n' "$C_GREEN" "$C_OFF" "$*"; }
msg_warn() { printf '  %s!%s %s\n' "$C_YELLOW" "$C_OFF" "$*" >&2; }
die() { printf '%serror:%s %s\n' "$C_RED" "$C_OFF" "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

DRY_RUN=${DRY_RUN:-0}
ASSUME_YES=${ASSUME_YES:-0}

# run CMD...: runs it, or only prints it with --dry-run.
run() {
    if ((DRY_RUN)); then
        printf '    %s[dry run]%s %s\n' "$C_DIM" "$C_OFF" "$*"
        return 0
    fi
    "$@"
}

# ask "Question" [default y|n]: yes/no from the terminal, even when this script is piped into bash (curl … | bash).
# -y answers yes; without a terminal and without -y the default answer is taken and said.
ask() {
    local question=$1 default=${2:-y} hint answer
    if ((ASSUME_YES)); then return 0; fi
    [[ $default == y ]] && hint='[Y/n]' || hint='[y/N]'
    if ! { exec 3</dev/tty; } 2>/dev/null; then
        msg_info "$question $hint: no terminal to ask, answering '$default' (use -y to answer yes)"
        [[ $default == y ]]
        return
    fi
    printf '%s?%s %s %s ' "$C_YELLOW" "$C_OFF" "$question" "$hint" >/dev/tty
    read -r answer <&3 || answer=''
    exec 3<&-
    answer=${answer:-$default}
    [[ $answer == [yY]* ]]
}

# A graphical session bus is needed for systemctl --user, gsettings and the Shell checks.
session_ready() {
    [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" || -S "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/bus" ]]
}

# gnome-shell major version, empty when gnome-shell is missing.
shell_major() {
    have gnome-shell || return 0
    LC_ALL=C gnome-shell --version 2>/dev/null | sed -n 's/^GNOME Shell \([0-9]*\).*/\1/p'
}
