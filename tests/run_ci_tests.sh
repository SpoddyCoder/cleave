#!/usr/bin/env bash
#
# Run the same headless test command as .github/workflows/tests.yml locally.
#
# requires:
#   sudo apt-get install -y libgl1 libglx-mesa0 libegl1 libgl1-mesa-dri xvfb
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APT_PKGS="libgl1 libglx-mesa0 libegl1 libgl1-mesa-dri xvfb"

if ! command -v xvfb-run >/dev/null; then
  echo "xvfb-run not found. Install with:" >&2
  echo "  sudo apt-get install -y ${APT_PKGS}" >&2
  exit 1
fi

if ! python3 - <<'PY'
import ctypes

missing = []
for lib in ("libEGL.so", "libGL.so"):
    try:
        ctypes.CDLL(lib)
    except OSError as exc:
        missing.append(f"  {lib}: {exc}")
if missing:
    print("OpenGL loader libraries missing (moderngl needs these at runtime):", flush=True)
    for line in missing:
        print(line, flush=True)
    raise SystemExit(1)
PY
then
  echo "Install the same system packages as CI:" >&2
  echo "  sudo apt-get install -y ${APT_PKGS}" >&2
  exit 1
fi

cleanup() {
  rm -f sdlaudio.raw
}
trap cleanup EXIT

unset SDL_VIDEODRIVER
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-disk}"

xvfb-run -a ./tests/run_unit_tests.py "$@"
