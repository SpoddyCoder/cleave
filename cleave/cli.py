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
    PresetScanResult,
    PresetResultCategory,
    build_scan_report,
    delete_presets,
    destructive_scan_categories,
    existing_report_status,
    load_resume_results,
    probe_profile,
    quarantine_presets,
    run_scan,
    scan_report_summary,
    scanned_preset_dirs,
    validate_quarantine_dir,
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
        f"black={summary['black']}, washed_out={summary['washed_out']}, "
        f"load_failed={summary['load_failed']}",
        file=sys.stderr,
    )


def _delete_candidate_count(
    results: list[PresetScanResult] | tuple[PresetScanResult, ...],
    *,
    categories: frozenset[PresetResultCategory],
) -> int:
    return sum(
        1
        for result in results
        if result.result in categories and result.path.is_file()
    )


def _confirm_delete(count: int, *, yes: bool) -> None:
    if count == 0:
        return
    if yes:
        return
    if not sys.stdin.isatty():
        _exit_error("error: --delete requires --yes when stdin is not a TTY")
    try:
        answer = input(f"Delete {count} preset file(s) flagged by scan? [y/N] ").strip()
    except EOFError:
        answer = ""
    if answer.lower() not in ("y", "yes"):
        _exit_error("error: delete cancelled")


def _warn_resume_mismatch(
    *,
    field: str,
    resume_value: str,
    current_value: str,
) -> None:
    print(
        f"warning: resume report {field} is {resume_value}, "
        f"current run is {current_value}",
        file=sys.stderr,
    )


def _format_scan_resume_command(args: argparse.Namespace) -> str:
    parts = [sys.argv[0], "scan"]
    if args.presets_dir is not None:
        parts.extend(["--presets-dir", str(args.presets_dir)])
        for texture_path in args.texture_path:
            parts.extend(["--texture-path", str(texture_path)])
        if args.recursive:
            parts.append("--recursive")
    elif args.project_dir is not None:
        parts.append(str(args.project_dir))
    if args.config is not None:
        parts.extend(["-c", str(args.config)])
    assert args.report is not None
    parts.extend(["--report", str(args.report)])
    parts.append("--resume")
    return " ".join(parts)


def _guard_incomplete_report(
    report_path: Path | None,
    args: argparse.Namespace,
    target_total: int,
) -> None:
    if report_path is None or args.resume or not report_path.is_file():
        return
    try:
        scanned, complete = existing_report_status(report_path)
    except ValueError:
        return
    if complete:
        return
    resume_cmd = _format_scan_resume_command(args)
    _exit_error(
        f"error: {report_path} is incomplete ({scanned}/{target_total}).\n"
        f"Resume with: {resume_cmd}\n"
        f"Or delete the file to start over."
    )


def _handle_scan_keyboard_interrupt(
    report_path: Path | None,
    args: argparse.Namespace,
    target_total: int,
) -> None:
    if report_path is None:
        print(
            "Scan interrupted; results were not saved "
            "(use --report to enable resume)",
            file=sys.stderr,
        )
    else:
        try:
            scanned, _ = existing_report_status(report_path)
        except ValueError:
            scanned = 0
        print(
            f"Scan interrupted; {scanned}/{target_total} saved (complete: false).\n"
            f"Resume: {_format_scan_resume_command(args)}",
            file=sys.stderr,
        )
    sys.exit(130)


def cmd_scan(args: argparse.Namespace) -> None:
    bulk_mode = args.presets_dir is not None

    destructive_categories = destructive_scan_categories(
        include_dim=args.include_dim,
        include_washout=args.include_washout,
    )
    if (
        (args.include_dim or args.include_washout)
        and args.quarantine is None
        and not args.delete
    ):
        print(
            "warning: --include-dim/--include-washout have no effect "
            "without --quarantine or --delete",
            file=sys.stderr,
        )

    if args.resume and args.report is None:
        _exit_error("error: --resume requires --report PATH")

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

    prior_results: list[PresetScanResult] = []
    skip_paths: frozenset[Path] = frozenset()
    resume_scan_mode: str | None = None

    if args.resume:
        assert args.report is not None
        resume_path = args.report.expanduser()
        if not resume_path.is_file():
            _exit_error(f"error: resume report not found: {resume_path}")
        try:
            resume_data = load_resume_results(resume_path)
        except ValueError as exc:
            _exit_error(f"error: cannot read resume report {resume_path}: {exc}")
        prior_results = list(resume_data.results)
        skip_paths = resume_data.skip_paths
        resume_scan_mode = resume_data.scan_mode
        if resume_data.complete:
            _exit_error(
                f"error: {resume_path} is already complete "
                f"({len(prior_results)} presets).\n"
                f"Or delete the file to scan again."
            )

    profile = probe_profile()
    current_scan_mode = "bulk" if bulk_mode else "project"
    if resume_scan_mode is not None and resume_scan_mode != current_scan_mode:
        _warn_resume_mismatch(
            field="scan_mode",
            resume_value=resume_scan_mode,
            current_value=current_scan_mode,
        )

    report_path = (
        args.report.expanduser().resolve() if args.report is not None else None
    )
    quarantine_dir: Path | None = None

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
        report_targets = ScanTargets(
            presets=targets.presets,
            presets_dir=targets.presets_dir,
            texture_paths=resolved_textures,
        )

        if args.quarantine is not None:
            try:
                quarantine_dir = validate_quarantine_dir(
                    args.quarantine,
                    scanned_preset_dirs(targets),
                )
            except ValueError as exc:
                _exit_error(f"error: {exc}")

        target_total = len(targets.presets)
        _guard_incomplete_report(report_path, args, target_total)

        def report_sink(new_results: list[PresetScanResult], complete: bool) -> None:
            assert report_path is not None
            report = build_scan_report(
                scan_mode="bulk",
                profile=profile,
                targets=report_targets,
                results=[*prior_results, *new_results],
                config_path=config_path,
                complete=complete,
            )
            write_scan_report(report_path, report)

        try:
            new_results = run_scan(
                targets,
                texture_paths=resolved_textures,
                report_sink=report_sink if report_path is not None else None,
                skip_paths=skip_paths,
            )
        except KeyboardInterrupt:
            _handle_scan_keyboard_interrupt(report_path, args, target_total)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            _exit_error(f"error: {e}")

        results = [*prior_results, *new_results]
        report = build_scan_report(
            scan_mode="bulk",
            profile=profile,
            targets=report_targets,
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

        if args.quarantine is not None:
            try:
                quarantine_dir = validate_quarantine_dir(
                    args.quarantine,
                    scanned_preset_dirs(targets),
                )
            except ValueError as exc:
                _exit_error(f"error: {exc}")

        target_total = len(targets.presets)
        _guard_incomplete_report(report_path, args, target_total)

        def report_sink(new_results: list[PresetScanResult], complete: bool) -> None:
            assert report_path is not None
            report = build_scan_report(
                scan_mode="project",
                profile=profile,
                targets=targets,
                results=[*prior_results, *new_results],
                project_dir=project_dir,
                config_path=config_path,
                complete=complete,
            )
            write_scan_report(report_path, report)

        try:
            new_results = run_scan(
                targets,
                report_sink=report_sink if report_path is not None else None,
                skip_paths=skip_paths,
            )
        except KeyboardInterrupt:
            _handle_scan_keyboard_interrupt(report_path, args, target_total)
        except (FileNotFoundError, ValueError, RuntimeError) as e:
            _exit_error(f"error: {e}")

        results = [*prior_results, *new_results]
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

    if report_path is not None:
        write_scan_report(report_path, report)
        print(f"Wrote scan report to {report_path}")

    if quarantine_dir is not None:
        moves = quarantine_presets(
            results,
            quarantine_dir,
            categories=destructive_categories,
        )
        for src, dst in moves:
            print(f"Quarantined {src} -> {dst}")

    if args.delete:
        delete_count = _delete_candidate_count(
            results,
            categories=destructive_categories,
        )
        _confirm_delete(delete_count, yes=args.yes)
        deleted = delete_presets(results, categories=destructive_categories)
        for path in deleted:
            print(f"Deleted {path}")


def cmd_scan_golden(args: argparse.Namespace) -> None:
    from cleave.preset_scan_golden import (
        DEFAULT_GOLDEN_SET_PATH,
        DEFAULT_METRICS_CACHE_PATH,
        DEFAULT_SWEEP_WARMUP_FRAMES,
        DEFAULT_SWEEP_WINDOW_FRAMES,
        default_threshold_sweep_variants,
        evaluate,
        format_probe_profile_summary,
        load_golden_set,
        load_metrics_cache,
        print_eval_report,
        probe_golden_set,
        probe_profile,
        sweep,
    )

    golden_path = (
        args.golden.expanduser().resolve()
        if args.golden is not None
        else DEFAULT_GOLDEN_SET_PATH
    )
    cache_path = (
        args.cache.expanduser().resolve()
        if args.cache is not None
        else DEFAULT_METRICS_CACHE_PATH.resolve()
    )

    if args.probe:
        golden = load_golden_set(golden_path)
        probe_golden_set(golden, cache_path)
        profile = probe_profile()
        print(
            f"Wrote cache ({format_probe_profile_summary(profile)}) to {cache_path}",
            file=sys.stderr,
        )
        return

    golden = load_golden_set(golden_path)
    cache = load_metrics_cache(cache_path)

    if args.eval:
        try:
            report = evaluate(
                cache,
                golden,
                warmup_frames=args.warmup,
                window_frames=args.window,
            )
        except ValueError as exc:
            _exit_error(f"error: {exc}")
        print_eval_report(report)
        return

    results = sweep(cache, golden)
    variant_count = len(default_threshold_sweep_variants())
    warmup_grid = DEFAULT_SWEEP_WARMUP_FRAMES
    window_grid = DEFAULT_SWEEP_WINDOW_FRAMES
    config_count = len(results)
    print(
        f"Sweep: {config_count} configs "
        f"({variant_count} threshold variants x "
        f"{len(warmup_grid)} warmups x "
        f"{len(window_grid)} windows)",
        file=sys.stderr,
    )
    print("Sweep results (best first):", file=sys.stderr)
    for index, entry in enumerate(results[:15], start=1):
        threshold_note = ""
        if entry.thresholds is not None:
            threshold_note = f" thresholds={entry.thresholds}"
        print(
            f"  {index}. warmup={entry.warmup_frames} window={entry.window_frames}"
            f"{threshold_note}: {entry.correct}/{entry.total} "
            f"({entry.accuracy * 100:.1f}%)",
            file=sys.stderr,
        )


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
        epilog=(
            "For large preset directories, use --report so an interrupted scan "
            "can be resumed with the same --report PATH and --resume."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "--report",
        type=Path,
        metavar="PATH",
        help=(
            "Write JSON scan report to PATH incrementally so an interrupted run "
            "can be resumed with the same PATH and --resume."
        ),
    )
    scan.add_argument(
        "--resume",
        action="store_true",
        help="Continue a prior scan; requires --report PATH to an existing report",
    )
    scan_action = scan.add_mutually_exclusive_group()
    scan_action.add_argument(
        "--quarantine",
        type=Path,
        metavar="DIR",
        help=(
            "Move failed presets (load_failed, black) to DIR; "
            "use --include-dim / --include-washout to extend"
        ),
    )
    scan_action.add_argument(
        "--delete",
        action="store_true",
        help=(
            "Delete failed presets after the scan (load_failed, black; "
            "prompts unless --yes)"
        ),
    )
    scan.add_argument(
        "--include-dim",
        action="store_true",
        help="Also quarantine or delete presets classified as dim",
    )
    scan.add_argument(
        "--include-washout",
        action="store_true",
        help="Also quarantine or delete presets classified as washed_out",
    )
    scan.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation for --delete (required when stdin is not a TTY)",
    )
    scan.set_defaults(func=cmd_scan)

    from cleave.paths import repo_root
    from cleave.preset_scan_golden import (
        DEFAULT_GOLDEN_SET_PATH,
        DEFAULT_METRICS_CACHE_PATH,
    )

    scan_golden = subparsers.add_parser(
        "scan-golden",
        prog="cleave scan-golden",
        help="Probe and evaluate the preset scan golden set",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode = scan_golden.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--probe",
        action="store_true",
        help="GL probe all golden presets and write metrics cache",
    )
    mode.add_argument(
        "--eval",
        action="store_true",
        help="Classify cached metrics and compare to golden labels",
    )
    mode.add_argument(
        "--sweep",
        action="store_true",
        help="Grid search warmup/window settings against golden labels",
    )
    scan_golden.add_argument(
        "--warmup",
        type=int,
        metavar="N",
        help="Override eval warmup frames (must match cache profile)",
    )
    scan_golden.add_argument(
        "--window",
        type=int,
        metavar="N",
        help="Override eval window frames (must match cache profile)",
    )
    scan_golden.add_argument(
        "--cache",
        type=Path,
        metavar="PATH",
        help=(
            "Metrics cache JSON path "
            f"(default: {DEFAULT_METRICS_CACHE_PATH.relative_to(repo_root())})"
        ),
    )
    scan_golden.add_argument(
        "--golden",
        type=Path,
        metavar="PATH",
        help=(
            "Golden set YAML path "
            f"(default: {DEFAULT_GOLDEN_SET_PATH.relative_to(repo_root())})"
        ),
    )
    scan_golden.set_defaults(func=cmd_scan_golden)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
