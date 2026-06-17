"""Live tuning session state and config bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from cleave.config import (
    DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY,
    DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_FONT,
    DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
    DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
    DEFAULT_RENDER_OVERLAY_POSITION,
    DEFAULT_RENDER_OVERLAY_START_DELAY,
    DEFAULT_RENDER_POST_FX_FADE_IN,
    DEFAULT_RENDER_POST_FX_FADE_OUT,
    VIZ_CONFIG_FILENAME,
    CleaveConfig,
    RenderOverlayPosition,
)
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor
from cleave.timeline import TimelineCue
from cleave.blend_modes import BlendMode


def config_path_display(path: Path | None) -> str:
    """Active config path for the config header row (truncation happens at draw time)."""
    return path.as_posix() if path is not None else VIZ_CONFIG_FILENAME


def allow_overwrite_for_path(
    active_path: Path | None,
    *,
    repo_root_example: Path,
) -> bool:
    """Hide overwrite only for the repo-root template cleave-viz.yaml."""
    if active_path is None:
        return False
    return active_path.resolve() != repo_root_example.resolve()


@dataclass
class RenderOverlayRuntime:
    enabled: bool
    expanded: bool
    position: RenderOverlayPosition
    title_expanded: bool
    body_expanded: bool
    title_font_size: int
    title_font: str
    title_margin_bottom: int
    body_font_size: int
    body_font: str
    opacity_pct: int
    border_width: int
    start_delay: float
    display_time: float


def default_render_overlay_runtime() -> RenderOverlayRuntime:
    return RenderOverlayRuntime(
        enabled=True,
        expanded=False,
        position=DEFAULT_RENDER_OVERLAY_POSITION,
        title_expanded=False,
        body_expanded=False,
        title_font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        title_font=DEFAULT_RENDER_OVERLAY_FONT,
        title_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        body_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        body_font=DEFAULT_RENDER_OVERLAY_FONT,
        opacity_pct=int(round(DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY * 100)),
        border_width=DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
        start_delay=DEFAULT_RENDER_OVERLAY_START_DELAY,
        display_time=DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    )


@dataclass
class RenderPostFxRuntime:
    enabled: bool
    expanded: bool
    fade_in: float
    fade_out: float


def default_render_post_fx_runtime() -> RenderPostFxRuntime:
    return RenderPostFxRuntime(
        enabled=True,
        expanded=False,
        fade_in=DEFAULT_RENDER_POST_FX_FADE_IN,
        fade_out=DEFAULT_RENDER_POST_FX_FADE_OUT,
    )


@dataclass
class TimelineRuntime:
    enabled: bool = True
    cues: list[TimelineCue] = field(default_factory=list)
    panel_open: bool = False
    submenu_focused: bool = False
    focus_row: int = 0
    armed_stems: set[str] = field(default_factory=set)
    recording: bool = False
    record_buffer: list[TimelineCue] = field(default_factory=list)
    record_baseline: dict[str, bool] = field(default_factory=dict)
    record_start_sec: float | None = None
    preview_active: bool = False
    monitor: dict[str, bool] = field(default_factory=dict)
    override_stems: set[str] = field(default_factory=set)
    override_visible: dict[str, bool] = field(default_factory=dict)


def default_timeline_runtime() -> TimelineRuntime:
    return TimelineRuntime()


@dataclass
class LayerRuntime:
    playlist: PresetPlaylist
    browse_floor: Path
    opacity_pct: int = 100
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    effects_expanded: bool = False
    blend_mode: BlendMode = "black-key"
    beat_sensitivity: float = 1.0
    enabled: bool = True
    expanded: bool = False
    locked: bool = False


@dataclass
class TuningSession:
    layer_z_order: list[str]
    layers: dict[str, LayerRuntime] = field(default_factory=dict)
    solo_stem: str | None = None
    render_overlay: RenderOverlayRuntime = field(default_factory=default_render_overlay_runtime)
    render_overlay_solo: bool = False
    render_post_fx: RenderPostFxRuntime = field(
        default_factory=default_render_post_fx_runtime
    )
    render_post_fx_solo: bool = False
    timeline: TimelineRuntime = field(default_factory=default_timeline_runtime)
    help_visible: bool = False


def render_overlay_runtime_from_cfg(cfg: CleaveConfig) -> RenderOverlayRuntime:
    overlay = cfg.render.overlay if cfg.render is not None else None
    if overlay is not None:
        return RenderOverlayRuntime(
            enabled=overlay.enabled,
            expanded=False,
            position=overlay.position,
            title_expanded=False,
            body_expanded=False,
            title_font_size=overlay.title.font_size,
            title_font=overlay.title.font,
            title_margin_bottom=overlay.title.margin_bottom,
            body_font_size=overlay.body.font_size,
            body_font=overlay.body.font,
            opacity_pct=int(round(overlay.background.opacity * 100)),
            border_width=overlay.background.border.width,
            start_delay=overlay.start_delay,
            display_time=overlay.display_time,
        )
    return RenderOverlayRuntime(
        enabled=True,
        expanded=False,
        position=DEFAULT_RENDER_OVERLAY_POSITION,
        title_expanded=False,
        body_expanded=False,
        title_font_size=DEFAULT_RENDER_OVERLAY_TITLE_FONT_SIZE,
        title_font=DEFAULT_RENDER_OVERLAY_FONT,
        title_margin_bottom=DEFAULT_RENDER_OVERLAY_TITLE_MARGIN_BOTTOM,
        body_font_size=DEFAULT_RENDER_OVERLAY_BODY_FONT_SIZE,
        body_font=DEFAULT_RENDER_OVERLAY_FONT,
        opacity_pct=int(round(DEFAULT_RENDER_OVERLAY_BACKGROUND_OPACITY * 100)),
        border_width=DEFAULT_RENDER_OVERLAY_BORDER_WIDTH,
        start_delay=DEFAULT_RENDER_OVERLAY_START_DELAY,
        display_time=DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    )


def render_post_fx_runtime_from_cfg(
    cfg: CleaveConfig,
) -> RenderPostFxRuntime:
    post_fx = cfg.render.post_fx if cfg.render is not None else None
    if post_fx is not None:
        return RenderPostFxRuntime(
            enabled=post_fx.enabled,
            expanded=False,
            fade_in=post_fx.fade_in,
            fade_out=post_fx.fade_out,
        )
    return RenderPostFxRuntime(
        enabled=True,
        expanded=False,
        fade_in=DEFAULT_RENDER_POST_FX_FADE_IN,
        fade_out=DEFAULT_RENDER_POST_FX_FADE_OUT,
    )


def timeline_runtime_from_cfg(cfg: CleaveConfig) -> TimelineRuntime:
    timeline = cfg.timeline
    if timeline is None:
        return TimelineRuntime()
    return TimelineRuntime(
        enabled=timeline.enabled,
        cues=list(timeline.cues),
    )


def _beat_sensitivity(cfg: CleaveConfig, layer_name: str) -> float:
    layer = cfg.layers[layer_name]
    if layer.beat_sensitivity is not None:
        return layer.beat_sensitivity
    return cfg.visualizer.beat_sensitivity


def session_from_cfg(
    cfg: CleaveConfig,
    playlists: dict[str, PresetPlaylist],
) -> TuningSession:
    preset_root = cfg.paths.preset_root
    return TuningSession(
        layer_z_order=list(cfg.layer_z_order),
        render_overlay=render_overlay_runtime_from_cfg(cfg),
        render_post_fx=render_post_fx_runtime_from_cfg(cfg),
        timeline=timeline_runtime_from_cfg(cfg),
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
