"""Project live tuning session state into overlay view state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from cleave.config import RenderOverlayPosition
from cleave.config_schema import (
    DEFAULT_HARD_CUT_DURATION,
    DEFAULT_HARD_CUT_SENSITIVITY,
    DEFAULT_HARD_CUT_ENABLED,
    DEFAULT_EASTER_EGG,
    DEFAULT_PRESET_START_CLEAN,
    DEFAULT_PRESET_DURATION,
    DEFAULT_SOFT_CUT_DURATION,
    DEFAULT_UI_FADE_SEC,
    default_render_overlay_runtime_values,
    default_render_post_fx_runtime_values,
)
from cleave.extract import StemSource
from cleave.preset_playlist import directory_display, preset_filename_display
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.row_semantics import RowDescriptor, RowKind
from cleave.viz.session import TuningSession, config_path_display

if TYPE_CHECKING:
    from cleave.viz.focus_nav import FocusCursor
    from cleave.viz.row_layout import RowLayout

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
class RenderPostFxBlock:
    enabled: bool = _RO_POST_FX_DEFAULTS["enabled"]
    expanded: bool = _RO_POST_FX_DEFAULTS["expanded"]
    fade_in: float = _RO_POST_FX_DEFAULTS["fade_in"]
    fade_out: float = _RO_POST_FX_DEFAULTS["fade_out"]
    solo: bool = False


@dataclass
class RenderTimelineBlock:
    enabled: bool = False
    expanded: bool = False


@dataclass
class SettingsBlock:
    expanded: bool = False
    render_mode: str = "balanced"
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
    layout: RowLayout = field(init=False, repr=False)

    def __post_init__(self) -> None:
        from cleave.viz.row_layout import RowLayout

        object.__setattr__(self, "layout", RowLayout.build(self))

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
        resolved = self.layout.resolve_navigable(self.focus_descriptor, self)
        return self.layout.find_descriptor(resolved)


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

    def build(
        self,
        *,
        paused: bool,
        position_sec: float | None = None,
        fps: float | None = None,
    ) -> TuningViewState:
        if position_sec is None:
            position_sec = current_sec(self.playback, self.duration_sec)

        from cleave.viz.layer_visibility import effective_layer_enabled

        tracks: dict[str, TrackBlock] = {}
        for slot in self.session.layer_z_order:
            layer = self.session.layers[slot]
            if self.session.timeline.enabled:
                visible = effective_layer_enabled(
                    self.session, slot, position_sec
                )
            else:
                visible = layer.enabled
            tracks[slot] = TrackBlock(
                stem=layer.stem,
                preset_dir_label=directory_display(
                    layer.playlist, self.preset_root
                ),
                preset_label=preset_filename_display(layer.playlist),
                blend_mode=layer.blend_mode,
                opacity_pct=layer.opacity_pct,
                effects=dict(layer.effects),
                effects_expanded=layer.effects_expanded,
                beat_sensitivity=layer.beat_sensitivity,
                enabled=layer.enabled,
                visible=visible,
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
            )

        notification_message, notification_remaining_sec = self._get_notification()

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        tl = self.session.timeline
        state = TuningViewState(
            layer_z_order=tuple(self.session.layer_z_order),
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_cursor=self._get_focus_cursor(),
            move_mode_slot=self._get_move_mode_slot(),
            notification_message=notification_message,
            notification_remaining_sec=notification_remaining_sec,
            allow_overwrite=self._config_save.allow_overwrite(),
            active_config_label=config_path_display(self._config_save.active_config_path),
            config_dirty=self._config_save.config_dirty,
            solo_slot=self.session.solo_slot,
            solo_active=self.session.solo_slot is not None,
            render_overlay=RenderOverlayBlock(
                enabled=ro.enabled,
                expanded=ro.expanded,
                position=ro.position,
                title_expanded=ro.title_expanded,
                body_expanded=ro.body_expanded,
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
            render_post_fx=RenderPostFxBlock(
                enabled=pp.enabled,
                expanded=pp.expanded,
                fade_in=pp.fade_in,
                fade_out=pp.fade_out,
                solo=self.session.render_post_fx_solo,
            ),
            render_timeline=RenderTimelineBlock(
                enabled=tl.enabled,
                expanded=tl.panel_open,
            ),
            settings=SettingsBlock(
                expanded=self.session.settings.expanded,
                render_mode=self._config_save.cfg.visualizer.render_mode,
                ui_fade=self._config_save.cfg.visualizer.ui_fade,
            ),
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
            fps=fps,
        )
        return state
