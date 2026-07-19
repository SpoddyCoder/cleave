"""Tests for per-layer shuffle seed modal controller."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.preset_playlist import PresetPlaylist
from cleave.preset_rotation import PresetRotation
from cleave.viz.layer import StemLayer
from cleave.viz.modal import ModalHost
from cleave.viz.preset_seed_controls import PresetSeedController
from cleave.viz.session import LayerRuntime, TuningSession


def _runtime(
    *,
    mode: str = "none",
    shuffle: bool = False,
    salt: int = 0,
) -> LayerRuntime:
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/drums"),
        paths=(Path("/tmp/presets/drums/a.milk"),),
        index=0,
    )
    return LayerRuntime(
        playlist=playlist,
        browse_floor=playlist.current_dir,
        stem="drums",
        preset_switching=mode,  # type: ignore[arg-type]
        preset_switching_shuffle=shuffle,
        preset_switching_shuffle_salt=salt,
    )


def _session(*runtimes: tuple[str, LayerRuntime]) -> TuningSession:
    order = [slot for slot, _ in runtimes]
    return TuningSession(
        layer_z_order=order,
        layers={slot: runtime for slot, runtime in runtimes},
    )


def test_prompt_opens_yes_cancel_when_shuffle_on() -> None:
    session = _session(("layer_1", _runtime(mode="projectm", shuffle=True, salt=1)))
    controller = PresetSeedController(session, ModalHost(), {})
    controller.prompt("layer_1")
    assert controller._modal.active is True
    view = controller._modal.view_state()
    assert view is not None
    assert view.message == "Generate a new seed?"
    assert view.options == ("Yes", "Cancel")


def test_prompt_noop_when_shuffle_off() -> None:
    session = _session(("layer_1", _runtime(mode="projectm", shuffle=False)))
    controller = PresetSeedController(session, ModalHost(), {})
    controller.prompt("layer_1")
    assert controller._modal.active is False


def test_prompt_noop_when_switching_none() -> None:
    session = _session(("layer_1", _runtime(mode="none", shuffle=True)))
    controller = PresetSeedController(session, ModalHost(), {})
    controller.prompt("layer_1")
    assert controller._modal.active is False


def test_confirm_changes_salt_and_rebuilds_projectm() -> None:
    session = _session(
        ("layer_1", _runtime(mode="projectm", shuffle=True, salt=1)),
    )
    switched: list[str] = []
    controller = PresetSeedController(
        session,
        ModalHost(),
        {},
        on_preset_switching_change=switched.append,
    )
    controller._confirm("layer_1")
    assert session.layers["layer_1"].preset_switching_shuffle_salt != 1
    assert switched == ["layer_1"]


@patch("cleave.viz.preset_seed_controls.rebuild_timeline_preset_rotation_preserving_count")
def test_confirm_timeline_preserves_switch_count(
    mock_rebuild: MagicMock,
) -> None:
    runtime = _runtime(mode="timeline", shuffle=True, salt=5)
    session = _session(("layer_1", runtime))
    layer = StemLayer(
        slot="layer_1",
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=runtime.playlist,
    )
    layer.timeline_switch_count = 3
    layer.rotation_anchor = 1
    layer.preset_rotation = PresetRotation(
        paths=(Path("a.milk"), Path("b.milk")),
        shuffle=True,
        seed=1,
        anchor=1,
    )
    controller = PresetSeedController(
        session,
        ModalHost(),
        {"layer_1": layer},
    )
    controller._confirm("layer_1")
    assert runtime.preset_switching_shuffle_salt != 5
    mock_rebuild.assert_called_once()
    kwargs = mock_rebuild.call_args.kwargs
    assert kwargs["shuffle_salt"] == runtime.preset_switching_shuffle_salt
    assert layer.timeline_switch_count == 3
