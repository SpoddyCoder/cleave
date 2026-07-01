"""Tests for shared content-frame finish."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cleave.viz.frame_finish import finish_content_frame
from tests.support.config import default_render_post_fx_runtime


def test_finish_content_frame_applies_highlight_rolloff_when_active() -> None:
    core = MagicMock()
    core.seed.width = 1280
    core.seed.height = 720
    core.seed.duration_sec = 60.0
    core.compositor.content_texture_id = 42
    core.compositor.content_width = 1280
    core.compositor.content_height = 720
    core.compositor.content_fbo_id = 99
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = core.seed.session.render_post_fx.highlight_rolloff
    hr.enabled = True
    hr.mode = "rolloff"
    hr.threshold_pct = 80
    hr.ceiling_pct = 60
    hr.strength_pct = 65
    hr.softness_pct = 35
    hr.desaturation_pct = 25

    with patch(
        "cleave.viz.frame_finish._composite_render_overlay",
    ):
        finish_content_frame(core, 1.0)

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


def test_finish_content_frame_passes_highlight_rolloff_mode_index() -> None:
    core = MagicMock()
    core.seed.width = 1280
    core.seed.height = 720
    core.seed.duration_sec = 60.0
    core.compositor.content_texture_id = 42
    core.compositor.content_width = 1280
    core.compositor.content_height = 720
    core.compositor.content_fbo_id = 99
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    hr = core.seed.session.render_post_fx.highlight_rolloff
    hr.enabled = True
    hr.mode = "aces_fit"

    with patch(
        "cleave.viz.frame_finish._composite_render_overlay",
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_called_once()
    assert core.post_process.apply_highlight_rolloff.call_args.args[-1] == 2


def test_finish_content_frame_skips_highlight_rolloff_when_solo() -> None:
    core = MagicMock()
    core.seed.width = 1280
    core.seed.height = 720
    core.seed.duration_sec = 60.0
    core.compositor.content_texture_id = 42
    core.compositor.content_width = 1280
    core.compositor.content_height = 720
    core.compositor.content_fbo_id = 99
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=True)
    core.seed.session.render_post_fx.highlight_rolloff.enabled = True

    with patch(
        "cleave.viz.frame_finish._composite_render_overlay",
    ):
        finish_content_frame(core, 1.0, post_fx_solo=True)

    core.post_process.apply_highlight_rolloff.assert_not_called()


def test_finish_content_frame_applies_highlight_rolloff_when_post_fx_disabled() -> None:
    core = MagicMock()
    core.seed.duration_sec = 60.0
    core.compositor.content_texture_id = 42
    core.compositor.content_width = 1280
    core.compositor.content_height = 720
    core.compositor.content_fbo_id = 99
    core.seed.session.render_post_fx = default_render_post_fx_runtime(enabled=False)
    core.seed.session.render_post_fx.highlight_rolloff.enabled = True

    with patch(
        "cleave.viz.frame_finish._composite_render_overlay",
    ):
        finish_content_frame(core, 1.0)

    core.post_process.apply_highlight_rolloff.assert_called_once()
