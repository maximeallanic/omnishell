#!/usr/bin/env bash
# Regenerate po/google-hub.pot from the sources listed in po/POTFILES and merge it into every po/*.po.
#
#   scripts/update-po.sh [--check]
#
# --check changes nothing: it fails when a translatable string of the sources is missing from a catalogue, when a
# catalogue has untranslated or fuzzy entries, or when a source file using gettext is not in POTFILES. Only _() and
# ngettext() are extracted: GLib.dgettext("glib20", ...) borrows GLib's own translations on purpose.
set -euo pipefail
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"
CHECK=0
ISSUES=https://github.com/maximeallanic/gnome-google-hub/issues
[[ ${1:-} == --check ]] && CHECK=1
for tool in xgettext msgmerge msgfmt msgcmp; do
    command -v "$tool" >/dev/null || { echo "error: $tool is required (package gettext)" >&2; exit 1; }
done

pot() { # OUT: template from POTFILES (Python and JavaScript sources)
    local py=() js=() f
    while IFS= read -r f; do
        [[ -z $f || $f == \#* ]] && continue
        case "$f" in *.py) py+=("$f") ;; *.js) js+=("$f") ;; esac
    done <po/POTFILES
    local opts=(--from-code=UTF-8 --add-comments=Translators: --add-location=file --package-name=google-hub
                --copyright-holder="Maxime Allanic" --msgid-bugs-address="$ISSUES" -k -k_ "-kngettext:1,2")
    xgettext "${opts[@]}" -o "$1" -L Python "${py[@]}"
    xgettext "${opts[@]}" -j -o "$1" -L JavaScript "${js[@]}"
}

if ((CHECK)); then
    fails=0
    tmp=$(mktemp -d)
    trap 'rm -rf -- "$tmp"' EXIT
    pot "$tmp/google-hub.pot"
    # Every file that calls gettext must be listed, or its strings silently stay English.
    while IFS= read -r f; do
        grep -qxF "$f" po/POTFILES || { echo "not in po/POTFILES: $f"; fails=1; }
    done < <(grep -lE '(^|[^A-Za-z0-9_.])(_|ngettext)\(' -r daemon/google_hub panel/google_hub_panel extension/*/ \
             --include='*.py' --include='*.js' | sed 's|//|/|g' | sort)
    for po in po/*.po; do
        msgcmp "$po" "$tmp/google-hub.pot" || { echo "$po: strings missing (run scripts/update-po.sh)"; fails=1; }
        stats=$(LC_ALL=C msgfmt --check --statistics -o /dev/null "$po" 2>&1)
        [[ $stats == *untranslated* || $stats == *fuzzy* ]] && { echo "$po: $stats"; fails=1; }
    done
    ((fails == 0)) && echo "translations: complete"
    exit "$fails"
fi

pot po/google-hub.pot
for po in po/*.po; do
    msgmerge --quiet --update --backup=none --no-fuzzy-matching "$po" po/google-hub.pot
    echo "updated $po"
done
