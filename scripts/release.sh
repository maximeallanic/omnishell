#!/usr/bin/env bash
# Prepares a release: builds the tarball that the one-line installer downloads and pins its sha256 in install.sh.
#
#   scripts/release.sh 0.2.0               1. checks that CHANGELOG.md has a "## [0.2.0] - date" section,
#                                           2. sets the version in lib/common.sh and install.sh,
#                                           3. builds dist/gnome-google-hub-0.2.0.tar.gz from that tree,
#                                           4. writes its sha256 into install.sh (RELEASE_SHA256) and commits the
#                                              two files as "chore(release): 0.2.0". Then tag and push.
#   scripts/release.sh --build-only 0.2.0  CI: rebuilds the tarball from the tag and checks it matches the pin.
#
# The tarball is reproducible (git archive, sorted entries, fixed dates, owners and modes, gzip -n) and is built with
# the RELEASE_SHA256 value of install.sh blanked, so its hash does not depend on the pin it is written into: the CI
# build of the tag gives the same bytes as the build made here.
set -euo pipefail
export LC_ALL=C
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
die() { echo "error: $*" >&2; exit 1; }

BUILD_ONLY=0
if [[ ${1:-} == --build-only ]]; then BUILD_ONLY=1; shift; fi
VERSION=${1:?usage: scripts/release.sh [--build-only] X.Y.Z}
[[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must be X.Y.Z"
NAME=gnome-google-hub-$VERSION
mkdir -p dist

# archive TREE-ISH: the tree as $NAME/, with the RELEASE_SHA256 value in install.sh emptied, gzip without timestamp.
archive() {
    local ref=$1 work
    work=$(mktemp -d "$ROOT/dist/.build.XXXXXX")
    git archive --format=tar --prefix="$NAME/" "$ref" | tar -x -C "$work"
    sed -i "s/^RELEASE_SHA256=.*/RELEASE_SHA256=''/" "$work/$NAME/install.sh"
    tar --sort=name --mtime='@0' --owner=0 --group=0 --numeric-owner --mode='u+rwX,go+rX,go-w' -C "$work" -cf - "$NAME" \
        | gzip -n -9 >"dist/$NAME.tar.gz"
    rm -rf -- "$work"
    (cd dist && sha256sum "$NAME.tar.gz" >"$NAME.tar.gz.sha256")
}

# The CHANGELOG section "## [X.Y.Z] - date", without its heading: the release notes.
notes() { awk -v h="## [$VERSION] - " 'index($0, h) == 1 {on = 1; next} /^## / {on = 0} on' CHANGELOG.md; }

[[ -n $(notes | tr -d '[:space:]') ]] || die "CHANGELOG.md has no '## [$VERSION] - YYYY-MM-DD' section"

if ((BUILD_ONLY)); then
    archive HEAD
    pinned=$(sed -n "s/^RELEASE_SHA256='\(.*\)'$/\1/p" install.sh)
    built=$(cut -d' ' -f1 "dist/$NAME.tar.gz.sha256")
    [[ $(sed -n 's/^RELEASE_VERSION=//p' install.sh) == "$VERSION" ]] || die "install.sh pins another version"
    [[ $(sed -n 's/^GOOGLE_HUB_VERSION=//p' lib/common.sh) == "$VERSION" ]] || die "lib/common.sh is another version"
    [[ $pinned == "$built" ]] || die "install.sh pins '$pinned', the tag builds $built"
    notes >dist/notes.md
    echo "dist/$NAME.tar.gz matches the pin ($built)"
    exit 0
fi

[[ -z $(git status --porcelain) ]] || die "commit or stash your changes first"
sed -i "s/^GOOGLE_HUB_VERSION=.*/GOOGLE_HUB_VERSION=$VERSION/" lib/common.sh
sed -i "s/^RELEASE_VERSION=.*/RELEASE_VERSION=$VERSION/" install.sh
git add lib/common.sh install.sh
# The tarball is the staged tree (version set, pin blanked by archive): the commit below differs only by the pin.
archive "$(git write-tree)"
sha=$(cut -d' ' -f1 "dist/$NAME.tar.gz.sha256")
sed -i "s/^RELEASE_SHA256=.*/RELEASE_SHA256='$sha'/" install.sh
git add install.sh
git commit -q -m "chore(release): $VERSION"
echo "Pinned $NAME.tar.gz ($sha) in install.sh and committed. Then:"
echo "    git tag -s v$VERSION -m 'Google Hub $VERSION' && git push origin main v$VERSION"
