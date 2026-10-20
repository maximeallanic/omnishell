# shellcheck shell=bash
# Dependency detection and per-distribution package names. Nothing is installed unless --install-deps is given,
# and then only after confirmation. Requires common.sh.
#
# Each row: check | apt (Debian, Ubuntu) | dnf (Fedora) | pacman (Arch) | need
#   check:  cmd:NAME (a command on PATH), py:MODULE (a Python module), gir:NS-VER (a GObject typelib),
#           gst:ELEMENT (a GStreamer element)
#   need:   core (search, tasks, calendar), panel (Gemini drawer), voice (dictation)
#   '-' means the distribution packages nothing that provides it.
DEP_TABLE='
cmd:python3|python3|python3|python|core
cmd:curl|curl|curl|curl|core
cmd:sha1sum|coreutils|coreutils|coreutils|core
cmd:gdbus|libglib2.0-bin|glib2|glib2|core
cmd:glib-compile-schemas|libglib2.0-bin|glib2|glib2|core
cmd:gnome-extensions|gnome-shell|gnome-shell|gnome-shell|core
cmd:msgfmt|gettext|gettext|gettext|core
py:gi|python3-gi|python3-gobject|python-gobject|core
gir:GLibUnix-2.0|gir1.2-glib-2.0|glib2|glib2|core
py:dateparser|python3-dateparser|python3-dateparser|python-dateparser|core
py:babel|python3-babel|python3-babel|python-babel|core
gir:Gtk-4.0|gir1.2-gtk-4.0|gtk4|gtk4|panel
gir:Adw-1|gir1.2-adw-1|libadwaita|libadwaita|panel
gir:WebKit-6.0|gir1.2-webkit-6.0|webkitgtk6.0|webkitgtk-6.0|panel
gir:Gst-1.0|gir1.2-gstreamer-1.0|gstreamer1|gstreamer|voice
gir:GstApp-1.0|gir1.2-gst-plugins-base-1.0|gstreamer1-plugins-base|gst-plugins-base-libs|voice
gst:audioconvert|gstreamer1.0-plugins-base|gstreamer1-plugins-base|gst-plugins-base|voice
gst:pipewiresrc|gstreamer1.0-pipewire|pipewire-gstreamer|gst-plugin-pipewire|voice
cmd:whisper-server|whisper.cpp-tools|-|whisper-cpp|voice
'
# Optional GPU backend for whisper.cpp (--vulkan). Only Debian and Ubuntu split it into its own package.
# shellcheck disable=SC2034  # used by install.sh
VULKAN_PKG_DEBIAN=libggml0-backend-vulkan

# Package family from /etc/os-release (ID, then ID_LIKE): debian, fedora, arch, or unsupported.
# OS_RELEASE lets the tests point at a fixture.
distro_family() {
    local file=${OS_RELEASE:-/etc/os-release} id='' like='' word
    [[ -r $file ]] || { echo unsupported; return; }
    id=$(sed -n 's/^ID=//p' "$file" | tr -d '"')
    like=$(sed -n 's/^ID_LIKE=//p' "$file" | tr -d '"')
    for word in $id $like; do
        case "$word" in
            debian|ubuntu) echo debian; return ;;
            fedora) echo fedora; return ;;
            arch) echo arch; return ;;
        esac
    done
    echo unsupported
}

distro_name() {
    local file=${OS_RELEASE:-/etc/os-release}
    [[ -r $file ]] && sed -n 's/^PRETTY_NAME=//p' "$file" | tr -d '"' || echo 'unknown system'
}

# dep_present CHECK: 0 when the system already provides it.
dep_present() {
    local kind=${1%%:*} what=${1#*:}
    case "$kind" in
        cmd) have "$what" ;;
        py) python3 -c "import $what" >/dev/null 2>&1 ;;
        gir) python3 - "${what%-*}" "${what##*-}" >/dev/null 2>&1 <<'PY'
import sys, gi
gi.require_version(sys.argv[1], sys.argv[2])
__import__("gi.repository." + sys.argv[1])
PY
        ;;
        gst) have gst-inspect-1.0 && gst-inspect-1.0 --exists "$what" >/dev/null 2>&1 && return 0
             python3 - "$what" >/dev/null 2>&1 <<'PY'
import sys, gi
gi.require_version("Gst", "1.0")
from gi.repository import Gst
Gst.init(None)
sys.exit(Gst.ElementFactory.find(sys.argv[1]) is None)
PY
        ;;
        *) return 1 ;;
    esac
}

# pkg_for FAMILY CHECK -> package name, '-' when the family has none, '' when the family is unknown.
pkg_for() {
    local family=$1 check=$2 col c p
    case "$family" in debian) col=2 ;; fedora) col=3 ;; arch) col=4 ;; *) return 0 ;; esac
    while IFS='|' read -r c p; do
        [[ $c == "$check" ]] && { printf '%s\n' "$p"; return 0; }
    done < <(printf '%s' "$DEP_TABLE" | sed '/^$/d' | cut -d'|' -f1,"$col")
}

# deps_rows NEED...: the table rows whose need is one of NEED.
deps_rows() {
    local row need
    while IFS= read -r row; do
        [[ -z $row ]] && continue
        for need in "$@"; do
            [[ ${row##*|} == "$need" ]] && { printf '%s\n' "$row"; break; }
        done
    done <<<"$DEP_TABLE"
}

install_cmd() { # family assume-yes packages... -> the command, one word per line
    local family=$1 yes=$2 flags=()
    shift 2
    case "$family" in
        debian) ((yes)) && flags=(-y); printf '%s\n' sudo apt-get install --no-install-recommends "${flags[@]}" "$@" ;;
        fedora) ((yes)) && flags=(-y); printf '%s\n' sudo dnf install "${flags[@]}" "$@" ;;
        arch) ((yes)) && flags=(--noconfirm); printf '%s\n' sudo pacman -S --needed "${flags[@]}" "$@" ;;
    esac
}

# pkg_available FAMILY PACKAGE: 0 when the configured repositories offer it (or when the package tool is not
# there to ask). Releases differ: whisper.cpp-tools, for instance, is in Debian testing but not in every Ubuntu.
pkg_available() {
    case "$1" in
        debian) have apt-cache || return 0
                # Read whole (no grep -q in a pipe: an early exit would be a SIGPIPE failure under pipefail).
                [[ $(apt-cache policy -- "$2" 2>/dev/null) =~ Candidate:\ [^\(] ]] ;;
        fedora) have dnf || return 0; dnf -q info -- "$2" >/dev/null 2>&1 ;;
        arch) have pacman || return 0; pacman -Si -- "$2" >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}

MISSING_CHECKS=()     # every check that failed
MISSING_PACKAGES=()   # the packages that provide them on this family
UNPACKAGED=()         # failed checks no package of this system provides

# check_deps FAMILY NEED...: fills the three arrays above.
check_deps() {
    local family=$1 row check pkg
    shift
    MISSING_CHECKS=() MISSING_PACKAGES=() UNPACKAGED=()
    while IFS= read -r row; do
        check=${row%%|*}
        dep_present "$check" && continue
        MISSING_CHECKS+=("$check")
        pkg=$(pkg_for "$family" "$check")
        if [[ -z $pkg || $pkg == - ]] || ! pkg_available "$family" "$pkg"; then UNPACKAGED+=("$check")
        elif [[ " ${MISSING_PACKAGES[*]} " != *" $pkg "* ]]; then MISSING_PACKAGES+=("$pkg"); fi
    done < <(deps_rows "$@")
}

# dep_consequence NEED: what a missing dependency of that need costs the user, in one line.
dep_consequence() {
    case "$1" in
        voice) echo 'voice dictation will not work' ;;
        panel) echo 'the Gemini drawer will not open' ;;
        *) echo 'Google Hub cannot run' ;;
    esac
}
