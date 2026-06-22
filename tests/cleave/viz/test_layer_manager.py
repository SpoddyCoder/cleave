"""Unit tests for LayerManager."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.config_schema import MAX_LAYER_COUNT, MIN_LAYER_COUNT
from cleave.preset_playlist import PresetPlaylist
from cleave.timeline import TimelineCue
from cleave.viz.layer import StemLayer
from cleave.viz.session import LayerRuntime, TuningSession
from cleave.viz.wiring import LayerManager, _discard_timeline_slot
from tests.support.viz import make_test_cfg


def _manager(
    slots: tuple[str, ...] = ("layer_1",),
) -> tuple[LayerManager, MagicMock]:
    preset_root = Path("/tmp/presets")
    cfg = make_test_cfg(slots, preset_root=preset_root)
    session = TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / slot,
                    paths=(preset_root / slot / "preset-0.milk",),
                    index=0,
                ),
                browse_floor=preset_root / slot,
                stem="drums",
            )
            for slot in slots
        },
    )
    compositor = MagicMock()
    layers: list[StemLayer] = []
    layers_by_slot: dict[str, StemLayer] = {}
    playlists = {
        slot: PresetPlaylist(
            current_dir=preset_root / slot,
            paths=(preset_root / slot / "preset-0.milk",),
            index=0,
        )
        for slot in slots
    }
    for slot in slots:
        stem_layer = StemLayer(
            slot=slot,
            pm=MagicMock(),
            fbo=MagicMock(),
            playlist=playlists[slot],
        )
        layers.append(stem_layer)
        layers_by_slot[slot] = stem_layer

    manager = LayerManager(
        cfg=cfg,
        session=session,
        compositor=compositor,
        layers=layers,
        layers_by_slot=layers_by_slot,
        playlists=playlists,
        preset_root=preset_root,
        project_dir=Path("/tmp/projects/test"),
        projectm_fps=30,
        texture_paths=[],
    )
    return manager, compositor


def test_can_add_and_can_remove_respect_limits() -> None:
    manager, _ = _manager(("layer_1",))
    assert manager.can_add() is True
    assert manager.can_remove() is False

    manager.session.layer_z_order = [f"layer_{i}" for i in range(1, MAX_LAYER_COUNT + 1)]
    assert manager.can_add() is False
    assert manager.can_remove() is True

    manager.session.layer_z_order = [f"layer_{i}" for i in range(1, MIN_LAYER_COUNT + 1)]
    assert manager.can_remove() is False


@patch("cleave.viz.wiring.LayerFramePipeline.build_single")
@patch("cleave.viz.wiring.scan_single_layer")
def test_add_layer_updates_cfg_session_and_collections(
    scan_single_layer: MagicMock,
    build_single: MagicMock,
) -> None:
    manager, compositor = _manager(("layer_1",))
    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/new"),
        paths=(Path("/tmp/presets/new/preset.milk"),),
        index=0,
    )
    scan_single_layer.return_value = playlist
    stem_layer = StemLayer(
        slot="layer_2",
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=playlist,
    )
    build_single.return_value = stem_layer

    slot = manager.add_layer()

    assert slot == "layer_2"
    assert "layer_2" in manager.cfg.layers
    assert manager.cfg.layer_z_order == ["layer_1", "layer_2"]
    assert manager.session.layer_z_order == ["layer_1", "layer_2"]
    assert manager.session.layers["layer_2"].stem == "full_mix"
    assert manager.layers_by_slot["layer_2"] is stem_layer
    assert manager.playlists["layer_2"] is playlist
    assert stem_layer in manager.layers
    build_single.assert_called_once()
    assert build_single.call_args.kwargs["beat_sensitivity"] == manager.cfg.visualizer.beat_sensitivity
    compositor.resize_layer_fbo.assert_called()


@patch("cleave.viz.wiring.LayerFramePipeline.destroy_single")
def test_remove_layer_updates_cfg_session_and_collections(
    destroy_single: MagicMock,
) -> None:
    manager, compositor = _manager(("layer_1", "layer_2"))
    manager.session.solo_slot = "layer_2"

    manager.remove_layer("layer_2")

    destroy_single.assert_called_once_with(
        "layer_2", manager.layers, manager.layers_by_slot, compositor
    )
    assert "layer_2" not in manager.cfg.layers
    assert manager.cfg.layer_z_order == ["layer_1"]
    assert manager.session.layer_z_order == ["layer_1"]
    assert "layer_2" not in manager.session.layers
    assert manager.session.solo_slot is None
    assert "layer_2" not in manager.playlists


def test_discard_timeline_slot_strips_slot_from_timeline_state() -> None:
    session = TuningSession(layer_z_order=["layer_1", "layer_2"])
    session.timeline.armed_slots.add("layer_2")
    session.timeline.override_slots.add("layer_2")
    session.timeline.record_baseline["layer_2"] = True
    session.timeline.monitor["layer_2"] = False
    session.timeline.override_visible["layer_2"] = True
    session.timeline.arm_flash_start_ms["layer_2"] = 100
    session.timeline.record_buffer = [
        TimelineCue(t=1.0, layers={"layer_1": True, "layer_2": False}),
        TimelineCue(t=2.0, layers={"layer_2": True}),
    ]

    _discard_timeline_slot(session, "layer_2")

    assert "layer_2" not in session.timeline.armed_slots
    assert "layer_2" not in session.timeline.override_slots
    assert "layer_2" not in session.timeline.record_baseline
    assert "layer_2" not in session.timeline.monitor
    assert "layer_2" not in session.timeline.override_visible
    assert "layer_2" not in session.timeline.arm_flash_start_ms
    assert session.timeline.record_buffer == [
        TimelineCue(t=1.0, layers={"layer_1": True}),
    ]
