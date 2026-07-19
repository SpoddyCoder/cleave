"""Per-layer shuffle seed confirm modal and salt re-roll orchestration."""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

from cleave.viz.layer import StemLayer
from cleave.viz.modal import ModalHost
from cleave.viz.preset_switching import rebuild_timeline_preset_rotation_preserving_count
from cleave.viz.session import LayerRuntime, TuningSession

_PROMPT = "Generate a new seed?"


def _new_salt(current: int) -> int:
    while True:
        candidate = random.getrandbits(31)
        if candidate != current:
            return candidate


class PresetSeedController:
    """Prompt for and apply a new shuffle salt on one layer."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        layers_by_slot: Mapping[str, StemLayer],
        *,
        on_preset_switching_change: Callable[[str], None] | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._layers_by_slot = layers_by_slot
        self._on_preset_switching_change = on_preset_switching_change

    def prompt(self, slot: str) -> None:
        runtime = self.session.layers.get(slot)
        if runtime is None or not runtime.preset_switching_shuffle:
            return
        if runtime.preset_switching not in ("projectm", "timeline"):
            return
        self._modal.prompt_yes_no(
            _PROMPT,
            on_confirm=lambda: self._confirm(slot),
            cancel_label="Cancel",
        )

    def _confirm(self, slot: str) -> None:
        runtime = self.session.layers.get(slot)
        if runtime is None or not runtime.preset_switching_shuffle:
            return
        if runtime.preset_switching not in ("projectm", "timeline"):
            return
        runtime.preset_switching_shuffle_salt = _new_salt(
            runtime.preset_switching_shuffle_salt
        )
        self._rebuild(slot, runtime)

    def _rebuild(self, slot: str, runtime: LayerRuntime) -> None:
        if runtime.preset_switching == "timeline":
            layer = self._layers_by_slot.get(slot)
            if layer is None:
                return
            rebuild_timeline_preset_rotation_preserving_count(
                layer,
                rotation_set=runtime.preset_switching_rotation_set,
                user_presets=runtime.user_presets,
                shuffle=runtime.preset_switching_shuffle,
                shuffle_salt=runtime.preset_switching_shuffle_salt,
                preset_start_clean=runtime.preset_start_clean,
            )
            return
        if self._on_preset_switching_change is not None:
            self._on_preset_switching_change(slot)
