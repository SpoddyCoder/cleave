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
    CleaveConfig,
    DEFAULT_PRESET_ROOT,
    DEFAULT_VISUALIZER_FPS,
    DEFAULT_VISUALIZER_HEIGHT,
    DEFAULT_VISUALIZER_WIDTH,
    find_config_path,
    load_config,
)
from cleave.preset_playlist import (  # noqa: E402
    PresetPlaylist,
    display_label,
    scan_all_layers,
    scan_preset_playlist,
    write_layer_presets,
)
from cleave.gl_compositor import GlCompositor, LayerFbo  # noqa: E402
from cleave.projectm import ProjectM, ProjectMLibraryError  # noqa: E402
from cleave.signals import Signals, load_signals  # noqa: E402
from cleave.stem_pcm import load_stem_pcm, samples_per_frame  # noqa: E402
from cleave.viz_overlay import (  # noqa: E402
    ControlRow,
    ControlsOverlay,
    format_layer_state,
    milkdrop_layered_rows,
    milkdrop_preset_legend_rows,
    playback_rows,
)
from cleave.viz_playback import (  # noqa: E402
    SKIP_SEC,
    current_sec,
    init_playback,
    seek,
    toggle_pause,
)

STEM_DRUMS = "drums"
LAYER_KEYS = {
    pygame.K_d: STEM_DRUMS,
    pygame.K_b: "bass",
    pygame.K_v: "vocals",
    pygame.K_o: "other",
}


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
        f"{name}: {len(playlist.paths)} presets in {playlist.anchor}",
        file=sys.stderr,
    )


def resolve_m1_preset(
    preset_override: Path,
    config_path: Path | None,
) -> tuple[PresetPlaylist, list[Path], float]:
    """Return (playlist, texture_paths, beat_sensitivity) for M1 --preset mode."""
    playlist = scan_preset_playlist(preset_override)
    textures = texture_paths_from_config(config_path)
    return playlist, textures, 1.0


@dataclass
class MilkdropLayer:
    name: str
    pm: ProjectM
    fbo: LayerFbo
    playlist: PresetPlaylist


def _mod_shift(mod: int) -> bool:
    return bool(mod & pygame.KMOD_SHIFT)


def _mod_ctrl(mod: int) -> bool:
    return bool(mod & (pygame.KMOD_CTRL | pygame.KMOD_LCTRL | pygame.KMOD_RCTRL))


def _layer_row_state(layer: MilkdropLayer, playlist: PresetPlaylist) -> str:
    label = (
        display_label(playlist.current, playlist.anchor)
        if layer.fbo.enabled
        else None
    )
    return format_layer_state(layer.fbo.enabled, label)


def _four_layer_overlay_rows(
    layers: list[MilkdropLayer],
    playlists: dict[str, PresetPlaylist],
    *,
    paused: bool,
) -> list[ControlRow]:
    by_name = {layer.name: layer for layer in layers}
    show_drums = by_name["drums"].fbo.enabled
    show_bass = by_name["bass"].fbo.enabled
    show_vocals = by_name["vocals"].fbo.enabled
    show_other = by_name["other"].fbo.enabled
    return milkdrop_layered_rows(
        show_drums=show_drums,
        show_bass=show_bass,
        show_vocals=show_vocals,
        show_other=show_other,
        paused=paused,
        drums_state=_layer_row_state(by_name["drums"], playlists["drums"]),
        bass_state=_layer_row_state(by_name["bass"], playlists["bass"]),
        vocals_state=_layer_row_state(by_name["vocals"], playlists["vocals"]),
        other_state=_layer_row_state(by_name["other"], playlists["other"]),
    )


def _step_playlist(layer: MilkdropLayer, playlist: PresetPlaylist, *, forward: bool) -> None:
    if forward:
        playlist.next()
    else:
        playlist.prev()
    playlist.load_into(layer.pm, smooth=True)
    layer.pm.lock_preset(True)


def _handle_preset_write(
    cfg: CleaveConfig,
    playlists: dict[str, PresetPlaylist],
) -> None:
    write_layer_presets(cfg.config_path, cfg.paths.preset_root, playlists)
    print(f"wrote layer presets to {cfg.config_path}", file=sys.stderr)


def _handle_m1_preset_write(
    config_path: Path | None,
    preset_root: Path,
    playlist: PresetPlaylist,
) -> None:
    path = find_config_path(config_path, ROOT)
    if path is None or not path.is_file():
        print("error: no config file found for Ctrl+W write", file=sys.stderr)
        return
    write_layer_presets(path, preset_root, {STEM_DRUMS: playlist})
    print(f"wrote layer presets to {path}", file=sys.stderr)


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
        blend_mode = "add" if name == STEM_DRUMS else "alpha"
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
            blend_mode=blend_mode,
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


def _m1_overlay_rows(playlist: PresetPlaylist, *, paused: bool) -> list[ControlRow]:
    label = display_label(playlist.current, playlist.anchor)
    rows = list(playback_rows(paused=paused))
    rows.append(
        ControlRow(
            "d",
            "Drums",
            format_layer_state(True, label),
        )
    )
    rows.extend(milkdrop_preset_legend_rows())
    return rows


def _handle_layer_keydown(
    event: pygame.event.Event,
    *,
    layers_by_name: dict[str, MilkdropLayer],
    playlists: dict[str, PresetPlaylist],
    cfg: CleaveConfig | None,
    config_path: Path | None,
    preset_root: Path | None,
) -> bool:
    """Handle stem / preset keys. Return True if overlay rows should refresh."""
    if event.key not in LAYER_KEYS and not (
        event.key == pygame.K_w and _mod_ctrl(event.mod)
    ):
        return False

    shift = _mod_shift(event.mod)
    ctrl = _mod_ctrl(event.mod)
    if shift and ctrl:
        return False

    if ctrl and event.key == pygame.K_w:
        if cfg is not None:
            _handle_preset_write(cfg, playlists)
        elif config_path is not None and preset_root is not None:
            _handle_m1_preset_write(
                config_path,
                preset_root,
                playlists[STEM_DRUMS],
            )
        return True

    if event.key not in LAYER_KEYS:
        return False

    stem = LAYER_KEYS[event.key]
    layer = layers_by_name[stem]
    playlist = playlists[stem]

    if shift:
        _step_playlist(layer, playlist, forward=True)
        return True
    if ctrl:
        _step_playlist(layer, playlist, forward=False)
        return True

    layer.fbo.enabled = not layer.fbo.enabled
    return True


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
        playlists = {STEM_DRUMS: playlist}
        layers_by_name = {STEM_DRUMS: layers[0]}

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        playback = init_playback()
        overlay = ControlsOverlay(
            _m1_overlay_rows(playlist, paused=playback.paused)
        )

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    overlay.notify_input()
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        toggle_pause(playback, duration_sec)
                    elif event.key == pygame.K_LEFT:
                        seek(playback, -SKIP_SEC, duration_sec)
                        _flush_all_pcm(layers)
                    elif event.key == pygame.K_RIGHT:
                        seek(playback, SKIP_SEC, duration_sec)
                        _flush_all_pcm(layers)
                    elif _handle_layer_keydown(
                        event,
                        layers_by_name=layers_by_name,
                        playlists=playlists,
                        cfg=None,
                        config_path=config_path,
                        preset_root=preset_root,
                    ):
                        pass
                    overlay.replace_rows(
                        _m1_overlay_rows(playlist, paused=playback.paused)
                    )

            t_sec = current_sec(playback, duration_sec)
            layer = layers[0]
            if not playback.paused:
                pcm = pcm_bank.slice_pcm(STEM_DRUMS, t_sec, n_pcm)
                layer.pm.feed_pcm(pcm)
                layer.pm.set_frame_time(t_sec)

            assert compositor is not None
            _render_layer_fbo(layer, layer.pm)
            compositor.composite([layer.fbo])

            overlay_surface.fill((0, 0, 0, 0))
            overlay.draw(overlay_surface)
            panel = overlay.panel_rect
            if panel is not None:
                px, py, pw, ph = panel
                panel_surface = overlay_surface.subsurface((px, py, pw, ph))
                tex_id = compositor.upload_overlay_texture(panel_surface)
                compositor.draw_overlay(tex_id, px, py, pw, ph)

            pygame.display.flip()
            overlay.update(clock.tick(fps) / 1000.0)

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

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()

        playback = init_playback()
        overlay = ControlsOverlay(
            _four_layer_overlay_rows(layers, playlists, paused=playback.paused)
        )
        layers_by_name = {layer.name: layer for layer in layers}

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    overlay.notify_input()
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        toggle_pause(playback, duration_sec)
                    elif event.key == pygame.K_LEFT:
                        seek(playback, -SKIP_SEC, duration_sec)
                        _flush_all_pcm(layers)
                    elif event.key == pygame.K_RIGHT:
                        seek(playback, SKIP_SEC, duration_sec)
                        _flush_all_pcm(layers)
                    elif _handle_layer_keydown(
                        event,
                        layers_by_name=layers_by_name,
                        playlists=playlists,
                        cfg=cfg,
                        config_path=None,
                        preset_root=None,
                    ):
                        pass
                    overlay.replace_rows(
                        _four_layer_overlay_rows(
                            layers, playlists, paused=playback.paused
                        )
                    )

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

            compositor.composite([layer.fbo for layer in layers])

            overlay_surface.fill((0, 0, 0, 0))
            overlay.draw(overlay_surface)
            panel = overlay.panel_rect
            if panel is not None:
                px, py, pw, ph = panel
                panel_surface = overlay_surface.subsurface((px, py, pw, ph))
                tex_id = compositor.upload_overlay_texture(panel_surface)
                compositor.draw_overlay(tex_id, px, py, pw, ph)

            pygame.display.flip()
            overlay.update(clock.tick(fps) / 1000.0)

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
            run(cfg, stems_dir, audio_path, playlists)
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
