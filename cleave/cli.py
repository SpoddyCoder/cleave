from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from cleave import __version__
from cleave.paths import is_frozen, resolve_project

if TYPE_CHECKING:
    from cleave.stems import StemSource
    from cleave.viz.render import RenderSegment

# Parser/help constants (must match defining modules; avoid importing them for -h).
VIZ_CONFIG_FILENAME = "cleave-viz.yaml"
BEAT_DETECTION_STEM_CHOICES = ("drums", "full-mix", "bass", "vocals", "other")

SIGNALS_FILENAME = "signals.json"
_TARGET_HELP = "Source audio file or cleave project (path or slug)"
_PROJECT_DIR_HELP = "Cleave project directory (path or slug)"
COMMANDS = ("separate", "play", "render", "backup", "restore")
_PAUSE_PROMPT = "Press Enter to close..."


class _CleaveHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            return "".join(self._format_action(sub) for sub in action._get_subactions())
        return super()._format_action(action)


def _exit_error(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(1)


def owns_console() -> bool:
    """Return True when this process is the only one attached to the console.

    Explorer-launched Windows apps own a fresh console (count == 1). A
    terminal session shares the console with the shell (count > 1).
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        buf = (wintypes.DWORD * 2)()
        get_list = ctypes.windll.kernel32.GetConsoleProcessList
        get_list.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
        get_list.restype = wintypes.DWORD
        count = int(get_list(buf, len(buf)))
    except (AttributeError, OSError, TypeError, ValueError):
        return False
    return count == 1


def _is_error_exit(exc: SystemExit) -> bool:
    code = exc.code
    if code is None:
        return False
    try:
        return int(code) != 0
    except (TypeError, ValueError):
        return True


def _pause_on_frozen_console_error() -> None:
    if not is_frozen() or not owns_console():
        return
    try:
        sys.stderr.flush()
        sys.stdout.flush()
        input(_PAUSE_PROMPT)
    except EOFError:
        pass


def _is_play_target(arg: str) -> bool:
    if Path(arg).exists():
        return True
    try:
        resolve_project(arg)
    except (FileNotFoundError, OSError, ValueError):
        return False
    return True


def normalise_argv(argv: list[str]) -> list[str]:
    """Prepend ``play`` when a single positional is an existing path or project."""
    argv = list(argv)
    positional = [i for i, arg in enumerate(argv) if not arg.startswith("-")]
    if len(positional) != 1:
        return argv
    index = positional[0]
    target = argv[index]
    if target in COMMANDS:
        return argv
    if not _is_play_target(target):
        return argv
    argv.insert(index, "play")
    return argv


def _format_elapsed(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    mins, secs = divmod(total, 60)
    return f"{mins} mins {secs} secs"


def _high_quality_clause(high_quality: bool) -> str:
    return ", in high-quality mode" if high_quality else ""


def _viz_quality_clause(viz_quality: bool) -> str:
    return ", in viz-quality mode" if viz_quality else ""


def _render_scope_clause(segment: RenderSegment | None) -> str:
    if segment is None:
        return "final render"
    return f"segment render {segment.start_sec}-{segment.end_label_sec}s"


def _optional_beat_detection_stem(args: argparse.Namespace) -> StemSource | None:
    from cleave.stems import parse_beat_detection_stem

    raw = getattr(args, "beat_detection_stem", None)
    if raw is None:
        return None
    return parse_beat_detection_stem(raw)


def cmd_separate(args: argparse.Namespace) -> None:
    from cleave.config import ensure_project_viz_config
    from cleave.separate import (
        beat_detection_stem_mismatch,
        project_stems_complete,
        resolve_separate_target,
        run_separate,
        signals_complete,
    )

    target = Path(args.target)
    try:
        project_dir, audio_path = resolve_separate_target(target)
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    ensure_project_viz_config(project_dir)

    beat_stem = _optional_beat_detection_stem(args)
    if (
        project_stems_complete(project_dir)
        and signals_complete(project_dir)
        and not args.force
        and not beat_detection_stem_mismatch(project_dir, beat_stem)
    ):
        print(
            f"project {project_dir} has stems and signals; "
            "use --force to redo separation and analysis"
        )
        return

    stems_before = project_stems_complete(project_dir)
    signals_before = signals_complete(project_dir)

    track_name = audio_path.name
    started = time.perf_counter()
    try:
        result = run_separate(
            target,
            high_quality=args.high_quality,
            force=args.force,
            beat_detection_stem=beat_stem,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")
    elapsed = _format_elapsed(time.perf_counter() - started)

    signals_path = result / SIGNALS_FILENAME
    if args.force:
        print(f"Re-separated and analysed project at {result}")
    elif stems_before and not signals_before:
        print(f"Wrote signals to {signals_path}")
    else:
        print(f"Wrote project to {result}")

    print(
        f"{track_name} audio separated and analysed"
        f"{_high_quality_clause(args.high_quality)}, in {elapsed}"
    )


def cmd_play(args: argparse.Namespace) -> None:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from cleave.separate import run_separate
    from cleave.viz import launch

    target = Path(args.target)
    try:
        project_dir = run_separate(
            target,
            high_quality=args.high_quality,
            beat_detection_stem=_optional_beat_detection_stem(args),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")

    launch(
        project_dir,
        config=args.config,
    )


def cmd_render(args: argparse.Namespace) -> None:
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    from cleave.paths import resolve_project
    from cleave.viz.render import render

    try:
        project_dir = resolve_project(Path(args.project_dir))
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    started = time.perf_counter()
    try:
        result = render(
            project_dir,
            config=args.config,
            output=args.output,
            high_quality=args.high_quality,
            viz_quality=args.viz_quality,
            start_sec=args.start,
            end_sec=args.end,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        _exit_error(f"error: {e}")
    elapsed = _format_elapsed(time.perf_counter() - started)

    print(f"Rendered to {result.output_path}")
    size = f"{result.output_width}x{result.output_height}"
    print(
        f"{result.mix_filename} {_render_scope_clause(result.segment)} at {size} "
        f"completed{_high_quality_clause(args.high_quality)}"
        f"{_viz_quality_clause(args.viz_quality)}, in {elapsed}"
    )


def cmd_backup(args: argparse.Namespace) -> None:
    from cleave.archive import backup_project
    from cleave.paths import resolve_project

    try:
        project_dir = resolve_project(Path(args.project_dir))
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    try:
        archive_path = backup_project(
            project_dir, Path(args.destination), force=args.force
        )
    except (FileNotFoundError, ValueError, FileExistsError, OSError) as e:
        _exit_error(f"error: {e}")

    print(f"Backed up to {archive_path}")


def cmd_restore(args: argparse.Namespace) -> None:
    from cleave.archive import restore_project

    try:
        project_path = restore_project(
            Path(args.archive), as_slug=args.as_slug, force=args.force
        )
    except (FileNotFoundError, ValueError, FileExistsError, OSError) as e:
        _exit_error(f"error: {e}")

    print(f"Restored to {project_path}")


def _add_beat_detection_stem_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-bds",
        "--beat-detection-stem",
        choices=BEAT_DETECTION_STEM_CHOICES,
        default=None,
        help=(
            "Audio source for Beat This! beat/downbeat grid "
            "(default: full-mix, or value stored in signals.json when re-analysing)"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cleave",
        description=(
            "Stem-driven music visualizer with editor and render\n\n"
            "positional arguments:\n"
            f"  target                {_TARGET_HELP}"
        ),
        usage="%(prog)s [-h] <command> target",
        formatter_class=_CleaveHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"cleave {__version__}")
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
    _add_beat_detection_stem_arg(separate)
    separate.set_defaults(func=cmd_separate)

    play = subparsers.add_parser(
        "play",
        prog="cleave play",
        help="Open the editor (separates first if needed)",
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
    _add_beat_detection_stem_arg(play)
    play.add_argument(
        "-c",
        "--config",
        type=Path,
        help=f"Config path (default: <project>/{VIZ_CONFIG_FILENAME})",
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
        help=f"Config path (default: <project>/{VIZ_CONFIG_FILENAME})",
    )
    render.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output MP4 path (default: <project>/renders/<editor.name>.mp4)",
    )
    render.add_argument(
        "-hq",
        "--hq",
        "--high-quality",
        dest="high_quality",
        action="store_true",
        help="veryslow libx264 preset for best encode quality (slower)",
    )
    render.add_argument(
        "-vq",
        "--viz-quality",
        dest="viz_quality",
        action="store_true",
        help=(
            "scale each layer with preview_quality instead of full render "
            "resolution (~20%% faster)"
        ),
    )
    render.add_argument(
        "--start",
        type=int,
        metavar="SEC",
        help="Segment start in whole seconds (default: 0)",
    )
    render.add_argument(
        "--end",
        type=int,
        metavar="SEC",
        help="Segment end in whole seconds, exclusive (default: full track)",
    )
    render.set_defaults(func=cmd_render)

    backup = subparsers.add_parser(
        "backup",
        prog="cleave backup",
        help="Backup a project to a .cleave-tar.gz archive",
    )
    backup.add_argument(
        "project_dir",
        help=_PROJECT_DIR_HELP,
    )
    backup.add_argument(
        "destination",
        help="Archive file path, directory, or parent path to create",
    )
    backup.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing archive without prompting",
    )
    backup.set_defaults(func=cmd_backup)

    restore = subparsers.add_parser(
        "restore",
        prog="cleave restore",
        help="Restore a project from a .cleave-tar.gz archive",
    )
    restore.add_argument(
        "archive",
        help="Path to a .cleave-tar.gz archive",
    )
    restore.add_argument(
        "--as",
        dest="as_slug",
        metavar="SLUG",
        help="Restore under a different project slug",
    )
    restore.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Replace existing project without prompting",
    )
    restore.set_defaults(func=cmd_restore)

    return parser


def main(argv: list[str] | None = None) -> None:
    try:
        parser = build_parser()
        raw = sys.argv[1:] if argv is None else list(argv)
        if not raw:
            parser.print_help()
            raise SystemExit(0)
        args = parser.parse_args(normalise_argv(raw))
        args.func(args)
    except SystemExit as exc:
        if _is_error_exit(exc):
            _pause_on_frozen_console_error()
        raise
