#!/usr/bin/env bash
# Installer round trip in a throw-away HOME with fake GNOME tools: dry run, install, reinstall, model download,
# one-line (piped) install, uninstall, purge, distribution detection. Never touches the real home or session:
# HOME is temporary, gsettings/systemctl/gnome-shell/sudo are shims (tests/shims) and the session bus is bogus.
# The model test sources lib/common.sh in a subshell on purpose: its DATA and CONF stay there.
# shellcheck disable=SC2031
set -uo pipefail

TESTS_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(dirname "$TESTS_DIR")
FAILS=0
pass() { printf '  ok    %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*"; FAILS=$((FAILS + 1)); }
check() { local d=$1; shift; if "$@" >/dev/null 2>&1; then pass "$d"; else fail "$d"; fi; }
check_not() { local d=$1; shift; if "$@" >/dev/null 2>&1; then fail "$d"; else pass "$d"; fi; }

T_ROOT=$(mktemp -d "${TMPDIR:-/tmp}/omnishell-test.XXXXXX")
trap 'rm -rf -- "$T_ROOT"' EXIT
export HOME="$T_ROOT/hôme with space" GH_FAKE_DIR="$T_ROOT/fake" NO_COLOR=1
mkdir -p "$HOME" "$GH_FAKE_DIR"
unset XDG_DATA_HOME XDG_CONFIG_HOME XDG_CACHE_HOME XDG_STATE_HOME
export DBUS_SESSION_BUS_ADDRESS="unix:path=$T_ROOT/no-bus" GSETTINGS_BACKEND=memory
export PATH="$TESTS_DIR/shims:/usr/bin:/bin"
[[ $(command -v gsettings) == "$TESTS_DIR/shims/gsettings" ]] || { echo "sandbox PATH leak: gsettings" >&2; exit 2; }
[[ $(command -v systemctl) == "$TESTS_DIR/shims/systemctl" ]] || { echo "sandbox PATH leak: systemctl" >&2; exit 2; }

UUID=omnishell@maximeallanic.github.io
DATA="$HOME/.local/share/omnishell"
EXT="$HOME/.local/share/gnome-shell/extensions/$UUID"
CONF="$HOME/.config/omnishell"
FLAGS=(--no-model --no-deps -y --no-verify)
enabled() { gsettings get org.gnome.shell enabled-extensions | grep -qF "'$UUID'"; }

echo "Dry run"
out=$("$REPO/install.sh" --dry-run "${FLAGS[@]}" 2>&1) || fail "dry run exits 0: $out"
# Only GStreamer's own plugin registry cache may appear: the dependency check asks GStreamer for its elements.
check "dry run creates nothing" test -z "$(find "$HOME" -mindepth 1 -not -path "$HOME/.cache" -not -path "$HOME/.cache/gstreamer-1.0*")"
check "dry run prints the steps" grep -q 'dry run' <<<"$out"

echo "Install"
if out=$("$REPO/install.sh" "${FLAGS[@]}" 2>&1); then pass "install exits 0"; else fail "install exits 0: $out"; fi
check "extension copied" test -f "$EXT/metadata.json"
check "extension schemas compiled" test -f "$EXT/schemas/gschemas.compiled"
check "extension French catalogue" test -f "$EXT/locale/fr/LC_MESSAGES/omnishell.mo"
check "daemon French catalogue" test -f "$DATA/locale/fr/LC_MESSAGES/omnishell.mo"
check "daemon installed" test -f "$DATA/daemon/omnishell/__main__.py"
check "drawer installed" test -f "$DATA/panel/omnishell_panel/__main__.py"
check "no bytecode copied" test -z "$(find "$DATA" "$EXT" -name __pycache__)"
check "config.json is the code's defaults" python3 -c 'import json, sys; c = json.load(open(sys.argv[1])); assert c["whisper_model"] == "" and "summary_hour" in c' "$CONF/config.json"
check "keywords.json installed" test -f "$CONF/keywords.json"
check "systemd unit installed" test -f "$HOME/.config/systemd/user/omnishell-daemon.service"
check "unit points at the installed daemon" grep -qxF "Environment=\"PYTHONPATH=$DATA/daemon\"" "$HOME/.config/systemd/user/omnishell-daemon.service"
check "D-Bus activation file installed" test -f "$HOME/.local/share/dbus-1/services/io.github.maximeallanic.Omnishell.service"
check "launcher installed" test -f "$HOME/.local/share/applications/io.github.maximeallanic.OmnishellPanel.desktop"
check "icon installed" test -f "$HOME/.local/share/icons/hicolor/symbolic/apps/omnishell-gemini-symbolic.svg"
check "extension enabled" enabled
check "service enabled and restarted" grep -q 'restart omnishell-daemon.service' "$GH_FAKE_DIR/systemctl.log"
check "release copy kept for uninstall/verify" test -x "$DATA/source/uninstall.sh"
check_not "release copy has no screenshots" test -e "$DATA/source/screenshots"
check_not "no sudo call" test -e "$GH_FAKE_DIR/sudo.log"
check_not "nothing written outside HOME's XDG folders" test -e "$HOME/omnishell"

echo "Reinstall keeps user settings"
echo '{"whisper_language": "ja"}' >"$CONF/config.json"
out=$("$REPO/install.sh" "${FLAGS[@]}" 2>&1) || fail "reinstall exits 0: $out"
check "config.json kept" grep -q '"ja"' "$CONF/config.json"
check "UUID listed once" test "$(gsettings get org.gnome.shell enabled-extensions | grep -o "$UUID" | wc -l)" = 1

echo "Model download"
model_test() { # sha1 -> exit status of step_model with a local file as the model URL
    (
        REPO_ROOT=$REPO
        # shellcheck source=lib/common.sh
        source "$REPO/lib/common.sh"
        # shellcheck source=lib/steps.sh
        source "$REPO/lib/steps.sh"
        ASSUME_YES=1
        MODEL_URL="file://$T_ROOT/fake-model.bin"
        MODEL_SHA1=$1
        step_model
    )
}
head -c 4096 /dev/urandom >"$T_ROOT/fake-model.bin"
good=$(sha1sum "$T_ROOT/fake-model.bin" | cut -d' ' -f1)
check_not "wrong checksum is refused" model_test 0000000000000000000000000000000000000000
check_not "refused download deleted" test -e "$DATA/models/ggml-small.bin.part"
check "right checksum is accepted" model_test "$good"
check "model in place" cmp "$T_ROOT/fake-model.bin" "$DATA/models/ggml-small.bin"

echo "Uninstall"
out=$("$DATA/source/uninstall.sh" -y 2>&1) || fail "uninstall exits 0: $out"
check_not "extension removed" test -e "$EXT"
check_not "daemon removed" test -e "$DATA/daemon"
check_not "unit removed" test -e "$HOME/.config/systemd/user/omnishell-daemon.service"
check_not "extension disabled" enabled
check_not "release copy removed" test -e "$DATA/source"
check "settings kept" test -f "$CONF/config.json"
check "model kept" test -f "$DATA/models/ggml-small.bin"

echo "One-line install (piped into bash, from a pinned release tarball)"
# piped PIN URL [PROTOCOLS]: install.sh fed to bash through a pipe, as by curl | bash, with the pin and the download URL
# replaced. PROTOCOLS widens curl's protocol list so that a local file:// stands for the GitHub release; left empty,
# the installer keeps its own HTTPS-only list.
piped() {
    sed -e "s|^RELEASE_SHA256=.*|RELEASE_SHA256='$1'|" -e "s|^RELEASE_URL=.*|RELEASE_URL='$2'|" \
        -e "s|--proto '=https'|--proto '=${3:-https}'|" "$REPO/install.sh" | bash -s -- "${FLAGS[@]}"
}
no_download_left() { ! compgen -G "$HOME/.cache/omnishell/bootstrap.*" >/dev/null; }
for line in "^RELEASE_SHA256=" "^RELEASE_URL=" "--proto '=https' "; do
    check "install.sh has the '$line' the piped tests replace" grep -q -- "$line" "$REPO/install.sh"
done
# The pin is emptied here, as scripts/release.sh does in the tarball: the test does not depend on whether the checkout
# is a release commit.
out=$(piped '' https://example.invalid/none.tar.gz 2>&1)
check_not "piped install refuses without a pinned release" test $? = 0
check "the refusal says no release is pinned" grep -q "no release of Omnishell is pinned" <<<"$out"
check "the refusal gives the clone command" grep -q "git clone" <<<"$out"
check_not "nothing downloaded without a pin" grep -q Downloading <<<"$out"
tar -C "$(dirname "$REPO")" --exclude=.git --exclude=__pycache__ --transform "s|^$(basename "$REPO")|omnishell-$(sed -n 's/^OMNISHELL_VERSION=//p' "$REPO/lib/common.sh")|" \
    -czf "$T_ROOT/release.tar.gz" "$(basename "$REPO")"
sum=$(sha256sum "$T_ROOT/release.tar.gz" | cut -d' ' -f1)
if out=$(piped "$sum" "file://$T_ROOT/release.tar.gz" https,file 2>&1); then pass "piped install exits 0"
else fail "piped install exits 0: $out"; fi
check "piped install installed the extension" test -f "$EXT/metadata.json"
check "piped install kept the release copy" test -x "$DATA/source/uninstall.sh"
check "piped install removed its download" no_download_left
cp "$T_ROOT/release.tar.gz" "$T_ROOT/tampered.tar.gz"
printf 'x' >>"$T_ROOT/tampered.tar.gz"
"$DATA/source/uninstall.sh" -y >/dev/null 2>&1 || fail "uninstall before the tampered test"
out=$(piped "$sum" "file://$T_ROOT/tampered.tar.gz" https,file 2>&1)
check_not "a tampered release is refused" test $? = 0
check "the refusal names the checksum" grep -q "does not match the pinned sha256" <<<"$out"
check_not "nothing installed from a tampered release" test -e "$EXT/metadata.json"
check "the refused download was removed" no_download_left
out=$(piped "$sum" "file://$T_ROOT/release.tar.gz" 2>&1)
check_not "a non-HTTPS URL is refused" test $? = 0
check_not "nothing installed from a non-HTTPS URL" test -e "$EXT/metadata.json"
check "the refused download was removed" no_download_left
out=$(piped "$sum" "file://$T_ROOT/release.tar.gz" https,file 2>&1) || fail "piped reinstall exits 0: $out"

echo "Purge"
out=$("$DATA/source/uninstall.sh" -y --purge 2>&1) || fail "purge exits 0: $out"
check_not "settings purged" test -e "$CONF"
check_not "data folder purged" test -e "$DATA"

echo "Custom XDG_DATA_HOME (with a space and a percent sign)"
xdg="$HOME/my data/50%"
if out=$(XDG_DATA_HOME="$xdg" "$REPO/install.sh" "${FLAGS[@]}" 2>&1); then pass "install exits 0"
else fail "install exits 0: $out"; fi
check "daemon under XDG_DATA_HOME" test -f "$xdg/omnishell/daemon/omnishell/__main__.py"
check "extension under XDG_DATA_HOME" test -f "$xdg/gnome-shell/extensions/$UUID/metadata.json"
check "unit names that daemon, % escaped" grep -qxF "Environment=\"PYTHONPATH=$HOME/my data/50%%/omnishell/daemon\"" \
    "$HOME/.config/systemd/user/omnishell-daemon.service"
out=$(XDG_DATA_HOME="$xdg" "$xdg/omnishell/source/uninstall.sh" -y --purge 2>&1) || fail "uninstall exits 0: $out"
check_not "nothing left under XDG_DATA_HOME" test -e "$xdg/omnishell"
check_not "unit removed" test -e "$HOME/.config/systemd/user/omnishell-daemon.service"

echo "Distribution detection"
# shellcheck source=lib/common.sh
source "$REPO/lib/common.sh"
# shellcheck source=lib/deps.sh
source "$REPO/lib/deps.sh"
family() { printf '%s\n' "$1" >"$T_ROOT/os-release"; OS_RELEASE="$T_ROOT/os-release" distro_family; }
check "Debian" test "$(family 'ID=debian')" = debian
check "Ubuntu" test "$(family $'ID=ubuntu\nID_LIKE=debian')" = debian
check "Linux Mint (ID_LIKE)" test "$(family $'ID=linuxmint\nID_LIKE="ubuntu debian"')" = debian
check "Fedora" test "$(family 'ID=fedora')" = fedora
check "Arch" test "$(family 'ID=arch')" = arch
check "EndeavourOS (ID_LIKE)" test "$(family $'ID=endeavouros\nID_LIKE=arch')" = arch
check "openSUSE is reported unsupported" test "$(family $'ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"')" = unsupported
check "Fedora has no whisper-server package" test "$(pkg_for fedora cmd:whisper-server)" = -
if command -v apt-cache >/dev/null; then
    check_not "a package the repositories lack is reported, not installed" pkg_available debian omnishell-no-such-package
    check "a package the repositories have is offered" pkg_available debian coreutils
fi
check "every row has five fields" test -z "$(printf '%s' "$DEP_TABLE" | sed '/^$/d' | awk -F'|' 'NF != 5')"

echo
if ((FAILS)); then echo "$FAILS check(s) failed"; exit 1; fi
echo "Installer round trip: all checks passed"
