"""Project live tuning session state into overlay view state."""

from __future__ import annotations

import time
from collections.abc import Callable

from cleave.preset_playlist import directory_display, preset_filename_display
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.overlay import (
    RenderOverlayBlock,
    RenderPostFxBlock,
    RenderTimelineBlock,
    TrackBlock,
    TuningViewState,
)
from cleave.viz.playback import PlaybackState, current_sec
from cleave.viz.session import TuningSession, config_path_display


class TuningViewStateBuilder:
    """Build TuningViewState from session and UI state."""

    def __init__(
        self,
        session: TuningSession,
        playback: PlaybackState,
        duration_sec: float,
        preset_root,
        *,
        get_focus_index: Callable[[], int],
        get_move_mode_stem: Callable[[], str | None],
        config_save: ConfigSaveController,
        get_toast_message: Callable[[], str | None],
        get_toast_deadline: Callable[[], float],
    ) -> None:
        self.session = session
        self.playback = playback
        self.duration_sec = duration_sec
        self.preset_root = preset_root
        self._get_focus_index = get_focus_index
        self._get_move_mode_stem = get_move_mode_stem
        self._config_save = config_save
        self._get_toast_message = get_toast_message
        self._get_toast_deadline = get_toast_deadline

    def build(
        self,
        *,
        paused: bool,
        position_sec: float | None = None,
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
            )

        toast_remaining = 0.0
        toast_message: str | None = None
        toast = self._get_toast_message()
        if toast is not None:
            toast_remaining = max(0.0, self._get_toast_deadline() - time.monotonic())
            if toast_remaining > 0:
                toast_message = toast

        ro = self.session.render_overlay
        pp = self.session.render_post_fx
        tl = self.session.timeline
        return TuningViewState(
            layer_z_order=tuple(self.session.layer_z_order),
            tracks=tracks,
            paused=paused,
            position_sec=position_sec,
            focus_index=self._get_focus_index(),
            move_mode_stem=self._get_move_mode_stem(),
            toast_message=toast_message,
            toast_remaining_sec=toast_remaining,
            allow_overwrite=self._config_save.allow_overwrite(),
            active_config_label=config_path_display(self._config_save.active_config_path),
            config_dirty=self._config_save.config_dirty,
            solo_stem=self.session.solo_slot,
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
            timeline_submenu_focused=tl.submenu_focused,
            timeline_recording=tl.recording,
            timeline_override_active=bool(tl.override_slots),
            help_visible=self.session.help_visible,
        )
