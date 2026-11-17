import subprocess
import sys

from cleave.viz.button_paint import ButtonState, ButtonTone, button_look
from cleave.viz.progress_bar import accent_at
from cleave.viz.row_paint import RowState, row_look
from cleave.viz.theme import palette


def test_hover_is_a_flat_violet_wash() -> None:
    look = row_look(RowState.HOVER)
    assert look.start == look.end
    assert look.start[0] == palette().hover
    assert look.edge is None and look.bar is None


def test_selected_fades_blue_left_to_right_with_a_bar() -> None:
    look = row_look(RowState.SELECTED)
    assert not look.vertical
    assert look.start[0] == look.end[0] == palette().row_select_tint
    assert look.start[1] > look.end[1]
    assert look.bar == palette().row_selected_bar
    assert look.edge is None


def test_focused_is_stronger_than_selected_and_has_an_edge() -> None:
    selected = row_look(RowState.SELECTED)
    focused = row_look(RowState.FOCUSED)
    assert focused.start[1] > selected.start[1]
    assert focused.end[1] > selected.end[1]
    assert focused.edge == palette().row_focus_edge
    assert focused.bar == palette().row_focused_bar


def test_lit_is_the_plain_button_hover_with_a_yellow_bar() -> None:
    look = row_look(RowState.LIT)
    hover = button_look(ButtonTone.PLAIN, ButtonState.HOVER)
    assert look.vertical
    assert look.start == (hover.top, 1.0)
    assert look.end == (hover.bottom, 1.0)
    assert look.bar == palette().highlight


def test_bar_can_be_dropped() -> None:
    for state in RowState:
        assert row_look(state, bar=False).bar is None


def test_no_row_look_fills_with_the_highlight_yellow() -> None:
    for state in RowState:
        look = row_look(state)
        assert look.start[0] != palette().highlight
        assert look.end[0] != palette().highlight


def test_accent_runs_from_blue_to_violet() -> None:
    assert accent_at(0.0) == palette().accent_from
    assert accent_at(1.0) == palette().accent_to
    assert accent_at(-1.0) == palette().accent_from
    assert accent_at(2.0) == palette().accent_to


def test_row_paint_imports_without_imgui() -> None:
    """The pygame strip shares the look on the frozen play path."""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import cleave.viz.row_paint; "
            "sys.exit('imgui_bundle' in sys.modules)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
