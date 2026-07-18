"""Editor mode transitions for live tuning (visualizer vs preset curation)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from cleave.config import CleaveConfig, load_config
from cleave.preset_playlist import PresetPlaylist, scan_all_layers
from cleave.project import load_manifest
from cleave.viz.config_save import ConfigSaveController
from cleave.viz.live_layer_bindings import LiveLayerBindings
from cleave.viz.modal import ModalHost, ModalOption
from cleave.viz.session import (
    EDITOR_MODES,
    EditorMode,
    TuningSession,
    session_from_cfg,
)

if TYPE_CHECKING:
    from cleave.viz.wiring import LayerManager

_ENTER_CURATION_DIRTY_MESSAGE = (
    "Save changes before entering preset curation mode?"
)


def is_preset_curation_mode(session: TuningSession) -> bool:
    return session.settings.editor_mode == "preset_curation"


def render_sections_active(session: TuningSession) -> bool:
    """False in preset curation: overlay, post-FX, and timeline must not affect output."""
    return not is_preset_curation_mode(session)


def _replace_cfg(target: CleaveConfig, fresh: CleaveConfig) -> None:
    target.paths = fresh.paths
    target.layers = fresh.layers
    target.editor = fresh.editor
    target.layer_z_order = list(fresh.layer_z_order)
    target.render = fresh.render
    target.timeline = fresh.timeline
    target.config_path = fresh.config_path
    target.user_config_path = fresh.user_config_path


def _merge_session_state(
    target: TuningSession,
    fresh: TuningSession,
    *,
    editor_mode: EditorMode | None = None,
    panel_open: bool | None = None,
) -> None:
    preserve_expanded = target.settings.expanded
    preserve_ui_expanded = target.settings.ui_expanded
    preserve_help = target.help_visible
    preserve_editor_mode = target.settings.editor_mode
    skip_tracker = target.preset_skip_notify_tracker
    log_tracker = target.projectm_log_notify_tracker

    target.layer_z_order = list(fresh.layer_z_order)
    target.layers = dict(fresh.layers)
    target.solo_slot = fresh.solo_slot
    target.render_overlay = fresh.render_overlay
    target.render_overlay_solo = fresh.render_overlay_solo
    target.render_post_fx = fresh.render_post_fx
    target.render_post_fx_solo = fresh.render_post_fx_solo
    target.timeline = fresh.timeline

    target.settings.expanded = preserve_expanded
    target.settings.ui_expanded = preserve_ui_expanded
    mode = editor_mode if editor_mode is not None else preserve_editor_mode
    target.settings.editor_mode = mode
    target.settings.editor_mode_selection = mode
    target.help_visible = preserve_help
    target.preset_skip_notify_tracker = skip_tracker
    target.projectm_log_notify_tracker = log_tracker

    if panel_open is not None:
        target.timeline.panel_open = panel_open


class EditorModeController:
    """Coordinates editor mode changes, dirty prompts, and YAML reload."""

    def __init__(
        self,
        session: TuningSession,
        cfg: CleaveConfig,
        config_save: ConfigSaveController,
        modal_host: ModalHost,
        *,
        project_dir: Path | None = None,
        layer_bindings: LiveLayerBindings | None = None,
        layer_manager: LayerManager | None = None,
        on_mode_changed: Callable[[], None] | None = None,
    ) -> None:
        self.session = session
        self.cfg = cfg
        self._config_save = config_save
        self._modal = modal_host
        self._project_dir = project_dir
        self._layer_bindings = layer_bindings
        self._layer_manager = layer_manager
        self._on_mode_changed = on_mode_changed
        self._enter_curation_after_save = False
        self._config_save.add_on_commit_save(self._on_config_committed)

    def cycle_editor_mode_selection(self, *, forward: bool) -> None:
        modes = EDITOR_MODES
        current = self.session.settings.editor_mode_selection
        try:
            index = modes.index(current)
        except ValueError:
            index = 0
        self.session.settings.editor_mode_selection = modes[
            (index + (1 if forward else -1)) % len(modes)
        ]

    def confirm_editor_mode_selection(self) -> None:
        selected = self.session.settings.editor_mode_selection
        current = self.session.settings.editor_mode
        if selected == current:
            return
        if current == "visualizer" and selected == "preset_curation":
            self.request_enter_curation()
            return
        if current == "preset_curation" and selected == "visualizer":
            self.request_exit_to_visualizer()

    def request_enter_curation(self) -> None:
        if is_preset_curation_mode(self.session):
            return
        if self._config_save.config_dirty:
            self._modal.prompt_choice(
                _ENTER_CURATION_DIRTY_MESSAGE,
                [
                    ModalOption("YES", self._enter_curation_via_save),
                    ModalOption("DISCARD CHANGES", self._enter_curation_via_discard),
                    ModalOption("CANCEL", self._cancel_enter_curation),
                ],
                on_dismiss=self._cancel_enter_curation,
            )
            return
        self._enter_curation_mode()

    def request_exit_to_visualizer(self) -> None:
        if not is_preset_curation_mode(self.session):
            return
        self._reload_active_config(editor_mode="visualizer")
        self._config_save.clear_config_dirty()
        self._notify_mode_changed()

    def sync_selection_to_mode(self) -> None:
        self.session.settings.editor_mode_selection = (
            self.session.settings.editor_mode
        )

    def _enter_curation_via_save(self) -> None:
        self._enter_curation_after_save = True
        self._config_save.prompt_save(on_dismiss=self._cancel_enter_curation)

    def _enter_curation_via_discard(self) -> None:
        self._reload_active_config(editor_mode="preset_curation", panel_open=False)
        self._config_save.clear_config_dirty()
        self._expand_layer_one()
        self._notify_mode_changed()

    def _cancel_enter_curation(self) -> None:
        self._enter_curation_after_save = False
        self.sync_selection_to_mode()

    def _on_config_committed(self) -> None:
        if not self._enter_curation_after_save:
            return
        self._enter_curation_after_save = False
        if is_preset_curation_mode(self.session):
            return
        self._enter_curation_mode()

    def _expand_layer_one(self) -> None:
        if not self.session.layer_z_order:
            return
        slot = self.session.layer_z_order[0]
        self.session.layers[slot].expanded = True

    def _enter_curation_mode(self) -> None:
        self.session.settings.editor_mode = "preset_curation"
        self.session.settings.editor_mode_selection = "preset_curation"
        self.session.timeline.panel_open = False
        self._expand_layer_one()
        self._notify_mode_changed()

    def _reload_active_config(
        self,
        *,
        editor_mode: EditorMode | None = None,
        panel_open: bool | None = None,
    ) -> None:
        active_path = self._config_save.active_config_path
        if active_path is None:
            return
        fresh_cfg = load_config(active_path, self._project_dir)
        _replace_cfg(self.cfg, fresh_cfg)
        playlists = scan_all_layers(self.cfg)
        fresh_session = session_from_cfg(self.cfg, playlists)
        _merge_session_state(
            self.session,
            fresh_session,
            editor_mode=editor_mode,
            panel_open=panel_open,
        )
        if self._project_dir is not None:
            self.session.song_markers.times = list(
                load_manifest(self._project_dir).song_markers
            )
        if self._layer_manager is not None:
            self._layer_manager.playlists.clear()
            self._layer_manager.playlists.update(playlists)
        self._sync_live_layers(playlists)

    def _sync_live_layers(self, playlists: dict[str, PresetPlaylist]) -> None:
        bindings = self._layer_bindings
        if bindings is None:
            return
        for slot in self.session.layer_z_order:
            layer = self.session.layers[slot]
            playlist = playlists.get(slot, layer.playlist)
            layer.playlist = playlist
            bindings.on_preset_change(slot, playlist)
            bindings.on_stem_change(slot, layer.stem)
            bindings.on_blend_change(slot, layer.blend_mode)
            bindings.on_opacity_change(slot, layer.opacity_pct)
            bindings.on_layer_enabled_change(slot, layer.enabled)
            bindings.on_beat_change(slot, layer.beat_sensitivity)
            bindings.on_preset_switching_change(slot)
        bindings.on_timeline_enabled_change()
        if self._layer_manager is not None:
            self._layer_manager.apply_preview_resolutions()

    def _notify_mode_changed(self) -> None:
        if self._on_mode_changed is not None:
            self._on_mode_changed()
