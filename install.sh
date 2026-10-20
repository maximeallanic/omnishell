#!/usr/bin/env bash
# Omnishell installer: Google search, Gemini, local voice dictation, Calendar and Tasks in GNOME Shell.
# Runs as your user (never as root), changes only your home directory, is idempotent and reversible (./uninstall.sh).
#
#   curl -fsSL https://raw.githubusercontent.com/maximeallanic/omnishell/main/install.sh | bash
#   ./install.sh [options]
#
# Options:
#   --dry-run            print what would be done, change nothing
#   -y, --yes            answer yes to every question (dependencies, model download)
#   --install-deps       install missing system packages with sudo without asking
#   --no-deps            never install system packages (only report what is missing)
#   --no-model           do not download the Whisper speech model (dictation stays off)
#   --vulkan             also install whisper.cpp's Vulkan GPU backend (Debian and Ubuntu)
#   --no-session-check   install without a running GNOME session (the service and extension start at next login)
#   --no-verify          do not run ./verify.sh at the end
#   --uninstall          remove Omnishell (same as ./uninstall.sh)
#   --version, -h, --help
#
# One-line install: the script downloads the release pinned below over HTTPS, checks its sha256 before unpacking it,
# and runs that release's installer. While no release is pinned it refuses and points to a clone instead.
set -euo pipefail

# Pinned release fetched by the one-line install. scripts/release.sh fills both values when a release is cut.
RELEASE_VERSION=0.1.0
RELEASE_SHA256=''
RELEASE_URL="https://github.com/maximeallanic/omnishell/releases/download/v${RELEASE_VERSION}/omnishell-${RELEASE_VERSION}.tar.gz"
REPO_URL=https://github.com/maximeallanic/omnishell

# Piped into bash (curl … | bash) there is no source tree next to this script: download the pinned release, check it
# and run its installer, which keeps its own copy in ~/.local/share/omnishell/source. The download directory is
# removed on every exit path. The function ends with exit, so the rest of the pipe is never run.
bootstrap() {
    local self=${BASH_SOURCE[0]:-} tool cache tmp rc=0
    if [[ -n $self && -f $self && -f $(dirname -- "$self")/lib/common.sh ]]; then return 0; fi
    [[ $(id -u) != 0 ]] || { echo "error: run this as your normal user, not as root (sudo is asked for when needed)" >&2; exit 1; }
    if [[ -z $RELEASE_SHA256 ]]; then
        echo "error: no release of Omnishell is pinned in this installer yet." >&2
        echo "       Use a clone instead: git clone $REPO_URL && omnishell/install.sh" >&2
        exit 1
    fi
    for tool in curl tar sha256sum; do
        command -v "$tool" >/dev/null || { echo "error: $tool is needed" >&2; exit 1; }
    done
    cache=${XDG_CACHE_HOME:-$HOME/.cache}/omnishell
    mkdir -p -- "$cache"
    # Global, not local: the EXIT trap runs after this function has returned.
    BOOTSTRAP_TMP=$(mktemp -d "$cache/bootstrap.XXXXXX")
    trap 'rm -rf -- "$BOOTSTRAP_TMP"' EXIT
    tmp=$BOOTSTRAP_TMP
    echo "==> Downloading Omnishell $RELEASE_VERSION"
    curl -fsSL --proto '=https' --proto-redir '=https' --tlsv1.2 -o "$tmp/release.tar.gz" "$RELEASE_URL"
    echo "$RELEASE_SHA256  $tmp/release.tar.gz" | sha256sum --check --status \
        || { echo "error: the download does not match the pinned sha256; nothing was installed." >&2; exit 1; }
    mkdir -- "$tmp/src"
    tar -xzf "$tmp/release.tar.gz" -C "$tmp/src" --strip-components=1 --no-same-owner
    [[ -f $tmp/src/install.sh && -f $tmp/src/lib/common.sh ]] || { echo "error: the release is not a Omnishell source archive" >&2; exit 1; }
    bash "$tmp/src/install.sh" "$@" || rc=$?
    exit "$rc"
}
bootstrap "$@"

REPO_ROOT=$(dirname -- "$(readlink -f -- "${BASH_SOURCE[0]}")")
LIB=$REPO_ROOT/lib
# shellcheck source=lib/common.sh
source "$LIB/common.sh"
# shellcheck source=lib/deps.sh
source "$LIB/deps.sh"
# shellcheck source=lib/steps.sh
source "$LIB/steps.sh"

INSTALL_DEPS=ask
WANT_MODEL=1
WANT_VULKAN=0
SESSION_CHECK=1
RUN_VERIFY=1
usage() { sed -n '2,/^set -e/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; }
while (($#)); do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        -y|--yes) ASSUME_YES=1 ;;
        --install-deps) INSTALL_DEPS=yes ;;
        --no-deps) INSTALL_DEPS=no ;;
        --no-model) WANT_MODEL=0 ;;
        --vulkan) WANT_VULKAN=1 ;;
        --no-session-check) SESSION_CHECK=0 ;;
        --no-verify) RUN_VERIFY=0 ;;
        --uninstall) shift; exec "$REPO_ROOT/uninstall.sh" "$@" ;;
        --version) echo "omnishell $OMNISHELL_VERSION"; exit 0 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done

preflight() {
    local major
    msg_step "Checking this system"
    [[ $(id -u) != 0 ]] || die "run the installer as your normal user, not as root (it asks for sudo when it needs it)"
    FAMILY=$(distro_family)
    case "$FAMILY" in
        debian|fedora|arch) msg_ok "$(distro_name) ($FAMILY packages)" ;;
        *) msg_warn "$(distro_name): no package list for this distribution; install the dependencies yourself"
           msg_info "List: $DOCS_URL/installation.md#dependencies" ;;
    esac
    major=$(shell_major)
    case "$major" in
        50|51) msg_ok "GNOME Shell $major" ;;
        '') msg_warn "GNOME Shell not found: the extension needs GNOME Shell 50 or 51" ;;
        *) msg_warn "GNOME Shell $major: this release is tested with 50 and 51 only; the extension may refuse to load" ;;
    esac
    if ((SESSION_CHECK)) && ! session_ready; then
        die "no graphical session found: run this from a terminal inside your GNOME session (or pass --no-session-check)"
    fi
}

step_deps() {
    local needs=(core panel voice) cmd=() row check
    msg_step "Dependencies"
    check_deps "$FAMILY" "${needs[@]}"
    if ((WANT_VULKAN)); then
        if [[ $FAMILY == debian ]]; then MISSING_PACKAGES+=("$VULKAN_PKG_DEBIAN")
        else msg_warn "--vulkan: only Debian and Ubuntu package the Vulkan backend separately; skipped"; fi
    fi
    if ((${#MISSING_CHECKS[@]} == 0 && ${#MISSING_PACKAGES[@]} == 0)); then msg_ok "everything needed is installed"; return 0; fi
    for check in "${MISSING_CHECKS[@]}"; do
        row=$(deps_rows core panel voice | grep -F "$check|")
        msg_warn "missing ${check#*:} (${check%%:*}): $(dep_consequence "${row##*|}")"
    done
    if ((${#MISSING_PACKAGES[@]})); then
        mapfile -t cmd < <(install_cmd "$FAMILY" "$ASSUME_YES" "${MISSING_PACKAGES[@]}")
        msg_info "To install: ${cmd[*]}"
        case "$INSTALL_DEPS" in
            no) msg_warn "--no-deps: not installing them" ;;
            yes) run "${cmd[@]}" || die "package installation failed" ;;
            ask) if ask "Install these packages now with sudo?" y; then run "${cmd[@]}" || die "package installation failed"
                 else msg_warn "not installing them"; fi ;;
        esac
    fi
    for check in "${UNPACKAGED[@]}"; do
        case "$check" in
            cmd:whisper-server)
                msg_warn "$(distro_name) has no whisper-server package: dictation needs whisper.cpp built from source"
                msg_info "How: $DOCS_URL/installation.md#dictation-without-a-whisper-server-package" ;;
            *) msg_warn "no package for ${check#*:} on $(distro_name): see $DOCS_URL/installation.md" ;;
        esac
    done
    ((DRY_RUN)) && return 0
    # What is still missing after the installation decides how far we can go.
    check_deps "$FAMILY" core
    ((${#MISSING_CHECKS[@]} == 0)) || die "still missing, Omnishell cannot run without: ${MISSING_CHECKS[*]#*:}"
    check_deps "$FAMILY" voice
    if ((${#MISSING_CHECKS[@]})); then VOICE_READY=0; msg_warn "dictation will be unavailable (missing: ${MISSING_CHECKS[*]#*:})"; fi
}

FAMILY=unsupported
VOICE_READY=1
printf '%sOmnishell %s%s installer\n' "$C_BOLD" "$OMNISHELL_VERSION" "$C_OFF"
((DRY_RUN)) && msg_info "dry run: nothing is changed"
preflight
step_deps
if ((WANT_MODEL && VOICE_READY)); then step_model
elif ((WANT_MODEL)); then msg_info "Speech model skipped: dictation is unavailable on this system for now"; fi
step_files
# The extension first: the daemon reads its search-suggestions key from the compiled schema when it starts.
step_extension
step_service
step_source_copy

cat <<EOF

${C_BOLD}Omnishell is installed.${C_OFF} Next:
  1. Log out and back in, so GNOME Shell loads the extension (Wayland cannot reload the Shell in place).
  2. Settings > Online Accounts > Google, with Calendar enabled, for Calendar and Tasks.
  3. Press Super+G and sign in to Gemini in the drawer once.
  4. Check everything again any time: $DATA/source/verify.sh
Uninstall: $DATA/source/uninstall.sh
EOF

if ((RUN_VERIFY && ! DRY_RUN && SESSION_CHECK)); then
    msg_step "Verification"
    "$REPO_ROOT/verify.sh" --after-install || true
fi
