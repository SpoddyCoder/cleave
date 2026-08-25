"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config_schema import (
    DEFAULT_CHROMA_BOOST_APPLY_MODE,
    DEFAULT_CHROMA_BOOST_VARIANT,
    DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_RESIDUAL_LATENCY_MS,
    DEFAULT_TIMELINE_ENABLED,
    DEFAULT_TIMELINE_FADES_ENABLED,
    DEFAULT_TIMELINE_FADE_IN,
    DEFAULT_TIMELINE_FADE_OUT,
    DEFAULT_TIMELINE_CROSSFADE,
    DEFAULT_TIMELINE_LOCKED,
    DEFAULT_TIMELINE_PLACEMENT_SNAP,
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    DEFAULT_VISUAL_LIMITER_ENABLED,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
    DEFAULT_VISUAL_LIMITER_RATIO,
    DEFAULT_VISUAL_LIMITER_RELEASE,
    default_render_overlays_runtime_values,
    default_render_pattern_mask_runtime_values,
    default_render_post_fx_runtime_values,
    PatternMaskType,
)
from cleave.preset_curation import PresetCurationIndex
from cleave.preset_playlist import (
    PresetPlaylist,
    preset_filename_display,
    scan_preset_playlist,
)
from cleave.timeline_presets.characters import DEFAULT_TIMELINE_PRESET_KIND
from cleave.timeline_presets.conductor import DEFAULT_TIMELINE_PRESET_CONDUCTOR
from cleave.timeline_presets.mode import (
    DEFAULT_TIMELINE_PRESET_MODE,
    TimelinePresetMode,
)
from cleave.viz.panel_notification import PanelNotificationActive
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
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.session import (
    LayerRuntime,
    RenderOverlayCardRuntime,
    TuningSession,
    config_path_display,
    default_render_overlay_card_runtime,
)
from cleave.viz.user_presets import (
    path_list_identity,
    preset_list_display_names,
)

if TYPE_CHECKING:
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.layer import StemLayer
    from cleave.viz.row_layout import RowLayout, RowLayoutFrame

_RO_OVERLAYS_DEFAULTS = default_render_overlays_runtime_values()
_RO_POST_FX_DEFAULTS = default_render_post_fx_runtime_values()
_RO_PATTERN_MASK_DEFAULTS = default_render_pattern_mask_runtime_values()


@dataclass
class TrackBlock:
    runtime: LayerRuntime
    preset_dir_label: str
    preset_label: str
    preset_list_labels: list[str] = field(default_factory=list)
    preset_empty: bool = False
    visible: bool = True
    # Index into runtime.preset_list of the currently playing preset, when present.
    # Baked at structure build (signature includes auto_preset_path / playlist).
    active_preset_list_index: int | None = None


@dataclass
class RenderOverlayCardBlock:
    runtime: RenderOverlayCardRuntime = field(
        default_factory=default_render_overlay_card_runtime
    )


@dataclass
class RenderOverlaysBlock:
    expanded: bool = _RO_OVERLAYS_DEFAULTS["expanded"]
    opening_card: RenderOverlayCardBlock = field(
        default_factory=RenderOverlayCardBlock
    )
    closing_card: RenderOverlayCardBlock = field(
        default_factory=lambda: RenderOverlayCardBlock(
            runtime=default_render_overlay_card_runtime(closing=True)
        )
    )
    solo: bool = False
    locked: bool = False


@dataclass
class HighlightRolloffBlock:
    expanded: bool = False
    mode: str = DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE
    curve: str = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE
    threshold_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT
    ceiling_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT
    strength_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT
    softness_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT
    desaturation_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT


@dataclass
class ChromaBoostBlock:
    expanded: bool = False
    mode: str = DEFAULT_CHROMA_BOOST_APPLY_MODE
    variant: str = DEFAULT_CHROMA_BOOST_VARIANT
    amount_pct: int = DEFAULT_CHROMA_BOOST_AMOUNT_PCT


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
class RenderPatternMaskBlock:
    enabled: bool = _RO_PATTERN_MASK_DEFAULTS["enabled"]
    expanded: bool = _RO_PATTERN_MASK_DEFAULTS["expanded"]
    type: PatternMaskType = _RO_PATTERN_MASK_DEFAULTS["type"]
    density: float = _RO_PATTERN_MASK_DEFAULTS["density"]
    feather_pct: int = _RO_PATTERN_MASK_DEFAULTS["feather_pct"]
    invert: bool = _RO_PATTERN_MASK_DEFAULTS["invert"]
    transition: float = _RO_PATTERN_MASK_DEFAULTS["transition"]
    seed: int = _RO_PATTERN_MASK_DEFAULTS["seed"]
    locked: bool = False


@dataclass
class TimelineFadeGroupBlock:
    enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_FADE_OUT
    crossfade: bool = DEFAULT_TIMELINE_CROSSFADE


@dataclass
class VisualLimiterBlock:
    enabled: bool = DEFAULT_VISUAL_LIMITER_ENABLED
    threshold: float = DEFAULT_VISUAL_LIMITER_THRESHOLD
    ratio: float = DEFAULT_VISUAL_LIMITER_RATIO
    release: float = DEFAULT_VISUAL_LIMITER_RELEASE


@dataclass
class RenderTimelineBlock:
    enabled: bool = DEFAULT_TIMELINE_ENABLED
    expanded: bool = False
    bar_phase_offset: int = 0
    show_bar_grid: bool = False
    beat_bar_grid_expanded: bool = False
    snap_cues_expanded: bool = False
    placement_snap: str = DEFAULT_TIMELINE_PLACEMENT_SNAP
    cuts_expanded: bool = False
    timeline_presets_expanded: bool = False
    visual_limiter_expanded: bool = False
    timeline_preset_kind: str = DEFAULT_TIMELINE_PRESET_KIND
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
    timeline_preset_mode: TimelinePresetMode = DEFAULT_TIMELINE_PRESET_MODE
    hard_cut_fades: TimelineFadeGroupBlock = field(
        default_factory=TimelineFadeGroupBlock
    )
    soft_cut_fades: TimelineFadeGroupBlock = field(
        default_factory=TimelineFadeGroupBlock
    )
    limiter: VisualLimiterBlock = field(default_factory=VisualLimiterBlock)
    locked: bool = DEFAULT_TIMELINE_LOCKED
    song_markers_expanded: bool = False
    song_marker_times: tuple[float, ...] = ()
    song_marker_types: tuple[str, ...] = ()


@dataclass
class SettingsBlock:
    expanded: bool = False
    ui_expanded: bool = False
    latency_compensation_expanded: bool = False
    editor_mode: str = "visualizer"
    editor_mode_selection: str = "visualizer"
    preview_quality: str = DEFAULT_EDITOR_PREVIEW_QUALITY
    ui_width_mode: str = DEFAULT_UI_WIDTH_MODE
    ui_width: int = DEFAULT_UI_WIDTH
    ui_fade: float = DEFAULT_UI_FADE_SEC
    residual_latency_ms: int = DEFAULT_RESIDUAL_LATENCY_MS


@dataclass
class TuningViewState:
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    paused: bool
    position_sec: float
    focus_cursor: FocusCursor
    move_mode_slot: str | None
    move_mode_preset: tuple[str, int] | None = None
    persistent_notification_message: str | None = None
    persistent_notification_elapsed_sec: float = 0.0
    notification_message: str | None = None
    notification_remaining_sec: float = 0.0
    notification_elapsed_sec: float = 0.0
    allow_overwrite: bool = True
    active_config_label: str = "cleave-viz.yaml"
    config_dirty: bool = False
    solo_slot: str | None = None
    solo_active: bool = False
    render_overlays: RenderOverlaysBlock = field(default_factory=RenderOverlaysBlock)
    render_post_fx: RenderPostFxBlock = field(
        default_factory=RenderPostFxBlock
    )
    render_pattern_mask: RenderPatternMaskBlock = field(
        default_factory=RenderPatternMaskBlock
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
            "preset_list_expanded": layer.preset_list_expanded,
            "preset_switching": layer.preset_switching,
            "preset_switching_trigger": layer.preset_switching_trigger,
            "preset_duration": layer.preset_duration,
            "soft_cut_duration": layer.soft_cut_duration,
            "hard_cut_duration": layer.hard_cut_duration,
            "hard_cut_sensitivity": layer.hard_cut_sensitivity,
            "hard_cut_enabled": layer.hard_cut_enabled,
            "easter_egg": layer.easter_egg,
            "preset_start_clean": layer.preset_start_clean,
            "effects": sorted(layer.effects.keys()),
            "preset_list": path_list_identity(layer.preset_list),
            "playlist": {
                "current_dir": str(playlist.current_dir),
                "paths": path_list_identity(
                    [str(path) for path in playlist.paths]
                ),
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
    pm = session.render_pattern_mask
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
        "render_pattern_mask": {
            "expanded": pm.expanded,
            # type gates the plasma-only seed row in the panel layout.
            "type": pm.type,
        },
        "render_timeline": {
            "enabled": tl.enabled,
            "panel_open": tl.panel_open,
            "song_markers_expanded": session.song_markers.expanded,
            "song_marker_count": len(session.song_markers.times),
            "beat_bar_grid_expanded": tl.beat_bar_grid_expanded,
            "snap_cues_expanded": tl.snap_cues_expanded,
            "cuts_expanded": tl.cuts_expanded,
            "timeline_presets_expanded": tl.timeline_presets_expanded,
            "visual_limiter_expanded": tl.visual_limiter_expanded,
            "hard_cut_fades_enabled": tl.hard_cut_fades.enabled,
            "soft_cut_fades_enabled": tl.soft_cut_fades.enabled,
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
    render_pattern_mask: RenderPatternMaskBlock
    render_timeline: RenderTimelineBlock
    layout: RowLayout


def _card_block_from_runtime(card: RenderOverlayCardRuntime) -> RenderOverlayCardBlock:
    return RenderOverlayCardBlock(runtime=card)


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
        get_move_mode_preset: Callable[[], tuple[str, int] | None],
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
        self._get_move_mode_preset = get_move_mode_preset
        self._config_save = config_save
        self._get_notification = get_notification
        self._layers_by_slot = layers_by_slot
        self._auto_display_cache: dict[Path, PresetPlaylist] = {}
        self._base_preset_list_label_cache: dict[tuple[str, ...], list[str]] = {}
        self._annotated_preset_list_label_cache: dict[
            tuple[tuple[str, ...], str], list[str]
        ] = {}
        self._user_basenames_cache: dict[tuple[tuple[str, ...], ...], set[str]] = {}
        self._structure: _ViewStateStructure | None = None

    def _sync_auto_preset_paths(self) -> None:
        """Mirror StemLayer playing paths onto session for panel display."""
        if not self._layers_by_slot:
            return
        for slot, stem in self._layers_by_slot.items():
            runtime = self.session.layers.get(slot)
            if runtime is not None:
                runtime.auto_preset_path = stem.auto_preset_path

    def _preset_list_paths_key(self) -> tuple[tuple[str, ...], ...]:
        return tuple(
            tuple(self.session.layers[slot].preset_list)
            for slot in self.session.layer_z_order
        )

    def _user_preset_basenames(self) -> set[str]:
        key = self._preset_list_paths_key()
        cached = self._user_basenames_cache.get(key)
        if cached is not None:
            return cached
        names: set[str] = set()
        for slot in self.session.layer_z_order:
            for path in self.session.layers[slot].preset_list:
                names.add(Path(path).name)
        self._user_basenames_cache[key] = names
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

    def _preset_list_labels(self, paths: list[str]) -> list[str]:
        paths_key = tuple(paths)
        annotated_key = (paths_key, self._curation_index.curation_stamp)
        cached = self._annotated_preset_list_label_cache.get(annotated_key)
        if cached is not None:
            return cached
        base = self._base_preset_list_label_cache.get(paths_key)
        if base is None:
            base = preset_list_display_names(paths)
            self._base_preset_list_label_cache[paths_key] = base
        labels = [
            base[i] + self._curation_index.marker(Path(paths[i]).name)
            for i in range(len(paths))
        ]
        self._annotated_preset_list_label_cache[annotated_key] = labels
        return labels

    @staticmethod
    def _active_preset_list_index(layer: LayerRuntime) -> int | None:
        """Return the preset_list index matching the playing preset, if any.

        Computed only when the view structure rebuilds (``auto_preset_path`` and
        playlist index are part of ``view_state_structure_signature``), so the
        draw path can read a precomputed index without resolving paths per frame.
        """
        paths = layer.preset_list
        if not paths:
            return None
        active = layer.auto_preset_path
        if active is None:
            current = layer.playlist.current
            if current is None:
                return None
            active = current.resolve()
        target = active.resolve()
        target_str = str(target)
        target_posix = target.as_posix()
        for index, raw in enumerate(paths):
            if raw == target_str or raw == target_posix:
                return index
        for index, raw in enumerate(paths):
            try:
                if Path(raw).resolve() == target:
                    return index
            except OSError:
                continue
        return None

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
            # Directory row always reflects browse navigation (Ctrl+Left/Right).
            # The file row alone follows auto_preset_path when switching plays
            # a cast/list preset outside the browse directory.
            tracks[slot] = TrackBlock(
                runtime=layer,
                preset_dir_label=layer.playlist.directory_display_label(
                    self.preset_root,
                    browse_floor=layer.browse_floor,
                ),
                preset_label=self._preset_label(
                    display, user_names=user_names
                ),
                preset_empty=not display.paths,
                visible=layer.enabled,
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
                active_preset_list_index=self._active_preset_list_index(layer),
            )

        ro = self.session.render_overlays
        pp = self.session.render_post_fx
        pm = self.session.render_pattern_mask
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
            opening_card=_card_block_from_runtime(ro.opening_card),
            closing_card=_card_block_from_runtime(ro.closing_card),
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
        render_pattern_mask = RenderPatternMaskBlock(
            enabled=pm.enabled,
            expanded=pm.expanded,
            type=pm.type,
            feather_pct=pm.feather_pct,
            density=pm.density,
            invert=pm.invert,
            transition=pm.transition,
            seed=pm.seed,
            locked=pm.locked,
        )
        render_timeline = RenderTimelineBlock(
            enabled=tl.enabled,
            expanded=tl.panel_open,
            bar_phase_offset=tl.bar_phase_offset,
            show_bar_grid=tl.show_bar_grid,
            beat_bar_grid_expanded=tl.beat_bar_grid_expanded,
            snap_cues_expanded=tl.snap_cues_expanded,
            placement_snap=tl.placement_snap,
            cuts_expanded=tl.cuts_expanded,
            timeline_presets_expanded=tl.timeline_presets_expanded,
            visual_limiter_expanded=tl.visual_limiter_expanded,
            timeline_preset_kind=tl.timeline_preset_kind,
            timeline_preset_density=tl.timeline_preset_density,
            timeline_preset_cue_snap=tl.timeline_preset_cue_snap,
            timeline_preset_song_marker_snap=tl.timeline_preset_song_marker_snap,
            timeline_preset_timeline_cuts=tl.timeline_preset_timeline_cuts,
            timeline_preset_repopulate=tl.timeline_preset_repopulate,
            timeline_preset_conductor=tl.timeline_preset_conductor,
            timeline_preset_mode=tl.timeline_preset_mode,
            hard_cut_fades=TimelineFadeGroupBlock(
                enabled=tl.hard_cut_fades.enabled,
                fade_in=tl.hard_cut_fades.fade_in,
                fade_out=tl.hard_cut_fades.fade_out,
                crossfade=tl.hard_cut_fades.crossfade,
            ),
            soft_cut_fades=TimelineFadeGroupBlock(
                enabled=tl.soft_cut_fades.enabled,
                fade_in=tl.soft_cut_fades.fade_in,
                fade_out=tl.soft_cut_fades.fade_out,
                crossfade=tl.soft_cut_fades.crossfade,
            ),
            limiter=VisualLimiterBlock(
                enabled=tl.limiter.enabled,
                threshold=tl.limiter.threshold,
                ratio=tl.limiter.ratio,
                release=tl.limiter.release,
            ),
            song_markers_expanded=self.session.song_markers.expanded,
            song_marker_times=tuple(self.session.song_markers.times),
            song_marker_types=tuple(
                m.marker_type for m in self.session.song_markers.markers
            ),
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
            render_pattern_mask=render_pattern_mask,
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
            render_pattern_mask=render_pattern_mask,
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
                visible=visible,
                preset_label=self._preset_label(
                    display, user_names=user_names
                ),
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
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
        notification_elapsed_sec = notification.elapsed_sec
        persistent_notification_message = notification.persistent_message
        persistent_notification_elapsed_sec = notification.persistent_elapsed_sec
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
        pm = self.session.render_pattern_mask
        tl = self.session.timeline
        state = TuningViewState(
            layer_z_order=structure.layer_z_order,
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_cursor=self._get_focus_cursor(),
            move_mode_slot=self._get_move_mode_slot(),
            move_mode_preset=self._get_move_mode_preset(),
            persistent_notification_message=persistent_notification_message,
            persistent_notification_elapsed_sec=persistent_notification_elapsed_sec,
            notification_message=notification_message,
            notification_remaining_sec=notification_remaining_sec,
            notification_elapsed_sec=notification_elapsed_sec,
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
            render_pattern_mask=replace(
                structure.render_pattern_mask,
                enabled=pm.enabled,
                expanded=pm.expanded,
                type=pm.type,
                feather_pct=pm.feather_pct,
                density=pm.density,
                invert=pm.invert,
                transition=pm.transition,
                seed=pm.seed,
                locked=pm.locked,
            ),
            render_timeline=replace(
                structure.render_timeline,
                expanded=tl.panel_open,
                bar_phase_offset=tl.bar_phase_offset,
                show_bar_grid=tl.show_bar_grid,
                beat_bar_grid_expanded=tl.beat_bar_grid_expanded,
                snap_cues_expanded=tl.snap_cues_expanded,
                placement_snap=tl.placement_snap,
                cuts_expanded=tl.cuts_expanded,
                timeline_presets_expanded=tl.timeline_presets_expanded,
                visual_limiter_expanded=tl.visual_limiter_expanded,
                timeline_preset_kind=tl.timeline_preset_kind,
                timeline_preset_density=tl.timeline_preset_density,
                timeline_preset_cue_snap=tl.timeline_preset_cue_snap,
                timeline_preset_song_marker_snap=tl.timeline_preset_song_marker_snap,
                timeline_preset_timeline_cuts=tl.timeline_preset_timeline_cuts,
                timeline_preset_repopulate=tl.timeline_preset_repopulate,
                timeline_preset_conductor=tl.timeline_preset_conductor,
                timeline_preset_mode=tl.timeline_preset_mode,
                hard_cut_fades=TimelineFadeGroupBlock(
                    enabled=tl.hard_cut_fades.enabled,
                    fade_in=tl.hard_cut_fades.fade_in,
                    fade_out=tl.hard_cut_fades.fade_out,
                    crossfade=tl.hard_cut_fades.crossfade,
                ),
                soft_cut_fades=TimelineFadeGroupBlock(
                    enabled=tl.soft_cut_fades.enabled,
                    fade_in=tl.soft_cut_fades.fade_in,
                    fade_out=tl.soft_cut_fades.fade_out,
                    crossfade=tl.soft_cut_fades.crossfade,
                ),
                limiter=VisualLimiterBlock(
                    enabled=tl.limiter.enabled,
                    threshold=tl.limiter.threshold,
                    ratio=tl.limiter.ratio,
                    release=tl.limiter.release,
                ),
                locked=tl.locked,
                song_markers_expanded=self.session.song_markers.expanded,
                song_marker_times=tuple(self.session.song_markers.times),
                song_marker_types=tuple(
                    m.marker_type for m in self.session.song_markers.markers
                ),
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
