"""Strip lane changes stay on the timeline cursor."""

from __future__ import annotations

import pygame

from cleave.viz.focus_nav import MainFocus, TimelineFocus, cursor_timeline_row
from cleave.viz.row_kinds import RowDescriptor, RowKind
from cleave.viz.shell_focus import ShellRegion
from cleave.viz.timeline_controls import TimelineControls
from tests.cleave.viz.test_controls import _make_controls
from tests.support.viz import keydown, stub_playback_state


def test_focus_nav_has_no_main_list_ring() -> None:
    import cleave.viz.focus_nav as focus_nav

    assert not hasattr(focus_nav, "build_focus_ring")
    assert not hasattr(focus_nav, "move_focus")
    assert not hasattr(focus_nav, "timeline_strip_in_ring")


def test_set_timeline_focus_row_does_not_grant_scope() -> None:
    controls = _make_controls(("layer_1", "layer_2"))
    controls.session.timeline.panel_open = True
    before = controls.focus_cursor
    controls.set_timeline_focus_row(1)
    assert controls.session.timeline.focus_row == 1
    assert controls.focus_cursor == before
    assert controls.shell_focus.region is ShellRegion.NAVIGATOR
    controls.set_shell_region(ShellRegion.TIMELINE)
    assert controls.focus_cursor == TimelineFocus(1)
    controls.set_timeline_focus_row(0)
    assert controls.focus_cursor == TimelineFocus(0)
    assert controls.shell_focus.region is ShellRegion.TIMELINE


def test_strip_up_down_stays_on_lanes() -> None:
    controls = _make_controls(("layer_1", "layer_2", "layer_3"))
    controls.session.timeline.panel_open = True
    controls.session.timeline.focus_row = 1
    controls.set_shell_region(ShellRegion.TIMELINE)
    playback = controls.playback
    timeline = TimelineControls(
        controls.session,
        playback,
        controls.duration_sec,
        on_focus_row=controls.set_timeline_focus_row,
    )

    timeline.handle_keydown(keydown(pygame.K_DOWN))
    assert controls.focus_cursor == TimelineFocus(2)
    assert controls.session.timeline.focus_row == 2

    timeline.handle_keydown(keydown(pygame.K_DOWN))
    assert controls.focus_cursor == TimelineFocus(2)

    timeline.handle_keydown(keydown(pygame.K_UP))
    timeline.handle_keydown(keydown(pygame.K_UP))
    assert controls.focus_cursor == TimelineFocus(0)
    timeline.handle_keydown(keydown(pygame.K_UP))
    assert isinstance(controls.focus_cursor, TimelineFocus)
    assert controls.focus_cursor.row == 0
    assert cursor_timeline_row(controls.focus_cursor) == 0


def test_strip_up_down_without_callback_updates_session_row() -> None:
    from cleave.viz.session import TuningSession

    session = TuningSession(layer_z_order=["layer_1", "layer_2"])
    session.timeline.focus_row = 0
    timeline = TimelineControls(
        session,
        stub_playback_state(),
        10.0,
    )
    timeline.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 1
    timeline.handle_keydown(keydown(pygame.K_DOWN))
    assert session.timeline.focus_row == 1
    assert not isinstance(MainFocus(RowDescriptor(RowKind.RENDER_TIMELINE_HEADER)), TimelineFocus)
