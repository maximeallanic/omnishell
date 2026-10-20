#!/usr/bin/env bash
# Driver of nested.sh for the screenshots: driver.sh OUT  (GOOGLE_HUB_SHOTS: space-separated shot names)
read -ra shots <<<"${GOOGLE_HUB_SHOTS:-}"
exec python3 "$(dirname "${BASH_SOURCE[0]}")/driver.py" "$1" ${shots[@]+"${shots[@]}"}
