"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config import (
    RenderOverlayAnimationType,
    RenderOverlayPosition,
    RenderOverlaySlideDirection,
)
from cleave.config_schema import (
    DEFAULT_CAST_ROLES_DEFAULT_ROLE,
    DEFAULT_CAST_ROLES_TIMELINE_BEHAVIOUR,
    DEFAULT_CHROMA_BOOST_APPLY_MODE,
    DEFAULT_CHROMA_BOOST_VARIANT,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_EASTER_EGG,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_DURATION,
    DEFAULT_PRESET_SWITCHING_SHUFFLE,
    DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT,
    DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE,
    DEFAULT_RENDER_OVERLAY_APPEAR_AT,
    DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT,
    DEFAULT_RENDER_OVERLAY_DISPLAY_TIME,
    DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION,
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_VISUAL_LIMITER_ENABLED,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
    DEFAULT_VISUAL_LIMITER_RELEASE,
    CastRolesTimelineBehaviour,
    default_render_overlay_card_runtime_values,
    default_render_overlays_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.cue_roles import CueRole
from cleave.extract import StemSource
from cleave.preset_curation import PresetCurationIndex
from cleave.preset_playlist import (
    PresetPlaylist,
    preset_filename_display,
    scan_preset_playlist,
)
from cleave.timeline_presets.conductor import DEFAULT_TIMELINE_PRESET_CONDUCTOR
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.timeline_presets.crescendo import CrescendoTarget
from cleave.timeline_presets.density import (
    DEFAULT_TIMELINE_PRESET_DENSITY,
    TimelinePresetDensity,
)
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.session import LayerRuntime, TuningSession, config_path_display
from cleave.viz.user_presets import user_preset_item_display_name

if TYPE_CHECKING:
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.layer import StemLayer
    from cleave.viz.row_layout import RowLayout, RowLayoutFrame

_RO_CARD_DEFAULTS = default_render_overlay_card_runtime_values(closing=False)
_RO_OVERLAYS_DEFAULTS = default_render_overlays_runtime_values()
_RO_POST_FX_DEFAULTS = default_render_post_fx_runtime_values()


@dataclass
class TrackBlock:
    stem: StemSource
    preset_dir_label: str
    preset_label: str
    blend_mode: str
    opacity_pct: int
    beat_sensitivity: float
    effects: dict[str, dict[str, int]]
    effects_expanded: bool = False
    enabled: bool = True
    visible: bool = True
    expanded: bool = False
    locked: bool = False
    preset_empty: bool = False
    preset_switching: str = "none"
    preset_switching_rotation_set: str = "directory"
    cast_roles_timeline_behaviour: CastRolesTimelineBehaviour = (
        DEFAULT_CAST_ROLES_TIMELINE_BEHAVIOUR
    )
    cast_roles_default_role: CueRole = DEFAULT_CAST_ROLES_DEFAULT_ROLE
    preset_switching_shuffle: bool = DEFAULT_PRESET_SWITCHING_SHUFFLE
    preset_switching_shuffle_salt: int = DEFAULT_PRESET_SWITCHING_SHUFFLE_SALT
    preset_duration: float = DEFAULT_PRESET_DURATION
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED
    easter_egg: float = DEFAULT_EASTER_EGG
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN
    user_presets: list[str] = field(default_factory=list)
    user_preset_labels: list[str] = field(default_factory=list)
    user_presets_expanded: bool = False


@dataclass
class RenderOverlayAnimationBlock:
    expanded: bool = False
    type: RenderOverlayAnimationType = DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE
    slide_direction: RenderOverlaySlideDirection = (
        DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION
    )
    appear_at: float = DEFAULT_RENDER_OVERLAY_APPEAR_AT
    display_time: float = DEFAULT_RENDER_OVERLAY_DISPLAY_TIME


@dataclass
class RenderOverlayClosingAnimationBlock:
    expanded: bool = False
    type: RenderOverlayAnimationType = DEFAULT_RENDER_OVERLAY_ANIMATION_TYPE
    slide_direction: RenderOverlaySlideDirection = (
        DEFAULT_RENDER_OVERLAY_SLIDE_DIRECTION
    )
    disappear_at: float = DEFAULT_RENDER_OVERLAY_DISAPPEAR_AT
    display_time: float = DEFAULT_RENDER_OVERLAY_DISPLAY_TIME


@dataclass
class RenderOverlayCardBlock:
    enabled: bool = _RO_CARD_DEFAULTS["enabled"]
    expanded: bool = _RO_CARD_DEFAULTS["expanded"]
    position: RenderOverlayPosition = _RO_CARD_DEFAULTS["position"]
    title_expanded: bool = _RO_CARD_DEFAULTS["title_expanded"]
    body_expanded: bool = _RO_CARD_DEFAULTS["body_expanded"]
    title_font_size: int = _RO_CARD_DEFAULTS["title_font_size"]
    title_font: str = _RO_CARD_DEFAULTS["title_font"]
    title_margin_bottom: int = _RO_CARD_DEFAULTS["title_margin_bottom"]
    body_font_size: int = _RO_CARD_DEFAULTS["body_font_size"]
    body_font: str = _RO_CARD_DEFAULTS["body_font"]
    opacity_pct: int = _RO_CARD_DEFAULTS["opacity_pct"]
    border_width: int = _RO_CARD_DEFAULTS["border_width"]
    animation: RenderOverlayAnimationBlock | RenderOverlayClosingAnimationBlock = field(
        default_factory=RenderOverlayAnimationBlock
    )


@dataclass
class RenderOverlaysBlock:
    expanded: bool = _RO_OVERLAYS_DEFAULTS["expanded"]
    opening_card: RenderOverlayCardBlock = field(
        default_factory=RenderOverlayCardBlock
    )
    closing_card: RenderOverlayCardBlock = field(
        default_factory=lambda: RenderOverlayCardBlock(
            animation=RenderOverlayClosingAnimationBlock()
        )
    )
    solo: bool = False
    locked: bool = False


@dataclass
class HighlightRolloffBlock:
    expanded: bool = False
    mode: str = DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE
    curve: str = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE
    threshold_pct: int = 78
    ceiling_pct: int = 65
    strength_pct: int = 70
    softness_pct: int = 40
    desaturation_pct: int = 30


@dataclass
class ChromaBoostBlock:
    expanded: bool = False
    mode: str = DEFAULT_CHROMA_BOOST_APPLY_MODE
    variant: str = DEFAULT_CHROMA_BOOST_VARIANT
    amount_pct: int = 25


@dataclass
class RenderPostFxBlock:
    enabled: bool = _RO_POST_FX_DEFAULTS["enabled"]
    expanded: bool = _RO_POST_FX_DEFAULTS["expanded"]
    fade_in: float = _RO_POST_FX_DEFAULTS["fade_in"]
    fade_out: float = _RO_POST_FX_DEFAULTS["fade_out"]
    highlight_rolloff: HighlightRolloffBlock = field(
        default_factory=HighlightRolloffBlock
    )
    chroma_boost: ChromaBoostBlock = field(default_factory=ChromaBoostBlock)
    solo: bool = False
    locked: bool = False


@dataclass
class TimelineFadeGroupBlock:
    enabled: bool = False
    fade_in: float = 2.0
    fade_out: float = 2.0


@dataclass
class VisualLimiterBlock:
    enabled: bool = DEFAULT_VISUAL_LIMITER_ENABLED
    threshold: float = DEFAULT_VISUAL_LIMITER_THRESHOLD
    release: float = DEFAULT_VISUAL_LIMITER_RELEASE


@dataclass
class RenderTimelineBlock:
    enabled: bool = False
    expanded: bool = False
    bar_phase_offset: int = 0
    show_bar_grid: bool = False
    beat_bar_grid_expanded: bool = False
    placement_snap: str = "beat"
    fades_expanded: bool = False
    timeline_presets_expanded: bool = False
    timeline_preset_kind: str = "breathing"
    timeline_preset_crescendo: CrescendoTarget | None = None
    timeline_preset_density: TimelinePresetDensity = DEFAULT_TIMELINE_PRESET_DENSITY
    timeline_preset_conductor: bool = DEFAULT_TIMELINE_PRESET_CONDUCTOR
    song_marker_fades: TimelineFadeGroupBlock = field(
        default_factory=TimelineFadeGroupBlock
    )
    standard_cue_fades: TimelineFadeGroupBlock = field(
        default_factory=TimelineFadeGroupBlock
    )
    limiter: VisualLimiterBlock = field(default_factory=VisualLimiterBlock)
    locked: bool = False
    song_markers_expanded: bool = False
    song_marker_times: tuple[float, ...] = ()


@dataclass
class SettingsBlock:
    expanded: bool = False
    ui_expanded: bool = False
    latency_compensation_expanded: bool = False
    editor_mode: str = "visualizer"
    editor_mode_selection: str = "visualizer"
    preview_quality: str = "balanced"
    ui_width_mode: str = DEFAULT_UI_WIDTH_MODE
    ui_width: int = DEFAULT_UI_WIDTH
    ui_fade: float = DEFAULT_UI_FADE_SEC
    residual_latency_ms: int = 0


@dataclass
class TuningViewState:
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    paused: bool
    position_sec: float
    focus_cursor: FocusCursor
    move_mode_slot: str | None
    persistent_notification_message: str | None = None
    notification_message: str | None = None
    notification_remaining_sec: float = 0.0
    allow_overwrite: bool = True
    active_config_label: str = "cleave-viz.yaml"
    config_dirty: bool = False
    solo_slot: str | None = None
    solo_active: bool = False
    render_overlays: RenderOverlaysBlock = field(default_factory=RenderOverlaysBlock)
    render_post_fx: RenderPostFxBlock = field(
        default_factory=RenderPostFxBlock
    )
    render_timeline: RenderTimelineBlock = field(
        default_factory=RenderTimelineBlock
    )
    settings: SettingsBlock = field(default_factory=SettingsBlock)
    timeline_recording: bool = False
    timeline_override_active: bool = False
    help_visible: bool = False
    fps: float | None = None
    layout: RowLayout | None = field(default=None, repr=False)
    layout_frame: RowLayoutFrame | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        from cleave.viz.row_layout import RowLayout, build_layout_frame

        if self.layout is None:
            object.__setattr__(self, "layout", RowLayout.build(self))
        if self.layout_frame is None:
            object.__setattr__(
                self, "layout_frame", build_layout_frame(self.layout, self)
            )

    @property
    def focus_descriptor(self) -> RowDescriptor:
        from cleave.viz.focus_nav import cursor_main_descriptor

        return self.layout.resolve_navigable(
            cursor_main_descriptor(self.focus_cursor), self
        )

    @focus_descriptor.setter
    def focus_descriptor(self, descriptor: RowDescriptor) -> None:
        from cleave.viz.focus_nav import MainFocus

        object.__setattr__(self, "focus_cursor", MainFocus(descriptor))

    @property
    def timeline_submenu_focused(self) -> bool:
        from cleave.viz.focus_nav import cursor_timeline_submenu_focused

        return cursor_timeline_submenu_focused(self.focus_cursor)

    @timeline_submenu_focused.setter
    def timeline_submenu_focused(self, value: bool) -> None:
        from cleave.viz.focus_nav import (
            MainFocus,
            TimelineFocus,
            cursor_timeline_row,
        )

        if value:
            row = (
                cursor_timeline_row(self.focus_cursor)
                if isinstance(self.focus_cursor, TimelineFocus)
                else 0
            )
            object.__setattr__(self, "focus_cursor", TimelineFocus(row))
        elif isinstance(self.focus_cursor, TimelineFocus):
            object.__setattr__(
                self,
                "focus_cursor",
                MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)),
            )

    @property
    def focus_index(self) -> int:
        if self.layout_frame is not None:
            from cleave.viz.focus_nav import cursor_main_descriptor
            from cleave.viz.row_layout import resolve_navigable_descriptor

            focus_desc = cursor_main_descriptor(self.focus_cursor)
            resolved = resolve_navigable_descriptor(
                focus_desc, self.layout_frame.navigable_descriptors
            )
            return self.layout.find_descriptor(resolved)
        resolved = self.layout.resolve_navigable(self.focus_descriptor, self)
        return self.layout.find_descriptor(resolved)


def view_state_structure_signature(
    session: TuningSession,
    config_save: ConfigSaveController,
    *,
    notification_active: bool,
    persistent_notification_active: bool = False,
) -> str:
    layers: dict[str, object] = {}
    for slot in session.layer_z_order:
        layer = session.layers[slot]
        playlist = layer.playlist
        layers[slot] = {
            "expanded": layer.expanded,
            "effects_expanded": layer.effects_expanded,
            "user_presets_expanded": layer.user_presets_expanded,
            "preset_switching": layer.preset_switching,
            "preset_switching_rotation_set": layer.preset_switching_rotation_set,
            "cast_roles_timeline_behaviour": layer.cast_roles_timeline_behaviour,
            "cast_roles_default_role": layer.cast_roles_default_role,
            "preset_switching_shuffle": layer.preset_switching_shuffle,
            "preset_duration": layer.preset_duration,
            "soft_cut_duration": layer.soft_cut_duration,
            "hard_cut_duration": layer.hard_cut_duration,
            "hard_cut_sensitivity": layer.hard_cut_sensitivity,
            "hard_cut_enabled": layer.hard_cut_enabled,
            "easter_egg": layer.easter_egg,
            "preset_start_clean": layer.preset_start_clean,
            "effects": sorted(layer.effects.keys()),
            "user_presets": list(layer.user_presets),
            "playlist": {
                "current_dir": str(playlist.current_dir),
                "paths": [str(path) for path in playlist.paths],
                "index": playlist.index,
            },
            "auto_preset_path": (
                None
                if layer.auto_preset_path is None
                else str(layer.auto_preset_path)
            ),
        }
    ro = session.render_overlays
    pp = session.render_post_fx
    tl = session.timeline
    payload = {
        "layer_z_order": list(session.layer_z_order),
        "settings": {
            "expanded": session.settings.expanded,
            "ui_expanded": session.settings.ui_expanded,
            "latency_compensation_expanded": session.settings.latency_compensation_expanded,
            "editor_mode": session.settings.editor_mode,
        },
        "notification_active": notification_active,
        "persistent_notification_active": persistent_notification_active,
        "layers": layers,
        "render_overlays": {
            "expanded": ro.expanded,
            "opening_card": {
                "enabled": ro.opening_card.enabled,
                "expanded": ro.opening_card.expanded,
                "title_expanded": ro.opening_card.title_expanded,
                "body_expanded": ro.opening_card.body_expanded,
                "animation_expanded": ro.opening_card.animation_expanded,
                "animation_type": ro.opening_card.animation.type,
            },
            "closing_card": {
                "enabled": ro.closing_card.enabled,
                "expanded": ro.closing_card.expanded,
                "title_expanded": ro.closing_card.title_expanded,
                "body_expanded": ro.closing_card.body_expanded,
                "animation_expanded": ro.closing_card.animation_expanded,
                "animation_type": ro.closing_card.animation.type,
            },
        },
        "render_post_fx": {
            "enabled": pp.enabled,
            "expanded": pp.expanded,
            "highlight_rolloff_expanded": pp.highlight_rolloff_expanded,
            "highlight_rolloff_mode": pp.highlight_rolloff.mode,
            "chroma_boost_expanded": pp.chroma_boost_expanded,
            "chroma_boost_mode": pp.chroma_boost.mode,
        },
        "render_timeline": {
            "enabled": tl.enabled,
            "panel_open": tl.panel_open,
            "song_markers_expanded": session.song_markers.expanded,
            "song_marker_count": len(session.song_markers.times),
            "beat_bar_grid_expanded": tl.beat_bar_grid_expanded,
            "fades_expanded": tl.fades_expanded,
            "timeline_presets_expanded": tl.timeline_presets_expanded,
            "song_marker_fades_enabled": tl.song_marker_fades.enabled,
            "standard_cue_fades_enabled": tl.standard_cue_fades.enabled,
            "visual_limiter_enabled": tl.limiter.enabled,
        },
        "timeline": {"enabled": tl.enabled},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class _ViewStateStructure:
    signature: str
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    settings: SettingsBlock
    render_overlays: RenderOverlaysBlock
    render_post_fx: RenderPostFxBlock
    render_timeline: RenderTimelineBlock
    layout: RowLayout


def _card_block_from_runtime(card, *, closing: bool) -> RenderOverlayCardBlock:
    anim = card.animation
    if closing:
        animation: RenderOverlayAnimationBlock | RenderOverlayClosingAnimationBlock = (
            RenderOverlayClosingAnimationBlock(
                expanded=card.animation_expanded,
                type=anim.type,
            )
        )
    else:
        animation = RenderOverlayAnimationBlock(
            expanded=card.animation_expanded,
            type=anim.type,
        )
    return RenderOverlayCardBlock(
        enabled=card.enabled,
        expanded=card.expanded,
        title_expanded=card.title_expanded,
        body_expanded=card.body_expanded,
        animation=animation,
    )


class TuningViewStateBuilder:
    """Build TuningViewState from session and UI state."""

    def __init__(
        self,
        session: TuningSession,
        playback: PlaybackState,
        duration_sec: float,
        preset_root,
        curation_index: PresetCurationIndex,
        *,
        get_focus_cursor: Callable[[], FocusCursor],
        get_move_mode_slot: Callable[[], str | None],
        config_save: ConfigSaveController,
        get_notification: Callable[[], PanelNotificationActive],
        layers_by_slot: dict[str, StemLayer] | None = None,
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self.preset_root = preset_root
        self._curation_index = curation_index
        self._get_focus_cursor = get_focus_cursor
        self._get_move_mode_slot = get_move_mode_slot
        self._config_save = config_save
        self._get_notification = get_notification
        self._layers_by_slot = layers_by_slot
        self._auto_display_cache: dict[Path, PresetPlaylist] = {}
        self._structure: _ViewStateStructure | None = None

    def _sync_auto_preset_paths(self) -> None:
        """Mirror StemLayer playing paths onto session for panel display."""
        if not self._layers_by_slot:
            return
        for slot, stem in self._layers_by_slot.items():
            runtime = self.session.layers.get(slot)
            if runtime is not None:
                runtime.auto_preset_path = stem.auto_preset_path

    def _user_preset_basenames(self) -> set[str]:
        names: set[str] = set()
        for layer in self.session.layers.values():
            for path in layer.user_presets:
                names.add(Path(path).name)
        return names

    def _display_playlist(self, layer: LayerRuntime) -> PresetPlaylist:
        """Playlist for dir/file rows: playing auto-switch preset when set."""
        auto = layer.auto_preset_path
        if auto is None:
            return layer.playlist
        cached = self._auto_display_cache.get(auto)
        if cached is not None:
            return cached
        try:
            playlist = scan_preset_playlist(auto)
        except (OSError, ValueError):
            return layer.playlist
        self._auto_display_cache[auto] = playlist
        return playlist

    def _preset_label(
        self, playlist: PresetPlaylist, *, user_names: set[str]
    ) -> str:
        label = preset_filename_display(playlist)
        if playlist.current is not None:
            name = playlist.current.name
            label += self._curation_index.marker(name, user=name in user_names)
        return label

    def _user_preset_labels(self, paths: list[str]) -> list[str]:
        return [
            user_preset_item_display_name(paths, i)
            + self._curation_index.marker(Path(paths[i]).name)
            for i in range(len(paths))
        ]

    def _build_structure(
        self,
        *,
        signature: str,
        notification_active: bool,
        persistent_notification_active: bool,
        user_names: set[str],
    ) -> _ViewStateStructure:
        from cleave.viz.focus_nav import MainFocus

        layer_z_order = tuple(self.session.layer_z_order)
        tracks: dict[str, TrackBlock] = {}
        for slot in layer_z_order:
            layer = self.session.layers[slot]
            display = self._display_playlist(layer)
            tracks[slot] = TrackBlock(
                stem=layer.stem,
                preset_dir_label=display.directory_display_label(
                    self.preset_root,
                    browse_floor=layer.browse_floor,
                ),
                preset_label=self._preset_label(
                    display, user_names=user_names
                ),
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                effects=dict(layer.effects),
                effects_expanded=layer.effects_expanded,
                beat_sensitivity=layer.beat_sensitivity,
                enabled=layer.enabled,
                visible=layer.enabled,
                expanded=layer.expanded,
                locked=layer.locked,
                preset_empty=not display.paths,
                preset_switching=layer.preset_switching,
                preset_switching_rotation_set=layer.preset_switching_rotation_set,
                cast_roles_timeline_behaviour=layer.cast_roles_timeline_behaviour,
                cast_roles_default_role=layer.cast_roles_default_role,
                preset_switching_shuffle=layer.preset_switching_shuffle,
                preset_switching_shuffle_salt=layer.preset_switching_shuffle_salt,
                preset_duration=layer.preset_duration,
                soft_cut_duration=layer.soft_cut_duration,
                hard_cut_duration=layer.hard_cut_duration,
                hard_cut_sensitivity=layer.hard_cut_sensitivity,
                hard_cut_enabled=layer.hard_cut_enabled,
                easter_egg=layer.easter_egg,
                preset_start_clean=layer.preset_start_clean,
                user_presets=list(layer.user_presets),
                user_preset_labels=self._user_preset_labels(list(layer.user_presets)),
                user_presets_expanded=layer.user_presets_expanded,
            )

        ro = self.session.render_overlays
        pp = self.session.render_post_fx
        tl = self.session.timeline
        settings = SettingsBlock(
            expanded=self.session.settings.expanded,
            ui_expanded=self.session.settings.ui_expanded,
            latency_compensation_expanded=self.session.settings.latency_compensation_expanded,
            editor_mode=self.session.settings.editor_mode,
            editor_mode_selection=self.session.settings.editor_mode_selection,
        )
        render_overlays = RenderOverlaysBlock(
            expanded=ro.expanded,
            opening_card=_card_block_from_runtime(ro.opening_card, closing=False),
            closing_card=_card_block_from_runtime(ro.closing_card, closing=True),
            locked=ro.locked,
        )
        render_post_fx = RenderPostFxBlock(
            enabled=pp.enabled,
            expanded=pp.expanded,
            highlight_rolloff=HighlightRolloffBlock(
                expanded=pp.highlight_rolloff_expanded,
                mode=pp.highlight_rolloff.mode,
                curve=pp.highlight_rolloff.curve,
                threshold_pct=pp.highlight_rolloff.threshold_pct,
                ceiling_pct=pp.highlight_rolloff.ceiling_pct,
                strength_pct=pp.highlight_rolloff.strength_pct,
                softness_pct=pp.highlight_rolloff.softness_pct,
                desaturation_pct=pp.highlight_rolloff.desaturation_pct,
            ),
            chroma_boost=ChromaBoostBlock(
                expanded=pp.chroma_boost_expanded,
                mode=pp.chroma_boost.mode,
                variant=pp.chroma_boost.variant,
                amount_pct=pp.chroma_boost.amount_pct,
            ),
        )
        render_timeline = RenderTimelineBlock(
            enabled=tl.enabled,
            expanded=tl.panel_open,
            bar_phase_offset=tl.bar_phase_offset,
            show_bar_grid=tl.show_bar_grid,
            beat_bar_grid_expanded=tl.beat_bar_grid_expanded,
            placement_snap=tl.placement_snap,
            fades_expanded=tl.fades_expanded,
            timeline_presets_expanded=tl.timeline_presets_expanded,
            timeline_preset_kind=tl.timeline_preset_kind,
            timeline_preset_crescendo=tl.timeline_preset_crescendo,
            timeline_preset_density=tl.timeline_preset_density,
            timeline_preset_conductor=tl.timeline_preset_conductor,
            song_marker_fades=TimelineFadeGroupBlock(
                enabled=tl.song_marker_fades.enabled,
                fade_in=tl.song_marker_fades.fade_in,
                fade_out=tl.song_marker_fades.fade_out,
            ),
            standard_cue_fades=TimelineFadeGroupBlock(
                enabled=tl.standard_cue_fades.enabled,
                fade_in=tl.standard_cue_fades.fade_in,
                fade_out=tl.standard_cue_fades.fade_out,
            ),
            limiter=VisualLimiterBlock(
                enabled=tl.limiter.enabled,
                threshold=tl.limiter.threshold,
                release=tl.limiter.release,
            ),
            song_markers_expanded=self.session.song_markers.expanded,
            song_marker_times=tuple(self.session.song_markers.times),
        )
        layout_state = TuningViewState(
            layer_z_order=layer_z_order,
            tracks=tracks,
            paused=False,
            position_sec=0.0,
            focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
            move_mode_slot=None,
            persistent_notification_message=(
                "…" if persistent_notification_active else None
            ),
            notification_message="…" if notification_active else None,
            notification_remaining_sec=1.0 if notification_active else 0.0,
            render_overlays=render_overlays,
            render_post_fx=render_post_fx,
            render_timeline=render_timeline,
            settings=settings,
        )
        layout = layout_state.layout
        assert layout is not None
        return _ViewStateStructure(
            signature=signature,
            layer_z_order=layer_z_order,
            tracks=tracks,
            settings=settings,
            render_overlays=render_overlays,
            render_post_fx=render_post_fx,
            render_timeline=render_timeline,
            layout=layout,
        )

    def _patch_tracks(
        self,
        structure: _ViewStateStructure,
        *,
        position_sec: float,
        user_names: set[str],
    ) -> dict[str, TrackBlock]:
        from cleave.viz.layer_visibility import effective_layer_enabled

        tracks: dict[str, TrackBlock] = {}
        for slot in structure.layer_z_order:
            base = structure.tracks[slot]
            layer = self.session.layers[slot]
            display = self._display_playlist(layer)
            visible = effective_layer_enabled(self.session, slot, position_sec)
            tracks[slot] = replace(
                base,
                stem=layer.stem,
                enabled=layer.enabled,
                visible=visible,
                locked=layer.locked,
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                beat_sensitivity=layer.beat_sensitivity,
                preset_switching_shuffle_salt=layer.preset_switching_shuffle_salt,
                preset_label=self._preset_label(
                    display, user_names=user_names
                ),
                user_preset_labels=self._user_preset_labels(list(layer.user_presets)),
                effects=dict(layer.effects),
            )
        return tracks

    def build(
        self,
        *,
        paused: bool,
        position_sec: float | None = None,
        fps: float | None = None,
    ) -> TuningViewState:
        if position_sec is None:
            position_sec = current_sec(self.playback, self.duration_sec)

        self._sync_auto_preset_paths()

        notification = self._get_notification()
        notification_message = notification.message
        notification_remaining_sec = notification.remaining_sec
        persistent_notification_message = notification.persistent_message
        notification_active = bool(
            notification_message and notification_remaining_sec > 0
        )
        persistent_notification_active = bool(persistent_notification_message)
        user_names = self._user_preset_basenames()
        signature = view_state_structure_signature(
            self.session,
            self._config_save,
            notification_active=notification_active,
            persistent_notification_active=persistent_notification_active,
        )
        if self._structure is None or self._structure.signature != signature:
            self._structure = self._build_structure(
                signature=signature,
                notification_active=notification_active,
                persistent_notification_active=persistent_notification_active,
                user_names=user_names,
            )
        structure = self._structure

        tracks = self._patch_tracks(
            structure, position_sec=position_sec, user_names=user_names
        )

        ro = self.session.render_overlays
        pp = self.session.render_post_fx
        tl = self.session.timeline
        opening = ro.opening_card
        closing = ro.closing_card
        state = TuningViewState(
            layer_z_order=structure.layer_z_order,
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_cursor=self._get_focus_cursor(),
            move_mode_slot=self._get_move_mode_slot(),
            persistent_notification_message=persistent_notification_message,
            notification_message=notification_message,
            notification_remaining_sec=notification_remaining_sec,
            allow_overwrite=self._config_save.allow_overwrite(),
            active_config_label=config_path_display(
                self._config_save.active_config_path
            ),
            config_dirty=self._config_save.config_dirty,
            solo_slot=self.session.solo_slot,
            solo_active=self.session.solo_slot is not None,
            render_overlays=replace(
                structure.render_overlays,
                expanded=ro.expanded,
                opening_card=replace(
                    structure.render_overlays.opening_card,
                    enabled=opening.enabled,
                    expanded=opening.expanded,
                    position=opening.position,
                    title_expanded=opening.title_expanded,
                    body_expanded=opening.body_expanded,
                    title_font_size=opening.title_font_size,
                    title_font=opening.title_font,
                    title_margin_bottom=opening.title_margin_bottom,
                    body_font_size=opening.body_font_size,
                    body_font=opening.body_font,
                    opacity_pct=opening.opacity_pct,
                    border_width=opening.border_width,
                    animation=replace(
                        structure.render_overlays.opening_card.animation,
                        expanded=opening.animation_expanded,
                        type=opening.animation.type,
                        slide_direction=opening.animation.slide_direction,
                        appear_at=getattr(opening.animation, "appear_at", 0.0),
                        display_time=opening.animation.display_time,
                    ),
                ),
                closing_card=replace(
                    structure.render_overlays.closing_card,
                    enabled=closing.enabled,
                    expanded=closing.expanded,
                    position=closing.position,
                    title_expanded=closing.title_expanded,
                    body_expanded=closing.body_expanded,
                    title_font_size=closing.title_font_size,
                    title_font=closing.title_font,
                    title_margin_bottom=closing.title_margin_bottom,
                    body_font_size=closing.body_font_size,
                    body_font=closing.body_font,
                    opacity_pct=closing.opacity_pct,
                    border_width=closing.border_width,
                    animation=replace(
                        structure.render_overlays.closing_card.animation,
                        expanded=closing.animation_expanded,
                        type=closing.animation.type,
                        slide_direction=closing.animation.slide_direction,
                        disappear_at=getattr(
                            closing.animation, "disappear_at", 0.0
                        ),
                        display_time=closing.animation.display_time,
                    ),
                ),
                solo=self.session.render_overlay_solo,
                locked=ro.locked,
            ),
            render_post_fx=replace(
                structure.render_post_fx,
                fade_in=pp.fade_in,
                fade_out=pp.fade_out,
                highlight_rolloff=replace(
                    structure.render_post_fx.highlight_rolloff,
                    expanded=pp.highlight_rolloff_expanded,
                    mode=pp.highlight_rolloff.mode,
                    curve=pp.highlight_rolloff.curve,
                    threshold_pct=pp.highlight_rolloff.threshold_pct,
                    ceiling_pct=pp.highlight_rolloff.ceiling_pct,
                    strength_pct=pp.highlight_rolloff.strength_pct,
                    softness_pct=pp.highlight_rolloff.softness_pct,
                    desaturation_pct=pp.highlight_rolloff.desaturation_pct,
                ),
                chroma_boost=replace(
                    structure.render_post_fx.chroma_boost,
                    expanded=pp.chroma_boost_expanded,
                    mode=pp.chroma_boost.mode,
                    variant=pp.chroma_boost.variant,
                    amount_pct=pp.chroma_boost.amount_pct,
                ),
                solo=self.session.render_post_fx_solo,
                locked=pp.locked,
            ),
            render_timeline=replace(
                structure.render_timeline,
                expanded=tl.panel_open,
                bar_phase_offset=tl.bar_phase_offset,
                show_bar_grid=tl.show_bar_grid,
                beat_bar_grid_expanded=tl.beat_bar_grid_expanded,
                placement_snap=tl.placement_snap,
                fades_expanded=tl.fades_expanded,
                timeline_presets_expanded=tl.timeline_presets_expanded,
                timeline_preset_kind=tl.timeline_preset_kind,
                timeline_preset_crescendo=tl.timeline_preset_crescendo,
                timeline_preset_density=tl.timeline_preset_density,
                timeline_preset_conductor=tl.timeline_preset_conductor,
                song_marker_fades=TimelineFadeGroupBlock(
                    enabled=tl.song_marker_fades.enabled,
                    fade_in=tl.song_marker_fades.fade_in,
                    fade_out=tl.song_marker_fades.fade_out,
                ),
                standard_cue_fades=TimelineFadeGroupBlock(
                    enabled=tl.standard_cue_fades.enabled,
                    fade_in=tl.standard_cue_fades.fade_in,
                    fade_out=tl.standard_cue_fades.fade_out,
                ),
                limiter=VisualLimiterBlock(
                    enabled=tl.limiter.enabled,
                    threshold=tl.limiter.threshold,
                    release=tl.limiter.release,
                ),
                locked=tl.locked,
                song_markers_expanded=self.session.song_markers.expanded,
                song_marker_times=tuple(self.session.song_markers.times),
            ),
            settings=replace(
                structure.settings,
                expanded=self.session.settings.expanded,
                ui_expanded=self.session.settings.ui_expanded,
                latency_compensation_expanded=self.session.settings.latency_compensation_expanded,
                editor_mode=self.session.settings.editor_mode,
                editor_mode_selection=self.session.settings.editor_mode_selection,
                preview_quality=self._config_save.cfg.editor.preview_quality,
                ui_width_mode=self._config_save.cfg.editor.ui_width_mode,
                ui_width=self._config_save.cfg.editor.ui_width,
                ui_fade=self._config_save.cfg.editor.ui_fade,
                residual_latency_ms=self._config_save.cfg.editor.residual_latency_ms,
            ),
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
            fps=fps,
            layout=structure.layout,
        )
        return state
