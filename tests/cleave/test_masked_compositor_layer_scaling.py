"""Hard pattern-mask array copy must scale each layer's own FBO size.

Live preview quality sizes layer FBOs per z-index (1.00, 0.85, 0.70, ...), so
the copy into the content-sized texture array has to stretch the layer's own
``width`` x ``height``. A same-size copy anchors smaller layers in the slice's
bottom-left corner and leaves black bars along the opposite edges.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cleave.gl_compositor import LayerFbo
from cleave.gl_masked_compositor import GlMaskedCompositor

CONTENT_W, CONTENT_H = 1280, 720


def _layer(name: str, width: int, height: int, fbo_id: int) -> LayerFbo:
    return LayerFbo(
        name=name,
        width=width,
        height=height,
        fbo_id=fbo_id,
        texture_id=fbo_id + 100,
        depth_rbo_id=0,
        enabled=True,
        opacity=1.0,
    )


def _copy_calls(layers: list[LayerFbo]) -> list[tuple[int, ...]]:
    compositor = GlMaskedCompositor(CONTENT_W, CONTENT_H)
    compositor._layer_array_id = 7
    compositor._layer_array_fbo_id = 9
    module = "cleave.gl_masked_compositor"
    with (
        patch.object(GlMaskedCompositor, "_ensure_layer_array", MagicMock()),
        patch(f"{module}.glBindFramebuffer", MagicMock()),
        patch(f"{module}.glReadBuffer", MagicMock()),
        patch(f"{module}.glFramebufferTextureLayer", MagicMock()),
        patch(f"{module}.glDisable", MagicMock()),
        patch(f"{module}.glColorMask", MagicMock()),
        patch(f"{module}.glBlitFramebuffer", MagicMock()) as blit,
    ):
        compositor._copy_layers_into_array(layers)
    return [tuple(int(v) for v in call.args[:8]) for call in blit.call_args_list]


def test_scaled_layer_blits_from_its_own_size_to_content_size() -> None:
    calls = _copy_calls([_layer("layer_2", 896, 504, fbo_id=2)])

    assert calls == [(0, 0, 896, 504, 0, 0, CONTENT_W, CONTENT_H)]


def test_full_size_layer_blits_one_to_one() -> None:
    calls = _copy_calls([_layer("layer_1", CONTENT_W, CONTENT_H, fbo_id=1)])

    assert calls == [(0, 0, CONTENT_W, CONTENT_H, 0, 0, CONTENT_W, CONTENT_H)]


def test_each_layer_uses_its_own_source_rect() -> None:
    layers = [
        _layer("layer_1", 1280, 720, fbo_id=1),
        _layer("layer_2", 1088, 612, fbo_id=2),
        _layer("layer_3", 512, 288, fbo_id=3),
    ]

    calls = _copy_calls(layers)

    assert [call[2:4] for call in calls] == [(1280, 720), (1088, 612), (512, 288)]
    assert all(call[4:8] == (0, 0, CONTENT_W, CONTENT_H) for call in calls)


def test_disabled_layer_is_not_copied() -> None:
    layer = _layer("layer_2", 896, 504, fbo_id=2)
    layer.enabled = False

    assert _copy_calls([layer]) == []
