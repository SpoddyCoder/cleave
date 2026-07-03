"""Tests for cleave.projectm_health live failure draining."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from cleave.projectm import PresetLoadFailure, ProjectM
from cleave.projectm_health import (
    PRESET_SKIP_NOTIFICATION_INTERVAL_SEC,
    drain_stem_layers_preset_failures,
)
from cleave.viz.layer import StemLayer
from cleave.viz.preset_switching import EMPTY_ROTATION_NOTIFICATION


def _layer_with_failures(*failures: PresetLoadFailure) -> StemLayer:
    pm = ProjectM.__new__(ProjectM)
    pm.drain_preset_failures = MagicMock(return_value=list(failures))
    return StemLayer(
        slot="layer_1",
        pm=pm,
        fbo=MagicMock(),
        playlist=MagicMock(),
    )


def test_drain_notifies_skipped_preset_rate_limited() -> None:
    import cleave.projectm_health as health

    health._last_skip_notify.clear()
    layer = _layer_with_failures(
        PresetLoadFailure(filename="/tmp/a.milk", message="bad")
    )
    notify = MagicMock()

    drain_stem_layers_preset_failures([layer], on_notification=notify)
    notify.assert_called_once_with("Skipped preset: a.milk")

    notify.reset_mock()
    drain_stem_layers_preset_failures([layer], on_notification=notify)
    notify.assert_not_called()

    health._last_skip_notify["layer_1"] = (
        time.monotonic() - PRESET_SKIP_NOTIFICATION_INTERVAL_SEC - 1
    )
    drain_stem_layers_preset_failures([layer], on_notification=notify)
    notify.assert_called_once_with("Skipped preset: a.milk")


def test_drain_notifies_exhausted_rotation() -> None:
    layer = _layer_with_failures(
        PresetLoadFailure(
            filename="/tmp/bad.milk",
            message="exhausted",
            exhausted=True,
        )
    )
    notify = MagicMock()
    drain_stem_layers_preset_failures([layer], on_notification=notify)
    notify.assert_called_once_with(EMPTY_ROTATION_NOTIFICATION)
