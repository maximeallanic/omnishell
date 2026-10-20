#!/usr/bin/env bash
# Check a Google Hub installation. Read-only: it changes nothing. Exit status 0 when nothing failed.
#
#   ./verify.sh [--quick] [--strict]
#
#   --quick          skip the real dictation test (it starts whisper-server on a short recording, about 10 s)
#   --strict         count warnings as failures
#   --after-install  used by install.sh: what only a new login brings (the extension loaded) is a warning
set -uo pipefail

REPO_ROOT=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
LIB=$REPO_ROOT/lib
# shellcheck source=lib/common.sh
source "$LIB/common.sh"
# shellcheck source=lib/deps.sh
source "$LIB/deps.sh"

QUICK=0 STRICT=0 AFTER_INSTALL=0
while (($#)); do
    case "$1" in
        --quick) QUICK=1 ;;
        --strict) STRICT=1 ;;
        --after-install) AFTER_INSTALL=1 ;;
        -h|--help) sed -n '2,/^set -u/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
    shift
done

FAILS=0 WARNS=0
pass() { printf '  %sOK%s    %s\n' "$C_GREEN" "$C_OFF" "$*"; }
warn() { printf '  %sWARN%s  %s\n' "$C_YELLOW" "$C_OFF" "$*"; WARNS=$((WARNS + 1)); }
fail() { printf '  %sFAIL%s  %s\n' "$C_RED" "$C_OFF" "$*"; FAILS=$((FAILS + 1)); }
section() { printf '\n%s%s%s\n' "$C_BOLD" "$*" "$C_OFF"; }
probe() { python3 -I "$LIB/bus_probe.py" "$@"; }
# json_get JSON KEY: one field of a JSON object, printed as JSON ('null' when absent).
json_get() { python3 -I -c 'import json, sys; print(json.dumps(json.loads(sys.argv[1]).get(sys.argv[2])))' "$1" "$2"; }

session_ready || die "no session bus: run ./verify.sh from a terminal inside your GNOME session"
FAMILY=$(distro_family)

section "Dependencies"
for need in core panel voice; do
    check_deps "$FAMILY" "$need"
    if ((${#MISSING_CHECKS[@]} == 0)); then pass "$need: everything installed"
    elif [[ $need == core ]]; then fail "missing: ${MISSING_CHECKS[*]#*:} ($REINSTALL installs them)"
    else warn "missing: ${MISSING_CHECKS[*]#*:}: $(dep_consequence "$need")"; fi
done

section "Background daemon"
if systemctl --user is-active --quiet "$UNIT"; then pass "$UNIT is running"
else fail "$UNIT is not running (journalctl --user -u $UNIT)"; fi
if groups=$(probe search github 2>&1) && [[ $groups == *\"google\"* ]]; then pass "search answers (groups: $groups)"
else fail "search does not answer: $groups"; fi
if status=$(probe status 2>&1); then
    if [[ $(json_get "$status" account) == true ]]; then
        pass "Google account found in Online Accounts"
        if n=$(probe tasks 2>&1); then pass "Google Tasks answers ($n tasks)"; else fail "Google Tasks: $n"; fi
    else
        warn "no Google account in Settings > Online Accounts: Calendar and Tasks stay empty"
    fi
else
    fail "daemon status unreadable: $status"
fi
for po in "$REPO_ROOT"/po/*.po; do
    lang=$(basename "$po" .po)
    for dir in "$DATA/locale" "$EXT_DIR/locale"; do
        [[ -f $dir/$lang/LC_MESSAGES/google-hub.mo ]] || fail "translation '$lang' missing from $dir (run $REINSTALL)"
    done
done

section "GNOME Shell extension"
if [[ -f $EXT_DIR/metadata.json && -f $EXT_DIR/schemas/gschemas.compiled ]]; then pass "installed in $EXT_DIR"
else fail "not installed (run $REINSTALL)"; fi
if python3 -I "$LIB/enabled_extensions.py" list | grep -qxF "$UUID"; then pass "enabled"
else fail "not enabled: gnome-extensions enable $UUID"; fi
if [[ $(gsettings get org.gnome.shell disable-user-extensions 2>/dev/null) == true ]]; then
    fail "all user extensions are switched off (Extensions app, top switch)"
fi
state=$(probe extension-state "$UUID" 2>/dev/null) || state=''
EXT_ACTIVE=0
case "${state%.0}" in
    1) pass "loaded by the running Shell"; EXT_ACTIVE=1 ;;
    ''|null|6) if ((AFTER_INSTALL)); then warn "not loaded yet: log out and back in"
               else fail "the running Shell has not loaded it: log out and back in"; fi ;;
    3) fail "the Shell reports an error: gnome-extensions info $UUID; journalctl --user -b | grep -A20 'JS ERROR'" ;;
    4) fail "out of date for this GNOME Shell version (gnome-shell --version)" ;;
    *) fail "not active (state ${state%.0}): gnome-extensions info $UUID" ;;
esac
if ((EXT_ACTIVE)) && shell=$(probe shell-state 2>/dev/null); then
    if [[ $(json_get "$shell" tasksInDateMenu) == true ]]; then pass "Tasks section in the clock menu"
    else warn "Tasks section missing from the clock menu"; fi
    if [[ $(json_get "$shell" panelProcess) == true ]]; then
        pass "Gemini drawer process running"
        if [[ $(json_get "$shell" panelLastShow) == *ready* ]]; then pass "Gemini drawer prepared"
        else warn "Gemini drawer not ready yet: $(json_get "$shell" panelLastShow)"; fi
        if [[ $(probe composer 2>/dev/null) == true ]]; then pass "Gemini prompt found (signed in, page selectors current)"
        else warn "Gemini prompt not found: press Super+G and sign in ($DOCS_URL/troubleshooting.md#gemini)"; fi
    else
        warn "Gemini drawer not started yet (it starts with the Shell; check journalctl --user -b | grep google-hub)"
    fi
fi

section "Voice dictation"
server=$(python3 -I -c 'import json, sys
try: print(json.load(open(sys.argv[1])).get("whisper_server") or "whisper-server")
except OSError: print("whisper-server")' "$CONF/config.json")
model=$(python3 -I -c 'import json, sys
try: print(json.load(open(sys.argv[1])).get("whisper_model") or "")
except OSError: print("")' "$CONF/config.json")
model=${model:-$DATA/models/$MODEL_NAME}
VOICE=1
if have "$server"; then pass "speech recogniser: $(command -v "$server")"
else warn "no '$server' program: dictation is off ($DOCS_URL/installation.md#voice-dictation)"; VOICE=0; fi
if [[ -f ${model/#\~/$HOME} ]]; then pass "speech model: $model"
else warn "speech model missing ($model): run $REINSTALL"; VOICE=0; fi
if have wpctl; then
    if source_name=$(wpctl inspect @DEFAULT_AUDIO_SOURCE@ 2>/dev/null | sed -n 's/.*node.description = "\(.*\)"/\1/p') && [[ -n $source_name ]]; then
        pass "microphone: $source_name"
    else warn "no default microphone (Settings > Sound > Input)"; fi
fi
if ((VOICE && ! QUICK)); then
    wav=$REPO_ROOT/daemon/tests/fixtures/speech.wav
    if text=$(probe transcribe "$DATA/daemon" "$wav" 2>&1) && [[ $text != '""' ]]; then pass "transcribes a test recording: $text"
    else fail "test transcription failed: $text"; fi
fi

# A source tree next to the installed copy: they must match (a stale install is the usual cause of odd behaviour).
if [[ -d $REPO_ROOT/daemon/google_hub && $(readlink -f "$REPO_ROOT") != "$(readlink -f "$DATA/source" 2>/dev/null)" ]]; then
    section "Installed copy"
    for pair in "daemon/google_hub:$DATA/daemon/google_hub" "panel/google_hub_panel:$DATA/panel/google_hub_panel" \
        "extension/$UUID:$EXT_DIR"; do
        if diff -rq -x __pycache__ -x gschemas.compiled -x locale "$REPO_ROOT/${pair%%:*}" "${pair#*:}" >/dev/null 2>&1; then
            pass "${pair%%:*} matches this source tree"
        else warn "${pair%%:*} differs from this source tree: run ./install.sh to update"; fi
    done
fi

printf '\n'
if ((FAILS)); then printf '%s%d check(s) failed%s, %d warning(s). See %s/troubleshooting.md\n' "$C_RED" "$FAILS" "$C_OFF" "$WARNS" "$DOCS_URL"
elif ((WARNS)); then printf '%sAll essential checks passed%s, %d warning(s) above.\n' "$C_GREEN" "$C_OFF" "$WARNS"
else printf '%sEverything checks out.%s\n' "$C_GREEN" "$C_OFF"; fi
((FAILS == 0 && (STRICT == 0 || WARNS == 0)))
