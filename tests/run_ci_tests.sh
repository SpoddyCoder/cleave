#!/usr/bin/env bash
#
# Run the same headless test command as .github/workflows/tests.yml locally.
#
# requires: 
#   sudo apt-get install -y xvfb libgl1 libgl1-mesa-dri
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v xvfb-run >/dev/null; then
  echo "xvfb-run not found. Install with:" >&2
  echo "  sudo apt-get install -y xvfb libgl1 libgl1-mesa-dri" >&2
  exit 1
fi

unset SDL_VIDEODRIVER
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-disk}"

exec xvfb-run -a ./tests/run_unit_tests.py "$@"

# cleanup cruft from run
rm -f sdlaudio.raw