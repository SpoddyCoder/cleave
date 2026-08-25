"""Session is the live authority for creative layer state; cfg.layers is bootstrap only."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.config import LayerConfig
from cleave.config_schema.persist import persisted_session_payload
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.session import (
    add_layer_to_session,
    new_layer_runtime,
    session_from_cfg,
)
from cleave.viz.wiring import LayerManager
from tests.support.viz import make_playlist, make_test_cfg


def _playlists_for_cfg(cfg) -> dict[str, PresetPlaylist]:
    return {slot: make_playlist(slot) for slot in cfg.layers}


def test_persisted_layers_ignore_poisoned_cfg() -> None:
    cfg = make_test_cfg(("layer_1",))
    session = session_from_cfg(cfg, _playlists_for_cfg(cfg))
    runtime = session.layers["layer_1"]
    runtime.opacity_pct = 37
    runtime.blend_mode = "add"
    runtime.stem = "vocals"
    runtime.beat_sensitivity = 0.25
    extra = new_layer_runtime(
        "layer_2",
        make_playlist("layer_2"),
        cfg.paths.preset_root,
        1.5,
    )
    add_layer_to_session(session, "layer_2", extra)
    session.layer_z_order[:] = ["layer_2", "layer_1"]

    cfg.layers.clear()
    cfg.layers["layer_1"] = LayerConfig(
        preset=Path("/tmp/poisoned.milk"),
        stem="drums",
        opacity=0.01,
        blend_mode="black-key",
        enabled=False,
        beat_sensitivity=5.0,
    )
    cfg.layer_z_order[:] = ["layer_1"]

    payload = persisted_session_payload(cfg, session)
    assert payload["layer_z_order"] == ["layer_2", "layer_1"]
    layer_1 = payload["layers"]["layer_1"]
    assert layer_1["opacity"] == 0.37
    assert layer_1["blend_mode"] == "add"
    assert layer_1["stem"] == "vocals"
    assert layer_1["beat_sensitivity"] == 0.25
    layer_2 = payload["layers"]["layer_2"]
    assert layer_2["stem"] == "full_mix"
    assert layer_2["beat_sensitivity"] == 1.5


@patch("cleave.viz.layer_pipeline.apply_preset_switching")
@patch("cleave.viz.layer_pipeline.ProjectM")
def test_build_seeds_fbo_from_session_not_cfg(
    project_m: MagicMock,
    _apply_preset_switching: MagicMock,
) -> None:
    cfg = make_test_cfg(("layer_1",))
    session = session_from_cfg(cfg, _playlists_for_cfg(cfg))
    runtime = session.layers["layer_1"]
    runtime.opacity_pct = 40
    runtime.blend_mode = "add"
    runtime.enabled = False
    runtime.beat_sensitivity = 0.5

    cfg.layers["layer_1"] = LayerConfig(
        preset=cfg.layers["layer_1"].preset,
        stem="drums",
        opacity=1.0,
        blend_mode="black-key",
        enabled=True,
        beat_sensitivity=5.0,
    )

    compositor = MagicMock()
    fbo = MagicMock()
    compositor.create_layer_fbo.return_value = fbo
    pm = MagicMock()
    project_m.return_value = pm

    LayerFramePipeline.build(
        cfg,
        compositor,
        {slot: session.layers[slot].playlist for slot in session.layer_z_order},
        session,
        projectm_fps=30,
        preview_resolutions=False,
    )

    compositor.create_layer_fbo.assert_called_once()
    kwargs = compositor.create_layer_fbo.call_args.kwargs
    assert kwargs["opacity"] == 0.4
    assert kwargs["blend_mode"] == "add"
    assert fbo.enabled is False
    pm.set_beat_sensitivity.assert_called_once_with(0.5)


@patch("cleave.viz.wiring.LayerFramePipeline.build_single")
@patch("cleave.viz.wiring.scan_single_layer")
def test_add_layer_save_round_trip_leaves_cfg_layers_untouched(
    scan_single_layer: MagicMock,
    build_single: MagicMock,
) -> None:
    cfg = make_test_cfg(("layer_1",))
    playlists = _playlists_for_cfg(cfg)
    session = session_from_cfg(cfg, playlists)
    session.layer_z_order[:] = ["layer_1"]
    cfg_layers_before = dict(cfg.layers)
    cfg_order_before = list(cfg.layer_z_order)
    existing = StemLayer(
        slot="layer_1",
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=playlists["layer_1"],
    )
    existing.fbo.width = 1280
    existing.fbo.height = 720

    playlist = PresetPlaylist(
        current_dir=Path("/tmp/presets/layer_2"),
        paths=(Path("/tmp/presets/layer_2/preset-0.milk"),),
        index=0,
    )
    scan_single_layer.return_value = playlist
    stem_layer = StemLayer(
        slot="layer_2",
        pm=MagicMock(),
        fbo=MagicMock(),
        playlist=playlist,
    )
    stem_layer.fbo.width = 1280
    stem_layer.fbo.height = 720
    build_single.return_value = stem_layer

    manager = LayerManager(
        cfg=cfg,
        session=session,
        compositor=MagicMock(),
        layers=[existing],
        layers_by_slot={"layer_1": existing},
        playlists={"layer_1": playlists["layer_1"]},
        preset_root=cfg.paths.preset_root,
        project_dir=Path("/tmp/projects/test"),
        projectm_fps=30,
        texture_paths=[],
    )
    slot = manager.add_layer()

    assert slot == "layer_2"
    assert cfg.layers == cfg_layers_before
    assert cfg.layer_z_order == cfg_order_before
    payload = persisted_session_payload(cfg, session)
    assert payload["layer_z_order"] == ["layer_1", "layer_2"]
    assert "layer_2" in payload["layers"]
    assert payload["layers"]["layer_2"]["stem"] == "full_mix"


def test_view_state_reflects_session_mutation_without_block_writes() -> None:
    from dataclasses import fields

    from cleave.viz.row_fields import format_row_value
    from cleave.viz.row_semantics import RowDescriptor, RowKind
    from cleave.viz.tuning_view_state import RenderOverlayCardBlock, TrackBlock
    from tests.support.viz import make_controls

    controls = make_controls(("layer_1",))
    runtime = controls.session.layers["layer_1"]
    card = controls.session.render_overlays.opening_card
    runtime.opacity_pct = 41
    runtime.blend_mode = "add"
    card.position = "top-right"

    view = controls.build_view_state(paused=False)
    block = view.tracks["layer_1"]
    assert block.runtime is runtime
    assert view.render_overlays.opening_card.runtime is card
    assert {field.name for field in fields(TrackBlock)} == {
        "runtime",
        "preset_dir_label",
        "preset_label",
        "preset_list_labels",
        "preset_empty",
        "visible",
        "active_preset_list_index",
    }
    assert {field.name for field in fields(RenderOverlayCardBlock)} == {"runtime"}
    assert format_row_value(
        view, RowDescriptor(RowKind.TRACK_OPACITY, slot="layer_1")
    ) == "41%"
    assert format_row_value(
        view, RowDescriptor(RowKind.TRACK_BLEND, slot="layer_1")
    ) == "add"
    assert format_row_value(
        view,
        RowDescriptor(RowKind.RENDER_OVERLAY_CARD_POSITION, card="opening_card"),
    ) == "top-right"
