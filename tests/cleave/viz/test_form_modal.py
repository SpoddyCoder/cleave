"""Form dialogs: draft values, keyboard, pointer, and conditional fields."""

from __future__ import annotations

import pygame

from cleave.viz.key_repeat import INITIAL_DELAY_SEC
from cleave.viz.modal import (
    ButtonRole,
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
    ModalKind,
)
from cleave.viz.modal_layout import (
    form_control_width,
    form_heading_height,
    form_row_height,
    measure_panel,
)
from cleave.choice import ChoiceKind
from cleave.viz.modal_surface import (
    ModalPointerIntent,
    ModalPointerKind,
    apply_modal_pointer,
)
from tests.support.viz import keydown


def _form(
    modal: ModalHost,
    confirmed: list[FormValues],
    cancelled: list[str] | None = None,
    *,
    destructive: bool = False,
) -> None:
    def on_cancel() -> None:
        if cancelled is not None:
            cancelled.append("cancel")

    modal.prompt_form(
        FormSpec(
            title="Snap cues",
            fields=(
                FormField("target", "snap to", ("a", "b"), 0),
                FormField(
                    "extra",
                    "extra",
                    ("x", "y", "z"),
                    1,
                    lambda values: values["target"] == 1,
                ),
            ),
            confirm_label="Go",
            on_confirm=confirmed.append,
            on_cancel=on_cancel,
            info=lambda values: f"target {values['target']}",
            destructive=destructive,
        )
    )


def test_form_view_lists_visible_fields_and_info() -> None:
    modal = ModalHost()
    _form(modal, [])
    view = modal.view_state()
    assert view is not None
    assert view.kind is ModalKind.FORM
    assert [row.label for row in view.form_rows] == ["snap to"]
    assert view.form_rows[0].focused is True
    assert view.form_info == "target 0"
    assert view.options == ("Go", "Cancel")
    assert view.option_roles == (ButtonRole.PRIMARY, ButtonRole.PLAIN)


def test_right_changes_a_field_and_reveals_conditional_rows() -> None:
    modal = ModalHost()
    _form(modal, [])
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    view = modal.view_state()
    assert [row.label for row in view.form_rows] == ["snap to", "extra"]
    assert view.form_rows[1].value == 1
    assert view.form_info == "target 1"


def test_enter_on_a_field_confirms_with_the_draft() -> None:
    modal = ModalHost()
    confirmed: list[FormValues] = []
    _form(modal, confirmed)
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert confirmed == [{"target": 1, "extra": 1}]
    assert modal.view_state() is None


def test_escape_cancels_without_confirming() -> None:
    modal = ModalHost()
    confirmed: list[FormValues] = []
    cancelled: list[str] = []
    _form(modal, confirmed, cancelled)
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    modal.handle_keydown(keydown(pygame.K_ESCAPE))
    assert confirmed == []
    assert cancelled == ["cancel"]


def test_down_walks_fields_then_buttons_and_wraps() -> None:
    modal = ModalHost()
    _form(modal, [])
    modal.handle_keydown(keydown(pygame.K_DOWN))
    view = modal.view_state()
    assert view.form_buttons_focused is True
    assert not any(row.focused for row in view.form_rows)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    assert modal.view_state().form_rows[0].focused is True


def test_left_and_right_move_between_buttons() -> None:
    modal = ModalHost()
    cancelled: list[str] = []
    _form(modal, [], cancelled)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    assert modal.view_state().focus_index == 1
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert cancelled == ["cancel"]


def test_destructive_form_starts_on_cancel_and_enter_on_a_field_never_confirms() -> None:
    modal = ModalHost()
    confirmed: list[FormValues] = []
    _form(modal, confirmed, destructive=True)
    view = modal.view_state()
    assert view.form_buttons_focused is True
    assert view.focus_index == 1
    assert view.option_roles[0] is ButtonRole.DANGER

    modal.handle_keydown(keydown(pygame.K_DOWN))
    assert modal.view_state().form_rows[0].focused is True
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert confirmed == []
    assert modal.view_state().form_buttons_focused is True


def test_pointer_set_and_step_update_the_draft() -> None:
    modal = ModalHost()
    confirmed: list[FormValues] = []
    _form(modal, confirmed)
    modal.set_form_value(0, 1)
    modal.step_form_value(1, 1)
    assert modal.view_state().form_rows[1].value == 2
    modal.activate_option(0)
    assert confirmed == [{"target": 1, "extra": 2}]


def test_stepping_a_field_stops_at_either_end() -> None:
    modal = ModalHost()
    _form(modal, [])
    modal.set_form_value(0, 1)
    modal.step_form_value(1, 1)
    modal.step_form_value(1, 1)
    assert modal.view_state().form_rows[1].value == 2
    modal.step_form_value(1, -5)
    assert modal.view_state().form_rows[1].value == 0


def test_hiding_the_focused_row_keeps_focus_in_range() -> None:
    modal = ModalHost()
    _form(modal, [])
    modal.set_form_value(0, 1)
    modal.focus_form_row(1)
    modal.set_form_value(0, 0)
    modal.focus_form_row(1)
    view = modal.view_state()
    assert [row.label for row in view.form_rows] == ["snap to"]
    assert view.form_rows[0].focused is True


class _Measure:
    def size(self, text: str) -> tuple[int, int]:
        return (len(text) * 8, 16)

    def get_linesize(self) -> int:
        return 16


def test_panel_grows_with_conditional_rows() -> None:
    modal = ModalHost()
    _form(modal, [])
    short = measure_panel(_Measure(), modal.view_state(), line_gap=2, screen_w=1920)
    modal.set_form_value(0, 1)
    view = modal.view_state()
    tall = measure_panel(_Measure(), view, line_gap=2, screen_w=1920)
    assert tall[1] == short[1] + form_row_height(16)


def _sectioned_form(modal: ModalHost, *, sections: bool) -> None:
    def section(name: str) -> str | None:
        return name if sections else None

    modal.prompt_form(
        FormSpec(
            title="Sections",
            fields=(
                FormField("a", "a", ("x", "y"), section=section("First")),
                FormField("b", "b", ("x", "y"), section=section("First")),
                FormField("c", "c", ("x", "y"), section=section("Second")),
            ),
            confirm_label="Go",
            on_confirm=lambda _values: None,
        )
    )


def test_sections_head_their_first_row_and_indent_rows() -> None:
    modal = ModalHost()
    _sectioned_form(modal, sections=True)
    rows = modal.view_state().form_rows
    assert [row.heading for row in rows] == ["First", None, "Second"]
    assert all(row.indented for row in rows)


def test_section_headings_add_height_but_not_focus_stops() -> None:
    plain_modal = ModalHost()
    _sectioned_form(plain_modal, sections=False)
    plain = measure_panel(
        _Measure(), plain_modal.view_state(), line_gap=2, screen_w=1920
    )
    modal = ModalHost()
    _sectioned_form(modal, sections=True)
    sectioned = measure_panel(_Measure(), modal.view_state(), line_gap=2, screen_w=1920)
    assert sectioned[1] == plain[1] + form_heading_height(
        16, first=True
    ) + form_heading_height(16, first=False)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    assert modal.view_state().form_rows[1].focused


def _info_form(modal: ModalHost, *, info: str | None) -> None:
    modal.prompt_form(
        FormSpec(
            title="Info",
            fields=(FormField("a", "a", ("x", "y")),),
            confirm_label="Go",
            on_confirm=lambda _values: None,
            info=lambda _values: info,
        )
    )


def test_info_adds_one_line_under_the_title() -> None:
    plain = ModalHost()
    _info_form(plain, info=None)
    with_info = ModalHost()
    _info_form(with_info, info="(moves 1 of 1 cues)")
    plain_h = measure_panel(_Measure(), plain.view_state(), line_gap=2, screen_w=1920)[1]
    info_h = measure_panel(
        _Measure(), with_info.view_state(), line_gap=2, screen_w=1920
    )[1]
    assert info_h == plain_h + 2 + 16


def _combo_form(modal: ModalHost, confirmed: list[FormValues]) -> None:
    modal.prompt_form(
        FormSpec(
            title="Pick",
            fields=(
                FormField("mode", "mode", ("a", "b"), 0),
                FormField("shape", "shape", ("one", "two", "three", "four"), 1),
            ),
            confirm_label="Go",
            on_confirm=confirmed.append,
        )
    )


def test_three_options_or_fewer_are_segments_more_are_a_combo() -> None:
    modal = ModalHost()
    _combo_form(modal, [])
    rows = modal.view_state().form_rows
    assert rows[0].kind is ChoiceKind.SEGMENT
    assert rows[1].kind is ChoiceKind.COMBO


def test_control_width_fits_its_widest_option() -> None:
    modal = ModalHost()
    _combo_form(modal, [])
    first = form_control_width(_Measure(), modal.view_state().form_rows[1])
    modal.step_form_value(1, 1)
    assert form_control_width(_Measure(), modal.view_state().form_rows[1]) == first


def test_space_opens_a_combo_and_enter_picks_the_highlighted_option() -> None:
    modal = ModalHost()
    confirmed: list[FormValues] = []
    _combo_form(modal, confirmed)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_SPACE))
    choice = modal.view_state().form_choice
    assert choice is not None and choice.target == 1 and choice.highlighted == 1
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_RETURN))
    view = modal.view_state()
    assert view.form_choice is None
    assert view.form_rows[1].value == 3
    assert confirmed == []
    modal.handle_keydown(keydown(pygame.K_RETURN))
    assert confirmed == [{"mode": 0, "shape": 3}]


def test_escape_closes_the_list_and_keeps_the_dialog_and_value() -> None:
    modal = ModalHost()
    _combo_form(modal, [])
    modal.open_form_choice(1)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_ESCAPE))
    view = modal.view_state()
    assert modal.active
    assert view.form_choice is None
    assert view.form_rows[1].value == 1


def test_a_segment_row_has_no_list() -> None:
    modal = ModalHost()
    _combo_form(modal, [])
    modal.open_form_choice(0)
    assert modal.view_state().form_choice is None


def test_pointer_opens_hovers_and_picks_from_the_list() -> None:
    modal = ModalHost()
    _combo_form(modal, [])
    apply_modal_pointer(modal, ModalPointerIntent(ModalPointerKind.OPEN_FORM_CHOICE, index=1))
    apply_modal_pointer(modal, ModalPointerIntent(ModalPointerKind.HOVER_FORM_CHOICE, value=2))
    assert modal.view_state().form_choice.highlighted == 2
    apply_modal_pointer(modal, ModalPointerIntent(ModalPointerKind.PICK_FORM_CHOICE, value=0))
    view = modal.view_state()
    assert view.form_choice is None
    assert view.form_rows[1].value == 0


def _help_form(modal: ModalHost, *, destructive: bool = False) -> None:
    modal.prompt_form(
        FormSpec(
            title="Generate timeline",
            fields=(
                FormField(
                    "mode",
                    "cue snap",
                    ("none", "bars"),
                    help=("Moves cues.",),
                    option_help=("keep them.", "to bars."),
                ),
                FormField("plain", "plain", ("a", "b")),
            ),
            confirm_label="Generate",
            on_confirm=lambda _values: None,
            help=("Makes a timeline.",),
            destructive=destructive,
        )
    )


def test_help_sections_follow_the_focused_field() -> None:
    modal = ModalHost()
    _help_form(modal)
    field, dialog = modal.help_sections()
    assert field.title == "Cue Snap"
    assert field.lines == ("Moves cues.",)
    assert field.entries == (("none", "keep them."), ("bars", "to bars."))
    assert dialog.title == "Generate Timeline"
    assert dialog.lines == ("Makes a timeline.",)
    assert ("Enter", "generate") in dialog.entries

    # A field with no help shows only the dialog.
    modal.handle_keydown(keydown(pygame.K_DOWN))
    assert [section.title for section in modal.help_sections()] == [
        "Generate Timeline"
    ]


def test_help_sections_follow_a_clicked_row() -> None:
    modal = ModalHost()
    _help_form(modal)
    modal.focus_form_row(1)
    assert [section.title for section in modal.help_sections()] == [
        "Generate Timeline"
    ]
    apply_modal_pointer(
        modal, ModalPointerIntent(ModalPointerKind.FOCUS_FORM_ROW, index=0)
    )
    assert modal.help_sections()[0].title == "Cue Snap"


def test_destructive_help_names_the_focused_button() -> None:
    modal = ModalHost()
    _help_form(modal, destructive=True)
    (dialog,) = modal.help_sections()
    assert ("Enter", "press the focused button") in dialog.entries


def test_help_sections_are_empty_without_help_or_form() -> None:
    modal = ModalHost()
    assert modal.help_sections() == ()
    _form(modal, [])
    assert modal.help_sections() == ()
    modal.prompt_confirm("Sure?", "Go", lambda: None)
    assert modal.help_sections() == ()


def _stepper_form(modal: ModalHost, changes: list[str] | None = None) -> None:
    def on_change(field_id: str, values: FormValues) -> None:
        if changes is not None:
            changes.append(field_id)
        if values["low"] > values["high"]:
            values["high"] = values["low"]

    modal.prompt_form(
        FormSpec(
            title="Range",
            fields=(
                FormField(
                    "low",
                    "low",
                    tuple(str(n) for n in range(30)),
                    0,
                    help=("Low end.",),
                    stepper=True,
                    large_step=10,
                ),
                FormField(
                    "high", "high", tuple(str(n) for n in range(30)), 5, stepper=True
                ),
                FormField("mode", "mode", ("a", "b")),
            ),
            confirm_label="Go",
            on_confirm=lambda _values: None,
            on_change=on_change,
        )
    )


def test_stepper_rows_report_stepper_and_fit_widest_option() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    rows = modal.view_state().form_rows
    assert [row.stepper for row in rows] == [True, True, False]
    first = form_control_width(_Measure(), rows[0])
    modal.step_form_value(0, 15)
    assert form_control_width(_Measure(), modal.view_state().form_rows[0]) == first


def test_page_keys_move_a_stepper_by_its_large_step_and_clamp() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    assert modal.view_state().form_rows[0].value == 10
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    assert modal.view_state().form_rows[0].value == 29
    modal.handle_keydown(keydown(pygame.K_PAGEDOWN))
    assert modal.view_state().form_rows[0].value == 19


def test_a_stepper_has_no_list() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.handle_keydown(keydown(pygame.K_SPACE))
    assert modal.view_state().form_choice is None
    modal.open_form_choice(0)
    assert modal.view_state().form_choice is None


def test_on_change_runs_with_the_field_id_and_may_adjust_other_values() -> None:
    modal = ModalHost()
    changes: list[str] = []
    _stepper_form(modal, changes)
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    rows = modal.view_state().form_rows
    assert changes == ["low"]
    assert (rows[0].value, rows[1].value) == (10, 10)
    apply_modal_pointer(
        modal,
        ModalPointerIntent(ModalPointerKind.PRESS_FORM_STEP, index=1, value=1),
    )
    assert changes == ["low", "high"]
    assert modal.view_state().form_rows[1].value == 11


def test_help_keys_list_page_step_only_with_a_large_step_and_space_only_with_a_combo() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    (field, dialog) = modal.help_sections()
    keys = [key for key, _text in dialog.entries]
    assert "PgUp/PgDn" in keys
    assert "Space" not in keys
    _help_form(modal)
    keys = [key for key, _text in modal.help_sections()[-1].entries]
    assert "PgUp/PgDn" not in keys
    assert "Space" not in keys


def _held_past_delay(modal: ModalHost) -> None:
    """Tick past the first repeat delay; fires exactly one repeat."""
    modal.tick(INITIAL_DELAY_SEC + 0.001)


def test_holding_a_step_key_repeats_until_keyup() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    assert modal.view_state().form_rows[0].value == 1
    _held_past_delay(modal)
    assert modal.view_state().form_rows[0].value == 2
    assert modal.handle_keyup(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT))
    _held_past_delay(modal)
    assert modal.view_state().form_rows[0].value == 2


def test_holding_page_up_repeats_the_large_step() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.handle_keydown(keydown(pygame.K_PAGEUP))
    _held_past_delay(modal)
    assert modal.view_state().form_rows[0].value == 20


def test_another_key_stops_a_held_step() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.handle_keydown(keydown(pygame.K_RIGHT))
    modal.handle_keydown(keydown(pygame.K_DOWN))
    _held_past_delay(modal)
    rows = modal.view_state().form_rows
    assert (rows[0].value, rows[1].value) == (1, 5)


def test_holding_a_stepper_arrow_repeats_until_release() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    apply_modal_pointer(
        modal,
        ModalPointerIntent(ModalPointerKind.PRESS_FORM_STEP, index=1, value=1),
    )
    view = modal.view_state()
    assert view.form_rows[1].value == 6
    assert view.form_step_held == (1, 1)
    _held_past_delay(modal)
    assert modal.view_state().form_rows[1].value == 7
    apply_modal_pointer(
        modal, ModalPointerIntent(ModalPointerKind.RELEASE_FORM_STEP)
    )
    assert modal.view_state().form_step_held is None
    _held_past_delay(modal)
    assert modal.view_state().form_rows[1].value == 7


def test_closing_the_dialog_drops_a_held_step() -> None:
    modal = ModalHost()
    _stepper_form(modal)
    modal.press_form_step(0, 1)
    modal.handle_keydown(keydown(pygame.K_ESCAPE))
    assert modal.view_state() is None
    _stepper_form(modal)
    assert modal.view_state().form_step_held is None
    _held_past_delay(modal)
    assert modal.view_state().form_rows[0].value == 0


def _vertical_form(modal: ModalHost) -> None:
    modal.prompt_form(
        FormSpec(
            title="Populate",
            fields=(
                FormField("source", "pick from", ("a", "b", "c"), 0, vertical=True),
                FormField("after", "after", ("x", "y"), 0),
            ),
            confirm_label="Go",
            on_confirm=lambda _values: None,
        )
    )


def test_up_and_down_move_through_a_vertical_field_then_leave_it() -> None:
    modal = ModalHost()
    _vertical_form(modal)
    modal.handle_keydown(keydown(pygame.K_DOWN))
    modal.handle_keydown(keydown(pygame.K_DOWN))
    rows = modal.view_state().form_rows
    assert rows[0].vertical is True
    assert rows[0].value == 2
    assert rows[0].focused is True
    modal.handle_keydown(keydown(pygame.K_DOWN))
    rows = modal.view_state().form_rows
    assert rows[1].focused is True
    assert rows[0].value == 2
    modal.handle_keydown(keydown(pygame.K_UP))
    rows = modal.view_state().form_rows
    assert rows[0].focused is True
    assert rows[0].value == 2
    modal.handle_keydown(keydown(pygame.K_UP))
    assert modal.view_state().form_rows[0].value == 1


def test_a_vertical_field_is_one_row_per_option() -> None:
    modal = ModalHost()
    _vertical_form(modal)
    view = modal.view_state()
    height = measure_panel(_Measure(), view, line_gap=2, screen_w=1920)[1]
    modal.prompt_form(
        FormSpec(
            title="Populate",
            fields=(
                FormField("source", "pick from", ("a", "b", "c"), 0),
                FormField("after", "after", ("x", "y"), 0),
            ),
            confirm_label="Go",
            on_confirm=lambda _values: None,
        )
    )
    flat = measure_panel(_Measure(), modal.view_state(), line_gap=2, screen_w=1920)[1]
    assert height == flat + 2 * form_row_height(16)


def test_a_vertical_field_has_no_list() -> None:
    modal = ModalHost()
    _vertical_form(modal)
    modal.handle_keydown(keydown(pygame.K_SPACE))
    assert modal.view_state().form_choice is None
