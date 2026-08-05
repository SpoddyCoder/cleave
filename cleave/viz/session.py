"""Live tuning session state and config bootstrap."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from cleave.config import (
    CleaveConfig,
    RenderOverlayAnimationType,
    RenderOverlayPosition,
    RenderOverlaySlideDirection,
    TimelineFadeGroupConfig,
    TimelineLimiterConfig,
    VIZ_CONFIG_FILENAME,
)
from cleave.config_schema import (
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_PRESET_SWITCHING,
    DEFAULT_PRESET_SWITCHING_TRIGGER,
    DEFAULT_PRESET_DURATION,
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_EASTER_EGG,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_TIMELINE_FADES_ENABLED,
    DEFAULT_TIMELINE_FADE_IN,
    DEFAULT_TIMELINE_FADE_OUT,
    DEFAULT_TIMELINE_CROSSFADE,
    DEFAULT_TIMELINE_PLACEMENT_SNAP,
    DEFAULT_VISUAL_LIMITER_ENABLED,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
    DEFAULT_VISUAL_LIMITER_RATIO,
    DEFAULT_VISUAL_LIMITER_RELEASE,
    HighlightRolloffApplyMode,
    HighlightRolloffCurve,
    PresetSwitchingMode,
    PresetSwitchingTrigger,
    TimelinePlacementSnap,
    default_render_overlay_animation_runtime_values,
    default_render_overlay_closing_animation_runtime_values,
    default_render_overlay_card_runtime_values,
    default_render_overlays_runtime_values,
    default_highlight_rolloff_runtime_values,
    default_chroma_boost_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.extract import StemSource
from cleave.preset_playlist import PresetPlaylist, preset_browse_floor
from cleave.projectm_health import PresetSkipNotifyTracker, ProjectMLogNotifyTracker
from cleave.timeline import SlotCue, TimelineLane, copy_lane, empty_lane
from cleave.blend_modes import BlendMode
from cleave.timeline_presets.characters import DEFAULT_TIMELINE_PRESET_KIND
from cleave.timeline_presets.conductor import DEFAULT_TIMELINE_PRESET_CONDUCTOR
from cleave.timeline_presets.crescendo import CrescendoTarget
from cleave.timeline_presets.cue_snap import (
    DEFAULT_TIMELINE_PRESET_CUE_SNAP,
    TimelinePresetCueSnap,
)
from cleave.timeline_presets.density import (
    DEFAULT_TIMELINE_PRESET_DENSITY,
    TimelinePresetDensity,
)
from cleave.timeline_presets.repopulate import (
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    TimelinePresetRepopulate,
)
from cleave.timeline_presets.song_marker_snap import (
    DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP,
    TimelinePresetSongMarkerSnap,
)
from cleave.timeline_presets.timeline_cuts import (
    DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS,
    TimelinePresetTimelineCuts,
)


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
class RenderOverlayAnimationRuntime:
    type: RenderOverlayAnimationType
    slide_direction: RenderOverlaySlideDirection
    appear_at: float
    display_time: float


@dataclass
class RenderOverlayClosingAnimationRuntime:
    type: RenderOverlayAnimationType
    slide_direction: RenderOverlaySlideDirection
    disappear_at: float
    display_time: float


def default_render_overlay_animation_runtime() -> RenderOverlayAnimationRuntime:
    return RenderOverlayAnimationRuntime(
        **default_render_overlay_animation_runtime_values()
    )


def default_render_overlay_closing_animation_runtime() -> (
    RenderOverlayClosingAnimationRuntime
):
    return RenderOverlayClosingAnimationRuntime(
        **default_render_overlay_closing_animation_runtime_values()
    )


@dataclass
class RenderOverlayCardRuntime:
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
    animation: RenderOverlayAnimationRuntime | RenderOverlayClosingAnimationRuntime
    animation_expanded: bool = False


@dataclass
class RenderOverlaysRuntime:
    expanded: bool
    opening_card: RenderOverlayCardRuntime
    closing_card: RenderOverlayCardRuntime
    locked: bool = False


def _card_runtime_from_values(values: dict[str, Any]) -> RenderOverlayCardRuntime:
    values = dict(values)
    animation_values = dict(values.pop("animation"))
    if "appear_at" in animation_values:
        animation: RenderOverlayAnimationRuntime | RenderOverlayClosingAnimationRuntime = (
            RenderOverlayAnimationRuntime(**animation_values)
        )
    else:
        animation = RenderOverlayClosingAnimationRuntime(**animation_values)
    return RenderOverlayCardRuntime(animation=animation, **values)


def default_render_overlay_card_runtime(
    *, closing: bool = False
) -> RenderOverlayCardRuntime:
    return _card_runtime_from_values(
        default_render_overlay_card_runtime_values(closing=closing)
    )


def default_render_overlays_runtime() -> RenderOverlaysRuntime:
    values = default_render_overlays_runtime_values()
    return RenderOverlaysRuntime(
        expanded=values["expanded"],
        opening_card=_card_runtime_from_values(dict(values["opening_card"])),
        closing_card=_card_runtime_from_values(dict(values["closing_card"])),
        locked=values["locked"],
    )


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
class TimelineFadeGroupRuntime:
    enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_FADE_OUT
    crossfade: bool = DEFAULT_TIMELINE_CROSSFADE


def default_timeline_fade_group_runtime() -> TimelineFadeGroupRuntime:
    return TimelineFadeGroupRuntime()


@dataclass
class VisualLimiterRuntime:
    enabled: bool = DEFAULT_VISUAL_LIMITER_ENABLED
    threshold: float = DEFAULT_VISUAL_LIMITER_THRESHOLD
    ratio: float = DEFAULT_VISUAL_LIMITER_RATIO
    release: float = DEFAULT_VISUAL_LIMITER_RELEASE


def default_visual_limiter_runtime() -> VisualLimiterRuntime:
    return VisualLimiterRuntime()


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
    record_baseline: dict[str, float] = field(default_factory=dict)
    record_start_sec: float | None = None
    record_slot_start_sec: dict[str, float] = field(default_factory=dict)
    record_high_water_mark: float | None = None
    preview_active: bool = False
    monitor: dict[str, bool] = field(default_factory=dict)
    override_slots: set[str] = field(default_factory=set)
    override_visible: dict[str, bool] = field(default_factory=dict)
    arm_flash_start_ms: dict[str, int] = field(default_factory=dict)
    selected_cue_t: dict[str, float] = field(default_factory=dict)
    selected_cue_flash_start_ms: int | None = None
    bar_phase_offset: int = 0
    show_bar_grid: bool = False
    beat_bar_grid_expanded: bool = False
    snap_cues_expanded: bool = False
    placement_snap: TimelinePlacementSnap = DEFAULT_TIMELINE_PLACEMENT_SNAP
    cuts_expanded: bool = False
    timeline_presets_expanded: bool = False
    timeline_preset_kind: str = DEFAULT_TIMELINE_PRESET_KIND
    timeline_preset_crescendo: CrescendoTarget | None = None
    timeline_preset_density: TimelinePresetDensity = DEFAULT_TIMELINE_PRESET_DENSITY
    timeline_preset_cue_snap: TimelinePresetCueSnap = DEFAULT_TIMELINE_PRESET_CUE_SNAP
    timeline_preset_song_marker_snap: TimelinePresetSongMarkerSnap = (
        DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP
    )
    timeline_preset_timeline_cuts: TimelinePresetTimelineCuts = (
        DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS
    )
    timeline_preset_repopulate: TimelinePresetRepopulate = (
        DEFAULT_TIMELINE_PRESET_REPOPULATE
    )
    timeline_preset_conductor: bool = DEFAULT_TIMELINE_PRESET_CONDUCTOR
    hard_cut_fades: TimelineFadeGroupRuntime = field(
        default_factory=default_timeline_fade_group_runtime
    )
    soft_cut_fades: TimelineFadeGroupRuntime = field(
        default_factory=default_timeline_fade_group_runtime
    )
    limiter: VisualLimiterRuntime = field(default_factory=default_visual_limiter_runtime)


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


EditorMode = Literal["visualizer", "preset_curation"]

EDITOR_MODES: tuple[EditorMode, ...] = ("visualizer", "preset_curation")
EDITOR_MODE_PANEL_LABELS: dict[EditorMode, str] = {
    "visualizer": "visualizer",
    "preset_curation": "preset curation",
}


@dataclass
class SettingsRuntime:
    expanded: bool = False
    ui_expanded: bool = False
    latency_compensation_expanded: bool = False
    editor_mode: EditorMode = "visualizer"
    # Staged panel selection; Left/Right cycles, Enter commits.
    editor_mode_selection: EditorMode = "visualizer"


@dataclass
class LayerRuntime:
    playlist: PresetPlaylist
    browse_floor: Path
    stem: StemSource
    opacity_pct: int = 100
    effects: dict[str, dict[str, int]] = field(default_factory=dict)
    effects_expanded: bool = False
    blend_mode: BlendMode = "black-key"
    beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY
    enabled: bool = True
    expanded: bool = False
    locked: bool = False
    preset_switching: PresetSwitchingMode = DEFAULT_PRESET_SWITCHING
    preset_switching_trigger: PresetSwitchingTrigger = DEFAULT_PRESET_SWITCHING_TRIGGER
    preset_duration: float = DEFAULT_PRESET_DURATION
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED
    easter_egg: float = DEFAULT_EASTER_EGG
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN
    preset_list: list[str] = field(default_factory=list)  # absolute paths
    preset_list_expanded: bool = False
    # Playing auto-switch preset (panel display); not persisted. Mirrored from
    # StemLayer.auto_preset_path while the live layer map is available.
    auto_preset_path: Path | None = None


@dataclass
class TuningSession:
    layer_z_order: list[str]
    layers: dict[str, LayerRuntime] = field(default_factory=dict)
    solo_slot: str | None = None
    render_overlays: RenderOverlaysRuntime = field(
        default_factory=default_render_overlays_runtime
    )
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
    projectm_log_notify_tracker: ProjectMLogNotifyTracker = field(
        default_factory=ProjectMLogNotifyTracker
    )


def _card_runtime_from_cfg(card: Any) -> RenderOverlayCardRuntime:
    anim = card.animation
    if hasattr(anim, "appear_at"):
        animation: RenderOverlayAnimationRuntime | RenderOverlayClosingAnimationRuntime = (
            replace(
                default_render_overlay_animation_runtime(),
                type=anim.type,
                slide_direction=anim.slide_direction,
                appear_at=anim.appear_at,
                display_time=anim.display_time,
            )
        )
        closing = False
    else:
        animation = replace(
            default_render_overlay_closing_animation_runtime(),
            type=anim.type,
            slide_direction=anim.slide_direction,
            disappear_at=anim.disappear_at,
            display_time=anim.display_time,
        )
        closing = True
    return replace(
        default_render_overlay_card_runtime(closing=closing),
        enabled=card.enabled,
        position=card.position,
        title_font_size=card.title.font_size,
        title_font=card.title.font,
        title_margin_bottom=card.title.margin_bottom,
        body_font_size=card.body.font_size,
        body_font=card.body.font,
        opacity_pct=int(round(card.background.opacity * 100)),
        border_width=card.background.border.width,
        animation=animation,
    )


def render_overlays_runtime_from_cfg(cfg: CleaveConfig) -> RenderOverlaysRuntime:
    overlays = cfg.render.overlays if cfg.render is not None else None
    if overlays is not None:
        return replace(
            default_render_overlays_runtime(),
            opening_card=_card_runtime_from_cfg(overlays.opening_card),
            closing_card=_card_runtime_from_cfg(overlays.closing_card),
            locked=overlays.locked,
        )
    return default_render_overlays_runtime()


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


def _fade_group_runtime_from_cfg(
    group: TimelineFadeGroupConfig | None,
) -> TimelineFadeGroupRuntime:
    if group is None:
        return TimelineFadeGroupRuntime()
    return TimelineFadeGroupRuntime(
        enabled=group.enabled,
        fade_in=group.fade_in,
        fade_out=group.fade_out,
        crossfade=group.crossfade,
    )


def _limiter_runtime_from_cfg(
    limiter: TimelineLimiterConfig | None,
) -> VisualLimiterRuntime:
    if limiter is None:
        return VisualLimiterRuntime()
    return VisualLimiterRuntime(
        enabled=limiter.enabled,
        threshold=limiter.threshold,
        ratio=limiter.ratio,
        release=limiter.release,
    )


def timeline_runtime_from_cfg(cfg: CleaveConfig) -> TimelineRuntime:
    timeline = cfg.timeline
    enabled = True if timeline is None else timeline.enabled
    locked = False if timeline is None else timeline.locked
    source_lanes = {} if timeline is None else timeline.lanes
    cuts = None if timeline is None else timeline.cuts
    placement_snap = (
        DEFAULT_TIMELINE_PLACEMENT_SNAP
        if timeline is None
        else timeline.placement_snap
    )
    preset = None if timeline is None else timeline.preset
    limiter_cfg = None if timeline is None else timeline.limiter
    preset_kind = (
        DEFAULT_TIMELINE_PRESET_KIND if preset is None else preset.character
    )
    preset_crescendo = None if preset is None else preset.crescendo
    preset_density = (
        DEFAULT_TIMELINE_PRESET_DENSITY if preset is None else preset.density
    )
    preset_cue_snap = (
        DEFAULT_TIMELINE_PRESET_CUE_SNAP if preset is None else preset.cue_snap
    )
    preset_song_marker_snap = (
        DEFAULT_TIMELINE_PRESET_SONG_MARKER_SNAP
        if preset is None
        else preset.song_marker_snap
    )
    preset_timeline_cuts = (
        DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS
        if preset is None
        else preset.timeline_cuts
    )
    preset_repopulate = (
        DEFAULT_TIMELINE_PRESET_REPOPULATE
        if preset is None
        else preset.repopulate
    )
    preset_conductor = (
        DEFAULT_TIMELINE_PRESET_CONDUCTOR if preset is None else preset.conductor
    )
    lanes: dict[str, TimelineLane] = {}
    for slot in cfg.layer_z_order:
        if slot in source_lanes:
            lanes[slot] = copy_lane(source_lanes[slot])
        else:
            lanes[slot] = empty_lane()
    limiter = _limiter_runtime_from_cfg(limiter_cfg)
    if cuts is None:
        return TimelineRuntime(
            enabled=enabled,
            locked=locked,
            lanes=lanes,
            placement_snap=placement_snap,
            timeline_preset_kind=preset_kind,
            timeline_preset_crescendo=preset_crescendo,
            timeline_preset_density=preset_density,
            timeline_preset_cue_snap=preset_cue_snap,
            timeline_preset_song_marker_snap=preset_song_marker_snap,
            timeline_preset_timeline_cuts=preset_timeline_cuts,
            timeline_preset_repopulate=preset_repopulate,
            timeline_preset_conductor=preset_conductor,
            limiter=limiter,
        )
    return TimelineRuntime(
        enabled=enabled,
        locked=locked,
        lanes=lanes,
        placement_snap=placement_snap,
        timeline_preset_kind=preset_kind,
        timeline_preset_crescendo=preset_crescendo,
        timeline_preset_density=preset_density,
        timeline_preset_cue_snap=preset_cue_snap,
        timeline_preset_song_marker_snap=preset_song_marker_snap,
        timeline_preset_timeline_cuts=preset_timeline_cuts,
        timeline_preset_repopulate=preset_repopulate,
        timeline_preset_conductor=preset_conductor,
        hard_cut_fades=_fade_group_runtime_from_cfg(cuts.hard),
        soft_cut_fades=_fade_group_runtime_from_cfg(cuts.soft),
        limiter=limiter,
    )


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
        render_overlays=render_overlays_runtime_from_cfg(cfg),
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
                preset_switching_trigger=layer_cfg.preset_switching_trigger,
                preset_duration=layer_cfg.preset_duration,
                soft_cut_duration=layer_cfg.soft_cut_duration,
                hard_cut_duration=layer_cfg.hard_cut_duration,
                hard_cut_sensitivity=layer_cfg.hard_cut_sensitivity,
                hard_cut_enabled=layer_cfg.hard_cut_enabled,
                easter_egg=layer_cfg.easter_egg,
                preset_start_clean=layer_cfg.preset_start_clean,
                preset_list=[
                    path.as_posix() for path in layer_cfg.preset_switching_list
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
