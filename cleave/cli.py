import argparse
import os
import sys
from pathlib import Path

from cleave.paths import repo_root, resolve_project
from cleave.project import manifest_path, mix_path
from cleave.separate import (
    project_stems_complete,
    resolve_separate_target,
    run_separate,
    signals_complete,
)

SIGNALS_FILENAME = "signals.json"


def _exit_error(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def validate_project(path_or_slug: str) -> Path:
    try:
        return resolve_project(path_or_slug)
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")


def validate_project_manifest(project_dir: Path) -> None:
    if not manifest_path(project_dir).is_file():
        _exit_error(
            f"error: project manifest not found: {manifest_path(project_dir)}; "
            "run separate first"
        )
    mix = mix_path(project_dir)
    if not mix.is_file():
        _exit_error(f"error: project mix not found: {mix}")


def cmd_separate(args: argparse.Namespace) -> None:
    target = Path(args.target)
    try:
        project_dir, _ = resolve_separate_target(target)
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    if (
        project_stems_complete(project_dir)
        and signals_complete(project_dir)
        and not args.force
    ):
        print(
            f"project {project_dir} has stems and signals; "
            "use --force to redo separation and analysis"
        )
        return

    stems_before = project_stems_complete(project_dir)
    signals_before = signals_complete(project_dir)

    try:
        result = run_separate(target, slow=args.slow, force=args.force)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    signals_path = result / SIGNALS_FILENAME
    if args.force:
        print(f"Re-separated and analysed project at {result}")
    elif stems_before and not signals_before:
        print(f"Wrote signals to {signals_path}")
    else:
        print(f"Wrote project to {result}")


def cmd_play(args: argparse.Namespace) -> None:
    project_dir = validate_project(args.project)
    validate_project_manifest(project_dir)

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from cleave.viz import launch

    launch(
        project_dir,
        config=args.config,
        preset=args.preset,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleave",
        description="Stem-driven music visualizer",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    separate = subparsers.add_parser(
        "separate",
        help="Separate audio into stems and extract signals",
    )
    separate.add_argument(
        "target",
        help="Source audio file or Cleave project (path or slug)",
    )
    separate.add_argument(
        "--slow",
        action="store_true",
        help="htdemucs_ft for separation; pyin for vocal pitch (default: fast)",
    )
    separate.add_argument(
        "--force",
        action="store_true",
        help="Re-run Demucs and signal extraction even when outputs exist",
    )
    separate.set_defaults(func=cmd_separate)

    play = subparsers.add_parser(
        "play",
        help="Run the live visualizer for a project",
    )
    play.add_argument(
        "project",
        help="Cleave project (path or slug)",
    )
    play.add_argument(
        "--config",
        type=Path,
        help=f"Config path (default: {repo_root() / 'cleave.config.yaml'})",
    )
    play.add_argument(
        "--preset",
        type=Path,
        help=(
            "Drums-only debug: load this .milk on drums (skips four-preset config "
            "validation; uses visualizer width/height/fps from config if present)"
        ),
    )
    play.set_defaults(func=cmd_play)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
