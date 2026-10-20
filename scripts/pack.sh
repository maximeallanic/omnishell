#!/usr/bin/env bash
# Build the extension zip for extensions.gnome.org with `gnome-extensions pack`: dist/<uuid>.shell-extension.zip.
#
#   scripts/pack.sh [--out DIR]
#
# The zip holds the GNOME Shell extension only. The search results, Calendar, Tasks and dictation come from the
# Python daemon and the Gemini drawer from a Python/WebKit program, which install.sh puts in place: see
# docs/development.md#extensionsgnomeorg before uploading.
set -euo pipefail
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
UUID=omnishell@maximeallanic.github.io
SRC=$REPO_ROOT/extension/$UUID
out=$REPO_ROOT/dist
die() { echo "error: $*" >&2; exit 1; }
while (($#)); do
    case "$1" in
        --out) [[ $# -ge 2 ]] || die "--out needs a directory"; out=$2; shift ;;
        -h|--help) sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) die "unknown argument: $1" ;;
    esac
    shift
done
command -v gnome-extensions >/dev/null || die "gnome-extensions is required (package gnome-shell)"
mkdir -p "$out"
out=$(cd "$out" && pwd)

args=(--force --quiet --out-dir "$out" --podir "$REPO_ROOT/po" --gettext-domain omnishell
      --schema "$SRC/schemas/org.gnome.shell.extensions.omnishell.gschema.xml")
# Everything else of the extension folder: modules, icons, the vendored M3E motion toolkit.
while IFS= read -r entry; do
    case "$entry" in
        extension.js|metadata.json|prefs.js|stylesheet.css|schemas|locale|po) ;;
        *) args+=("--extra-source=$SRC/$entry") ;;
    esac
done < <(find "$SRC" -mindepth 1 -maxdepth 1 ! -name '__pycache__' ! -name '*.compiled' -printf '%f\n' | sort)
gnome-extensions pack "${args[@]}" "$SRC"
zip=$out/$UUID.shell-extension.zip
[[ -f $zip ]] || die "expected $zip was not produced"
echo "packed $zip"
