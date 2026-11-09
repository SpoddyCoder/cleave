"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config_schema.compositor import DEFAULT_COMPOSITOR_HDR
from cleave.config_schema.editor import (
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_RESIDUAL_LATENCY_MS,
    DEFAULT_HELP_SIDE,
    DEFAULT_NAVIGATOR_HEIGHT,
    DEFAULT_UI_SCALE,
    DEFAULT_NAVIGATOR_SIDE,
    DEFAULT_NOTIFICATION_DISPLAY_SEC,
)
from cleave.config_schema.project_render import (
    DEFAULT_PROJECT_RENDER_OUTPUT_LABEL,
    DEFAULT_PROJECT_RENDER_QUALITY,
    DEFAULT_PROJECT_RENDER_START_SEC,
    DEFAULT_RENDER_FPS,
    default_project_render_path,
    resolved_project_render_end_sec,
)
from cleave.config_schema.project_resolution import (
    DEFAULT_RESOLUTION_HEIGHT,
    DEFAULT_RESOLUTION_WIDTH,
)
from cleave.config_schema.render import (
    DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
    DEFAULT_CHROMA_BOOST_APPLY_MODE,
    DEFAULT_CHROMA_BOOST_VARIANT,
    DEFAULT_FADE_CURVE,
    DEFAULT_FADE_IN_END,
    DEFAULT_FADE_IN_START,
    DEFAULT_FADE_OUT_END,
    DEFAULT_FADE_OUT_START,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT,
    DEFAULT_VISUAL_LIMITER_ENABLED,
    DEFAULT_VISUAL_LIMITER_RATIO,
    DEFAULT_VISUAL_LIMITER_RELEASE,
    DEFAULT_VISUAL_LIMITER_THRESHOLD,
    PatternMaskType,
    default_render_overlays_runtime_values,
    default_render_pattern_mask_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.config_schema.timeline import (
    DEFAULT_TIMELINE_CROSSFADE,
    DEFAULT_TIMELINE_ENABLED,
    DEFAULT_TIMELINE_FADES_ENABLED,
    DEFAULT_TIMELINE_HARD_FADE_IN,
    DEFAULT_TIMELINE_HARD_FADE_OUT,
    DEFAULT_TIMELINE_SOFT_FADE_IN,
    DEFAULT_TIMELINE_SOFT_FADE_OUT,
    DEFAULT_TIMELINE_LOCKED,
    DEFAULT_TIMELINE_BAR_PHASE,
    DEFAULT_TIMELINE_PLACEMENT_SNAP,
    DEFAULT_TIMELINE_SHOW_BAR_GRID,
)
from cleave.preset_curation import PresetCurationIndex
from cleave.viz.session import FadeRuntime
from cleave.preset_playlist import (
    PresetPlaylist,
    preset_filename_display,
    preset_position_display,
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
from cleave.timeline import (
    SlotCue,
    cue_at_time,
    cue_editable_for_blend_role,
    empty_lane,
)
from cleave.timeline_presets.timeline_cuts import (
    DEFAULT_TIMELINE_PRESET_TIMELINE_CUTS,
    TimelinePresetTimelineCuts,
)
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import (
    LayerRuntime,
    OverlayCardRuntime,
    TuningSession,
    default_overlay_card_runtime,
)
from cleave.viz.user_presets import (
    path_list_identity,
    preset_list_display_names,
)

if TYPE_CHECKING:
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.layer import StemLayer

_RO_OVERLAYS_DEFAULTS = default_render_overlays_runtime_values()
_RO_POST_FX_DEFAULTS = default_render_post_fx_runtime_values()
_RO_PATTERN_MASK_DEFAULTS = default_render_pattern_mask_runtime_values()


@dataclass
class TrackBlock:
    runtime: LayerRuntime
    preset_dir_label: str
    preset_label: str
    preset_dir_position: str = ""
    preset_dir_can_go_up: bool = False
    preset_dir_can_go_down: bool = False
    preset_position: str = ""
    preset_markers: str = ""
    preset_list_labels: list[str] = field(default_factory=list)
    preset_list_markers: list[str] = field(default_factory=list)
    preset_empty: bool = False
    visible: bool = True
    # Index into runtime.preset_list of the currently playing preset, when present.
    # Baked at structure build (signature includes auto_preset_path / playlist).
    active_preset_list_index: int | None = None


@dataclass
class OverlayCardBlock:
    runtime: OverlayCardRuntime = field(
        default_factory=default_overlay_card_runtime
    )


@dataclass
class OverlaysBlock:
    opening_card: OverlayCardBlock = field(
        default_factory=OverlayCardBlock
    )
    closing_card: OverlayCardBlock = field(
        default_factory=lambda: OverlayCardBlock(
            runtime=default_overlay_card_runtime(closing=True)
        )
    )
    solo: bool = False
    locked: bool = _RO_OVERLAYS_DEFAULTS["locked"]


@dataclass
class FadeSideBlock:
    start: float = DEFAULT_FADE_IN_START
    end: float = DEFAULT_FADE_IN_END
    type: str = DEFAULT_FADE_CURVE


def _default_fade_out_side() -> FadeSideBlock:
    return FadeSideBlock(
        start=DEFAULT_FADE_OUT_START,
        end=DEFAULT_FADE_OUT_END,
        type=DEFAULT_FADE_CURVE,
    )


@dataclass
class FadeBlock:
    fade_in: FadeSideBlock = field(default_factory=FadeSideBlock)
    fade_out: FadeSideBlock = field(default_factory=_default_fade_out_side)


def _fade_block_from_runtime(fade: FadeRuntime) -> FadeBlock:
    fade_in = fade.fade_in
    fade_out = fade.fade_out
    return FadeBlock(
        fade_in=FadeSideBlock(
            start=fade_in.start,
            end=fade_in.end,
            type=fade_in.type,
        ),
        fade_out=FadeSideBlock(
            start=fade_out.start,
            end=fade_out.end,
            type=fade_out.type,
        ),
    )


@dataclass
class HighlightRolloffBlock:
    mode: str = DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE
    curve: str = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE
    threshold_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT
    ceiling_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT
    strength_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT
    softness_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT
    desaturation_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT


@dataclass
class ChromaBoostBlock:
    mode: str = DEFAULT_CHROMA_BOOST_APPLY_MODE
    variant: str = DEFAULT_CHROMA_BOOST_VARIANT
    amount_pct: int = DEFAULT_CHROMA_BOOST_AMOUNT_PCT


@dataclass
class VisualLimiterBlock:
    enabled: bool = DEFAULT_VISUAL_LIMITER_ENABLED
    threshold: float = DEFAULT_VISUAL_LIMITER_THRESHOLD
    ratio: float = DEFAULT_VISUAL_LIMITER_RATIO
    release: float = DEFAULT_VISUAL_LIMITER_RELEASE


@dataclass
class PostFxBlock:
    enabled: bool = _RO_POST_FX_DEFAULTS["enabled"]
    fade: FadeBlock = field(default_factory=FadeBlock)
    highlight_rolloff: HighlightRolloffBlock = field(
        default_factory=HighlightRolloffBlock
    )
    chroma_boost: ChromaBoostBlock = field(default_factory=ChromaBoostBlock)
    limiter: VisualLimiterBlock = field(default_factory=VisualLimiterBlock)
    solo: bool = False
    locked: bool = _RO_POST_FX_DEFAULTS["locked"]


@dataclass
class PatternMaskBlock:
    enabled: bool = _RO_PATTERN_MASK_DEFAULTS["enabled"]
    type: PatternMaskType = _RO_PATTERN_MASK_DEFAULTS["type"]
    density: float = _RO_PATTERN_MASK_DEFAULTS["density"]
    feather_pct: int = _RO_PATTERN_MASK_DEFAULTS["feather_pct"]
    invert: bool = _RO_PATTERN_MASK_DEFAULTS["invert"]
    transition: float = _RO_PATTERN_MASK_DEFAULTS["transition"]
    seed: int = _RO_PATTERN_MASK_DEFAULTS["seed"]
    locked: bool = _RO_PATTERN_MASK_DEFAULTS["locked"]


@dataclass
class TimelineFadeGroupBlock:
    enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_SOFT_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_SOFT_FADE_OUT
    crossfade: bool = DEFAULT_TIMELINE_CROSSFADE


def default_hard_timeline_fade_group_block() -> TimelineFadeGroupBlock:
    return TimelineFadeGroupBlock(
        fade_in=DEFAULT_TIMELINE_HARD_FADE_IN,
        fade_out=DEFAULT_TIMELINE_HARD_FADE_OUT,
    )


def default_soft_timeline_fade_group_block() -> TimelineFadeGroupBlock:
    return TimelineFadeGroupBlock(
        fade_in=DEFAULT_TIMELINE_SOFT_FADE_IN,
        fade_out=DEFAULT_TIMELINE_SOFT_FADE_OUT,
    )


@dataclass
class TimelineBlock:
    enabled: bool = DEFAULT_TIMELINE_ENABLED
    bar_phase_offset: int = DEFAULT_TIMELINE_BAR_PHASE
    show_bar_grid: bool = DEFAULT_TIMELINE_SHOW_BAR_GRID
    placement_snap: str = DEFAULT_TIMELINE_PLACEMENT_SNAP
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
        default_factory=default_hard_timeline_fade_group_block
    )
    soft_cut_fades: TimelineFadeGroupBlock = field(
        default_factory=default_soft_timeline_fade_group_block
    )
    locked: bool = DEFAULT_TIMELINE_LOCKED
    song_marker_times: tuple[float, ...] = ()
    song_marker_types: tuple[str, ...] = ()
    # Selected strip cue per slot, for the timeline row inspector page.
    selected_cues: dict[str, SlotCue] = field(default_factory=dict)


def timeline_cue_kind(cue: SlotCue | None) -> str:
    """``start`` for a cue that turns the layer on, ``end`` for one that turns it off."""
    if cue is None:
        return "none"
    return "start" if cue_editable_for_blend_role(cue) else "end"


def selected_timeline_cues(session: TuningSession) -> dict[str, SlotCue]:
    """Each layer's selected strip cue, when that cue still exists."""
    tl = session.timeline
    cues: dict[str, SlotCue] = {}
    for slot in session.layer_z_order:
        cue_t = tl.selected_cue_t.get(slot)
        if cue_t is None:
            continue
        cue = cue_at_time(tl.lanes.get(slot) or empty_lane(), cue_t)
        if cue is not None:
            cues[slot] = cue
    return cues


@dataclass
class SettingsBlock:
    editor_mode: str = "visualizer"
    preview_quality: str = DEFAULT_EDITOR_PREVIEW_QUALITY
    navigator_side: str = DEFAULT_NAVIGATOR_SIDE
    help_side: str = DEFAULT_HELP_SIDE
    notification_display_sec: int = DEFAULT_NOTIFICATION_DISPLAY_SEC
    navigator_height: int = DEFAULT_NAVIGATOR_HEIGHT
    ui_scale: int = DEFAULT_UI_SCALE
    residual_latency_ms: int = DEFAULT_RESIDUAL_LATENCY_MS


@dataclass
class ProjectBlock:
    milkdrop_beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY
    compositor_hdr: bool = DEFAULT_COMPOSITOR_HDR
    quality: str = DEFAULT_PROJECT_RENDER_QUALITY
    start_sec: int = DEFAULT_PROJECT_RENDER_START_SEC
    end_sec: int = DEFAULT_PROJECT_RENDER_START_SEC
    width: int = DEFAULT_RESOLUTION_WIDTH
    height: int = DEFAULT_RESOLUTION_HEIGHT
    fps: int = DEFAULT_RENDER_FPS
    output_label: str = DEFAULT_PROJECT_RENDER_OUTPUT_LABEL


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
    config_dirty: bool = False
    solo_slot: str | None = None
    solo_active: bool = False
    overlays: OverlaysBlock = field(default_factory=OverlaysBlock)
    post_fx: PostFxBlock = field(
        default_factory=PostFxBlock
    )
    pattern_mask: PatternMaskBlock = field(
        default_factory=PatternMaskBlock
    )
    timeline: TimelineBlock = field(
        default_factory=TimelineBlock
    )
    settings: SettingsBlock = field(default_factory=SettingsBlock)
    project: ProjectBlock = field(default_factory=ProjectBlock)
    timeline_recording: bool = False
    timeline_override_active: bool = False
    help_visible: bool = False
    fps: float | None = None

    @property
    def focus_descriptor(self) -> RowDescriptor:
        from cleave.viz.focus_nav import cursor_main_descriptor

        return cursor_main_descriptor(self.focus_cursor)

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
                MainFocus(RowDescriptor(RowKind.TIMELINE_HEADER)),
            )


def view_state_structure_signature(
    session: TuningSession,
    config_save: ConfigSaveController,
) -> str:
    layers: dict[str, object] = {}
    for slot in session.layer_z_order:
        layer = session.layers[slot]
        playlist = layer.playlist
        layers[slot] = {
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
            "switching_paused": layer.switching_paused,
        }
    ro = session.overlays
    pp = session.post_fx
    pm = session.pattern_mask
    tl = session.timeline
    payload = {
        "layer_z_order": list(session.layer_z_order),
        "settings": {
            "editor_mode": session.settings.editor_mode,
        },
        "project": {},
        "layers": layers,
        "overlays": {
            "opening_card": {
                "enabled": ro.opening_card.enabled,
                "animation_type": ro.opening_card.animation.type,
            },
            "closing_card": {
                "enabled": ro.closing_card.enabled,
                "animation_type": ro.closing_card.animation.type,
            },
        },
        "post_fx": {
            "enabled": pp.enabled,
            "highlight_rolloff_mode": pp.highlight_rolloff.mode,
            "chroma_boost_mode": pp.chroma_boost.mode,
            "limiter_enabled": pp.limiter.enabled,
        },
        "pattern_mask": {
            # type gates the plasma-only seed row in the inspector.
            "type": pm.type,
        },
        "timeline": {
            "enabled": tl.enabled,
            "song_marker_count": len(session.song_markers.times),
            "hard_cut_fades_enabled": tl.hard_cut_fades.enabled,
            "soft_cut_fades_enabled": tl.soft_cut_fades.enabled,
            # Start or end cue per slot gates the timeline row page's cue rows.
            "selected_cue_kinds": {
                slot: timeline_cue_kind(cue)
                for slot, cue in selected_timeline_cues(session).items()
            },
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class _ViewStateStructure:
    signature: str
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    settings: SettingsBlock
    project: ProjectBlock
    overlays: OverlaysBlock
    post_fx: PostFxBlock
    pattern_mask: PatternMaskBlock
    timeline: TimelineBlock


def _card_block_from_runtime(card: OverlayCardRuntime) -> OverlayCardBlock:
    return OverlayCardBlock(runtime=card)


def _project_block_from_session(
    session: TuningSession,
    *,
    duration_sec: float,
    project_dir: Path | None,
    project_slug: str,
) -> ProjectBlock:
    render = session.project.render
    resolution = session.project.resolution
    end_sec = resolved_project_render_end_sec(render.end_sec, duration_sec)
    root = project_dir if project_dir is not None else Path(".")
    return ProjectBlock(
        milkdrop_beat_sensitivity=session.project.milkdrop_beat_sensitivity,
        compositor_hdr=session.project.compositor_hdr,
        quality=render.quality,
        start_sec=render.start_sec,
        end_sec=end_sec,
        width=resolution.width,
        height=resolution.height,
        fps=render.fps,
        output_label=default_project_render_path(
            root,
            project_slug,
            start_sec=render.start_sec,
            end_sec=end_sec,
            duration_sec=duration_sec,
        ).as_posix(),
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
        get_move_mode_preset: Callable[[], tuple[str, int] | None],
        config_save: ConfigSaveController,
        get_notification: Callable[[], PanelNotificationActive],
        layers_by_slot: dict[str, StemLayer] | None = None,
        project_dir: Path | None = None,
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
        self._project_dir = project_dir
        self._auto_display_cache: dict[Path, PresetPlaylist] = {}
        self._preset_list_label_cache: dict[tuple[str, ...], list[str]] = {}
        self._preset_list_marker_cache: dict[
            tuple[tuple[str, ...], str], list[str]
        ] = {}
        self._user_basenames_cache: dict[tuple[tuple[str, ...], ...], set[str]] = {}
        self._structure: _ViewStateStructure | None = None

    def _sync_auto_preset_paths(self) -> None:
        """Mirror the playing switching preset onto session for panel display."""
        if not isinstance(self._layers_by_slot, dict) or not self._layers_by_slot:
            return
        from cleave.viz.preset_switching import playing_switching_preset_path

        for slot, stem in self._layers_by_slot.items():
            runtime = self.session.layers.get(slot)
            if runtime is None:
                continue
            playing = playing_switching_preset_path(stem)
            if playing is not None:
                stem.auto_preset_path = playing
            runtime.auto_preset_path = stem.auto_preset_path
            runtime.switching_paused = stem.switching_paused

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

    def _preset_markers(
        self, playlist: PresetPlaylist, *, user_names: set[str]
    ) -> str:
        if playlist.current is None:
            return ""
        name = playlist.current.name
        return self._curation_index.marker(name, user=name in user_names).strip()

    def _preset_list_labels(self, paths: list[str]) -> list[str]:
        paths_key = tuple(paths)
        labels = self._preset_list_label_cache.get(paths_key)
        if labels is None:
            labels = preset_list_display_names(paths)
            self._preset_list_label_cache[paths_key] = labels
        return labels

    def _preset_list_markers(self, paths: list[str]) -> list[str]:
        key = (tuple(paths), self._curation_index.curation_stamp)
        markers = self._preset_list_marker_cache.get(key)
        if markers is None:
            markers = [
                self._curation_index.marker(Path(path).name).strip()
                for path in paths
            ]
            self._preset_list_marker_cache[key] = markers
        return markers

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
            if current is not None:
                active = current.resolve()
            elif layer.preset_switching == "on":
                return 0
            else:
                return None
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
        if layer.preset_switching == "on" and layer.auto_preset_path is None:
            return 0
        return None

    def _build_structure(
        self,
        *,
        signature: str,
        user_names: set[str],
    ) -> _ViewStateStructure:
        layer_z_order = tuple(self.session.layer_z_order)
        tracks: dict[str, TrackBlock] = {}
        for slot in layer_z_order:
            layer = self.session.layers[slot]
            display = self._display_playlist(layer)
            # Directory row always reflects browse navigation (Left/Right, Enter, Backspace).
            # The file row alone follows auto_preset_path when switching plays
            # a cast/list preset outside the browse directory.
            directory = layer.playlist.directory_display(
                self.preset_root,
                browse_floor=layer.browse_floor,
            )
            tracks[slot] = TrackBlock(
                runtime=layer,
                preset_dir_label=directory.path,
                preset_dir_position=directory.position,
                preset_dir_can_go_up=directory.can_go_up,
                preset_dir_can_go_down=directory.can_go_down,
                preset_label=preset_filename_display(display),
                preset_position=preset_position_display(display),
                preset_markers=self._preset_markers(
                    display, user_names=user_names
                ),
                preset_empty=not display.paths,
                visible=layer.enabled,
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
                preset_list_markers=self._preset_list_markers(list(layer.preset_list)),
                active_preset_list_index=self._active_preset_list_index(layer),
            )

        ro = self.session.overlays
        pp = self.session.post_fx
        pm = self.session.pattern_mask
        tl = self.session.timeline
        settings = SettingsBlock(
            editor_mode=self.session.settings.editor_mode,
        )
        project = _project_block_from_session(
            self.session,
            duration_sec=self.duration_sec,
            project_dir=self._project_dir,
            project_slug=self._config_save.cfg.project_slug,
        )
        overlays = OverlaysBlock(
            opening_card=_card_block_from_runtime(ro.opening_card),
            closing_card=_card_block_from_runtime(ro.closing_card),
            locked=ro.locked,
        )
        post_fx = PostFxBlock(
            enabled=pp.enabled,
            fade=_fade_block_from_runtime(pp.fade),
            highlight_rolloff=HighlightRolloffBlock(
                mode=pp.highlight_rolloff.mode,
                curve=pp.highlight_rolloff.curve,
                threshold_pct=pp.highlight_rolloff.threshold_pct,
                ceiling_pct=pp.highlight_rolloff.ceiling_pct,
                strength_pct=pp.highlight_rolloff.strength_pct,
                softness_pct=pp.highlight_rolloff.softness_pct,
                desaturation_pct=pp.highlight_rolloff.desaturation_pct,
            ),
            chroma_boost=ChromaBoostBlock(
                mode=pp.chroma_boost.mode,
                variant=pp.chroma_boost.variant,
                amount_pct=pp.chroma_boost.amount_pct,
            ),
            limiter=VisualLimiterBlock(
                enabled=pp.limiter.enabled,
                threshold=pp.limiter.threshold,
                ratio=pp.limiter.ratio,
                release=pp.limiter.release,
            ),
        )
        pattern_mask = PatternMaskBlock(
            enabled=pm.enabled,
            type=pm.type,
            feather_pct=pm.feather_pct,
            density=pm.density,
            invert=pm.invert,
            transition=pm.transition,
            seed=pm.seed,
            locked=pm.locked,
        )
        timeline = TimelineBlock(
            enabled=tl.enabled,
            bar_phase_offset=tl.bar_phase_offset,
            show_bar_grid=tl.show_bar_grid,
            placement_snap=tl.placement_snap,
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
            song_marker_times=tuple(self.session.song_markers.times),
            song_marker_types=tuple(
                m.marker_type for m in self.session.song_markers.markers
            ),
            selected_cues=selected_timeline_cues(self.session),
        )
        return _ViewStateStructure(
            signature=signature,
            layer_z_order=layer_z_order,
            tracks=tracks,
            settings=settings,
            project=project,
            overlays=overlays,
            post_fx=post_fx,
            pattern_mask=pattern_mask,
            timeline=timeline,
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
                preset_label=preset_filename_display(display),
                preset_position=preset_position_display(display),
                preset_markers=self._preset_markers(
                    display, user_names=user_names
                ),
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
                preset_list_markers=self._preset_list_markers(list(layer.preset_list)),
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
        user_names = self._user_preset_basenames()
        signature = view_state_structure_signature(
            self.session,
            self._config_save,
        )
        if self._structure is None or self._structure.signature != signature:
            self._structure = self._build_structure(
                signature=signature,
                user_names=user_names,
            )
        structure = self._structure

        tracks = self._patch_tracks(
            structure, position_sec=position_sec, user_names=user_names
        )

        ro = self.session.overlays
        pp = self.session.post_fx
        pm = self.session.pattern_mask
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
            config_dirty=self._config_save.config_dirty,
            solo_slot=self.session.solo_slot,
            solo_active=self.session.solo_slot is not None,
            overlays=replace(
                structure.overlays,
                solo=self.session.overlay_solo,
                locked=ro.locked,
            ),
            post_fx=replace(
                structure.post_fx,
                fade=_fade_block_from_runtime(pp.fade),
                highlight_rolloff=replace(
                    structure.post_fx.highlight_rolloff,
                    mode=pp.highlight_rolloff.mode,
                    curve=pp.highlight_rolloff.curve,
                    threshold_pct=pp.highlight_rolloff.threshold_pct,
                    ceiling_pct=pp.highlight_rolloff.ceiling_pct,
                    strength_pct=pp.highlight_rolloff.strength_pct,
                    softness_pct=pp.highlight_rolloff.softness_pct,
                    desaturation_pct=pp.highlight_rolloff.desaturation_pct,
                ),
                chroma_boost=replace(
                    structure.post_fx.chroma_boost,
                    mode=pp.chroma_boost.mode,
                    variant=pp.chroma_boost.variant,
                    amount_pct=pp.chroma_boost.amount_pct,
                ),
                limiter=VisualLimiterBlock(
                    enabled=pp.limiter.enabled,
                    threshold=pp.limiter.threshold,
                    ratio=pp.limiter.ratio,
                    release=pp.limiter.release,
                ),
                solo=self.session.post_fx_solo,
                locked=pp.locked,
            ),
            pattern_mask=replace(
                structure.pattern_mask,
                enabled=pm.enabled,
                type=pm.type,
                feather_pct=pm.feather_pct,
                density=pm.density,
                invert=pm.invert,
                transition=pm.transition,
                seed=pm.seed,
                locked=pm.locked,
            ),
            timeline=replace(
                structure.timeline,
                bar_phase_offset=tl.bar_phase_offset,
                show_bar_grid=tl.show_bar_grid,
                placement_snap=tl.placement_snap,
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
                locked=tl.locked,
                song_marker_times=tuple(self.session.song_markers.times),
                song_marker_types=tuple(
                    m.marker_type for m in self.session.song_markers.markers
                ),
                selected_cues=selected_timeline_cues(self.session),
            ),
            settings=replace(
                structure.settings,
                editor_mode=self.session.settings.editor_mode,
                preview_quality=self._config_save.cfg.editor.preview_quality,
                navigator_side=self._config_save.cfg.editor.navigator_side,
                help_side=self._config_save.cfg.editor.help_side,
                notification_display_sec=(
                    self._config_save.cfg.editor.notification_display_sec
                ),
                navigator_height=self._config_save.cfg.editor.navigator_height,
                ui_scale=self._config_save.cfg.editor.ui_scale,
                residual_latency_ms=self._config_save.cfg.editor.residual_latency_ms,
            ),
            project=_project_block_from_session(
                self.session,
                duration_sec=self.duration_sec,
                project_dir=self._project_dir,
                project_slug=self._config_save.cfg.project_slug,
            ),
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
            fps=fps,
        )
        return state
