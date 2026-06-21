"""Unit tests for session add/remove helpers."""

from __future__ import annotations

from pathlib import Path

from cleave.preset_playlist import PresetPlaylist
from cleave.viz.session import (
    LayerRuntime,
    TuningSession,
    add_layer_to_session,
    remove_layer_from_session,
)


def _runtime(slot: str) -> LayerRuntime:
    current_dir = Path(f"/tmp/presets/{slot}")
    return LayerRuntime(
        playlist=PresetPlaylist(current_dir=current_dir, paths=(), index=0),
        browse_floor=current_dir,
        stem="full_mix",
    )


def test_add_layer_to_session_appends_slot_and_runtime() -> None:
    session = TuningSession(layer_z_order=["layer_1"], layers={"layer_1": _runtime("layer_1")})
    runtime = _runtime("layer_2")

    add_layer_to_session(session, "layer_2", runtime)

    assert session.layer_z_order == ["layer_1", "layer_2"]
    assert session.layers["layer_2"] is runtime


def test_remove_layer_from_session_drops_slot() -> None:
    session = TuningSession(
        layer_z_order=["layer_1", "layer_2"],
        layers={
            "layer_1": _runtime("layer_1"),
            "layer_2": _runtime("layer_2"),
        },
    )

    remove_layer_from_session(session, "layer_2")

    assert session.layer_z_order == ["layer_1"]
    assert "layer_2" not in session.layers


def test_remove_layer_from_session_clears_solo() -> None:
    session = TuningSession(
        layer_z_order=["layer_1"],
        layers={"layer_1": _runtime("layer_1")},
        solo_slot="layer_1",
    )

    remove_layer_from_session(session, "layer_1")

    assert session.solo_slot is None
