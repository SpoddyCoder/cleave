#!/usr/bin/env python3
"""Milkdrop visualizer (Phase 5): four stem-driven libprojectM layers via OpenGL FBOs.

Default path loads cleave.config.yaml: one ProjectM instance per
stem (other, bass, vocals, drums), tiered FBO sizes, alpha/add compositing, and stem PCM
at the visualizer fps (30 by default). Use ``--preset`` for a single drums-layer debug run.
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import pygame
import yaml
from OpenGL.GL import GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear, glClearColor, glViewport

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cleave.config import (  # noqa: E402
    CONFIG_FILENAME,
    CleaveConfig,
    clamp_beat_sensitivity,
    DEFAULT_PRESET_ROOT,
    DEFAULT_VISUALIZER_FPS,
    DEFAULT_VISUALIZER_HEIGHT,
    DEFAULT_VISUALIZER_WIDTH,
    find_config_path,
    load_config,
)
from cleave.config_snapshot import next_unnamed_path, write_session_snapshot  # noqa: E402
from cleave.preset_playlist import (  # noqa: E402
    PresetPlaylist,
    scan_all_layers,
    scan_preset_playlist,
)
from cleave.gl_compositor import GlCompositor, LayerFbo  # noqa: E402
from cleave.projectm import ProjectM, ProjectMLibraryError  # noqa: E402
from cleave.signals import Signals, load_signals  # noqa: E402
from cleave.stem_pcm import load_stem_pcm, samples_per_frame  # noqa: E402
from cleave.viz_overlay import truncate_counter_label, truncate_preset_label  # noqa: E402
from cleave.viz_playback import (  # noqa: E402
    current_sec,
    init_playback,
    seek,
)
from cleave.viz_tuning_controls import (  # noqa: E402
    LayerRuntime,
    TuningControls,
    TuningSession,
)
from cleave.viz_tuning_overlay import (  # noqa: E402
    TrackBlock,
    TuningOverlay,
    TuningViewState,
)

STEM_DRUMS = "drums"
SAVED_CONFIGS_DIR = ROOT / "saved-cleave-configs"


def resolve_stems_dir(path: Path) -> Path:
    p = path.resolve()
    if p.is_file() and p.name == "signals.json":
        p = p.parent
    if not p.is_dir():
        print(f"error: stems folder not found: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def resolve_audio_path(signals: Signals, override: Path | None) -> Path:
    if override is not None:
        path = override.resolve()
    elif signals.source is None:
        print(
            "error: signals.json has no source; pass --source path/to/mix.wav",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        path = Path(signals.source)
        if not path.is_file():
            path = ROOT / signals.source
    if not path.is_file():
        print(f"error: audio not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path


def resolve_mix_path(stems_dir: Path, source_override: Path | None) -> Path:
    if source_override is not None:
        path = source_override.resolve()
        if not path.is_file():
            print(f"error: audio not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path

    signals_path = stems_dir / "signals.json"
    if signals_path.is_file():
        signals = load_signals(signals_path)
        return resolve_audio_path(signals, None)

    print(
        "error: no signals.json source; pass --source path/to/mix.wav",
        file=sys.stderr,
    )
    sys.exit(1)


def visualizer_settings_from_config(
    config_path: Path | None,
) -> tuple[int, int, int]:
    """Load visualizer width/height/fps without preset validation."""
    path = find_config_path(config_path, ROOT)
    if path is None or not path.is_file():
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    visualizer = data.get("visualizer")
    if not isinstance(visualizer, dict):
        return (
            DEFAULT_VISUALIZER_WIDTH,
            DEFAULT_VISUALIZER_HEIGHT,
            DEFAULT_VISUALIZER_FPS,
        )

    return (
        int(visualizer.get("width", DEFAULT_VISUALIZER_WIDTH)),
        int(visualizer.get("height", DEFAULT_VISUALIZER_HEIGHT)),
        int(visualizer.get("fps", DEFAULT_VISUALIZER_FPS)),
    )


def texture_paths_from_config(config_path: Path | None) -> list[Path]:
    """Load texture search paths without validating preset files."""
    path = find_config_path(config_path, ROOT)
    if path is None or not path.is_file():
        return []

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return []

    paths_raw = data.get("paths")
    if not isinstance(paths_raw, dict):
        return []

    raw = paths_raw.get("texture_paths")
    if not isinstance(raw, list) or not raw:
        return []

    return [Path(os.path.expanduser(str(p))).resolve() for p in raw]


def preset_root_from_config(config_path: Path | None) -> Path:
    """Load preset_root without validating preset files."""
    path = find_config_path(config_path, ROOT)
    if path is None or not path.is_file():
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    paths_raw = data.get("paths")
    if not isinstance(paths_raw, dict):
        return Path(os.path.expanduser(str(DEFAULT_PRESET_ROOT))).resolve()

    raw = paths_raw.get("preset_root", DEFAULT_PRESET_ROOT)
    return Path(os.path.expanduser(str(raw))).resolve()


def _print_playlist_scan(name: str, playlist: PresetPlaylist) -> None:
    print(
        f"{name}: {len(playlist.paths)} presets in {playlist.current_dir}",
        file=sys.stderr,
    )


def resolve_m1_preset(
    preset_override: Path,
    config_path: Path | None,
) -> tuple[PresetPlaylist, list[Path], float]:
    """Return (playlist, texture_paths, beat_sensitivity) for M1 --preset mode."""
    playlist = scan_preset_playlist(preset_override)
    textures = texture_paths_from_config(config_path)
    beat_sensitivity = 1.0
    path = find_config_path(config_path, ROOT)
    if path is not None and path.is_file():
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if isinstance(data, dict):
            visualizer = data.get("visualizer")
            if isinstance(visualizer, dict):
                beat_sensitivity = clamp_beat_sensitivity(
                    visualizer.get("beat_sensitivity", 1.0)
                )
    return playlist, textures, beat_sensitivity


@dataclass
class MilkdropLayer:
    name: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist


def _beat_sensitivity(cfg: CleaveConfig, layer_name: str) -> float:
    layer = cfg.layers[layer_name]
    if layer.beat_sensitivity is not None:
        return layer.beat_sensitivity
    return cfg.visualizer.beat_sensitivity


def _build_layers(
    cfg: CleaveConfig,
    compositor: GlCompositor,
    playlists: dict[str, PresetPlaylist],
) -> list[MilkdropLayer]:
    texture_paths = list(cfg.paths.texture_paths)
    fps = cfg.visualizer.fps
    runtimes: list[MilkdropLayer] = []

    for name, layer_cfg in cfg.layers_in_z_order():
        w, h = layer_cfg.width, layer_cfg.height
        playlist = playlists[name]

        pm = ProjectM()
        pm.set_window_size(w, h)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        pm.set_fps(fps)
        pm.set_beat_sensitivity(_beat_sensitivity(cfg, name))

        fbo = compositor.create_layer_fbo(
            name,
            w,
            h,
            opacity=layer_cfg.opacity,
            blend_mode=layer_cfg.blend_mode,
        )
        fbo.enabled = layer_cfg.enabled
        runtimes.append(
            MilkdropLayer(name=name, pm=pm, fbo=fbo, playlist=playlist)
        )

    return runtimes


def _render_layer_fbo(layer: MilkdropLayer, pm: ProjectM) -> None:
    fbo = layer.fbo
    with fbo:
        glViewport(0, 0, fbo.width, fbo.height)
        glClearColor(0.0, 0.0, 0.0, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        pm.render_to_fbo(fbo.fbo_id)


def _flush_all_pcm(layers: list[MilkdropLayer]) -> None:
    for layer in layers:
        layer.pm.flush_pcm()


def _destroy_layers(layers: list[MilkdropLayer]) -> None:
    for layer in layers:
        layer.pm.destroy()


def _session_from_cfg(
    cfg: CleaveConfig,
    playlists: dict[str, PresetPlaylist],
) -> TuningSession:
    return TuningSession(
        layer_z_order=list(cfg.layer_z_order),
        layers={
            name: LayerRuntime(
                playlist=playlists[name],
                opacity_pct=int(layer_cfg.opacity * 100),
                blend_mode=layer_cfg.blend_mode,
                beat_sensitivity=_beat_sensitivity(cfg, name),
                enabled=layer_cfg.enabled,
            )
            for name, layer_cfg in cfg.layers.items()
        },
    )


def _allow_overwrite_config(config_cli: Path | None, cfg: CleaveConfig) -> bool:
    """Overwrite is hidden only for implicit repo-root cleave.config.yaml."""
    config_explicit = config_cli is not None
    implicit_local = (
        not config_explicit
        and (ROOT / CONFIG_FILENAME).resolve() == cfg.config_path.resolve()
    )
    return not implicit_local


def build_view_state(
    controls: TuningControls,
    *,
    paused: bool,
    position_sec: float,
) -> TuningViewState:
    """Build overlay view state with truncated preset labels."""
    base = controls.build_view_state(paused=paused, position_sec=position_sec)
    tracks = {
        stem: TrackBlock(
            stem=block.stem,
            preset_dir_label=truncate_counter_label(block.preset_dir_label),
            preset_label=block.preset_label,
            blend_mode=block.blend_mode,
            opacity_pct=block.opacity_pct,
            beat_sensitivity=block.beat_sensitivity,
            enabled=block.enabled,
            preset_empty=block.preset_empty,
        )
        for stem, block in base.tracks.items()
    }
    return TuningViewState(
        layer_z_order=base.layer_z_order,
        tracks=tracks,
        paused=base.paused,
        position_sec=base.position_sec,
        focus_index=base.focus_index,
        move_mode_stem=base.move_mode_stem,
        toast_message=base.toast_message,
        toast_remaining_sec=base.toast_remaining_sec,
        confirm_message=base.confirm_message,
        confirm_focus_yes=base.confirm_focus_yes,
        allow_overwrite=base.allow_overwrite,
        active_config_label=base.active_config_label,
    )


def _make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig,
    layers_by_name: dict[str, MilkdropLayer],
    layers: list[MilkdropLayer],
    playback,
    duration_sec: float,
    allow_overwrite: bool,
) -> TuningControls:
    def on_preset_change(stem: str, playlist: PresetPlaylist) -> None:
        layer = layers_by_name[stem]
        layer.playlist = playlist
        if playlist.current is not None:
            playlist.load_into(layer.pm, smooth=False)
            layer.pm.lock_preset(True)

    def on_blend_change(stem: str, blend_mode) -> None:
        layers_by_name[stem].fbo.blend_mode = blend_mode

    def on_opacity_change(stem: str, pct: int) -> None:
        fbo = layers_by_name[stem].fbo
        fbo.opacity = pct / 100.0

    def on_layer_enabled_change(stem: str, enabled: bool) -> None:
        fbo = layers_by_name[stem].fbo
        fbo.enabled = enabled
        if enabled:
            fbo.opacity = session.layers[stem].opacity_pct / 100.0

    def on_beat_change(stem: str, beat: float) -> None:
        layers_by_name[stem].pm.set_beat_sensitivity(beat)

    def on_seek(delta_sec: float) -> None:
        seek(playback, delta_sec, duration_sec)
        _flush_all_pcm(layers)

    def on_save_new_config() -> Path:
        out_path = next_unnamed_path(SAVED_CONFIGS_DIR)
        write_session_snapshot(out_path, cfg=cfg, session=session)
        return out_path

    def on_overwrite_config(path: Path) -> str:
        write_session_snapshot(path, cfg=cfg, session=session)
        return path.name

    return TuningControls(
        session,
        preset_root=cfg.paths.preset_root,
        playback=playback,
        duration_sec=duration_sec,
        on_preset_change=on_preset_change,
        on_blend_change=on_blend_change,
        on_opacity_change=on_opacity_change,
        on_layer_enabled_change=on_layer_enabled_change,
        on_beat_change=on_beat_change,
        on_z_order_change=lambda _order: None,
        on_seek=on_seek,
        on_save_new_config=on_save_new_config,
        on_overwrite_config=on_overwrite_config,
        launch_config_path=cfg.config_path,
        allow_overwrite=allow_overwrite,
    )


def _composite_ordered(
    compositor: GlCompositor,
    layers_by_name: dict[str, MilkdropLayer],
    session: TuningSession,
) -> None:
    ordered = [layers_by_name[name] for name in reversed(session.layer_z_order)]
    compositor.composite([layer.fbo for layer in ordered])


def _draw_tuning_overlay(
    compositor: GlCompositor,
    overlay: TuningOverlay,
    overlay_surface: pygame.Surface,
    view_state: TuningViewState,
) -> None:
    overlay_surface.fill((0, 0, 0, 0))
    overlay.draw(overlay_surface, view_state)
    panel = overlay.panel_rect
    if panel is not None:
        px, py, pw, ph = panel
        panel_surface = overlay_surface.subsurface((px, py, pw, ph))
        tex_id = compositor.upload_overlay_texture(panel_surface)
        compositor.draw_overlay(tex_id, px, py, pw, ph)


def run_m1(
    stems_dir: Path,
    audio_path: Path,
    playlist: PresetPlaylist,
    texture_paths: list[Path],
    beat_sensitivity: float,
    config_path: Path | None,
    preset_root: Path,
    width: int,
    height: int,
    fps: int,
) -> None:
    """M1 debug: one drums ProjectM instance and one FBO."""
    cfg: CleaveConfig | None = None
    try:
        cfg = load_config(config_path, ROOT)
    except (FileNotFoundError, ValueError):
        pass

    pcm_bank = load_stem_pcm(stems_dir)
    duration_sec = pcm_bank.duration_sec
    n_pcm = samples_per_frame(fps)

    pygame.init()
    pygame.mixer.init()

    try:
        pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
    except pygame.error as exc:
        print(f"error: failed to open OpenGL window: {exc}", file=sys.stderr)
        pygame.quit()
        sys.exit(1)

    trackname = stems_dir.name
    pygame.display.set_caption(f"Cleave Milkdrop (M1) — {trackname}")
    clock = pygame.time.Clock()

    compositor: GlCompositor | None = None
    layers: list[MilkdropLayer] = []
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    try:
        compositor = GlCompositor(width, height)
        compositor.init()

        pm = ProjectM()
        pm.set_window_size(width, height)
        if texture_paths:
            pm.set_texture_paths(texture_paths)
        playlist.load_into(pm)
        pm.lock_preset(True)
        pm.set_hard_cut_enabled(False)
        pm.set_fps(fps)
        pm.set_beat_sensitivity(beat_sensitivity)

        fbo = compositor.create_layer_fbo(STEM_DRUMS, width, height, blend_mode="add")
        layers = [
            MilkdropLayer(name=STEM_DRUMS, pm=pm, fbo=fbo, playlist=playlist)
        ]
        layers_by_name = {STEM_DRUMS: layers[0]}

        session = TuningSession(
            layer_z_order=[STEM_DRUMS],
            layers={
                STEM_DRUMS: LayerRuntime(
                    playlist=playlist,
                    opacity_pct=100,
                    blend_mode="add",
                    beat_sensitivity=beat_sensitivity,
                ),
            },
        )

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        playback = init_playback()
        if cfg is not None:
            controls = _make_tuning_controls(
                session=session,
                cfg=cfg,
                layers_by_name=layers_by_name,
                layers=layers,
                playback=playback,
                duration_sec=duration_sec,
                allow_overwrite=_allow_overwrite_config(config_path, cfg),
            )
        else:

            def on_preset_change(stem: str, pl: PresetPlaylist) -> None:
                layer = layers_by_name[stem]
                layer.playlist = pl
                if pl.current is not None:
                    pl.load_into(layer.pm, smooth=False)
                    layer.pm.lock_preset(True)

            controls = TuningControls(
                session,
                preset_root=preset_root,
                playback=playback,
                duration_sec=duration_sec,
                on_preset_change=on_preset_change,
                on_blend_change=lambda stem, mode: setattr(
                    layers_by_name[stem].fbo, "blend_mode", mode
                ),
                on_opacity_change=lambda stem, pct: setattr(
                    layers_by_name[stem].fbo, "opacity", pct / 100.0
                ),
                on_layer_enabled_change=lambda stem, on: (
                    setattr(layers_by_name[stem].fbo, "enabled", on),
                    setattr(
                        layers_by_name[stem].fbo,
                        "opacity",
                        session.layers[stem].opacity_pct / 100.0,
                    )
                    if on
                    else None,
                ),
                on_beat_change=lambda stem, beat: layers_by_name[
                    stem
                ].pm.set_beat_sensitivity(beat),
                on_seek=lambda delta: (
                    seek(playback, delta, duration_sec),
                    _flush_all_pcm(layers),
                ),
            )
        overlay = TuningOverlay()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if controls.handle_keydown(event) is False:
                        running = False
                    else:
                        overlay.notify_input()
                elif event.type == pygame.KEYUP:
                    controls.handle_keyup(event)

            dt = clock.tick(fps) / 1000.0
            controls.tick(dt)

            t_sec = current_sec(playback, duration_sec)
            layer = layers[0]
            if not playback.paused:
                pcm = pcm_bank.slice_pcm(STEM_DRUMS, t_sec, n_pcm)
                layer.pm.feed_pcm(pcm)
                layer.pm.set_frame_time(t_sec)

            assert compositor is not None
            _render_layer_fbo(layer, layer.pm)
            compositor.composite([layer.fbo])

            view_state = build_view_state(
                controls,
                paused=playback.paused,
                position_sec=t_sec,
            )
            overlay.update(dt)
            _draw_tuning_overlay(compositor, overlay, overlay_surface, view_state)

            pygame.display.flip()

            if not playback.paused and not pygame.mixer.music.get_busy():
                if t_sec >= duration_sec - 0.05:
                    running = False

    finally:
        _destroy_layers(layers)
        if compositor is not None:
            compositor.destroy()
        pygame.mixer.music.stop()
        pygame.quit()


def run(
    cfg: CleaveConfig,
    stems_dir: Path,
    audio_path: Path,
    playlists: dict[str, PresetPlaylist],
    *,
    allow_overwrite: bool,
) -> None:
    """Four config-driven libprojectM layers composited bottom-to-top."""
    pcm_bank = load_stem_pcm(stems_dir)
    duration_sec = pcm_bank.duration_sec
    width = cfg.visualizer.width
    height = cfg.visualizer.height
    fps = cfg.visualizer.fps
    n_pcm = samples_per_frame(fps)

    pygame.init()
    pygame.mixer.init()

    try:
        pygame.display.set_mode((width, height), pygame.OPENGL | pygame.DOUBLEBUF)
    except pygame.error as exc:
        print(f"error: failed to open OpenGL window: {exc}", file=sys.stderr)
        pygame.quit()
        sys.exit(1)

    trackname = stems_dir.name
    pygame.display.set_caption(f"Cleave Milkdrop — {trackname}")
    clock = pygame.time.Clock()

    compositor: GlCompositor | None = None
    layers: list[MilkdropLayer] = []
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    try:
        compositor = GlCompositor(width, height)
        compositor.init()
        layers = _build_layers(cfg, compositor, playlists)
        layers_by_name = {layer.name: layer for layer in layers}
        session = _session_from_cfg(cfg, playlists)

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        playback = init_playback()
        controls = _make_tuning_controls(
            session=session,
            cfg=cfg,
            layers_by_name=layers_by_name,
            layers=layers,
            playback=playback,
            duration_sec=duration_sec,
            allow_overwrite=allow_overwrite,
        )
        overlay = TuningOverlay()

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if controls.handle_keydown(event) is False:
                        running = False
                    else:
                        overlay.notify_input()
                elif event.type == pygame.KEYUP:
                    controls.handle_keyup(event)

            dt = clock.tick(fps) / 1000.0
            controls.tick(dt)

            t_sec = current_sec(playback, duration_sec)
            if not playback.paused:
                for layer in layers:
                    if not layer.fbo.enabled:
                        continue
                    pcm = pcm_bank.slice_pcm(layer.name, t_sec, n_pcm)
                    layer.pm.feed_pcm(pcm)
                    layer.pm.set_frame_time(t_sec)

            assert compositor is not None
            for layer in layers:
                if layer.fbo.enabled:
                    _render_layer_fbo(layer, layer.pm)

            _composite_ordered(compositor, layers_by_name, session)

            view_state = build_view_state(
                controls,
                paused=playback.paused,
                position_sec=t_sec,
            )
            overlay.update(dt)
            _draw_tuning_overlay(compositor, overlay, overlay_surface, view_state)

            pygame.display.flip()

            if not playback.paused and not pygame.mixer.music.get_busy():
                if t_sec >= duration_sec - 0.05:
                    running = False

    finally:
        _destroy_layers(layers)
        if compositor is not None:
            compositor.destroy()
        pygame.mixer.music.stop()
        pygame.quit()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Milkdrop visualizer: four stem layers from cleave.config.yaml "
            "(default), or M1 single drums preset via --preset"
        ),
    )
    parser.add_argument("path", type=Path, help="stems folder for the track")
    parser.add_argument(
        "--source",
        type=Path,
        help="Original mix wav (overrides signals.json source)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Config path (default: {ROOT / 'cleave.config.yaml'})",
    )
    parser.add_argument(
        "--preset",
        type=Path,
        help=(
            "M1 debug: load this .milk on drums only (skips four-preset config "
            "validation; uses visualizer width/height/fps from config if present)"
        ),
    )
    args = parser.parse_args()

    stems_dir = resolve_stems_dir(args.path)
    audio_path = resolve_mix_path(stems_dir, args.source)

    try:
        if args.preset is not None:
            playlist, texture_paths, beat_sensitivity = resolve_m1_preset(
                args.preset,
                args.config,
            )
            _print_playlist_scan(STEM_DRUMS, playlist)
            width, height, fps = visualizer_settings_from_config(args.config)
            preset_root = preset_root_from_config(args.config)
            run_m1(
                stems_dir,
                audio_path,
                playlist,
                texture_paths,
                beat_sensitivity,
                args.config,
                preset_root,
                width,
                height,
                fps,
            )
        else:
            cfg = load_config(args.config, ROOT)
            playlists = scan_all_layers(cfg)
            for name, pl in playlists.items():
                _print_playlist_scan(name, pl)
            run(
                cfg,
                stems_dir,
                audio_path,
                playlists,
                allow_overwrite=_allow_overwrite_config(args.config, cfg),
            )
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
