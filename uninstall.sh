#!/usr/bin/env bash
# Remove Omnishell. Runs as your user and removes only what install.sh installed, by exact path.
#
#   ./uninstall.sh [--dry-run] [-y|--yes] [--purge]
#
#   --purge   also delete your settings, the Gemini sign-in, the Whisper model and the task cache
#             (by default they are kept, so a later reinstall picks up where you left off)
set -euo pipefail

REPO_ROOT=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
LIB=$REPO_ROOT/lib
# shellcheck source=lib/common.sh
source "$LIB/common.sh"
# shellcheck source=lib/uninstall.sh
source "$LIB/uninstall.sh"

PURGE=0
SESSION_CHECK=1
while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        -y|--yes) ASSUME_YES=1 ;;
        --purge) PURGE=1 ;;
        --no-session-check) SESSION_CHECK=0 ;;
        -h|--help) sed -n '2,/^set -e/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
[[ $(id -u) != 0 ]] || die "run this as your normal user, not as root"
if ((PURGE)); then question="Remove Omnishell and delete your settings, Gemini sign-in, speech model and task cache?"
else question="Remove Omnishell (your settings, Gemini sign-in and speech model are kept)?"; fi
ask "$question" n || { msg_info "Nothing removed."; exit 0; }
do_uninstall "$PURGE"
