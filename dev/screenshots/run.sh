#!/usr/bin/env bash
# README screenshots, taken for real: the extension and the Gemini drawer of this repository in a nested headless
# GNOME Shell (extension/tests/nested/nested.sh: private bus, private XDG folders, nothing from your session), fed by
# the demo daemon (demo_daemon.py: invented tasks and events, no Google account, no microphone).
#
# Usage: run.sh OUT_DIR [--locale LOCALE] [--shots "search calendar add-task tasks typing voice"]
# Environment: GOOGLE_HUB_SHOT_QUERIES (texts typed, as JSON, for another language), GOOGLE_HUB_DEMO_PHRASE,
#              GOOGLE_HUB_STOCK_GRESOURCE (the Shell theme resource to use, see below).
set -u
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
OUT=${1:?usage: run.sh OUT_DIR [--locale LOCALE] [--shots LIST]}
shift
LOCALE=en_US.UTF-8
while (($#)); do
    case "$1" in
        --locale) LOCALE=${2:?}; shift 2 ;;
        --shots) export GOOGLE_HUB_SHOTS=${2:?}; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done
mkdir -p "$OUT"
KEYS=$(mktemp "${TMPDIR:-/tmp}/google-hub-shots.XXXXXX.keyfile")
trap 'rm -f -- "$KEYS"' EXIT
# Dark style and the weekday in the clock; nothing else differs from a fresh GNOME session. The drawer loads a blank
# page: the README's drawer picture is a separate capture (screenshots/README.md), because repeated automated loads
# of gemini.google.com get answered with Google's "unusual traffic" page, which prints the network's IP address.
cat >"$KEYS" <<K
[org/gnome/desktop/interface]
color-scheme='prefer-dark'
enable-animations=true
enable-hot-corners=false
clock-show-weekday=true

[org/gnome/shell/extensions/google-hub]
panel-url='about:blank'
K
# A host whose Shell theme was replaced (dpkg diversion of the theme resource, as the m3e-gnome login-screen
# theming does) is shot with the distribution's original theme; GOOGLE_HUB_STOCK_GRESOURCE overrides the choice.
STOCK=${GOOGLE_HUB_STOCK_GRESOURCE:-}
THEME=/usr/share/gnome-shell/gnome-shell-theme.gresource
if [[ -z $STOCK ]] && command -v dpkg-divert >/dev/null; then
    real=$(dpkg-divert --truename "$THEME")
    [[ $real == "$THEME" ]] || STOCK=$real
fi
bash "$REPO/extension/tests/nested/nested.sh" --keyfile "$KEYS" --prepare "$HERE/prepare.sh" --driver "$HERE/driver.sh" \
    --locale "$LOCALE" --out "$OUT" ${STOCK:+--stock-theme "$STOCK"}
code=$?
# The typing frames become a small animation for the README (ffmpeg's two-pass palette keeps the GIF sharp).
if ((code == 0)) && compgen -G "$OUT/typing-*.png" >/dev/null && command -v ffmpeg >/dev/null; then
    ffmpeg -loglevel error -y -framerate 1.25 -i "$OUT/typing-%03d.png" \
        -vf "crop=1100:760:410:0,scale=880:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none" \
        -loop 0 "$OUT/search-typing.gif" || code=1
fi
exit "$code"
