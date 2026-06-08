import argparse
import os
import sys
from pathlib import Path

from cleave.analyse import run_analyse
from cleave.extract import STEM_NAMES
from cleave.paths import repo_root, resolve_project
from cleave.project import manifest_path, mix_path
from cleave.separate import ProjectStemsExist, run_separate

SIGNALS_FILENAME = "signals.json"


def _exit_error(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def validate_project(path_or_slug: str) -> Path:
    try:
        return resolve_project(path_or_slug)
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")


def validate_stem_files(project_dir: Path) -> None:
    missing = [
        f"{name}.wav"
        for name in STEM_NAMES
        if not (project_dir / f"{name}.wav").is_file()
    ]
    if missing:
        _exit_error(
            f"error: missing stem files in {project_dir}: {', '.join(missing)}"
        )


def validate_project_manifest(project_dir: Path) -> None:
    if not manifest_path(project_dir).is_file():
        _exit_error(
            f"error: project manifest not found: {manifest_path(project_dir)}; "
            "run separate first"
        )
    mix = mix_path(project_dir)
    if not mix.is_file():
        _exit_error(f"error: project mix not found: {mix}")


def cmd_analyse(args: argparse.Namespace) -> None:
    project_dir = validate_project(args.project)
    validate_stem_files(project_dir)
    validate_project_manifest(project_dir)

    signals_path = project_dir / SIGNALS_FILENAME
    if signals_path.exists() and not args.force:
        print(
            f"signals.json already exists at {signals_path}; "
            "use --force to regenerate"
        )
        return

    signals_path = run_analyse(project_dir, slow=args.slow)
    print(f"Wrote signals to {signals_path}")


def cmd_separate(args: argparse.Namespace) -> None:
    try:
        project_dir = run_separate(
            Path(args.audiofile), slow=args.slow, force=args.force
        )
    except ProjectStemsExist as e:
        print(
            f"stem wavs already exist in project {e.project_dir}; "
            "use --force to re-separate"
        )
        return
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    print(f"Wrote project to {project_dir}")


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

    analyse = subparsers.add_parser(
        "analyse",
        help="Extract per-stem signals to signals.json",
    )
    analyse.add_argument(
        "project",
        help="Cleave project (path or slug)",
    )
    analyse.add_argument(
        "--slow",
        action="store_true",
        help="Use pyin for vocal pitch (default: yin)",
    )
    analyse.add_argument(
        "--force",
        action="store_true",
        help="Regenerate signals.json even if it already exists",
    )
    analyse.set_defaults(func=cmd_analyse)

    separate = subparsers.add_parser(
        "separate",
        help="Separate audio into stems with Demucs",
    )
    separate.add_argument(
        "audiofile",
        help="Path to source audio file (project slug derived from filename)",
    )
    separate.add_argument(
        "--slow",
        action="store_true",
        help="Use htdemucs_ft model (default: htdemucs)",
    )
    separate.add_argument(
        "--force",
        action="store_true",
        help="Re-separate even if stems already exist",
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
