import argparse
import os
import sys
from pathlib import Path

from cleave.config import PROJECT_VIZ_CONFIG_FILENAME, ensure_project_viz_config
from cleave.paths import resolve_project
from cleave.separate import (
    project_stems_complete,
    resolve_separate_target,
    run_separate,
    signals_complete,
)

SIGNALS_FILENAME = "signals.json"
_TARGET_HELP = "Source audio file or cleave project (path or slug)"
_PROJECT_DIR_HELP = "Cleave project directory (path or slug)"


class _CleaveHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            return "".join(self._format_action(sub) for sub in action._get_subactions())
        return super()._format_action(action)


def _exit_error(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def cmd_separate(args: argparse.Namespace) -> None:
    target = Path(args.target)
    try:
        project_dir, _ = resolve_separate_target(target)
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    ensure_project_viz_config(project_dir)

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
        result = run_separate(
            target, high_quality=args.high_quality, force=args.force
        )
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
    target = Path(args.target)
    try:
        project_dir = run_separate(target, high_quality=args.high_quality)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from cleave.viz import launch

    launch(
        project_dir,
        config=args.config,
    )


def cmd_render(args: argparse.Namespace) -> None:
    try:
        project_dir = resolve_project(Path(args.project_dir))
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    from cleave.viz.render import render

    try:
        output_path = render(
            project_dir,
            config=args.config,
            output=args.output,
            high_quality=args.high_quality,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    print(f"Rendered to {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleave",
        description=(
            "Stem-driven music visualizer\n\n"
            "positional arguments:\n"
            f"  target                {_TARGET_HELP}"
        ),
        usage="%(prog)s [-h] <command> target",
        formatter_class=_CleaveHelpFormatter,
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, title="commands"
    )

    separate = subparsers.add_parser(
        "separate",
        prog="cleave separate",
        help="Separate audio into stems and extract signals",
    )
    separate.add_argument(
        "target",
        help=_TARGET_HELP,
    )
    separate.add_argument(
        "-hq",
        "--high-quality",
        action="store_true",
        help="htdemucs_ft for separation; pyin for vocal pitch (slower)",
    )
    separate.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Re-run Demucs and signal extraction even when outputs exist",
    )
    separate.set_defaults(func=cmd_separate)

    play = subparsers.add_parser(
        "play",
        prog="cleave play",
        help="Run the live visualizer (separates first if needed)",
    )
    play.add_argument(
        "target",
        help=_TARGET_HELP,
    )
    play.add_argument(
        "-hq",
        "--high-quality",
        action="store_true",
        help="htdemucs_ft for separation; pyin for vocal pitch (slower)",
    )
    play.add_argument(
        "-c",
        "--config",
        type=Path,
        help=f"Config path (default: <project>/{PROJECT_VIZ_CONFIG_FILENAME})",
    )
    play.set_defaults(func=cmd_play)

    render = subparsers.add_parser(
        "render",
        prog="cleave render",
        help="Render project visuals to MP4",
    )
    render.add_argument(
        "project_dir",
        help=_PROJECT_DIR_HELP,
    )
    render.add_argument(
        "-c",
        "--config",
        type=Path,
        help=f"Config path (default: <project>/{PROJECT_VIZ_CONFIG_FILENAME})",
    )
    render.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output MP4 path (default: <project>/renders/<visualizer.name>.mp4)",
    )
    render.add_argument(
        "-hq",
        "--hq",
        "--high-quality",
        dest="high_quality",
        action="store_true",
        help="veryslow libx264 preset for best encode quality (slower)",
    )
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
