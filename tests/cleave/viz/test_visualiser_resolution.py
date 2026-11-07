"""Tests for sizing the live visualiser to its on-screen rect."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import MagicMock

from cleave.viz.session import TuningSession
from cleave.viz.visualiser_resolution import (
    VISUALISER_RESOLUTION_SETTLE_SEC,
    VisualiserResolutionSync,
)
from tests.support.viz import make_test_cfg

SETTLE = VISUALISER_RESOLUTION_SETTLE_SEC


def _sync(
    project: tuple[int, int] = (3840, 2160),
) -> tuple[VisualiserResolutionSync, MagicMock, TuningSession]:
    cfg = make_test_cfg(("layer_1",))
    cfg = replace(cfg, editor=replace(cfg.editor, preview_quality="full-quality"))
    session = TuningSession(layer_z_order=[], layers={})
    session.project.resolution.width, session.project.resolution.height = project
    apply = MagicMock()
    return VisualiserResolutionSync(session, cfg, apply), apply, session


def test_starts_at_project_size_before_any_draw_rect() -> None:
    sync, apply, _session = _sync()
    sync.tick(SETTLE)
    assert sync.applied_size == (3840, 2160)
    apply.assert_not_called()


def test_first_draw_rect_applies_at_once() -> None:
    sync, apply, _session = _sync()
    sync.note_draw_rect((300, 40, 1600, 900))
    sync.tick(0.0)
    apply.assert_called_once_with((1600, 900))
    assert sync.applied_size == (1600, 900)


def test_draw_rect_change_applies_after_settle() -> None:
    sync, apply, _session = _sync()
    sync.note_draw_rect((0, 0, 1600, 900))
    sync.tick(0.0)
    apply.reset_mock()

    sync.note_draw_rect((0, 0, 1920, 1080))
    sync.tick(0.0)
    sync.tick(SETTLE / 2)
    apply.assert_not_called()
    sync.tick(SETTLE)
    apply.assert_called_once_with((1920, 1080))


def test_draw_rect_change_within_one_step_does_not_apply() -> None:
    sync, apply, _session = _sync()
    sync.note_draw_rect((0, 0, 1600, 900))
    sync.tick(0.0)
    apply.reset_mock()

    sync.note_draw_rect((0, 0, 1590, 895))
    for _ in range(4):
        sync.tick(SETTLE)
    apply.assert_not_called()


def test_output_quality_applies_project_size() -> None:
    sync, apply, _session = _sync()
    sync.note_draw_rect((0, 0, 1600, 900))
    sync.tick(0.0)
    apply.reset_mock()

    sync.cfg.editor = replace(sync.cfg.editor, preview_quality="output")
    sync.tick(0.0)
    sync.tick(SETTLE)
    apply.assert_called_once_with((3840, 2160))


def test_project_resolution_change_applies() -> None:
    sync, apply, session = _sync(project=(1280, 720))
    sync.note_draw_rect((0, 0, 1600, 900))
    sync.tick(0.0)
    apply.assert_not_called()  # Already the project size, nothing to reallocate.

    session.project.resolution.width, session.project.resolution.height = 3840, 2160
    sync.tick(0.0)
    sync.tick(SETTLE)
    apply.assert_called_once_with((1600, 900))
