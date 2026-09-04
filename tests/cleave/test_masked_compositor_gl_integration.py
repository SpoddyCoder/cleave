"""OpenGL integration: soft pattern-mask composite must blend weight-gated layers."""

from __future__ import annotations

import pytest

pygame = pytest.importorskip("pygame")
from OpenGL.GL import (  # noqa: E402
    GL_COLOR_BUFFER_BIT,
    GL_FRAMEBUFFER,
    GL_RGBA,
    GL_UNSIGNED_BYTE,
    glBindFramebuffer,
    glClear,
    glClearColor,
    glReadPixels,
)

from cleave.gl_compositor import GlCompositor  # noqa: E402
from cleave.gl_masked_compositor import GlMaskedCompositor, PatternMaskParams  # noqa: E402
from cleave.layer_composite import LayerCompositeRequest  # noqa: E402
from cleave.pattern_mask import lerp_hard_layout_1d  # noqa: E402
from cleave.pattern_mask_transition import (  # noqa: E402
    MaskTransition,
    mask_transition_kind,
)

W, H = 64, 32


@pytest.fixture
def gl_context():
    pygame.init()
    pygame.display.set_mode((W * 2, H * 2), pygame.OPENGL | pygame.DOUBLEBUF)
    comp = GlCompositor(
        content_width=W,
        content_height=H,
        display_width=W * 2,
        display_height=H * 2,
    )
    comp.init()
    masked = GlMaskedCompositor(W, H)
    masked.init()
    try:
        yield comp, masked
    finally:
        masked.release()
        comp.destroy()
        pygame.quit()


def _wipe(
    mask_type: str,
    start_sec: float,
    duration: float,
    from_slots: list[bool] | tuple[bool, ...],
) -> MaskTransition:
    return MaskTransition(
        kind=mask_transition_kind(mask_type),
        start_sec=start_sec,
        duration=duration,
        from_slots=tuple(from_slots),
    )


def _run(masked: GlMaskedCompositor, comp: GlCompositor, layers, **kwargs) -> None:
    transition = kwargs.pop("transition", None)
    masked.composite(_request(comp, layers, transition=transition, **kwargs))


def _request(comp: GlCompositor, layers, *, transition=None, **kwargs) -> LayerCompositeRequest:
    active = kwargs.pop("active_slots", None)
    song_time_sec = kwargs.pop("song_time_sec", 0.0)
    kwargs.pop("transition_duration", None)
    return LayerCompositeRequest(
        target_fbo_id=comp.content_fbo_id,
        layers=layers,
        color_format=comp.color_format,
        mask=PatternMaskParams(
            mask_type=kwargs.get("mask_type", "strips"),
            feather_pct=kwargs.get("feather_pct", 0),
            density=kwargs.get("density", 1.0),
            invert=kwargs.get("invert", False),
            seed=kwargs.get("seed", 0),
        ),
        active_slots=tuple(active) if active is not None else None,
        song_time_sec=song_time_sec,
        transition=transition,
    )


def _fill_layer(layer, rgb: tuple[float, float, float]) -> None:
    glBindFramebuffer(GL_FRAMEBUFFER, layer.fbo_id)
    glClearColor(rgb[0], rgb[1], rgb[2], 1.0)
    glClear(GL_COLOR_BUFFER_BIT)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)


def _read_content_pixel(
    comp: GlCompositor, x: int, y: int
) -> tuple[int, ...]:
    glBindFramebuffer(GL_FRAMEBUFFER, comp.content_fbo_id)
    raw = glReadPixels(x, y, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE)
    glBindFramebuffer(GL_FRAMEBUFFER, 0)
    return tuple(raw)


def test_hard_composite_splits_layers_by_strips(gl_context) -> None:
    comp, masked = gl_context
    left = comp.create_layer_fbo("left", W, H, opacity=1.0, blend_mode="black-key")
    right = comp.create_layer_fbo("right", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(left, (1.0, 0.0, 0.0))
    _fill_layer(right, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [left, right],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
    )

    left_px = _read_content_pixel(comp, W // 4, H // 2)
    right_px = _read_content_pixel(comp, 3 * W // 4, H // 2)
    assert left_px[0] > 200 and left_px[2] < 40, f"left={left_px}"
    assert right_px[2] > 200 and right_px[0] < 40, f"right={right_px}"


def test_soft_composite_accepts_generated_strips_weights(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 1.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 1.0))

    _run(
        masked,
        comp,
        [a, b],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
    )

    mid = _read_content_pixel(comp, W // 2, H // 2)
    # Soft strips with density 1.0x still light the frame (not all black).
    assert max(mid[:3]) > 20, f"mid={mid}"


def test_soft_plasma_composite_does_not_crash(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b],
        mask_type="plasma",
        feather_pct=100,
        density=2.0,
        seed=7,
    )

    px = _read_content_pixel(comp, W // 2, H // 2)
    assert max(px[:3]) > 10, f"plasma soft composite produced black frame: {px}"


def test_plasma_hard_gpu_restores_full_viewport(gl_context) -> None:
    comp, masked = gl_context
    assert masked._ctx is not None
    masked._ctx.viewport = (0, 0, W, H)
    gen_w, gen_h = W, H
    params = PatternMaskParams(
        mask_type="plasma",
        feather_pct=0,
        density=2.0,
        invert=False,
        seed=3,
    )

    masked._generate_plasma_hard_gpu(
        gen_width=gen_w,
        gen_height=gen_h,
        layer_count=2,
        params=params,
    )

    assert masked._ctx.viewport == (0, 0, W, H)


def test_plasma_hard_composite_fills_content_frame(gl_context) -> None:
    comp, masked = gl_context
    left = comp.create_layer_fbo("left", W, H, opacity=1.0, blend_mode="black-key")
    right = comp.create_layer_fbo("right", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(left, (1.0, 0.0, 0.0))
    _fill_layer(right, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [left, right],
        mask_type="plasma",
        feather_pct=0,
        density=2.0,
        seed=5,
    )

    corner = _read_content_pixel(comp, W - 2, H - 2)
    assert max(corner[:3]) > 10, f"plasma hard left content corner black: {corner}"


def test_mask_cache_skips_regeneration(gl_context) -> None:
    comp, masked = gl_context
    layer = comp.create_layer_fbo("solo", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(layer, (1.0, 0.0, 0.0))

    _run(
        masked,
        comp,
        [layer],
        mask_type="strips",
        feather_pct=0,
        density=2.0,
        seed=1,
    )
    first_key = masked._mask_cache_key

    _run(
        masked,
        comp,
        [layer],
        mask_type="strips",
        feather_pct=0,
        density=2.0,
        seed=1,
    )
    assert masked._mask_cache_key is first_key


def _is_hard_primary(px: tuple[int, ...]) -> bool:
    highs = sum(1 for channel in px[:3] if channel > 200)
    lows = sum(1 for channel in px[:3] if channel < 40)
    return highs == 1 and lows == 2


def test_transition_blends_weights_over_song_time(gl_context) -> None:
    """Hard 2-to-3 strips: disputed band moves before t=0.5; one winner per pixel."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is None
    right_before = _read_content_pixel(comp, W - 2, H // 2)
    assert right_before[1] > 200 and right_before[0] < 40, f"t0 right={right_before}"

    c.enabled = True
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition=_wipe("strips", 0.0, 1.0, (True, True, False)),
    )
    assert masked._transition_old_layout is not None
    assert masked._transition_target_layout is not None
    right_t0 = _read_content_pixel(comp, W - 2, H // 2)
    assert right_t0[1] > 200 and right_t0[2] < 40, f"morph t=0 right={right_t0}"

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.25,
        transition_duration=1.0,
    )
    right_t25 = _read_content_pixel(comp, W - 2, H // 2)
    assert right_t25[2] > 200 and right_t25[1] < 40, f"t=0.25 right={right_t25}"
    assert right_t25 != right_t0
    for x in (W // 8, W // 2, W - 2):
        px = _read_content_pixel(comp, x, H // 2)
        assert _is_hard_primary(px), f"mixed pixel at x={x}: {px}"

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=1.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is None
    left_px = _read_content_pixel(comp, W // 6, H // 2)
    assert left_px[0] > 200, f"after transition left={left_px}"


def test_mid_transition_retarget_snapshots_blend(gl_context) -> None:
    """A slot change during a feathered strips wipe snapshots the lerped cuts."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    b.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, False, True],
        song_time_sec=0.0,
        transition=_wipe("strips", 0.0, 2.0, (True, True, True)),
    )
    first_old = masked._transition_old_layout
    first_target = masked._transition_target_layout
    assert first_old is not None
    assert first_target is not None
    assert masked._transition_old_weights is None
    c.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
        active_slots=[True, False, False],
        song_time_sec=0.5,
        transition=_wipe("strips", 0.5, 2.0, (True, False, True)),
    )
    assert masked._transition_start == 0.5
    expected_old = lerp_hard_layout_1d(first_old, first_target, 0.5 / 2.0)
    assert masked._transition_old_layout == expected_old
    assert masked._transition_old_weights is None


def test_hard_path_retarget_continues_from_inflight_cuts(gl_context) -> None:
    """A slot change during a hard wipe snapshots the lerped cuts as the new old."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=2.0,
    )
    b.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, False, True],
        song_time_sec=0.0,
        transition=_wipe("strips", 0.0, 2.0, (True, True, True)),
    )
    first_old = masked._transition_old_layout
    first_target = masked._transition_target_layout
    assert first_old is not None
    assert first_target is not None

    c.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, False, False],
        song_time_sec=0.25,
        transition=_wipe("strips", 0.25, 2.0, (True, False, True)),
    )
    assert masked._transition_start == 0.25
    expected_old = lerp_hard_layout_1d(first_old, first_target, 0.25 / 2.0)
    assert masked._transition_old_layout == expected_old
    # Static 1-active would be all red; in-flight cuts still own the right band.
    right_px = _read_content_pixel(comp, 3 * W // 4, H // 2)
    assert right_px[0] < 200, f"retarget jumped to target: right={right_px}"
    assert _is_hard_primary(right_px), f"retarget mixed pixel: {right_px}"


def test_live_slots_matches_active_when_idle() -> None:
    masked = GlMaskedCompositor(W, H)
    assert masked.live_slots((True, False, True), 0.0) == (True, False, True)
    assert masked.live_slots((False, False), 0.5) == (False, False)


def test_live_slots_departing_hard_layout_until_width_zero(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked.live_slots((True, True, True), 0.0) == (True, True, True)
    departing = _wipe("strips", 0.0, 1.0, (True, True, True))
    assert masked.live_slots((True, True, False), 0.0, departing) == (True, True, True)

    c.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition=departing,
    )
    assert masked.live_slots((True, True, False), 0.25) == (True, True, True)
    assert masked.live_slots((True, True, False), 1.0) == (True, True, False)

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=1.0,
        transition_duration=1.0,
    )
    assert masked.live_slots((True, True, False), 1.0) == (True, True, False)


def test_live_slots_departing_feathered_hard_layout(gl_context) -> None:
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=50,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    c.enabled = False
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=50,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition=_wipe("strips", 0.0, 1.0, (True, True, True)),
    )
    assert masked._transition_old_layout is not None
    assert masked._transition_old_weights is None
    assert masked.live_slots((True, True, False), 0.25) == (True, True, True)
    assert masked.live_slots((True, True, False), 1.0) == (True, True, False)


def test_feathered_strips_two_to_three_grows_right_edge(gl_context) -> None:
    """Feathered 2-to-3 strips uses 1D layout morph; right edge grows the new color."""
    comp, masked = gl_context
    a = comp.create_layer_fbo("a", W, H, opacity=1.0, blend_mode="black-key")
    b = comp.create_layer_fbo("b", W, H, opacity=1.0, blend_mode="black-key")
    c = comp.create_layer_fbo("c", W, H, opacity=1.0, blend_mode="black-key")
    _fill_layer(a, (1.0, 0.0, 0.0))
    _fill_layer(b, (0.0, 1.0, 0.0))
    _fill_layer(c, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=50,
        density=1.0,
        active_slots=[True, True, False],
        song_time_sec=0.0,
        transition_duration=1.0,
    )
    assert masked._transition_old_layout is None
    assert masked._transition_old_weights is None
    right_before = _read_content_pixel(comp, W - 2, H // 2)
    assert right_before[1] > right_before[2], f"t0 right={right_before}"

    c.enabled = True
    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=50,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.0,
        transition=_wipe("strips", 0.0, 1.0, (True, True, False)),
    )
    assert masked._transition_old_layout is not None
    assert masked._transition_target_layout is not None
    assert masked._transition_old_weights is None

    _run(
        masked,
        comp,
        [a, b, c],
        mask_type="strips",
        feather_pct=50,
        density=1.0,
        active_slots=[True, True, True],
        song_time_sec=0.25,
        transition_duration=1.0,
    )
    right_t25 = _read_content_pixel(comp, W - 2, H // 2)
    assert right_t25[2] > right_t25[1], f"t=0.25 right={right_t25}"
    assert right_t25 != right_before


def _four_solid_layers(comp):
    layers = []
    colors = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        (1.0, 1.0, 0.0),
    )
    for name, rgb in zip(("a", "b", "c", "d"), colors, strict=True):
        layer = comp.create_layer_fbo(name, W, H, opacity=1.0, blend_mode="black-key")
        _fill_layer(layer, rgb)
        layers.append(layer)
    return layers


def _assert_hard_weight_field_mid_morph(
    comp,
    masked,
    layers,
    *,
    mask_type: str,
    seed: int = 0,
) -> None:
    import numpy as np

    two = [True, True, False, False]
    three = [True, True, True, False]
    common = dict(
        mask_type=mask_type,
        feather_pct=0,
        density=1.0,
        seed=seed,
        transition_duration=1.0,
    )
    _run(
        masked,
        comp,
        layers,
        active_slots=two,
        song_time_sec=0.0,
        **common,
    )
    assert masked._transition_old_weights is None
    layers[2].enabled = True
    _run(
        masked,
        comp,
        layers,
        active_slots=three,
        song_time_sec=0.0,
        transition=_wipe(mask_type, 0.0, 1.0, two),
        **common,
    )
    assert masked._transition_old_weights is not None
    assert masked._transition_target_weights is not None
    old_winners = np.argmax(masked._transition_old_weights, axis=0)
    new_winners = np.argmax(masked._transition_target_weights, axis=0)
    ys, xs = np.nonzero(old_winners != new_winners)
    assert ys.size > 0, f"{mask_type} old and target fields are identical"
    field_y = int(ys[ys.size // 2])
    field_x = int(xs[xs.size // 2])
    gen_h = int(old_winners.shape[0])
    gen_w = int(old_winners.shape[1])
    sample_x = min(W - 1, int((field_x + 0.5) * W / gen_w))
    sample_y = min(H - 1, int((field_y + 0.5) * H / gen_h))
    assert masked._transition_in_progress(0.25)
    _run(
        masked,
        comp,
        layers,
        active_slots=three,
        song_time_sec=0.25,
        **common,
    )
    assert masked._transition_in_progress(0.25)
    blended = masked._blended_transition_weights(0.25)
    assert not np.array_equal(blended, masked._transition_target_weights)
    mid_px = _read_content_pixel(comp, sample_x, sample_y)
    _run(
        masked,
        comp,
        layers,
        active_slots=three,
        song_time_sec=1.0,
        **common,
    )
    assert masked._transition_old_weights is None
    settled_px = _read_content_pixel(comp, sample_x, sample_y)
    assert mid_px != settled_px, (
        f"{mask_type} t=0.25 already settled at ({sample_x},{sample_y}): {mid_px}"
    )


def test_hard_checker_slot_change_is_mid_morph_at_quarter(gl_context) -> None:
    comp, masked = gl_context
    _assert_hard_weight_field_mid_morph(
        comp, masked, _four_solid_layers(comp), mask_type="checker"
    )


def test_hard_plasma_slot_change_is_mid_morph_at_quarter(gl_context) -> None:
    comp, masked = gl_context
    _assert_hard_weight_field_mid_morph(
        comp, masked, _four_solid_layers(comp), mask_type="plasma", seed=7
    )


def test_hard_composite_stretches_preview_scaled_layer(gl_context) -> None:
    """Live preview quality gives back layers a smaller FBO than the content."""
    comp, masked = gl_context
    full = comp.create_layer_fbo("full", W, H, opacity=1.0, blend_mode="black-key")
    small = comp.create_layer_fbo(
        "small", W // 2, H // 2, opacity=1.0, blend_mode="black-key"
    )
    _fill_layer(full, (1.0, 0.0, 0.0))
    _fill_layer(small, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [full, small],
        mask_type="strips",
        feather_pct=0,
        density=1.0,
    )

    # Right strip belongs to the half-size layer; it must cover the full strip,
    # not just the bottom-left quarter of it.
    for y in (2, H // 2, H - 3):
        px = _read_content_pixel(comp, 3 * W // 4, y)
        assert px[2] > 200 and px[0] < 40, f"y={y} px={px}"


def test_soft_composite_stretches_preview_scaled_layer(gl_context) -> None:
    comp, masked = gl_context
    full = comp.create_layer_fbo("full", W, H, opacity=1.0, blend_mode="black-key")
    small = comp.create_layer_fbo(
        "small", W // 2, H // 2, opacity=1.0, blend_mode="black-key"
    )
    _fill_layer(full, (1.0, 0.0, 0.0))
    _fill_layer(small, (0.0, 0.0, 1.0))

    _run(
        masked,
        comp,
        [full, small],
        mask_type="strips",
        feather_pct=100,
        density=1.0,
    )

    for y in (2, H - 3):
        px = _read_content_pixel(comp, 3 * W // 4, y)
        assert px[2] > 100, f"y={y} px={px}"
