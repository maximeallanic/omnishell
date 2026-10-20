#!/usr/bin/env bash
# Driver of nested.sh for the screenshots: driver.sh OUT  (OMNISHELL_SHOTS: space-separated shot names)
read -ra shots <<<"${OMNISHELL_SHOTS:-}"
exec python3 "$(dirname "${BASH_SOURCE[0]}")/driver.py" "$1" ${shots[@]+"${shots[@]}"}
