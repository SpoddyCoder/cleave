"""Unit tests for LayerFramePipeline add/remove helpers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from cleave.config import RenderConfig
from cleave.preset_playlist import PresetPlaylist
from cleave.viz.layer import StemLayer
from cleave.viz.layer_pipeline import LayerFramePipeline
from cleave.viz.session import LayerRuntime, TuningSession
from tests.support.config import TEST_LAYER_STEMS, default_render_post_fx_runtime
from tests.support.viz import make_test_cfg


def _stem_layer(slot: str, *, width: int = 1280, height: int = 720) -> StemLayer:
    current_dir = Path(f"/tmp/presets/{slot}")
    fbo = MagicMock()
    fbo.width = width
    fbo.height = height
    return StemLayer(
        slot=slot,
        pm=MagicMock(),
        fbo=fbo,
        playlist=PresetPlaylist(
            current_dir=current_dir,
            paths=(current_dir / "preset.milk",),
            index=0,
        ),
    )


def _session(slots: tuple[str, ...]) -> TuningSession:
    preset_root = Path("/tmp/presets")
    return TuningSession(
        layer_z_order=list(slots),
        layers={
            slot: LayerRuntime(
                playlist=PresetPlaylist(
                    current_dir=preset_root / slot,
                    paths=(preset_root / slot / "preset.milk",),
                    index=0,
                ),
                browse_floor=preset_root / slot,
                stem=TEST_LAYER_STEMS.get(slot, "drums"),
            )
            for slot in slots
        },
    )


def test_destroy_single_tears_down_gl_and_updates_collections() -> None:
    layer = _stem_layer("layer_5")
    layers = [layer]
    layers_by_slot = {"layer_5": layer}
    compositor = MagicMock()

    LayerFramePipeline.destroy_single("layer_5", layers, layers_by_slot, compositor)

    assert layers == []
    assert layers_by_slot == {}
    layer.pm.destroy.assert_called_once()
    compositor.remove_layer_fbo.assert_called_once_with("layer_5")


def test_resize_layer_updates_projectm_and_compositor() -> None:
    layer = _stem_layer("layer_1")
    compositor = MagicMock()

    LayerFramePipeline.resize_layer(layer, compositor, 960, 540)

    layer.pm.set_window_size.assert_called_once_with(960, 540)
    compositor.resize_layer_fbo.assert_called_once_with("layer_1", 960, 540)


def test_apply_preview_resolutions_resizes_when_size_changes() -> None:
    layer = _stem_layer("layer_1")
    base_cfg = make_test_cfg(("layer_1",))
    cfg = replace(base_cfg, editor=replace(base_cfg.editor, preview_quality="performance"))
    session = _session(("layer_1",))
    compositor = MagicMock()

    LayerFramePipeline.apply_preview_resolutions(
        cfg, session, {"layer_1": layer}, compositor
    )

    layer.pm.set_window_size.assert_called_once_with(960, 540)
    compositor.resize_layer_fbo.assert_called_once_with("layer_1", 960, 540)


def test_apply_preview_resolutions_skips_when_unchanged() -> None:
    layer = _stem_layer("layer_1", width=960, height=540)
    base_cfg = make_test_cfg(("layer_1",))
    cfg = replace(base_cfg, editor=replace(base_cfg.editor, preview_quality="performance"))
    session = _session(("layer_1",))
    compositor = MagicMock()

    LayerFramePipeline.apply_preview_resolutions(
        cfg, session, {"layer_1": layer}, compositor
    )

    layer.pm.set_window_size.assert_not_called()
    compositor.resize_layer_fbo.assert_not_called()


@patch.object(LayerFramePipeline, "build_single")
def test_build_preview_resolutions_false_uses_render_output_size(
    build_single: MagicMock,
) -> None:
    slot = "layer_1"
    stem_layer = _stem_layer(slot)
    build_single.return_value = stem_layer
    base_cfg = make_test_cfg((slot,))
    cfg = replace(
        base_cfg,
        render=RenderConfig(fps=30, width=1920, height=1080),
        editor=replace(base_cfg.editor, preview_quality="performance"),
    )
    compositor = MagicMock()
    playlist = stem_layer.playlist

    layers, layers_by_slot = LayerFramePipeline.build(
        cfg,
        compositor,
        {slot: playlist},
        projectm_fps=30,
        preview_resolutions=False,
    )

    assert layers == [stem_layer]
    assert layers_by_slot == {slot: stem_layer}
    build_single.assert_called_once()
    assert build_single.call_args.kwargs["width"] == 1920
    assert build_single.call_args.kwargs["height"] == 1080
    compositor.resize_layer_fbo.assert_not_called()
    stem_layer.pm.set_window_size.assert_not_called()


@patch.object(LayerFramePipeline, "build_single")
def test_build_preview_resolutions_false_viz_quality_uses_preview_sizes(
    build_single: MagicMock,
) -> None:
    slot = "layer_1"
    stem_layer = _stem_layer(slot)
    build_single.return_value = stem_layer
    base_cfg = make_test_cfg((slot,))
    cfg = replace(
        base_cfg,
        render=RenderConfig(fps=30, width=1920, height=1080),
        editor=replace(base_cfg.editor, preview_quality="performance"),
    )
    compositor = MagicMock()
    playlist = stem_layer.playlist

    LayerFramePipeline.build(
        cfg,
        compositor,
        {slot: playlist},
        projectm_fps=30,
        preview_resolutions=False,
        viz_quality=True,
    )

    build_single.assert_called_once()
    assert build_single.call_args.kwargs["width"] == 960
    assert build_single.call_args.kwargs["height"] == 540


@patch.object(LayerFramePipeline, "apply_preview_resolutions")
@patch.object(LayerFramePipeline, "build_single")
def test_build_preview_resolutions_true_builds_at_preview_size(
    build_single: MagicMock,
    apply_preview_resolutions: MagicMock,
) -> None:
    slot = "layer_1"
    stem_layer = _stem_layer(slot)
    build_single.return_value = stem_layer
    base_cfg = make_test_cfg((slot,))
    cfg = replace(base_cfg, editor=replace(base_cfg.editor, preview_quality="performance"))
    session = _session((slot,))
    compositor = MagicMock()
    playlist = stem_layer.playlist

    LayerFramePipeline.build(
        cfg,
        compositor,
        {slot: playlist},
        projectm_fps=30,
        preview_resolutions=True,
        session=session,
    )

    build_single.assert_called_once()
    assert build_single.call_args.kwargs["width"] == 960
    assert build_single.call_args.kwargs["height"] == 540
    apply_preview_resolutions.assert_called_once_with(
        cfg, session, {slot: stem_layer}, compositor
    )


def test_render_frame_applies_per_layer_highlight_rolloff_when_playing() -> None:
    layer = _stem_layer("layer_1")
    layer.fbo.enabled = True
    layer.fbo.texture_id = 11
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = session.render_post_fx.highlight_rolloff
    hr.mode = "per_layer"
    compositor = MagicMock()
    compositor.rolloff_source_texture_id.return_value = 22
    post_process = MagicMock()
    pcm_bank = MagicMock()
    pcm_bank.slice_pcm.return_value = b""
    pcm_bank.channels.return_value = 2
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {"layer_1": MagicMock(
        opacity=1.0, flash_alpha=0.0, bloom_strength=0.0, hue_rgb=(1, 1, 1),
        hue_mix=0.0, grit_strength=0.0, aberration_px=0.0,
    )}

    with patch("cleave.viz.layer_pipeline._render_layer_fbo"):
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            pcm_bank,
            512,
            post_process,
            effect_runtime,
            None,
            1.0,
            paused=False,
            pm_time_sec=1.0,
            compositor=compositor,
        )

    compositor.copy_layer_to_rolloff_source.assert_called_once()
    post_process.apply_highlight_rolloff.assert_called_once()
    assert post_process.apply_highlight_rolloff.call_args.kwargs["source_texture_id"] == 22


def test_render_frame_skips_per_layer_highlight_rolloff_when_post_fx_disabled() -> None:
    layer = _stem_layer("layer_1")
    layer.fbo.enabled = True
    layer.fbo.texture_id = 11
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    session.render_post_fx.highlight_rolloff.mode = "per_layer"
    compositor = MagicMock()
    post_process = MagicMock()
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {"layer_1": MagicMock(
        opacity=1.0, flash_alpha=0.0, bloom_strength=0.0, hue_rgb=(1, 1, 1),
        hue_mix=0.0, grit_strength=0.0, aberration_px=0.0,
    )}

    with patch("cleave.viz.layer_pipeline._render_layer_fbo"):
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            MagicMock(),
            512,
            post_process,
            effect_runtime,
            None,
            1.0,
            paused=False,
            pm_time_sec=1.0,
            compositor=compositor,
        )

    compositor.copy_layer_to_rolloff_source.assert_not_called()
    post_process.apply_highlight_rolloff.assert_not_called()


def test_render_frame_paused_per_layer_uses_frozen_rolloff_source() -> None:
    layer = _stem_layer("layer_1")
    layer.fbo.enabled = True
    layer.fbo.texture_id = 11
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = session.render_post_fx.highlight_rolloff
    hr.mode = "per_layer"
    compositor = MagicMock()
    compositor.rolloff_source_texture_id.return_value = 22
    post_process = MagicMock()
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {"layer_1": MagicMock(
        opacity=1.0, flash_alpha=0.0, bloom_strength=0.0, hue_rgb=(1, 1, 1),
        hue_mix=0.0, grit_strength=0.0, aberration_px=0.0,
    )}

    with patch("cleave.viz.layer_pipeline._render_layer_fbo") as render_fbo:
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            MagicMock(),
            512,
            post_process,
            effect_runtime,
            None,
            1.0,
            paused=True,
            pm_time_sec=1.0,
            compositor=compositor,
        )

    render_fbo.assert_not_called()
    compositor.copy_layer_to_rolloff_source.assert_not_called()
    post_process.apply_highlight_rolloff.assert_called_once()
    assert post_process.apply_highlight_rolloff.call_args.kwargs["source_texture_id"] == 22


def test_render_frame_applies_per_layer_chroma_boost_when_playing() -> None:
    layer = _stem_layer("layer_1")
    layer.fbo.enabled = True
    layer.fbo.texture_id = 11
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    cb = session.render_post_fx.chroma_boost
    cb.mode = "per_layer"
    cb.amount_pct = 30
    compositor = MagicMock()
    compositor.chroma_source_texture_id.return_value = 33
    post_process = MagicMock()
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {"layer_1": MagicMock(
        opacity=1.0, flash_alpha=0.0, bloom_strength=0.0, hue_rgb=(1, 1, 1),
        hue_mix=0.0, grit_strength=0.0, aberration_px=0.0,
    )}

    with patch("cleave.viz.layer_pipeline._render_layer_fbo"):
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            MagicMock(),
            512,
            post_process,
            effect_runtime,
            None,
            1.0,
            paused=False,
            pm_time_sec=1.0,
            compositor=compositor,
        )

    compositor.copy_layer_to_chroma_source.assert_called_once()
    post_process.apply_chroma_boost.assert_called_once()
    assert post_process.apply_chroma_boost.call_args.kwargs["source_texture_id"] == 33


def test_render_frame_skips_per_layer_chroma_boost_when_amount_zero() -> None:
    layer = _stem_layer("layer_1")
    layer.fbo.enabled = True
    session = _session(("layer_1",))
    session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    cb = session.render_post_fx.chroma_boost
    cb.mode = "per_layer"
    cb.amount_pct = 0
    compositor = MagicMock()
    post_process = MagicMock()
    effect_runtime = MagicMock()
    effect_runtime.modifiers.return_value = {"layer_1": MagicMock(
        opacity=1.0, flash_alpha=0.0, bloom_strength=0.0, hue_rgb=(1, 1, 1),
        hue_mix=0.0, grit_strength=0.0, aberration_px=0.0,
    )}

    with patch("cleave.viz.layer_pipeline._render_layer_fbo"):
        LayerFramePipeline.render_frame(
            session,
            [layer],
            {"layer_1": layer},
            MagicMock(),
            512,
            post_process,
            effect_runtime,
            None,
            1.0,
            paused=False,
            pm_time_sec=1.0,
            compositor=compositor,
        )

    compositor.copy_layer_to_chroma_source.assert_not_called()
    post_process.apply_chroma_boost.assert_not_called()

