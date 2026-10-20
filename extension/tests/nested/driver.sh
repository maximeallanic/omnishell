#!/usr/bin/env bash
# Driver of nested.sh (run on the private bus once the extension answers Ping): driver.sh OUT
exec python3 "$(dirname "${BASH_SOURCE[0]}")/driver.py" "$1"
