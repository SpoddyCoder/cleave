"""Form dialogs: draft values, keyboard, pointer, and conditional fields."""

from __future__ import annotations

import pygame

from cleave.viz.modal import (
    ButtonRole,
    FormField,
    FormFieldKind,
    FormSpec,
    FormValues,
    ModalHost,
    ModalKind,
)
from cleave.viz.modal_layout import (
    form_control_width,
    form_row_height,
    measure_panel,
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
                FormField("target", "snap to", FormFieldKind.SEGMENT, ("a", "b"), 0),
                FormField(
                    "extra",
                    "extra",
                    FormFieldKind.STEP,
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
    assert tall[1] == short[1] + form_row_height(view.form_rows[1], 16, 2)


def test_stepper_width_fits_its_widest_option() -> None:
    modal = ModalHost()
    _form(modal, [])
    modal.set_form_value(0, 1)
    row = modal.view_state().form_rows[1]
    first = form_control_width(_Measure(), row)
    modal.step_form_value(1, 1)
    assert form_control_width(_Measure(), modal.view_state().form_rows[1]) == first
