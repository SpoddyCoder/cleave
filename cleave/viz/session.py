"""Live tuning session state and config bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from cleave.config import (
    CleaveConfig,
    RenderOverlayPosition,
    VIZ_CONFIG_FILENAME,
)
from cleave.config_schema import (
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_PRESET_SWITCHING,
    DEFAULT_PRESET_SWITCHING_SCOPE,
    DEFAULT_PRESET_SWITCHING_SHUFFLE,
    DEFAULT_PRESET_DURATION,
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_EASTER_EGG,
    DEFAULT_PRESET_START_CLEAN,
    HighlightRolloffApplyMode,
    HighlightRolloffCurve,
    PresetSwitchingMode,
    PresetSwitchingScope,
    default_render_overlay_runtime_values,
    default_highlight_rolloff_runtime_values,
    default_chroma_boost_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.extract import StemSource
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor
from cleave.projectm_health import PresetSkipNotifyTracker
from cleave.timeline import SlotCue, TimelineLane, copy_lane, empty_lane
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
    locked: bool = False


def default_render_overlay_runtime() -> RenderOverlayRuntime:
    return RenderOverlayRuntime(**default_render_overlay_runtime_values())


@dataclass
class HighlightRolloffRuntime:
    mode: HighlightRolloffApplyMode
    curve: HighlightRolloffCurve
    threshold_pct: int
    ceiling_pct: int
    strength_pct: int
    softness_pct: int
    desaturation_pct: int


def default_highlight_rolloff_runtime() -> HighlightRolloffRuntime:
    return HighlightRolloffRuntime(**default_highlight_rolloff_runtime_values())


@dataclass
class ChromaBoostRuntime:
    mode: str
    variant: str
    amount_pct: int


def default_chroma_boost_runtime() -> ChromaBoostRuntime:
    return ChromaBoostRuntime(**default_chroma_boost_runtime_values())


@dataclass
class RenderPostFxRuntime:
    enabled: bool
    expanded: bool
    fade_in: float
    fade_out: float
    highlight_rolloff: HighlightRolloffRuntime
    highlight_rolloff_expanded: bool = False
    chroma_boost: ChromaBoostRuntime = field(default_factory=default_chroma_boost_runtime)
    chroma_boost_expanded: bool = False
    locked: bool = False


def default_render_post_fx_runtime() -> RenderPostFxRuntime:
    values = default_render_post_fx_runtime_values()
    highlight_rolloff = HighlightRolloffRuntime(**values.pop("highlight_rolloff"))
    chroma_boost = ChromaBoostRuntime(**values.pop("chroma_boost"))
    return RenderPostFxRuntime(
        highlight_rolloff=highlight_rolloff,
        chroma_boost=chroma_boost,
        **values,
    )


@dataclass
class TimelineRuntime:
    enabled: bool = True
    locked: bool = False
    lanes: dict[str, TimelineLane] = field(default_factory=dict)
    panel_open: bool = False
    focus_row: int = 0
    armed_slots: set[str] = field(default_factory=set)
    recording: bool = False
    record_buffer: dict[str, list[SlotCue]] = field(default_factory=dict)
    record_baseline: dict[str, bool] = field(default_factory=dict)
    record_start_sec: float | None = None
    record_slot_start_sec: dict[str, float] = field(default_factory=dict)
    record_high_water_mark: float | None = None
    preview_active: bool = False
    monitor: dict[str, bool] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    override_visible: dict[str, bool] = field(default_factory=dict)
    arm_flash_start_ms: dict[str, int] = field(default_factory=dict)
    bar_phase_offset: int = 0
    show_bar_grid: bool = False


def default_timeline_runtime() -> TimelineRuntime:
    return TimelineRuntime()


@dataclass
class SongMarkerRuntime:
    """Project-scoped song markers held live; not part of viz YAML."""

    times: list[float] = field(default_factory=list)
    selected_index: int | None = None
    expanded: bool = False


def default_song_marker_runtime() -> SongMarkerRuntime:
    return SongMarkerRuntime()


@dataclass
class SettingsRuntime:
    expanded: bool = False
    ui_expanded: bool = False


@dataclass
class LayerRuntime:
    playlist: PresetPlaylist
    browse_floor: Path
    stem: StemSource
    opacity_pct: int = 100
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    effects_expanded: bool = False
    preset_switching_expanded: bool = False
    blend_mode: BlendMode = "black-key"
    beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY
    enabled: bool = True
    expanded: bool = False
    locked: bool = False
    preset_switching: PresetSwitchingMode = DEFAULT_PRESET_SWITCHING
    preset_switching_scope: PresetSwitchingScope = DEFAULT_PRESET_SWITCHING_SCOPE
    preset_switching_shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE
    preset_duration: float = DEFAULT_PRESET_DURATION
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED
    easter_egg: float = DEFAULT_EASTER_EGG
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN
    user_presets: list[str] = field(default_factory=list)  # absolute paths
    user_presets_expanded: bool = False


@dataclass
class TuningSession:
    layer_z_order: list[str]
    layers: dict[str, LayerRuntime] = field(default_factory=dict)
    solo_slot: str | None = None
    render_overlay: RenderOverlayRuntime = field(default_factory=default_render_overlay_runtime)
    render_overlay_solo: bool = False
    render_post_fx: RenderPostFxRuntime = field(
        default_factory=default_render_post_fx_runtime
    )
    render_post_fx_solo: bool = False
    timeline: TimelineRuntime = field(default_factory=default_timeline_runtime)
    song_markers: SongMarkerRuntime = field(default_factory=default_song_marker_runtime)
    settings: SettingsRuntime = field(default_factory=SettingsRuntime)
    help_visible: bool = False
    preset_skip_notify_tracker: PresetSkipNotifyTracker = field(
        default_factory=PresetSkipNotifyTracker
    )


def render_overlay_runtime_from_cfg(cfg: CleaveConfig) -> RenderOverlayRuntime:
    overlay = cfg.render.overlay if cfg.render is not None else None
    if overlay is not None:
        return replace(
            default_render_overlay_runtime(),
            enabled=overlay.enabled,
            position=overlay.position,
            title_font_size=overlay.title.font_size,
            title_font=overlay.title.font,
            title_margin_bottom=overlay.title.margin_bottom,
            body_font_size=overlay.body.font_size,
            body_font=overlay.body.font,
            opacity_pct=int(round(overlay.background.opacity * 100)),
            border_width=overlay.background.border.width,
            start_delay=overlay.start_delay,
            display_time=overlay.display_time,
            locked=overlay.locked,
        )
    return default_render_overlay_runtime()


def render_post_fx_runtime_from_cfg(
    cfg: CleaveConfig,
) -> RenderPostFxRuntime:
    post_fx = cfg.render.post_fx if cfg.render is not None else None
    if post_fx is not None:
        hr = post_fx.highlight_rolloff
        cb = post_fx.chroma_boost
        return replace(
            default_render_post_fx_runtime(),
            enabled=post_fx.enabled,
            locked=post_fx.locked,
            fade_in=post_fx.fade_in,
            fade_out=post_fx.fade_out,
            highlight_rolloff=replace(
                default_highlight_rolloff_runtime(),
                mode=hr.mode,
                curve=hr.curve,
                threshold_pct=hr.threshold_pct,
                ceiling_pct=hr.ceiling_pct,
                strength_pct=hr.strength_pct,
                softness_pct=hr.softness_pct,
                desaturation_pct=hr.desaturation_pct,
            ),
            chroma_boost=replace(
                default_chroma_boost_runtime(),
                mode=cb.mode,
                variant=cb.variant,
                amount_pct=cb.amount_pct,
            ),
        )
    return default_render_post_fx_runtime()


def timeline_runtime_from_cfg(cfg: CleaveConfig) -> TimelineRuntime:
    timeline = cfg.timeline
    enabled = True if timeline is None else timeline.enabled
    locked = False if timeline is None else timeline.locked
    source_lanes = {} if timeline is None else timeline.lanes
    lanes: dict[str, TimelineLane] = {}
    for slot in cfg.layer_z_order:
        if slot in source_lanes:
            lanes[slot] = copy_lane(source_lanes[slot])
        else:
            lanes[slot] = empty_lane()
    return TimelineRuntime(enabled=enabled, locked=locked, lanes=lanes)


def _beat_sensitivity(cfg: CleaveConfig, slot: str) -> float:
    layer = cfg.layers[slot]
    if layer.beat_sensitivity is not None:
        return layer.beat_sensitivity
    return cfg.editor.beat_sensitivity


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
            slot: LayerRuntime(
                playlist=playlists[slot],
                browse_floor=preset_browse_floor(
                    cfg.layers[slot].preset, preset_root
                ),
                stem=layer_cfg.stem,
                opacity_pct=int(layer_cfg.opacity * 100),
                effects={
                    effect_id: dict(drivers)
                    for effect_id, drivers in layer_cfg.effects.items()
                },
                blend_mode=layer_cfg.blend_mode,
                beat_sensitivity=_beat_sensitivity(cfg, slot),
                enabled=layer_cfg.enabled,
                locked=layer_cfg.locked,
                preset_switching=layer_cfg.preset_switching,
                preset_switching_scope=layer_cfg.preset_switching_scope,
                preset_switching_shuffle=layer_cfg.preset_switching_shuffle,
                preset_duration=layer_cfg.preset_duration,
                soft_cut_duration=layer_cfg.soft_cut_duration,
                hard_cut_duration=layer_cfg.hard_cut_duration,
                hard_cut_sensitivity=layer_cfg.hard_cut_sensitivity,
                hard_cut_enabled=layer_cfg.hard_cut_enabled,
                easter_egg=layer_cfg.easter_egg,
                preset_start_clean=layer_cfg.preset_start_clean,
                user_presets=[
                    path.as_posix()
                    for path in layer_cfg.preset_switching_presets
                ],
            )
            for slot, layer_cfg in cfg.layers.items()
        },
    )


def add_layer_to_session(
    session: TuningSession,
    slot: str,
    runtime: LayerRuntime,
) -> None:
    session.layers[slot] = runtime
    session.layer_z_order.append(slot)
    session.timeline.lanes[slot] = empty_lane()


def remove_layer_from_session(session: TuningSession, slot: str) -> None:
    session.layer_z_order.remove(slot)
    del session.layers[slot]
    session.timeline.lanes.pop(slot, None)
    session.timeline.record_buffer.pop(slot, None)
    if session.solo_slot == slot:
        session.solo_slot = None
