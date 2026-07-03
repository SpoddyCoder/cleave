"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from cleave.config import RenderOverlayPosition
from cleave.config_schema import (
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
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_UI_FADE_SEC,
    DEFAULT_UI_WIDTH,
    DEFAULT_UI_WIDTH_MODE,
    default_render_overlay_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.extract import StemSource
from cleave.preset_playlist import preset_filename_display
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.session import TuningSession, config_path_display

if TYPE_CHECKING:
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.row_layout import RowLayout, RowLayoutFrame

_RO_OVERLAY_DEFAULTS = default_render_overlay_runtime_values()
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
    preset_switching_expanded: bool = False
    enabled: bool = True
    visible: bool = True
    expanded: bool = False
    locked: bool = False
    preset_empty: bool = False
    preset_switching: str = "none"
    preset_switching_scope: str = "directory"
    preset_duration: float = DEFAULT_PRESET_DURATION
    soft_cut_duration: float = DEFAULT_SOFT_CUT_DURATION
    hard_cut_duration: float = DEFAULT_HARD_CUT_DURATION
    hard_cut_sensitivity: float = DEFAULT_HARD_CUT_SENSITIVITY
    hard_cut_enabled: bool = DEFAULT_HARD_CUT_ENABLED
    easter_egg: float = DEFAULT_EASTER_EGG
    preset_start_clean: bool = DEFAULT_PRESET_START_CLEAN
    user_presets: list[str] = field(default_factory=list)
    user_presets_expanded: bool = False


@dataclass
class RenderOverlayBlock:
    enabled: bool = _RO_OVERLAY_DEFAULTS["enabled"]
    expanded: bool = _RO_OVERLAY_DEFAULTS["expanded"]
    position: RenderOverlayPosition = _RO_OVERLAY_DEFAULTS["position"]
    title_expanded: bool = _RO_OVERLAY_DEFAULTS["title_expanded"]
    body_expanded: bool = _RO_OVERLAY_DEFAULTS["body_expanded"]
    title_font_size: int = _RO_OVERLAY_DEFAULTS["title_font_size"]
    title_font: str = _RO_OVERLAY_DEFAULTS["title_font"]
    title_margin_bottom: int = _RO_OVERLAY_DEFAULTS["title_margin_bottom"]
    body_font_size: int = _RO_OVERLAY_DEFAULTS["body_font_size"]
    body_font: str = _RO_OVERLAY_DEFAULTS["body_font"]
    opacity_pct: int = _RO_OVERLAY_DEFAULTS["opacity_pct"]
    border_width: int = _RO_OVERLAY_DEFAULTS["border_width"]
    start_delay: float = _RO_OVERLAY_DEFAULTS["start_delay"]
    display_time: float = _RO_OVERLAY_DEFAULTS["display_time"]
    solo: bool = False


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


@dataclass
class RenderTimelineBlock:
    enabled: bool = False
    expanded: bool = False


@dataclass
class SettingsBlock:
    expanded: bool = False
    ui_expanded: bool = False
    preview_quality: str = "balanced"
    ui_width_mode: str = DEFAULT_UI_WIDTH_MODE
    ui_width: int = DEFAULT_UI_WIDTH
    ui_fade: float = DEFAULT_UI_FADE_SEC


@dataclass
class TuningViewState:
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    paused: bool
    position_sec: float
    focus_cursor: FocusCursor
    move_mode_slot: str | None
    notification_message: str | None = None
    notification_remaining_sec: float = 0.0
    allow_overwrite: bool = True
    active_config_label: str = "cleave-viz.yaml"
    config_dirty: bool = False
    solo_slot: str | None = None
    solo_active: bool = False
    render_overlay: RenderOverlayBlock = field(default_factory=RenderOverlayBlock)
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
) -> str:
    layers: dict[str, object] = {}
    for slot in session.layer_z_order:
        layer = session.layers[slot]
        playlist = layer.playlist
        layers[slot] = {
            "expanded": layer.expanded,
            "effects_expanded": layer.effects_expanded,
            "preset_switching_expanded": layer.preset_switching_expanded,
            "user_presets_expanded": layer.user_presets_expanded,
            "preset_switching": layer.preset_switching,
            "preset_switching_scope": layer.preset_switching_scope,
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
        }
    ro = session.render_overlay
    pp = session.render_post_fx
    tl = session.timeline
    payload = {
        "layer_z_order": list(session.layer_z_order),
        "settings": {
            "expanded": session.settings.expanded,
            "ui_expanded": session.settings.ui_expanded,
        },
        "notification_active": notification_active,
        "layers": layers,
        "render_overlay": {
            "enabled": ro.enabled,
            "expanded": ro.expanded,
            "title_expanded": ro.title_expanded,
            "body_expanded": ro.body_expanded,
        },
        "render_post_fx": {
            "enabled": pp.enabled,
            "expanded": pp.expanded,
            "highlight_rolloff_expanded": pp.highlight_rolloff_expanded,
            "highlight_rolloff_mode": pp.highlight_rolloff.mode,
            "chroma_boost_expanded": pp.chroma_boost_expanded,
            "chroma_boost_mode": pp.chroma_boost.mode,
        },
        "render_timeline": {"enabled": tl.enabled},
        "timeline": {"enabled": tl.enabled},
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class _ViewStateStructure:
    signature: str
    layer_z_order: tuple[str, ...]
    tracks: dict[str, TrackBlock]
    settings: SettingsBlock
    render_overlay: RenderOverlayBlock
    render_post_fx: RenderPostFxBlock
    render_timeline: RenderTimelineBlock
    layout: RowLayout


class TuningViewStateBuilder:
    """Build TuningViewState from session and UI state."""

    def __init__(
        self,
        session: TuningSession,
        playback: PlaybackState,
        duration_sec: float,
        preset_root,
        *,
        get_focus_cursor: Callable[[], FocusCursor],
        get_move_mode_slot: Callable[[], str | None],
        config_save: ConfigSaveController,
        get_notification: Callable[[], tuple[str | None, float]],
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self.preset_root = preset_root
        self._get_focus_cursor = get_focus_cursor
        self._get_move_mode_slot = get_move_mode_slot
        self._config_save = config_save
        self._get_notification = get_notification
        self._structure: _ViewStateStructure | None = None

    def _build_structure(
        self,
        *,
        signature: str,
        notification_active: bool,
    ) -> _ViewStateStructure:
        from cleave.viz.focus_nav import MainFocus

        layer_z_order = tuple(self.session.layer_z_order)
        tracks: dict[str, TrackBlock] = {}
        for slot in layer_z_order:
            layer = self.session.layers[slot]
            tracks[slot] = TrackBlock(
                stem=layer.stem,
                preset_dir_label=layer.playlist.directory_display_label(
                    self.preset_root
                ),
                preset_label=preset_filename_display(layer.playlist),
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                effects=dict(layer.effects),
                effects_expanded=layer.effects_expanded,
                preset_switching_expanded=layer.preset_switching_expanded,
                beat_sensitivity=layer.beat_sensitivity,
                enabled=layer.enabled,
                visible=layer.enabled,
                expanded=layer.expanded,
                locked=layer.locked,
                preset_empty=not layer.playlist.paths,
                preset_switching=layer.preset_switching,
                preset_switching_scope=layer.preset_switching_scope,
                preset_duration=layer.preset_duration,
                soft_cut_duration=layer.soft_cut_duration,
                hard_cut_duration=layer.hard_cut_duration,
                hard_cut_sensitivity=layer.hard_cut_sensitivity,
                hard_cut_enabled=layer.hard_cut_enabled,
                easter_egg=layer.easter_egg,
                preset_start_clean=layer.preset_start_clean,
                user_presets=list(layer.user_presets),
                user_presets_expanded=layer.user_presets_expanded,
            )

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        tl = self.session.timeline
        settings = SettingsBlock(
            expanded=self.session.settings.expanded,
            ui_expanded=self.session.settings.ui_expanded,
        )
        render_overlay = RenderOverlayBlock(
            enabled=ro.enabled,
            expanded=ro.expanded,
            title_expanded=ro.title_expanded,
            body_expanded=ro.body_expanded,
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
        render_timeline = RenderTimelineBlock(enabled=tl.enabled)
        layout_state = TuningViewState(
            layer_z_order=layer_z_order,
            tracks=tracks,
            paused=False,
            position_sec=0.0,
            focus_cursor=MainFocus(RowDescriptor(RowKind.TRANSPORT)),
            move_mode_slot=None,
            notification_message="…" if notification_active else None,
            notification_remaining_sec=1.0 if notification_active else 0.0,
            render_overlay=render_overlay,
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
            render_overlay=render_overlay,
            render_post_fx=render_post_fx,
            render_timeline=render_timeline,
            layout=layout,
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
            if self.session.timeline.enabled:
                visible = effective_layer_enabled(
                    self.session, slot, position_sec
                )
            else:
                visible = layer.enabled
            tracks[slot] = replace(
                base,
                stem=layer.stem,
                enabled=layer.enabled,
                visible=visible,
                locked=layer.locked,
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                beat_sensitivity=layer.beat_sensitivity,
                preset_label=preset_filename_display(layer.playlist),
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

        notification_message, notification_remaining_sec = self._get_notification()
        notification_active = bool(
            notification_message and notification_remaining_sec > 0
        )
        signature = view_state_structure_signature(
            self.session,
            self._config_save,
            notification_active=notification_active,
        )
        if self._structure is None or self._structure.signature != signature:
            self._structure = self._build_structure(
                signature=signature,
                notification_active=notification_active,
            )
        structure = self._structure

        tracks = self._patch_tracks(structure, position_sec=position_sec)

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        tl = self.session.timeline
        state = TuningViewState(
            layer_z_order=structure.layer_z_order,
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_cursor=self._get_focus_cursor(),
            move_mode_slot=self._get_move_mode_slot(),
            notification_message=notification_message,
            notification_remaining_sec=notification_remaining_sec,
            allow_overwrite=self._config_save.allow_overwrite(),
            active_config_label=config_path_display(
                self._config_save.active_config_path
            ),
            config_dirty=self._config_save.config_dirty,
            solo_slot=self.session.solo_slot,
            solo_active=self.session.solo_slot is not None,
            render_overlay=replace(
                structure.render_overlay,
                position=ro.position,
                title_font_size=ro.title_font_size,
                title_font=ro.title_font,
                title_margin_bottom=ro.title_margin_bottom,
                body_font_size=ro.body_font_size,
                body_font=ro.body_font,
                opacity_pct=ro.opacity_pct,
                border_width=ro.border_width,
                start_delay=ro.start_delay,
                display_time=ro.display_time,
                solo=self.session.render_overlay_solo,
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
            ),
            render_timeline=replace(
                structure.render_timeline,
                expanded=tl.panel_open,
            ),
            settings=replace(
                structure.settings,
                preview_quality=self._config_save.cfg.visualizer.preview_quality,
                ui_width_mode=self._config_save.cfg.visualizer.ui_width_mode,
                ui_width=self._config_save.cfg.visualizer.ui_width,
                ui_fade=self._config_save.cfg.visualizer.ui_fade,
            ),
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
            fps=fps,
            layout=structure.layout,
        )
        return state
