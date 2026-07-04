import argparse
import os
import sys
import time
from pathlib import Path

from cleave.config import (
    VIZ_CONFIG_FILENAME,
    ensure_project_viz_config,
    find_config_path,
    load_config,
)
from cleave.paths import resolve_project
from cleave.preset_scan import (
    build_scan_report,
    probe_profile,
    run_scan,
    scan_report_summary,
    write_scan_report,
)
from cleave.preset_scan_targets import ScanTargets, build_bulk_targets, build_project_targets
from cleave.separate import (
    project_stems_complete,
    resolve_separate_target,
    run_separate,
    signals_complete,
)
from cleave.viz.render import RenderSegment

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


def cmd_separate(args: argparse.Namespace) -> None:
    target = Path(args.target)
    try:
        project_dir, audio_path = resolve_separate_target(target)
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

    track_name = audio_path.name
    started = time.perf_counter()
    try:
        result = run_separate(
            target, high_quality=args.high_quality, force=args.force
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
    try:
        project_dir = resolve_project(Path(args.project_dir))
    except (FileNotFoundError, ValueError) as e:
        _exit_error(f"error: {e}")

    from cleave.archive import backup_project

    try:
        archive_path = backup_project(
            project_dir, Path(args.destination), force=args.force
        )
    except (FileNotFoundError, ValueError, FileExistsError, OSError) as e:
        _exit_error(f"error: {e}")

    print(f"Backed up to {archive_path}")


def _dedupe_texture_paths(paths: list[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    ordered: list[Path] = []
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return tuple(ordered)


def _print_scan_summary(summary: dict[str, int]) -> None:
    print(
        "Scan complete: "
        f"{summary['total']} preset(s); "
        f"ok={summary['ok']}, dim={summary['dim']}, "
        f"black={summary['black']}, load_failed={summary['load_failed']}",
        file=sys.stderr,
    )


def cmd_scan(args: argparse.Namespace) -> None:
    bulk_mode = args.presets_dir is not None

    if bulk_mode:
        if args.project_dir is not None:
            _exit_error(
                "error: --presets-dir cannot be used with a project directory"
            )
    else:
        if args.project_dir is None:
            _exit_error("error: project directory required (or use --presets-dir)")
        if args.texture_path:
            _exit_error("error: --texture-path is only valid in bulk scan mode")
        if args.recursive:
            _exit_error("error: --recursive is only valid in bulk scan mode")

    profile = probe_profile(slow=args.slow)

    if bulk_mode:
        texture_paths = list(args.texture_path)
        config_path: Path | None = None
        if args.config is not None:
            config_path = args.config.expanduser().resolve()
            cfg = load_config(config_path, None)
            texture_paths.extend(cfg.paths.texture_paths)
        resolved_textures = _dedupe_texture_paths(texture_paths)
        if not resolved_textures:
            _exit_error(
                "error: bulk scan requires at least one --texture-path "
                "or paths.texture_paths in -c config"
            )

        presets_dir = args.presets_dir.expanduser().resolve()
        if not presets_dir.is_dir():
            _exit_error(f"error: presets directory not found: {presets_dir}")

        targets = build_bulk_targets(presets_dir, recursive=args.recursive)
        try:
            results = run_scan(
                targets,
                slow=args.slow,
                texture_paths=resolved_textures,
            )
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            _exit_error(f"error: {e}")

        report = build_scan_report(
            scan_mode="bulk",
            profile=profile,
            targets=ScanTargets(
                presets=targets.presets,
                presets_dir=targets.presets_dir,
                texture_paths=resolved_textures,
            ),
            results=results,
            config_path=config_path,
        )
    else:
        try:
            project_dir = resolve_project(Path(args.project_dir))
        except (FileNotFoundError, ValueError) as e:
            _exit_error(f"error: {e}")

        config_path = find_config_path(args.config, project_dir)
        if config_path is None:
            _exit_error(f"error: no {VIZ_CONFIG_FILENAME} found for project")

        try:
            cfg = load_config(args.config, project_dir)
        except (FileNotFoundError, ValueError) as e:
            _exit_error(f"error: {e}")

        targets = build_project_targets(cfg)
        try:
            results = run_scan(targets, slow=args.slow)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            _exit_error(f"error: {e}")

        report = build_scan_report(
            scan_mode="project",
            profile=profile,
            targets=targets,
            results=results,
            project_dir=project_dir,
            config_path=config_path,
        )

    summary = scan_report_summary(report)
    _print_scan_summary(summary)

    if args.report is not None:
        report_path = args.report.expanduser()
        write_scan_report(report_path, report)
        print(f"Wrote scan report to {report_path.resolve()}")


def cmd_restore(args: argparse.Namespace) -> None:
    from cleave.archive import restore_project

    try:
        project_path = restore_project(
            Path(args.archive), as_slug=args.as_slug, force=args.force
        )
    except (FileNotFoundError, ValueError, FileExistsError, OSError) as e:
        _exit_error(f"error: {e}")

    print(f"Restored to {project_path}")


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

    scan = subparsers.add_parser(
        "scan",
        prog="cleave scan",
        help="Scan Milkdrop presets for load failures and black output",
    )
    scan.add_argument(
        "project_dir",
        nargs="?",
        help=_PROJECT_DIR_HELP,
    )
    scan.add_argument(
        "-c",
        "--config",
        type=Path,
        help=f"Config path (default: <project>/{VIZ_CONFIG_FILENAME})",
    )
    scan.add_argument(
        "--presets-dir",
        type=Path,
        help="Bulk mode: directory of .milk presets (mutually exclusive with project)",
    )
    scan.add_argument(
        "--texture-path",
        action="append",
        type=Path,
        default=[],
        metavar="DIR",
        help="Bulk mode: texture search path (repeatable; required unless -c supplies paths)",
    )
    scan.add_argument(
        "--recursive",
        action="store_true",
        help="Bulk mode: scan subdirectories for .milk files",
    )
    scan.add_argument(
        "--slow",
        action="store_true",
        help="Longer probe warmup and render before luminance sample",
    )
    scan.add_argument(
        "--report",
        type=Path,
        metavar="PATH",
        help="Write JSON scan report to PATH",
    )
    scan.set_defaults(func=cmd_scan)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
