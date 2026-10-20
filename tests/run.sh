#!/usr/bin/env bash
# Every headless test: static checks, daemon, extension logic, Gemini drawer, installer round trip.
#
#   tests/run.sh [--nested]
#
# A suite whose tool is missing is reported as SKIP (the CI installs all of them); --nested also runs the extension
# in a nested, headless GNOME Shell (extension/tests/nested/run.sh, needs gnome-shell 50 or 51 and a free machine).
set -uo pipefail
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO" || exit 2
NESTED=0
[[ ${1:-} == --nested ]] && NESTED=1
RESULTS=()
FAILED=0

suite() { # NAME COMMAND...: runs a suite, records PASS or FAIL
    local name=$1; shift
    printf '\n=== %s\n' "$name"
    if "$@"; then RESULTS+=("PASS  $name"); else RESULTS+=("FAIL  $name"); FAILED=1; fi
}
skip() { printf '\n=== %s\n%s\n' "$1" "$2"; RESULTS+=("SKIP  $1 ($2)"); }
have() { command -v "$1" >/dev/null 2>&1; }

# shellcheck disable=SC2329  # called through suite()
run_shellcheck() {
    local files
    mapfile -t files < <(git ls-files -co --exclude-standard '*.sh' 2>/dev/null || find . -name '*.sh' -not -path './.git/*')
    shellcheck -x "${files[@]}" tests/shims/*
}
if have shellcheck; then suite "ShellCheck" run_shellcheck
else skip "ShellCheck" "shellcheck missing"; fi

suite "File sizes" python3 tests/check_sizes.py
if have xgettext && have msgcmp; then suite "Translations" scripts/update-po.sh --check
else skip "Translations" "gettext missing"; fi

suite "Daemon unit tests" bash -c 'cd daemon && python3 -m unittest discover -s tests -t . 2>&1'

if have gjs; then
    suite "Extension logic (gjs)" bash -c 'cd extension && gjs -m tests/test_logic.js && gjs -m tests/test_async.js'
else skip "Extension logic (gjs)" "gjs missing"; fi

if have weston && python3 -c 'import gi; gi.require_version("WebKit", "6.0"); from gi.repository import WebKit' 2>/dev/null; then
    suite "Gemini drawer (headless weston)" panel/tests/run.sh
else skip "Gemini drawer (headless weston)" "weston or WebKitGTK 6 for Python missing"; fi

suite "Installer round trip" tests/roundtrip.sh

if ((NESTED)); then suite "Nested GNOME Shell" extension/tests/nested/run.sh
else skip "Nested GNOME Shell" "pass --nested to run it"; fi

printf '\n=== Summary\n'
printf '  %s\n' "${RESULTS[@]}"
exit "$FAILED"
