#!/usr/bin/env python3
"""Time the editor shell's ImGui frame on a synthetic session.

Opens a hidden OpenGL window, builds tuning controls from the test fixtures
(no project needed), and runs the per-frame UI work the live loop does:
controller tick, command context, then ``draw_shell_frame``. Prints
milliseconds per frame, split into ImGui build and ImGui render.

    python scripts/bench_shell_frame.py --layers 4 --preset-list 20

No projectM, compositing, or post-FX runs, so this measures CPU time in the
shell only. The synthetic preset paths do not exist on disk.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pygame  # noqa: E402

_MAX_LAYERS = 8
_DT = 1.0 / 60.0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--layers", type=int, default=4, help="layer count (1-8)")
    parser.add_argument(
        "--preset-list",
        type=int,
        default=20,
        help="preset list entries per layer",
    )
    parser.add_argument(
        "--folder-presets",
        type=int,
        default=300,
        help="presets in each layer's folder",
    )
    parser.add_argument("--frames", type=int, default=200, help="timed frames")
    parser.add_argument("--warmup", type=int, default=20, help="untimed frames first")
    parser.add_argument("--size", default="1920x1080", help="window size, WxH")
    parser.add_argument(
        "--page",
        default=None,
        help="navigator id of the inspector page to show (default: first layer)",
    )
    args = parser.parse_args(argv)
    if not 1 <= args.layers <= _MAX_LAYERS:
        parser.error(f"--layers must be 1 to {_MAX_LAYERS}")
    if args.frames < 1 or args.warmup < 0:
        parser.error("--frames must be at least 1 and --warmup at least 0")
    try:
        width, height = (int(part) for part in args.size.lower().split("x"))
    except ValueError:
        parser.error("--size must look like 1920x1080")
    args.width, args.height = width, height
    return args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    pygame.init()
    pygame.display.set_mode(
        (args.width, args.height),
        pygame.OPENGL | pygame.DOUBLEBUF | pygame.HIDDEN,
    )

    # Import after the GL context exists; ImGuiHost picks its renderer from it.
    from cleave.viz.commands import command_context
    from cleave.viz.imgui_host import ImGuiHost
    from cleave.viz.menu_bar import MenuBarState
    from cleave.viz.navigator import layer_node_id
    from cleave.viz.overlay_profiler import OverlayProfiler
    from cleave.viz.shell_host import ShellHost, draw_shell_frame
    from cleave.viz.shell_menu_bar import menu_bar_height_px
    from cleave.viz.shell_transport import TransportReadout
    from cleave.viz.shell_layout import ShellLayout
    from tests.support.viz import make_controls, make_playlist

    slots = tuple(f"layer_{index}" for index in range(1, args.layers + 1))
    controls = make_controls(slots)
    session = controls.session
    for slot in slots:
        layer = session.layers[slot]
        layer.playlist = make_playlist(slot, args.folder_presets)
        layer.preset_list = [
            str(path) for path in layer.playlist.paths[: args.preset_list]
        ]
        if len(layer.preset_list) < args.preset_list:
            raise SystemExit("--preset-list cannot exceed --folder-presets")
    controls.shell_focus.selected_id = args.page or layer_node_id(slots[0])

    menu = MenuBarState()
    profiler = OverlayProfiler(enabled=True, window_frames=args.frames)
    imgui_host = ImGuiHost.create()
    shell = ShellHost(
        imgui_host, menu, controls, menu_bar_height_px(), profiler=profiler
    )
    imgui_host.set_display_size(args.width, args.height)
    readout = TransportReadout(
        paused=False,
        position_sec=12.0,
        duration_sec=120.0,
        bar_text="4.1",
        fps=60.0,
    )

    def frame() -> None:
        controls.tick(_DT)
        measured = shell.nav_content_height_px
        shell.set_layout(
            ShellLayout.compute(
                args.width,
                args.height,
                int(shell.menu_bar_height_px),
                menu_bar_height_px(),
                0,
                nav_content_h=measured if measured > 0 else None,
            )
        )
        with profiler.time_section("ui_build"):
            draw_shell_frame(
                shell, menu, command_context(controls), _DT, readout, None
            )

    try:
        for _ in range(args.warmup):
            frame()
        # First boundary: drops the warmup frames' section times.
        profiler.end_frame()
        frame_ms: list[float] = []
        for _ in range(args.frames):
            start = time.perf_counter()
            frame()
            frame_ms.append((time.perf_counter() - start) * 1000.0)
            profiler.end_frame()
    finally:
        imgui_host.destroy()
        pygame.quit()

    report = profiler.report
    assert report is not None
    sections = dict(report.sections)
    print(
        f"{args.layers} layers, {args.preset_list} preset list entries, "
        f"{args.folder_presets} folder presets, {args.width}x{args.height}, "
        f"{args.frames} frames"
    )
    print(f"frame mean    {statistics.fmean(frame_ms):8.3f} ms")
    print(f"frame median  {statistics.median(frame_ms):8.3f} ms")
    print(f"frame min     {min(frame_ms):8.3f} ms")
    print(f"ImGui build   {sections['ui_build']:8.3f} ms")
    print(f"ImGui render  {sections['ui_render']:8.3f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
