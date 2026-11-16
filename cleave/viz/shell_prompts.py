"""Prompts the shell draws on its top layer: tap sync progress, a modal, the project picker."""

from __future__ import annotations

from imgui_bundle import imgui

from cleave.viz.controls import TuningControls
from cleave.viz.file_picker_surface import FilePickerSurface
from cleave.viz.modal import ModalHost, ModalKind
from cleave.viz.modal_surface import (
    ImGuiTextMeasure,
    ModalSurface,
    apply_modal_pointer,
    text_field_wrap,
)
from cleave.viz.tap_sync_controls import tap_sync_info_panel
from cleave.viz.top_layer import InfoPanelSurface, TopLayer


class ShellPrompts:
    """Pushes the open prompt before the shell frame, applies its clicks after.

    The modal wins over the project picker; tap sync progress stacks under either.
    """

    def __init__(self, controls: TuningControls, modal_host: ModalHost) -> None:
        self._controls = controls
        self._modal_host = modal_host
        self._modal: ModalSurface | None = None
        self._picker: FilePickerSurface | None = None

    def push(self, top_layer: TopLayer) -> None:
        """Queue this frame's prompt surfaces on the top layer."""
        self._modal = None
        self._picker = None
        tap_sync = self._controls.tap_sync
        if tap_sync.showing_progress:
            progress = tap_sync.progress_view()
            if progress is not None:
                top_layer.push(InfoPanelSurface(tap_sync_info_panel(progress)))
        if self._modal_host.active:
            modal_view = self._modal_host.view_state()
            if modal_view is not None:
                self._modal = ModalSurface(
                    modal_view,
                    ImGuiTextMeasure(),
                    passthrough=top_layer.lifted_rects,
                )
                top_layer.push(self._modal)
        elif self._controls.project_switch.active:
            picker_view = self._controls.project_switch.view_state()
            if picker_view is not None:
                self._picker = FilePickerSurface(picker_view)
                top_layer.push(self._picker)

    def apply(self) -> None:
        """After the shell frame: act on the clicks the surfaces collected."""
        if self._modal is not None and self._modal.intent is not None:
            apply_modal_pointer(self._modal_host, self._modal.intent)
        if self._picker is not None and self._picker.intent is not None:
            self._controls.project_switch.apply_pointer(self._picker.intent)
        shown = self._modal_host.view_state()
        if shown is not None and shown.kind == ModalKind.TEXT:
            display_w = max(1, int(imgui.get_io().display_size.x))
            self._modal_host.set_text_field_wrap(text_field_wrap(display_w))
        else:
            self._modal_host.set_text_field_wrap(None)
