"""CLI entry for the Cleave visualizer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cleave.paths import repo_root, resolve_project
from cleave.viz import launch


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Cleave visualizer: four stem layers from cleave.config.yaml "
            "(default), or drums-only debug via --preset"
        ),
    )
    parser.add_argument("path", type=Path, help="project path or slug")
    parser.add_argument(
        "--source",
        type=Path,
        help="Original mix wav (overrides signals.json source)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Config path (default: {repo_root() / 'cleave.config.yaml'})",
    )
    parser.add_argument(
        "--preset",
        type=Path,
        help=(
            "Drums-only debug: load this .milk on drums (skips four-preset config "
            "validation; uses visualizer width/height/fps from config if present)"
        ),
    )
    args = parser.parse_args()

    try:
        project_dir = resolve_project(args.path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    launch(
        project_dir,
        source=args.source,
        config=args.config,
        preset=args.preset,
    )
