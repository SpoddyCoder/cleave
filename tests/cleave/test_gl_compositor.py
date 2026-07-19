"""Tests for layer opacity mapping in the GL compositor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pygame
import pytest

from cleave.blend_modes import BLEND_MODES
from cleave.gl_compositor import (
    GlCompositor,
    LayerFbo,
    OverlayTextureSlot,
    _overlay_subimage_y,
)

# Modes whose GL blend func uses GL_SRC_ALPHA (opacity stays in glColor alpha).
_OPACITY_VIA_ALPHA = frozenset({"add"})

# All other modes bake opacity into glColor RGB (SRC_COLOR-weighted blends).
_OPACITY_VIA_RGB = frozenset(mode for mode in BLEND_MODES if mode not in _OPACITY_VIA_ALPHA)


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_RGB))
def test_layer_gl_color_bakes_opacity_into_rgb(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.4, 0.3, 0.2, 1.0))


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_ALPHA))
def test_layer_gl_color_uses_alpha_channel(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba[:3] == pytest.approx((0.8, 0.6, 0.4))
    assert rgba[3] == pytest.approx(0.5)


def test_layer_gl_color_full_opacity_preserves_tint() -> None:
    tint = (0.9, 0.7, 0.5)
    for mode in BLEND_MODES:
        rgba = GlCompositor._layer_gl_color(tint, 1.0, mode)
        assert rgba == pytest.approx((*tint, 1.0))


@pytest.mark.parametrize("blend_mode", sorted(_OPACITY_VIA_RGB))
def test_layer_gl_color_hue_tint_multiplies_with_opacity_in_rgb(blend_mode: str) -> None:
    rgba = GlCompositor._layer_gl_color((1.2, 0.8, 0.6), 0.5, blend_mode)  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.6, 0.4, 0.3, 1.0))


def test_layer_gl_color_add_keeps_hue_in_rgb_and_opacity_in_alpha() -> None:
    rgba = GlCompositor._layer_gl_color((1.2, 0.8, 0.6), 0.5, "add")
    assert rgba == pytest.approx((1.2, 0.8, 0.6, 0.5))


def test_layer_gl_color_unknown_mode_matches_black_key_rgb_scaling() -> None:
    """Runtime fallback blend is black-key; opacity must scale RGB."""
    rgba = GlCompositor._layer_gl_color((0.8, 0.6, 0.4), 0.5, "legacy")  # type: ignore[arg-type]
    assert rgba == pytest.approx((0.4, 0.3, 0.2, 1.0))


def test_blend_modes_partition_opacity_channel() -> None:
    assert _OPACITY_VIA_ALPHA | _OPACITY_VIA_RGB == frozenset(BLEND_MODES)
    assert not _OPACITY_VIA_ALPHA & _OPACITY_VIA_RGB


def test_flash_rgba_puts_strength_in_alpha_for_add_blend() -> None:
    """Flash draws a solid quad with add blend; strength must be glColor alpha."""
    flash_alpha = 0.35
    rgba = (240 / 255.0, 235 / 255.0, 230 / 255.0, flash_alpha)
    assert rgba[3] == pytest.approx(flash_alpha)
    assert rgba[:3] == pytest.approx((240 / 255.0, 235 / 255.0, 230 / 255.0))


@pytest.mark.parametrize(
    ("hue_rgb", "hue_mix", "expected"),
    [
        ((0.5, 0.7, 0.9), 0.0, (1.0, 1.0, 1.0)),
        ((0.5, 0.7, 0.9), 1.0, (0.5, 0.7, 0.9)),
        ((1.2, 0.8, 0.6), 0.5, (1.1, 0.9, 0.8)),
    ],
)
def test_lerp_tint_rgb_scales_hue_mix(
    hue_rgb: tuple[float, float, float],
    hue_mix: float,
    expected: tuple[float, float, float],
) -> None:
    result = GlCompositor._lerp_tint_rgb(hue_rgb, hue_mix)
    assert result == pytest.approx(expected)


def test_pulse_zero_opacity_can_still_leave_flash_visible() -> None:
    """Flash burst can outlast a pulse envelope; flash must not require layer opacity."""
    from cleave.effects.flash import flash_alpha
    from cleave.effects.pulse import effective_opacity

    assert effective_opacity(1.0, 100, 0.0) == 0.0
    assert flash_alpha(100, 0.15) >= 0.01


def test_remove_layer_fbo_removes_and_destroys() -> None:
    compositor = GlCompositor.__new__(GlCompositor)
    fbo = MagicMock(spec=LayerFbo)
    fbo.name = "layer_5"
    compositor._layers = [fbo]

    compositor.remove_layer_fbo("layer_5")

    fbo.destroy.assert_called_once()
    assert compositor._layers == []


def test_remove_layer_fbo_unknown_name_raises() -> None:
    compositor = GlCompositor.__new__(GlCompositor)
    compositor._layers = []

    with pytest.raises(ValueError, match="no layer FBO named 'missing'"):
        compositor.remove_layer_fbo("missing")


def test_resize_layer_fbo_noop_when_same_size() -> None:
    compositor = GlCompositor.__new__(GlCompositor)
    fbo = MagicMock(spec=LayerFbo)
    fbo.name = "layer_1"
    fbo.width = 640
    fbo.height = 360
    compositor._layers = [fbo]

    compositor.resize_layer_fbo("layer_1", 640, 360)

    fbo.destroy.assert_not_called()


def test_set_color_format_noop_when_unchanged() -> None:
    from cleave.gl_color_format import RGBA8

    compositor = GlCompositor.__new__(GlCompositor)
    compositor._color_format = RGBA8
    compositor._initialized = True
    compositor._destroy_content_fbo = MagicMock()
    compositor._allocate_content_fbo = MagicMock()
    compositor._layers = []

    compositor.set_color_format(RGBA8)

    compositor._destroy_content_fbo.assert_not_called()
    compositor._allocate_content_fbo.assert_not_called()


def test_set_color_format_reallocates_content_and_layers() -> None:
    from cleave.gl_color_format import RGBA8, RGBA16F

    compositor = GlCompositor.__new__(GlCompositor)
    compositor._color_format = RGBA16F
    compositor._initialized = True
    compositor.content_width = 64
    compositor.content_height = 64
    compositor._destroy_content_fbo = MagicMock()
    compositor._allocate_content_fbo = MagicMock()
    compositor._replace_layer_framebuffer = MagicMock()
    layer = MagicMock(spec=LayerFbo)
    layer.width = 640
    layer.height = 360
    compositor._layers = [layer]

    compositor.set_color_format(RGBA8)

    assert compositor.color_format is RGBA8
    compositor._destroy_content_fbo.assert_called_once()
    compositor._allocate_content_fbo.assert_called_once()
    compositor._replace_layer_framebuffer.assert_called_once_with(layer, 640, 360)


def test_resize_layer_fbo_unknown_name_raises() -> None:
    compositor = GlCompositor.__new__(GlCompositor)
    compositor._layers = []

    with pytest.raises(ValueError, match="no layer FBO named 'missing'"):
        compositor.resize_layer_fbo("missing", 640, 360)


def test_resize_layer_fbo_reallocates_and_preserves_state() -> None:
    compositor = GlCompositor.__new__(GlCompositor)
    compositor._allocate_layer_framebuffer = MagicMock(return_value=(11, 22, 33))

    fbo = MagicMock(spec=LayerFbo)
    fbo.name = "layer_1"
    fbo.width = 1280
    fbo.height = 720
    fbo.fbo_id = 1
    fbo.texture_id = 2
    fbo.depth_rbo_id = 3
    fbo.enabled = False
    fbo.opacity = 0.42
    fbo.flash_alpha = 0.15
    fbo.bloom_strength = 0.8
    fbo.hue_rgb = (0.5, 0.6, 0.7)
    fbo.hue_mix = 0.25
    fbo.grit_strength = 0.33
    fbo.aberration_px = 2.5
    fbo.blend_mode = "add"
    compositor._layers = [fbo]

    compositor.resize_layer_fbo("layer_1", 640, 360)

    fbo.destroy.assert_called_once()
    assert compositor._allocate_layer_framebuffer.call_args_list == [
        (("layer_1", 640, 360),),
        (("layer_1_rolloff_source", 640, 360),),
        (("layer_1_chroma_source", 640, 360),),
    ]
    assert fbo.width == 640
    assert fbo.height == 360
    assert fbo.fbo_id == 11
    assert fbo.texture_id == 22
    assert fbo.depth_rbo_id == 33
    assert fbo.enabled is False
    assert fbo.opacity == 0.42
    assert fbo.blend_mode == "add"
    assert fbo.flash_alpha == 0.15
    assert fbo.bloom_strength == 0.8
    assert fbo.hue_rgb == (0.5, 0.6, 0.7)
    assert fbo.hue_mix == 0.25
    assert fbo.grit_strength == 0.33
    assert fbo.aberration_px == 2.5


def _make_overlay_compositor() -> GlCompositor:
    compositor = GlCompositor.__new__(GlCompositor)
    compositor._initialized = True
    compositor._overlay_slots = {}
    compositor._texture_realloc_count = 0
    compositor._layers = []
    compositor._content_fbo_id = 0
    compositor._content_texture_id = 0
    compositor._content_depth_rbo_id = 0
    compositor._bind_default_framebuffer = MagicMock()
    compositor._bind_content_fbo = MagicMock()
    return compositor


def _make_surface(width: int, height: int) -> pygame.Surface:
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    surface.fill((10, 20, 30, 200))
    return surface


@pytest.fixture
def gl_texture_mocks():
    texture_ids = iter(range(100, 200))

    def _gen_textures(_count: int = 1) -> list[int]:
        return [next(texture_ids)]

    with (
        patch("cleave.gl_compositor.glGenTextures", side_effect=_gen_textures) as gen,
        patch("cleave.gl_compositor.glTexImage2D") as tex_image,
        patch("cleave.gl_compositor.glTexSubImage2D") as tex_subimage,
        patch("cleave.gl_compositor.glDeleteTextures") as delete,
        patch("cleave.gl_compositor.glBindTexture") as bind,
        patch("cleave.gl_compositor.GlCompositor._configure_texture_params"),
        patch(
            "cleave.gl_compositor._overlay_surface_rgba",
            return_value=b"\x00" * 16,
        ) as rgba_bytes,
    ):
        yield {
            "gen": gen,
            "tex_image": tex_image,
            "tex_subimage": tex_subimage,
            "delete": delete,
            "bind": bind,
            "rgba_bytes": rgba_bytes,
        }


def test_ensure_overlay_texture_allocates_once_per_slot(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()

    tex_id = compositor.ensure_overlay_texture(OverlayTextureSlot.TUNING, 200, 100)

    assert tex_id == 100
    assert compositor.overlay_texture_capacity(OverlayTextureSlot.TUNING) == (200, 100)
    gl_texture_mocks["gen"].assert_called_once()
    gl_texture_mocks["tex_image"].assert_called_once()
    gl_texture_mocks["delete"].assert_not_called()

    tex_id_again = compositor.ensure_overlay_texture(OverlayTextureSlot.TUNING, 200, 100)
    assert tex_id_again == 100
    gl_texture_mocks["gen"].assert_called_once()
    gl_texture_mocks["tex_image"].assert_called_once()


def test_upload_overlay_region_subimage_within_capacity(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    compositor.ensure_overlay_texture(OverlayTextureSlot.TUNING, 400, 300)
    gl_texture_mocks["tex_image"].reset_mock()
    gl_texture_mocks["gen"].reset_mock()
    gl_texture_mocks["delete"].reset_mock()

    surface = _make_surface(200, 150)
    tex_id = compositor.upload_overlay_region(
        OverlayTextureSlot.TUNING, surface, dest_x=10, dest_y=20
    )

    assert tex_id == 100
    gl_texture_mocks["delete"].assert_not_called()
    gl_texture_mocks["tex_image"].assert_not_called()
    gl_texture_mocks["gen"].assert_not_called()
    gl_texture_mocks["tex_subimage"].assert_called_once()
    args = gl_texture_mocks["tex_subimage"].call_args[0]
    assert args[2] == 10
    assert args[3] == _overlay_subimage_y(20, 150, 300)
    assert args[4] == 200
    assert args[5] == 150


def test_upload_overlay_region_active_size_clips_surface(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    compositor.ensure_overlay_texture(OverlayTextureSlot.TUNING, 400, 300)
    gl_texture_mocks["rgba_bytes"].reset_mock()

    surface = _make_surface(400, 300)
    compositor.upload_overlay_region(
        OverlayTextureSlot.TUNING,
        surface,
        dest_x=0,
        dest_y=0,
        active_w=200,
        active_h=150,
    )

    rgba_call = gl_texture_mocks["rgba_bytes"].call_args[0][0]
    assert rgba_call.get_size() == (200, 150)
    subimage_args = gl_texture_mocks["tex_subimage"].call_args[0]
    assert subimage_args[4] == 200
    assert subimage_args[5] == 150


def test_upload_overlay_region_realloc_when_capacity_grows(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    compositor.ensure_overlay_texture(OverlayTextureSlot.TUNING, 200, 100)
    gl_texture_mocks["tex_image"].reset_mock()
    gl_texture_mocks["gen"].reset_mock()

    surface = _make_surface(300, 200)
    tex_id = compositor.upload_overlay_region(OverlayTextureSlot.TUNING, surface)

    assert tex_id == 101
    gl_texture_mocks["delete"].assert_called_once_with(1, [100])
    gl_texture_mocks["gen"].assert_called_once()
    gl_texture_mocks["tex_image"].assert_called_once()
    image_args = gl_texture_mocks["tex_image"].call_args[0]
    assert image_args[3] == 300
    assert image_args[4] == 200
    assert compositor.consume_texture_reallocs() == 1
    assert compositor.consume_texture_reallocs() == 0


def test_overlay_slots_are_independent(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()

    tuning_id = compositor.upload_overlay_region(
        OverlayTextureSlot.TUNING, _make_surface(100, 50)
    )
    help_id = compositor.upload_overlay_region(
        OverlayTextureSlot.HELP, _make_surface(80, 40)
    )

    assert tuning_id == 100
    assert help_id == 101
    assert gl_texture_mocks["gen"].call_count == 2
    tuning_state = compositor._overlay_slots[OverlayTextureSlot.TUNING]
    help_state = compositor._overlay_slots[OverlayTextureSlot.HELP]
    assert tuning_state.texture_id == 100
    assert help_state.texture_id == 101


def test_upload_overlay_texture_same_size_uses_subimage(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    surface = _make_surface(128, 64)

    tex_id = compositor.upload_overlay_texture(surface)
    assert tex_id == 100
    gl_texture_mocks["tex_image"].assert_called_once()
    assert gl_texture_mocks["tex_subimage"].call_count == 1

    gl_texture_mocks["tex_image"].reset_mock()
    gl_texture_mocks["tex_subimage"].reset_mock()
    tex_id_again = compositor.upload_overlay_texture(surface)
    assert tex_id_again == 100
    gl_texture_mocks["tex_image"].assert_not_called()
    gl_texture_mocks["delete"].assert_not_called()
    gl_texture_mocks["tex_subimage"].assert_called_once()


def test_upload_overlay_texture_size_change_reallocates(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()

    compositor.upload_overlay_texture(_make_surface(100, 50))
    gl_texture_mocks["delete"].reset_mock()
    gl_texture_mocks["gen"].reset_mock()
    gl_texture_mocks["tex_image"].reset_mock()

    tex_id = compositor.upload_overlay_texture(_make_surface(120, 60))

    assert tex_id == 101
    gl_texture_mocks["delete"].assert_called_once_with(1, [100])
    gl_texture_mocks["gen"].assert_called_once()
    gl_texture_mocks["tex_image"].assert_called_once()


def test_draw_overlay_custom_tex_uv(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    tex_uv = (0.1, 0.2, 0.9, 0.8)

    with (
        patch("cleave.gl_compositor.glTexCoord2f") as tex_coord,
        patch("cleave.gl_compositor.glBegin"),
        patch("cleave.gl_compositor.glEnd"),
        patch("cleave.gl_compositor.glColor4f"),
        patch("cleave.gl_compositor.glBindTexture"),
        patch("cleave.gl_compositor.GlCompositor._push_blend_state", return_value=(True, 0, 0, 0)),
        patch("cleave.gl_compositor.GlCompositor._pop_blend_state"),
        patch("cleave.gl_compositor.GlCompositor._apply_src_alpha_blend"),
        patch("cleave.gl_compositor.glEnable"),
    ):
        compositor.draw_overlay(42, 0, 0, 200, 100, tex_uv=tex_uv)

    u0, v0, u1, v1 = tex_uv
    tex_coord.assert_any_call(u0, 1.0 - v0)
    tex_coord.assert_any_call(u1, 1.0 - v0)
    tex_coord.assert_any_call(u1, 1.0 - v1)
    tex_coord.assert_any_call(u0, 1.0 - v1)


def test_destroy_deletes_all_slot_textures(gl_texture_mocks) -> None:
    compositor = _make_overlay_compositor()
    compositor.upload_overlay_region(
        OverlayTextureSlot.TUNING, _make_surface(50, 50)
    )
    compositor.upload_overlay_region(
        OverlayTextureSlot.HELP, _make_surface(40, 40)
    )
    compositor._destroy_content_fbo = MagicMock()

    compositor.destroy()

    delete_calls = [call[0][1][0] for call in gl_texture_mocks["delete"].call_args_list]
    assert 100 in delete_calls
    assert 101 in delete_calls
    assert compositor._overlay_slots == {}
    assert compositor._initialized is False
