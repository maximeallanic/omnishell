#!/usr/bin/env bash
# Nested check of the Gemini drawer: the real extension and the real drawer in an isolated headless Shell
# (nested.sh: private bus, private XDG folders), the drawer loading a local page whose load the driver holds and
# releases (server.py). Never touches the live session or the Gemini profile.
# Usage: run.sh [--out DIR] [--url URL]
#   --url   page loaded by the drawer instead of the held local page (measurements; the profile stays private)
# Exit: nested.sh's codes (0 ok, 1 failure, 2 refusal or lock held, 3/4 guards).
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT='' URL=''
while (($#)); do
    case "$1" in
        --out) OUT=${2:?directory}; shift 2 ;;
        --url) URL=${2:?url}; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
[[ -n $OUT ]] || OUT=$(mktemp -d "${TMPDIR:-/tmp}/omnishell-nested.XXXXXX") || exit 2
mkdir -p "$OUT" && OUT=$(cd "$OUT" && pwd) || exit 2
WORK=$(mktemp -d "${TMPDIR:-/tmp}/omnishell-nested-work.XXXXXX") || exit 2
SERVER_PID=''
cleanup() {
    [[ -z $SERVER_PID ]] || kill "$SERVER_PID" 2>/dev/null
    rm -rf -- "${WORK:?}"
}
trap cleanup EXIT

python3 "$HERE/server.py" "$WORK/port" &
SERVER_PID=$!
for _ in $(seq 50); do [[ -s $WORK/port ]] && break; sleep 0.1; done
[[ -s $WORK/port ]] || { echo "run.sh: page server did not start" >&2; exit 2; }
PORT=$(cat "$WORK/port")
cat >"$WORK/drawer.keyfile" <<K
[org/gnome/shell/extensions/omnishell]
panel-url='${URL:-http://127.0.0.1:$PORT/page.html}'
K
echo "$PORT" >"$OUT/port"
echo "output: $OUT"
bash "$HERE/nested.sh" --keyfile "$WORK/drawer.keyfile" --prepare "$HERE/prepare.sh" --driver "$HERE/driver.sh" --out "$OUT"
