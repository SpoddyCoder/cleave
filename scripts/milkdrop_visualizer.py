#!/usr/bin/env python3
"""Milkdrop visualizer (Phase 5): four stem-driven libprojectM layers via OpenGL FBOs.

Default path loads cleave.config.yaml: one ProjectM instance per
stem (other, bass, vocals, drums), tiered FBO sizes, black-key/add compositing, and stem PCM
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
from cleave.effects.runtime import EffectRuntime  # noqa: E402
from cleave.preset_playlist import (  # noqa: E402
    PresetPlaylist,
    preset_browse_floor,
    scan_all_layers,
    scan_preset_playlist,
)
from cleave.gl_compositor import GlCompositor, LayerFbo  # noqa: E402
from cleave.gl_post_process import GlPostProcess  # noqa: E402
from cleave.projectm import ProjectM, ProjectMLibraryError  # noqa: E402
from cleave.signals import Signals, load_signals  # noqa: E402
from cleave.stem_pcm import load_stem_pcm, samples_per_frame  # noqa: E402
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
    TuningOverlay,
    TuningViewState,
)

STEM_DRUMS = "drums"
SAVED_CONFIGS_DIR = ROOT / "saved-cleave-configs"


def load_stem_signals(stems_dir: Path) -> Signals | None:
    signals_path = stems_dir / "signals.json"
    if not signals_path.is_file():
        return None
    return load_signals(signals_path)


def _apply_effect_modifiers(
    session: TuningSession,
    layers_by_name: dict[str, MilkdropLayer],
    effect_runtime: EffectRuntime,
    signals: Signals | None,
    t_sec: float,
    *,
    update: bool = True,
) -> None:
    if update:
        effect_runtime.update(session, signals, t_sec)
    modifiers = effect_runtime.modifiers(session)
    for stem, layer in layers_by_name.items():
        if not session.layers[stem].enabled:
            continue
        mod = modifiers[stem]
        layer.fbo.opacity = mod.opacity
        layer.fbo.flash_alpha = mod.flash_alpha
        layer.fbo.bloom_strength = mod.bloom_strength
        layer.fbo.hue_rgb = mod.hue_rgb
        layer.fbo.hue_mix = mod.hue_mix
        layer.fbo.grit_strength = mod.grit_strength
        layer.fbo.aberration_px = mod.aberration_px


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
        GlCompositor.reset_blend_for_external_render()
        pm.render_to_fbo(fbo.fbo_id)


def _apply_layer_bloom(layer: MilkdropLayer, post_process: GlPostProcess | None) -> None:
    if post_process is None:
        return
    fbo = layer.fbo
    if fbo.bloom_strength <= 0.0:
        return
    post_process.apply_bloom(
        fbo.texture_id,
        fbo.width,
        fbo.height,
        fbo.bloom_strength,
    )


def _apply_layer_grit(layer: MilkdropLayer, post_process: GlPostProcess | None) -> None:
    if post_process is None:
        return
    fbo = layer.fbo
    if fbo.grit_strength <= 0.0 and fbo.aberration_px <= 0.0:
        return
    post_process.apply_grit(
        fbo.texture_id,
        fbo.width,
        fbo.height,
        fbo.grit_strength,
        fbo.aberration_px,
    )


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
    preset_root = cfg.paths.preset_root
    return TuningSession(
        layer_z_order=list(cfg.layer_z_order),
        layers={
            name: LayerRuntime(
                playlist=playlists[name],
                browse_floor=preset_browse_floor(
                    cfg.layers[name].preset, preset_root
                ),
                opacity_pct=int(layer_cfg.opacity * 100),
                effects={
                    effect_id: dict(drivers)
                    for effect_id, drivers in layer_cfg.effects.items()
                },
                blend_mode=layer_cfg.blend_mode,
                beat_sensitivity=_beat_sensitivity(cfg, name),
                enabled=layer_cfg.enabled,
                locked=layer_cfg.locked,
            )
            for name, layer_cfg in cfg.layers.items()
        },
    )


def _make_tuning_controls(
    *,
    session: TuningSession,
    cfg: CleaveConfig,
    layers_by_name: dict[str, MilkdropLayer],
    layers: list[MilkdropLayer],
    playback,
    duration_sec: float,
    signals: Signals | None,
    effect_runtime: EffectRuntime,
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
        _apply_effect_modifiers(
            session,
            layers_by_name,
            effect_runtime,
            signals,
            current_sec(playback, duration_sec),
            update=False,
        )

    def on_layer_enabled_change(stem: str, enabled: bool) -> None:
        fbo = layers_by_name[stem].fbo
        fbo.enabled = enabled
        if enabled:
            _apply_effect_modifiers(
                session,
                layers_by_name,
                effect_runtime,
                signals,
                current_sec(playback, duration_sec),
                update=False,
            )

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
        repo_root_example=ROOT / CONFIG_FILENAME,
    )


def build_view_state(
    controls: TuningControls,
    *,
    paused: bool,
    position_sec: float,
) -> TuningViewState:
    """Build overlay view state; label width is capped when the panel draws."""
    return controls.build_view_state(paused=paused, position_sec=position_sec)


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
    preset_anchor: Path,
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
    post_process: GlPostProcess | None = None
    layers: list[MilkdropLayer] = []
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    try:
        compositor = GlCompositor(width, height)
        compositor.init()
        post_process = GlPostProcess()
        post_process.init()

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

        drums_cfg = cfg.layers[STEM_DRUMS] if cfg is not None else None
        session = TuningSession(
            layer_z_order=[STEM_DRUMS],
            layers={
                STEM_DRUMS: LayerRuntime(
                    playlist=playlist,
                    browse_floor=preset_browse_floor(preset_anchor, preset_root),
                    opacity_pct=int(
                        (drums_cfg.opacity if drums_cfg else 1.0) * 100
                    ),
                    effects={
                        effect_id: dict(drivers)
                        for effect_id, drivers in (
                            drums_cfg.effects if drums_cfg else {}
                        ).items()
                    },
                    blend_mode="add",
                    beat_sensitivity=beat_sensitivity,
                ),
            },
        )

        signals = load_stem_signals(stems_dir)
        effect_runtime = EffectRuntime()

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
                signals=signals,
                effect_runtime=effect_runtime,
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
                on_opacity_change=lambda stem, pct: _apply_effect_modifiers(
                    session,
                    layers_by_name,
                    effect_runtime,
                    signals,
                    current_sec(playback, duration_sec),
                    update=False,
                ),
                on_layer_enabled_change=lambda stem, on: (
                    setattr(layers_by_name[stem].fbo, "enabled", on),
                    _apply_effect_modifiers(
                        session,
                        layers_by_name,
                        effect_runtime,
                        signals,
                        current_sec(playback, duration_sec),
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

            _apply_effect_modifiers(
                session, layers_by_name, effect_runtime, signals, t_sec
            )

            assert compositor is not None
            if not playback.paused:
                _render_layer_fbo(layer, layer.pm)
                _apply_layer_bloom(layer, post_process)
                _apply_layer_grit(layer, post_process)
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
        if post_process is not None:
            post_process.destroy()
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
    post_process: GlPostProcess | None = None
    layers: list[MilkdropLayer] = []
    overlay_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    try:
        compositor = GlCompositor(width, height)
        compositor.init()
        post_process = GlPostProcess()
        post_process.init()
        layers = _build_layers(cfg, compositor, playlists)
        layers_by_name = {layer.name: layer for layer in layers}
        session = _session_from_cfg(cfg, playlists)
        signals = load_stem_signals(stems_dir)
        effect_runtime = EffectRuntime()

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
            signals=signals,
            effect_runtime=effect_runtime,
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

            _apply_effect_modifiers(
                session, layers_by_name, effect_runtime, signals, t_sec
            )

            assert compositor is not None
            if not playback.paused:
                for layer in layers:
                    if layer.fbo.enabled:
                        _render_layer_fbo(layer, layer.pm)
                        _apply_layer_bloom(layer, post_process)
                        _apply_layer_grit(layer, post_process)

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
        if post_process is not None:
            post_process.destroy()
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
                args.preset,
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
            )
    except ProjectMLibraryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
