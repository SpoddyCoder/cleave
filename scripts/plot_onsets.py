#!/usr/bin/env python3
"""Plot drum vs mix onset strength from signals.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.signals import resolve_signals_path  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot drum vs mix onset strength from signals.json",
    )
    parser.add_argument("path", type=Path, help="signals.json or stems folder")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output PNG (default: onset_comparison.png beside signals.json)",
    )
    parser.add_argument("--show", action="store_true", help="Show plot interactively")
    args = parser.parse_args()

    signals_path = resolve_signals_path(args.path)
    if not signals_path.is_file():
        print(f"error: {signals_path} not found", file=sys.stderr)
        sys.exit(1)

    with signals_path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    sr = float(data["sample_rate_hz"])
    drums = data["drums"]
    onset = drums["onset_strength"]
    times = [i / sr for i in range(len(onset))]

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(times, onset, label="drum stem", color="C0")

    mix = drums.get("mix_onset_strength")
    if mix is None:
        print(
            "warning: mix_onset_strength missing; "
            "re-run cleave analyse with --source to include full mix",
            file=sys.stderr,
        )
    else:
        mix_times = [i / sr for i in range(len(mix))]
        ax.plot(mix_times, mix, label="full mix", color="C1", alpha=0.85)

    track = signals_path.parent.name
    ax.set(xlabel="Time (s)", ylabel="Onset strength", title=f"Onset strength — {track}")
    ax.legend()
    duration = data.get("duration_sec")
    if duration is not None:
        ax.set_xlim(0, duration)
    fig.tight_layout()

    out = args.output or signals_path.parent / "onset_comparison.png"
    fig.savefig(out, dpi=150)
    print(f"saved {out}")

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
