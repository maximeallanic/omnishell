#!/usr/bin/env bash
# Google Hub installer: Google search, Gemini, local voice dictation, Calendar and Tasks in GNOME Shell.
# Runs as your user (never as root), changes only your home directory, is idempotent and reversible (./uninstall.sh).
#
#   curl -fsSL https://raw.githubusercontent.com/maximeallanic/gnome-google-hub/main/install.sh | bash
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
#   --uninstall          remove Google Hub (same as ./uninstall.sh)
#   --version, -h, --help
#
# One-line install: GOOGLE_HUB_REF picks the release tag or branch to download (default: the pinned release),
# GOOGLE_HUB_TARBALL a tarball URL or local file to install from instead.
set -euo pipefail

PINNED_RELEASE=v0.1.0
REPO_URL=https://github.com/maximeallanic/gnome-google-hub

# Piped into bash (curl … | bash) there is no source tree next to this script: download the release and run its
# installer. The whole function is read before it runs, so the rest of the pipe does not matter.
bootstrap() {
    local self=${BASH_SOURCE[0]:-} ref=${GOOGLE_HUB_REF:-$PINNED_RELEASE} src dir
    if [[ -n $self && -f $self && -f $(dirname -- "$self")/lib/common.sh ]]; then return 0; fi
    [[ $(id -u) != 0 ]] || { echo "error: run this as your normal user, not as root (sudo is asked for when needed)" >&2; exit 1; }
    if ! command -v curl >/dev/null || ! command -v tar >/dev/null; then echo "error: curl and tar are needed" >&2; exit 1; fi
    src=${GOOGLE_HUB_TARBALL:-$REPO_URL/archive/$ref.tar.gz}
    dir=${XDG_CACHE_HOME:-$HOME/.cache}/google-hub/bootstrap
    rm -rf -- "$dir"
    mkdir -p -- "$dir"
    echo "==> Downloading Google Hub ($ref)"
    if [[ -f $src ]]; then tar -xzf "$src" -C "$dir" --strip-components=1
    else curl -fsSL "$src" | tar -xz -C "$dir" --strip-components=1; fi
    [[ -f $dir/install.sh && -f $dir/lib/common.sh ]] || { echo "error: $src is not a Google Hub source archive" >&2; exit 1; }
    exec bash "$dir/install.sh" "$@"
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
        --version) echo "google-hub $GOOGLE_HUB_VERSION"; exit 0 ;;
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
    ((${#MISSING_CHECKS[@]} == 0)) || die "still missing, Google Hub cannot run without: ${MISSING_CHECKS[*]#*:}"
    check_deps "$FAMILY" voice
    if ((${#MISSING_CHECKS[@]})); then VOICE_READY=0; msg_warn "dictation will be unavailable (missing: ${MISSING_CHECKS[*]#*:})"; fi
}

FAMILY=unsupported
VOICE_READY=1
printf '%sGoogle Hub %s%s installer\n' "$C_BOLD" "$GOOGLE_HUB_VERSION" "$C_OFF"
((DRY_RUN)) && msg_info "dry run: nothing is changed"
preflight
step_deps
if ((WANT_MODEL && VOICE_READY)); then step_model
elif ((WANT_MODEL)); then msg_info "Speech model skipped: dictation is unavailable on this system for now"; fi
step_files
step_service
step_extension
step_source_copy

cat <<EOF

${C_BOLD}Google Hub is installed.${C_OFF} Next:
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
