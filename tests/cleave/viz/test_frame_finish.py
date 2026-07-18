"""Tests for shared content-frame finish."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cleave.viz.frame_finish import finish_content_frame
from tests.support.config import default_render_post_fx_runtime


def _make_core(*, hdr_compositing: bool = False) -> MagicMock:
    core = MagicMock()
    core.seed.width = 1280
    core.seed.height = 720
    core.seed.duration_sec = 60.0
    core.seed.cfg.render.hdr_compositing = hdr_compositing
    core.compositor.content_texture_id = 42
    core.compositor.content_width = 1280
    core.compositor.content_height = 720
    core.compositor.content_fbo_id = 99
    return core


def test_finish_content_frame_applies_highlight_rolloff_when_active() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = core.seed.session.render_post_fx.highlight_rolloff
    hr.mode = "composite"
    hr.curve = "rolloff"
    hr.threshold_pct = 80
    hr.ceiling_pct = 60
    hr.strength_pct = 65
    hr.softness_pct = 35
    hr.desaturation_pct = 25

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder") as shoulder,
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    shoulder.assert_not_called()
    core.post_process.apply_highlight_rolloff.assert_called_once_with(
        42,
        1280,
        720,
        0.8,
        0.6,
        0.65,
        0.35,
        0.25,
        0,
    )


def test_finish_content_frame_passes_highlight_rolloff_curve_index() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = core.seed.session.render_post_fx.highlight_rolloff
    hr.mode = "composite"
    hr.curve = "aces_fit"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_called_once()
    assert core.post_process.apply_highlight_rolloff.call_args.args[-1] == 2


def test_finish_content_frame_skips_highlight_rolloff_when_solo() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0, post_fx_solo=True)

    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_skips_highlight_rolloff_when_post_fx_disabled() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_call_order_rolloff_fade_overlay_present() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"
    call_order: list[str] = []

    core.post_process.apply_highlight_rolloff.side_effect = (
        lambda *_a, **_k: call_order.append("highlight_rolloff")
    )
    core.compositor.apply_frame_fade.side_effect = (
        lambda *_a, **_k: call_order.append("frame_fade")
    )
    core.compositor.present_content.side_effect = (
        lambda: call_order.append("present_content")
    )

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch(
            "cleave.viz.frame_finish._composite_render_overlay",
            side_effect=lambda *_a, **_k: call_order.append("overlay"),
        ),
    ):
        finish_content_frame(core, 1.0)

    assert call_order == [
        "highlight_rolloff",
        "frame_fade",
        "overlay",
        "present_content",
    ]


def test_finish_content_frame_applies_chroma_boost_when_active() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    cb = core.seed.session.render_post_fx.chroma_boost
    cb.mode = "composite"
    cb.variant = "vibrance"
    cb.amount_pct = 40

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_chroma_boost.assert_called_once_with(
        42,
        1280,
        720,
        40,
        1,
    )


def test_finish_content_frame_skips_chroma_boost_when_post_fx_disabled() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    core.seed.session.render_post_fx.chroma_boost.mode = "composite"
    core.seed.session.render_post_fx.chroma_boost.amount_pct = 25

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_chroma_boost.assert_not_called()


def test_finish_content_frame_call_order_rolloff_chroma_fade_overlay_present() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"
    core.seed.session.render_post_fx.chroma_boost.mode = "composite"
    core.seed.session.render_post_fx.chroma_boost.amount_pct = 25
    call_order: list[str] = []

    core.post_process.apply_highlight_rolloff.side_effect = (
        lambda *_a, **_k: call_order.append("highlight_rolloff")
    )
    core.post_process.apply_chroma_boost.side_effect = (
        lambda *_a, **_k: call_order.append("chroma_boost")
    )
    core.compositor.apply_frame_fade.side_effect = (
        lambda *_a, **_k: call_order.append("frame_fade")
    )
    core.compositor.present_content.side_effect = (
        lambda: call_order.append("present_content")
    )

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch(
            "cleave.viz.frame_finish._composite_render_overlay",
            side_effect=lambda *_a, **_k: call_order.append("overlay"),
        ),
    ):
        finish_content_frame(core, 1.0)

    assert call_order == [
        "highlight_rolloff",
        "chroma_boost",
        "frame_fade",
        "overlay",
        "present_content",
    ]


def test_finish_content_frame_skips_composite_rolloff_when_per_layer() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = core.seed.session.render_post_fx.highlight_rolloff
    hr.mode = "per_layer"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_hdr_on_rolloff_off_applies_display_shoulder_only() -> None:
    core = _make_core(hdr_compositing=True)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "off"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder") as shoulder,
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    shoulder.assert_called_once_with(core.post_process, 42, 1280, 720)
    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_hdr_on_rolloff_on_call_order() -> None:
    core = _make_core(hdr_compositing=True)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"
    call_order: list[str] = []

    with (
        patch(
            "cleave.viz.frame_finish.apply_hdr_display_shoulder",
            side_effect=lambda *_a, **_k: call_order.append("display_shoulder"),
        ),
        patch(
            "cleave.viz.frame_finish._composite_render_overlay",
            side_effect=lambda *_a, **_k: call_order.append("overlay"),
        ),
    ):
        core.post_process.apply_highlight_rolloff.side_effect = (
            lambda *_a, **_k: call_order.append("highlight_rolloff")
        )
        core.compositor.apply_frame_fade.side_effect = (
            lambda *_a, **_k: call_order.append("frame_fade")
        )
        core.compositor.present_content.side_effect = (
            lambda: call_order.append("present_content")
        )
        finish_content_frame(core, 1.0)

    assert call_order == [
        "display_shoulder",
        "highlight_rolloff",
        "frame_fade",
        "overlay",
        "present_content",
    ]


def test_finish_content_frame_hdr_off_skips_display_shoulder() -> None:
    core = _make_core(hdr_compositing=False)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "off"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder") as shoulder,
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    shoulder.assert_not_called()


def test_finish_content_frame_hdr_on_post_fx_disabled_still_applies_display_shoulder() -> None:
    core = _make_core(hdr_compositing=True)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder") as shoulder,
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    shoulder.assert_called_once_with(core.post_process, 42, 1280, 720)
    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_hdr_on_post_fx_solo_still_applies_display_shoulder() -> None:
    core = _make_core(hdr_compositing=True)
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder") as shoulder,
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0, post_fx_solo=True)

    shoulder.assert_called_once_with(core.post_process, 42, 1280, 720)
    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_skips_render_sections_in_curation() -> None:
    from cleave.viz.frame_finish import _composite_render_overlay

    core = _make_core(hdr_compositing=False)
    core.seed.session.settings.editor_mode = "preset_curation"
    core.seed.session.render_overlay.enabled = True
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.mode = "composite"
    core.seed.session.render_post_fx.chroma_boost.mode = "composite"
    core.seed.session.render_post_fx.chroma_boost.amount_pct = 40
    core.seed.session.render_post_fx.fade_in = 2.0
    core.seed.session.render_post_fx.fade_out = 2.0

    with (
        patch("cleave.viz.frame_finish.apply_hdr_display_shoulder"),
        patch("cleave.viz.frame_finish._composite_render_overlay"),
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_not_called()
    core.post_process.apply_chroma_boost.assert_not_called()
    core.compositor.apply_frame_fade.assert_called_once_with(1.0)

    with (
        patch(
            "cleave.viz.frame_finish.resolve_overlay_config",
            return_value=MagicMock(),
        ),
        patch(
            "cleave.viz.frame_finish.live_overlay_alpha",
            return_value=0.0,
        ) as alpha,
        patch("cleave.viz.frame_finish.composite_render_overlay_with_alpha"),
    ):
        _composite_render_overlay(
            core,
            1.0,
            core.seed.session,
            overlay_solo=False,
            panel_cache=None,
        )
    assert alpha.call_args.kwargs["enabled"] is False
