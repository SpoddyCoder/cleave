"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config_schema.compositor import DEFAULT_COMPOSITOR_HDR
from cleave.config_schema.editor import (
    DEFAULT_BEAT_SENSITIVITY,
    DEFAULT_EDITOR_PREVIEW_QUALITY,
    DEFAULT_AUDIO_LATENCY_MS,
    DEFAULT_TAP_LATENCY_MS,
    DEFAULT_HELP_SIDE,
    DEFAULT_HIGHLIGHT_NEW_PAGE,
    DEFAULT_SHOW_TOOLTIPS,
    DEFAULT_CRASH_LOG,
    DEFAULT_NAVIGATOR_EXPAND_CLICK,
    DEFAULT_THEME,
    DEFAULT_UI_SCALE,
    DEFAULT_NAVIGATOR_SIDE,
    DEFAULT_NOTIFICATION_DISPLAY_SEC,
)
from cleave.config_schema.project_resolution import (
    DEFAULT_RESOLUTION_HEIGHT,
    DEFAULT_RESOLUTION_WIDTH,
)
from cleave.config_schema.render import (
    DEFAULT_CHROMA_BOOST_AMOUNT_PCT,
    DEFAULT_CHROMA_BOOST_APPLY_MODE,
    DEFAULT_CHROMA_BOOST_ENABLED,
    DEFAULT_CHROMA_BOOST_VARIANT,
    DEFAULT_FADE_CURVE,
    DEFAULT_FADE_ENABLED,
    DEFAULT_FADE_IN_END,
    DEFAULT_FADE_IN_START,
    DEFAULT_FADE_OUT_END,
    DEFAULT_FADE_OUT_START,
    DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE,
    DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_CURVE,
    DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT,
    DEFAULT_HIGHLIGHT_ROLLOFF_ENABLED,
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
from cleave.preset_library import PresetLibrary
from cleave.viz.timeline_clip_edits import selected_clip
from cleave.viz.preset_browser import BrowserCrumb
from cleave.preset_playlist import (
    PresetPlaylist,
    preset_filename_display,
    preset_position_display,
    scan_preset_playlist,
)
from cleave.viz.panel_notification import PanelNotificationActive
from cleave.timeline import TimelineClip
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.editor_mode_controls import is_preset_curation_mode
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.session import (
    ChromaBoostRuntime,
    FadeRuntime,
    FadeSideRuntime,
    HighlightRolloffRuntime,
    LayerRuntime,
    OverlayCardRuntime,
    PatternMaskRuntime,
    TimelineFadeGroupRuntime,
    TuningSession,
    VisualLimiterRuntime,
    default_overlay_card_runtime,
)
from cleave.preset_list_entry import PresetListEntry
from cleave.viz.user_presets import (
    path_list_identity,
    preset_list_display_names,
    preset_list_identity,
)

if TYPE_CHECKING:
    from cleave.config import EditorConfig
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.layer import StemLayer

_RO_OVERLAYS_DEFAULTS = default_render_overlays_runtime_values()
_RO_POST_FX_DEFAULTS = default_render_post_fx_runtime_values()
_RO_PATTERN_MASK_DEFAULTS = default_render_pattern_mask_runtime_values()


def directory_crumbs(
    playlist: PresetPlaylist, preset_root: Path, label: str
) -> tuple[BrowserCrumb, ...]:
    """Folders from the top-level pack down to *playlist*'s folder."""
    if playlist.collection is not None:
        return (BrowserCrumb(label),)
    root = preset_root.resolve()
    folder = playlist.current_dir.resolve()
    try:
        parts = folder.relative_to(root).parts
    except ValueError:
        return (BrowserCrumb(label),)
    if not parts:
        return (BrowserCrumb(label, folder),)
    crumbs: list[BrowserCrumb] = []
    path = root
    for part in parts:
        path = path / part
        crumbs.append(BrowserCrumb(part, path))
    return tuple(crumbs)


@dataclass
class TrackBlock:
    runtime: LayerRuntime
    preset_dir_label: str
    preset_label: str
    # The directory row's path as folders a click can jump to; a collection
    # or a folder outside the preset root is one crumb with no path.
    preset_dir_crumbs: tuple[BrowserCrumb, ...] = ()
    preset_dir_position: str = ""
    preset_dir_can_go_up: bool = False
    preset_dir_can_go_down: bool = False
    preset_position: str = ""
    preset_markers: str = ""
    preset_list_labels: list[str] = field(default_factory=list)
    preset_list_markers: list[str] = field(default_factory=list)
    # Why the directory row's folder cannot be browsed (None: fine).
    preset_dir_problem: str | None = None
    # Why the preset row's file, or each list entry's, cannot play (None: fine).
    preset_problem: str | None = None
    preset_list_problems: tuple[str | None, ...] = ()
    # The driving stem has no sound in this project's audio.
    stem_silent: bool = False
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
    preview: bool = False
    locked: bool = _RO_OVERLAYS_DEFAULTS["locked"]

    @classmethod
    def from_session(cls, session: TuningSession) -> OverlaysBlock:
        ro = session.overlays
        return cls(
            opening_card=OverlayCardBlock(runtime=ro.opening_card),
            closing_card=OverlayCardBlock(runtime=ro.closing_card),
            preview=session.overlay_preview,
            locked=ro.locked,
        )


@dataclass
class FadeSideBlock:
    start: float = DEFAULT_FADE_IN_START
    end: float = DEFAULT_FADE_IN_END
    type: str = DEFAULT_FADE_CURVE

    @classmethod
    def from_runtime(cls, side: FadeSideRuntime) -> FadeSideBlock:
        return cls(start=side.start, end=side.end, type=side.type)


def _default_fade_out_side() -> FadeSideBlock:
    return FadeSideBlock(
        start=DEFAULT_FADE_OUT_START,
        end=DEFAULT_FADE_OUT_END,
        type=DEFAULT_FADE_CURVE,
    )


@dataclass
class FadeBlock:
    enabled: bool = DEFAULT_FADE_ENABLED
    fade_in: FadeSideBlock = field(default_factory=FadeSideBlock)
    fade_out: FadeSideBlock = field(default_factory=_default_fade_out_side)

    @classmethod
    def from_runtime(cls, fade: FadeRuntime) -> FadeBlock:
        return cls(
            enabled=fade.enabled,
            fade_in=FadeSideBlock.from_runtime(fade.fade_in),
            fade_out=FadeSideBlock.from_runtime(fade.fade_out),
        )


@dataclass
class HighlightRolloffBlock:
    enabled: bool = DEFAULT_HIGHLIGHT_ROLLOFF_ENABLED
    mode: str = DEFAULT_HIGHLIGHT_ROLLOFF_APPLY_MODE
    curve: str = DEFAULT_HIGHLIGHT_ROLLOFF_CURVE
    threshold_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_THRESHOLD_PCT
    ceiling_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_CEILING_PCT
    strength_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_STRENGTH_PCT
    softness_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_SOFTNESS_PCT
    desaturation_pct: int = DEFAULT_HIGHLIGHT_ROLLOFF_DESATURATION_PCT

    @classmethod
    def from_runtime(cls, rolloff: HighlightRolloffRuntime) -> HighlightRolloffBlock:
        return cls(
            enabled=rolloff.enabled,
            mode=rolloff.mode,
            curve=rolloff.curve,
            threshold_pct=rolloff.threshold_pct,
            ceiling_pct=rolloff.ceiling_pct,
            strength_pct=rolloff.strength_pct,
            softness_pct=rolloff.softness_pct,
            desaturation_pct=rolloff.desaturation_pct,
        )


@dataclass
class ChromaBoostBlock:
    enabled: bool = DEFAULT_CHROMA_BOOST_ENABLED
    mode: str = DEFAULT_CHROMA_BOOST_APPLY_MODE
    variant: str = DEFAULT_CHROMA_BOOST_VARIANT
    amount_pct: int = DEFAULT_CHROMA_BOOST_AMOUNT_PCT

    @classmethod
    def from_runtime(cls, boost: ChromaBoostRuntime) -> ChromaBoostBlock:
        return cls(
            enabled=boost.enabled,
            mode=boost.mode,
            variant=boost.variant,
            amount_pct=boost.amount_pct,
        )


@dataclass
class VisualLimiterBlock:
    enabled: bool = DEFAULT_VISUAL_LIMITER_ENABLED
    threshold: float = DEFAULT_VISUAL_LIMITER_THRESHOLD
    ratio: float = DEFAULT_VISUAL_LIMITER_RATIO
    release: float = DEFAULT_VISUAL_LIMITER_RELEASE

    @classmethod
    def from_runtime(cls, limiter: VisualLimiterRuntime) -> VisualLimiterBlock:
        return cls(
            enabled=limiter.enabled,
            threshold=limiter.threshold,
            ratio=limiter.ratio,
            release=limiter.release,
        )


@dataclass
class PostFxBlock:
    fade: FadeBlock = field(default_factory=FadeBlock)
    highlight_rolloff: HighlightRolloffBlock = field(
        default_factory=HighlightRolloffBlock
    )
    chroma_boost: ChromaBoostBlock = field(default_factory=ChromaBoostBlock)
    limiter: VisualLimiterBlock = field(default_factory=VisualLimiterBlock)
    solo: bool = False
    locked: bool = _RO_POST_FX_DEFAULTS["locked"]

    @classmethod
    def from_session(cls, session: TuningSession) -> PostFxBlock:
        pp = session.post_fx
        return cls(
            fade=FadeBlock.from_runtime(pp.fade),
            highlight_rolloff=HighlightRolloffBlock.from_runtime(
                pp.highlight_rolloff
            ),
            chroma_boost=ChromaBoostBlock.from_runtime(pp.chroma_boost),
            limiter=VisualLimiterBlock.from_runtime(pp.limiter),
            solo=session.post_fx_solo,
            locked=pp.locked,
        )


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

    @classmethod
    def from_runtime(cls, pm: PatternMaskRuntime) -> PatternMaskBlock:
        return cls(
            enabled=pm.enabled,
            type=pm.type,
            density=pm.density,
            feather_pct=pm.feather_pct,
            invert=pm.invert,
            transition=pm.transition,
            seed=pm.seed,
            locked=pm.locked,
        )


@dataclass
class TimelineFadeGroupBlock:
    enabled: bool = DEFAULT_TIMELINE_FADES_ENABLED
    fade_in: float = DEFAULT_TIMELINE_SOFT_FADE_IN
    fade_out: float = DEFAULT_TIMELINE_SOFT_FADE_OUT
    crossfade: bool = DEFAULT_TIMELINE_CROSSFADE

    @classmethod
    def from_runtime(cls, group: TimelineFadeGroupRuntime) -> TimelineFadeGroupBlock:
        return cls(
            enabled=group.enabled,
            fade_in=group.fade_in,
            fade_out=group.fade_out,
            crossfade=group.crossfade,
        )


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
    hard_cut_fades: TimelineFadeGroupBlock = field(
        default_factory=default_hard_timeline_fade_group_block
    )
    soft_cut_fades: TimelineFadeGroupBlock = field(
        default_factory=default_soft_timeline_fade_group_block
    )
    locked: bool = DEFAULT_TIMELINE_LOCKED
    song_marker_times: tuple[float, ...] = ()
    song_marker_types: tuple[str, ...] = ()
    # Selected strip clip per slot, for the timeline row inspector page.
    selected_clips: dict[str, TimelineClip] = field(default_factory=dict)

    @classmethod
    def from_session(
        cls, session: TuningSession, duration_sec: float
    ) -> TimelineBlock:
        tl = session.timeline
        markers = session.song_markers.markers
        return cls(
            enabled=tl.enabled,
            bar_phase_offset=tl.bar_phase_offset,
            show_bar_grid=tl.show_bar_grid,
            placement_snap=tl.placement_snap,
            hard_cut_fades=TimelineFadeGroupBlock.from_runtime(tl.hard_cut_fades),
            soft_cut_fades=TimelineFadeGroupBlock.from_runtime(tl.soft_cut_fades),
            locked=tl.locked,
            song_marker_times=tuple(session.song_markers.times),
            song_marker_types=tuple(m.marker_type for m in markers),
            selected_clips=selected_timeline_clips(session, duration_sec),
        )


def selected_timeline_clips(
    session: TuningSession, duration_sec: float
) -> dict[str, TimelineClip]:
    """Each layer's selected strip clip, when that clip still exists."""
    clips: dict[str, TimelineClip] = {}
    for slot in session.layer_z_order:
        clip = selected_clip(session, slot, duration_sec)
        if clip is not None:
            clips[slot] = clip
    return clips


@dataclass
class SettingsBlock:
    editor_mode: str = "visualizer"
    preview_quality: str = DEFAULT_EDITOR_PREVIEW_QUALITY
    navigator_side: str = DEFAULT_NAVIGATOR_SIDE
    help_side: str = DEFAULT_HELP_SIDE
    navigator_expand_click: str = DEFAULT_NAVIGATOR_EXPAND_CLICK
    highlight_new_page: bool = DEFAULT_HIGHLIGHT_NEW_PAGE
    show_tooltips: bool = DEFAULT_SHOW_TOOLTIPS
    crash_log: bool = DEFAULT_CRASH_LOG
    notification_display_sec: int = DEFAULT_NOTIFICATION_DISPLAY_SEC
    theme: str = DEFAULT_THEME
    ui_scale: int = DEFAULT_UI_SCALE
    audio_latency_ms: int = DEFAULT_AUDIO_LATENCY_MS
    tap_latency_ms: int = DEFAULT_TAP_LATENCY_MS

    @classmethod
    def from_session(
        cls, session: TuningSession, editor: EditorConfig
    ) -> SettingsBlock:
        return cls(
            editor_mode=session.settings.editor_mode,
            preview_quality=editor.preview_quality,
            navigator_side=editor.navigator_side,
            help_side=editor.help_side,
            navigator_expand_click=editor.navigator_expand_click,
            highlight_new_page=editor.highlight_new_page,
            show_tooltips=editor.show_tooltips,
            crash_log=editor.crash_log,
            notification_display_sec=editor.notification_display_sec,
            theme=editor.theme,
            ui_scale=editor.ui_scale,
            audio_latency_ms=editor.audio_latency_ms,
            tap_latency_ms=editor.tap_latency_ms,
        )


@dataclass
class ProjectBlock:
    milkdrop_beat_sensitivity: float = DEFAULT_BEAT_SENSITIVITY
    compositor_hdr: bool = DEFAULT_COMPOSITOR_HDR
    width: int = DEFAULT_RESOLUTION_WIDTH
    height: int = DEFAULT_RESOLUTION_HEIGHT

    @classmethod
    def from_session(cls, session: TuningSession) -> ProjectBlock:
        project = session.project
        return cls(
            milkdrop_beat_sensitivity=project.milkdrop_beat_sensitivity,
            compositor_hdr=project.compositor_hdr,
            width=project.resolution.width,
            height=project.resolution.height,
        )


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


@lru_cache(maxsize=64)
def _preset_list_identity(
    entries: tuple[PresetListEntry, ...],
) -> dict[str, int | str]:
    """Digest of a preset list, kept per list content.

    The key hashes the frozen entries, so an unchanged list costs no digest.
    """
    return preset_list_identity(entries)


@lru_cache(maxsize=64)
def _playlist_paths_identity(paths: tuple[Path, ...]) -> dict[str, int | str]:
    """Digest of a preset folder's paths, kept per folder content."""
    return path_list_identity([str(path) for path in paths])


def view_state_structure_signature(
    session: TuningSession,
    config_save: ConfigSaveController,
    *,
    duration_sec: float = math.inf,
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
            "preset_list": _preset_list_identity(tuple(layer.preset_list)),
            "playlist": {
                "current_dir": str(playlist.current_dir),
                "collection": playlist.collection,
                "paths": _playlist_paths_identity(tuple(playlist.paths)),
                "index": playlist.index,
            },
            "auto_preset_path": (
                None
                if layer.auto_preset_path is None
                else str(layer.auto_preset_path)
            ),
            "switching_paused": layer.switching_paused,
            "switching_list_index": layer.switching_list_index,
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
            "highlight_rolloff_enabled": pp.highlight_rolloff.enabled,
            "chroma_boost_enabled": pp.chroma_boost.enabled,
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
            # A selected clip gates the timeline row page's clip rows.
            "selected_clip_slots": sorted(
                selected_timeline_clips(session, duration_sec)
            ),
        },
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class _ViewStateStructure:
    """Track blocks, rebuilt only when the structure signature changes.

    The section blocks are cheap and come from the session every frame
    (``<Block>.from_session`` / ``from_runtime``).
    """

    signature: str
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]


class TuningViewStateBuilder:
    """Build TuningViewState from session and UI state."""

    def __init__(
        self,
        session: TuningSession,
        playback: PlaybackState,
        duration_sec: float,
        preset_root,
        library: PresetLibrary,
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
        self._library = library
        self._get_focus_cursor = get_focus_cursor
        self._get_move_mode_slot = get_move_mode_slot
        self._get_move_mode_preset = get_move_mode_preset
        self._config_save = config_save
        self._get_notification = get_notification
        self._layers_by_slot = layers_by_slot
        self._auto_display_cache: dict[Path, PresetPlaylist] = {}
        self._preset_list_label_cache: dict[
            tuple[PresetListEntry, ...], list[str]
        ] = {}
        self._preset_list_marker_cache: dict[
            tuple[tuple[PresetListEntry, ...], int], list[str]
        ] = {}
        self._list_basenames_cache: dict[
            tuple[PresetListEntry, ...], frozenset[str]
        ] = {}
        self._structure: _ViewStateStructure | None = None

    def invalidate_structure(self) -> None:
        """Rebuild the track blocks on the next ``build``."""
        self._structure = None

    def _sync_auto_preset_paths(self) -> None:
        """Mirror the playing switching preset onto session for panel display."""
        if not isinstance(self._layers_by_slot, dict) or not self._layers_by_slot:
            return
        from cleave.viz.preset_switching import (
            playing_switching_preset_path,
            switching_list_index,
        )

        for slot, stem in self._layers_by_slot.items():
            runtime = self.session.layers.get(slot)
            if runtime is None:
                continue
            playing = playing_switching_preset_path(stem)
            if playing is not None:
                stem.auto_preset_path = playing
            runtime.auto_preset_path = stem.auto_preset_path
            runtime.switching_paused = stem.switching_paused
            runtime.switching_list_index = switching_list_index(stem)
            revision = stem.pm.failure_revision
            if runtime.failed_presets_revision != revision:
                runtime.failed_presets = dict(stem.pm.failed_presets)
                runtime.failed_presets_revision = revision

    def _preset_list_basenames(self, layer: LayerRuntime) -> frozenset[str]:
        """File names in *layer*'s preset list: each project copy and its original."""
        key = tuple(layer.preset_list)
        names = self._list_basenames_cache.get(key)
        if names is None:
            names = frozenset(
                name
                for entry in key
                for name in (entry.file.name, entry.display_name)
            )
            self._list_basenames_cache[key] = names
        return names

    def _display_playlist(self, layer: LayerRuntime) -> PresetPlaylist:
        """Playlist for dir/file rows: playing auto-switch preset when set."""
        auto = layer.auto_preset_path
        if auto is None or auto == layer.playlist.current:
            # Browsing (folder or collection): count within what is browsed.
            return layer.playlist
        cached = self._auto_display_cache.get(auto)
        if cached is not None:
            return cached
        try:
            playlist = scan_preset_playlist(auto, catalog=layer.playlist.catalog)
        except (OSError, ValueError):
            return layer.playlist
        self._auto_display_cache[auto] = playlist
        return playlist

    def _preset_markers(self, layer: LayerRuntime, playlist: PresetPlaylist) -> str:
        """Markers for the current preset row; ``[L]`` is never shown in curation."""
        current = playlist.current
        if current is None:
            return ""
        in_list = (
            not is_preset_curation_mode(self.session.settings.editor_mode)
            and current.name in self._preset_list_basenames(layer)
        )
        return self._library.marker(current, in_preset_list=in_list).strip()

    def _preset_problem(
        self, layer: LayerRuntime, playlist: PresetPlaylist
    ) -> str | None:
        """The preset row's file problem; none inside a missing folder, whose
        directory row carries the mark."""
        current = playlist.current
        health = self.session.preset_health
        if current is None or health.dir_problem(playlist.current_dir) is not None:
            return None
        return health.file_problem(layer, current)

    def _preset_list_labels(self, entries: list[PresetListEntry]) -> list[str]:
        entries_key = tuple(entries)
        labels = self._preset_list_label_cache.get(entries_key)
        if labels is None:
            labels = preset_list_display_names(entries)
            self._preset_list_label_cache[entries_key] = labels
        return labels

    def _preset_list_markers(self, entries: list[PresetListEntry]) -> list[str]:
        key = (tuple(entries), self._library.revision)
        markers = self._preset_list_marker_cache.get(key)
        if markers is None:
            markers = [
                self._library.marker(entry.file).strip()
                for entry in entries
            ]
            self._preset_list_marker_cache[key] = markers
        return markers

    @staticmethod
    def _active_preset_list_index(layer: LayerRuntime) -> int | None:
        """Return the preset_list index to highlight, if any.

        While switching runs, that is the list position (paused: where it
        resumes), not the preset being browsed. Otherwise the list item that
        matches the playing preset. Computed only when the view structure rebuilds (``auto_preset_path`` and
        playlist index are part of ``view_state_structure_signature``), so the
        draw path can read a precomputed index without resolving paths per frame.
        """
        paths = layer.preset_list
        if not paths:
            return None
        if layer.switching_list_index is not None:
            return min(layer.switching_list_index, len(paths) - 1)
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
        for index, entry in enumerate(paths):
            if entry.path in (target_str, target_posix):
                return index
        for index, entry in enumerate(paths):
            if entry.source in (target_str, target_posix):
                return index
        for index, entry in enumerate(paths):
            try:
                if entry.file.resolve() == target:
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
                preset_dir_crumbs=directory_crumbs(
                    layer.playlist, self.preset_root, directory.path
                ),
                preset_dir_position=directory.position,
                preset_dir_can_go_up=directory.can_go_up,
                preset_dir_can_go_down=directory.can_go_down,
                preset_label=preset_filename_display(display),
                preset_position=preset_position_display(display),
                preset_markers=self._preset_markers(layer, display),
                preset_empty=not display.paths,
                visible=layer.enabled,
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
                preset_list_markers=self._preset_list_markers(list(layer.preset_list)),
                preset_dir_problem=self.session.preset_health.dir_problem(
                    display.current_dir
                ),
                preset_problem=self._preset_problem(layer, display),
                preset_list_problems=self.session.preset_health.list_problems(
                    slot, layer
                ),
                active_preset_list_index=self._active_preset_list_index(layer),
            )

        return _ViewStateStructure(
            signature=signature,
            layer_z_order=layer_z_order,
            tracks=tracks,
        )

    def _patch_tracks(
        self,
        structure: _ViewStateStructure,
        *,
        position_sec: float,
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
                preset_markers=self._preset_markers(layer, display),
                preset_list_labels=self._preset_list_labels(list(layer.preset_list)),
                preset_list_markers=self._preset_list_markers(list(layer.preset_list)),
                preset_dir_problem=self.session.preset_health.dir_problem(
                    display.current_dir
                ),
                preset_problem=self._preset_problem(layer, display),
                preset_list_problems=self.session.preset_health.list_problems(
                    slot, layer
                ),
                stem_silent=layer.stem in self.session.silent_stems,
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
        signature = view_state_structure_signature(
            self.session,
            self._config_save,
            duration_sec=self.duration_sec,
        )
        if self._structure is None or self._structure.signature != signature:
            self._structure = self._build_structure(
                signature=signature,
            )
        structure = self._structure

        tracks = self._patch_tracks(
            structure, position_sec=position_sec
        )

        session = self.session
        tl = session.timeline
        return TuningViewState(
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
            solo_slot=session.solo_slot,
            solo_active=session.solo_slot is not None,
            overlays=OverlaysBlock.from_session(session),
            post_fx=PostFxBlock.from_session(session),
            pattern_mask=PatternMaskBlock.from_runtime(session.pattern_mask),
            timeline=TimelineBlock.from_session(session, self.duration_sec),
            settings=SettingsBlock.from_session(
                session, self._config_save.cfg.editor
            ),
            project=ProjectBlock.from_session(session),
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
            fps=fps,
        )
