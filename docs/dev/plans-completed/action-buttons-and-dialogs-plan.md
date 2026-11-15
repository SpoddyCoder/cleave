# Action buttons and dialogs: delivery plan

## Context

The ui-refactor gives Cleave mouse support and standard desktop editor behaviour. Green action rows are the last old-style element. "Action row" currently covers four different things: properties edited through a modal, simple commands, commands whose parameters hide in chained modals, and staged rows that look live but do nothing until Apply.

The agreed design is in [menu-overhaul-design.html](docs/dev/plans/menu-overhaul-design.html), section 7, and the `actions-*` and `dialog-*` views.

The rule: **the inspector holds live properties. Commands are real buttons. A command that needs parameters opens one dialog, and its label ends in "...".**

Outcome: `RowAffordance.ACTION` and the `ACTION` colour no longer exist. Every action is a button backed by the command registry, usable by mouse and keyboard.

## Decisions

- **Project YAML is unchanged.** Timeline preset values stay in the same config keys, so no migration. Snap and Set cut type remember their last values for the session only.
- **Form fields are plain data, not inspector rows.** This replaces my earlier idea of sharing `_draw_inspector_row`. Modals already use their own draw and pointer-intent path, and a dialog that edits draft values makes Cancel free, with no snapshot and restore.
- **Inline text reuses the text modal's editor.** It gets its caret, wrapping, key repeat and validation from existing code, rather than adding a second keyboard path through ImGui.
- **Undo covers bulk timeline commands only.** The roadmap's wider undo for config edits stays out of scope.
- **Timeline navigator:** the `timeline.preset` page goes. Generate and Reset move to the Timeline root page.

## Phase 0: Set up

- Copy this plan to `docs/dev/plans/action-buttons-and-dialogs-plan.md`.
- Work on `ui-refactor`. Commit only when asked.

## Phase 1: Buttons and colour

- [theme.py](cleave/viz/theme.py): add `BUTTON_BG`, `BUTTON_BORDER`, `BUTTON_PRIMARY_BG`, and `BUTTON_DANGER_BG`, aliased to `SOLO_BG` like `ARMED_BG`. Remove `ACTION`.
- Move every `ACTION` use to `VALUE`: `shell_host.py` (transport, navigator toggles, check marks), `commands.py`, `top_layer.py`, `file_picker_surface.py`, `row_present_renderers.py`. Set the button colours in `imgui_theme.py`.
- Inspector buttons:
  - `InspectorRow.command_id` becomes `command_ids`, a tuple, so one row can hold paired buttons.
  - `_draw_command_row` in `shell_host.py` draws real buttons.
  - `inspector_controls.py`: Left/Right move between buttons in a row. `inspector_command_id` still marks the focused button.
- Placement: add `SectionNode(commands=...)` in `row_sections.py`. This replaces `_LEAF_COMMANDS`, `_PAGE_COMMANDS`, and the matching placeholder `RowKind`s.
- Move the "Delete Layer" label check in `row_value_color_for` into the command's `enabled`.

## Phase 2: Modal language

- `modal.py`: replace `prompt_yes_no` with `prompt_confirm(title, body, confirm_label, on_confirm, on_cancel, destructive=False)`, and update all 14 callers.
- Destructive confirms use the red button, and Cancel takes initial focus.
- Remove `capital_case_modal_option`, so labels read as written, such as `Delete layer`.
- `modal_surface.py`: one shared button primitive for yes/no, unsaved quit, and text modal buttons. Genuine lists, such as curation choices, stay lists.
- Add Layer and Add Current Preset run at once and show a toast. Keep `P` for add preset.

## Phase 3: Form dialog and parameter commands

- `modal.py`: add `ModalKind.FORM`.
  - New data types: `FormField` (id, label, kind of step, segment or radio, options, value, optional visibility rule), `FormButton`, and `FormSpec`, which holds a title, a body, an `info(values)` callback, and the fields and buttons.
  - `prompt_form` holds draft values and handles the keyboard as in section 7 of the design page.
- `modal_layout.py` and `modal_surface.py`: measure and draw forms, and add pointer intents for segments, arrows, and buttons. Follow the existing `ModalPointerIntent` pattern.
- Move each command onto a form:

| Command | Controller | Notes |
|---|---|---|
| `Snap cues...` | `timeline_snap_controls.py` | Replaces both snap rows and the chained prompts |
| `Set cut type...` | `timeline_cut_controls.py` | Replaces 4 rows. Fixes Remove clearing every cut type. Count comes from a dry run of `apply_cut_to_lanes` on a copy of the lanes |
| `Reset timeline...` | `timeline_preset_controls.py` | Layers on/off field, red confirm |
| `Populate...` | `preset_list_controls.py` | Radio list. Keep the preset lock and unlock on every exit path |
| `Generate timeline...` | `timeline_preset_controls.py` | Seed from session, write on confirm only |

- Remove the `TIMELINE_PRESET_*` rows, `TIMELINE_PRESETS_SECTION`, the `timeline.preset` page, the 4 Apply/Remove rows, and the echo modal.
- `commands.py`: rename `timeline.apply_preset` to `timeline.generate`, add `timeline.set_cut_type`, and update labels with "...". Add the Timeline menu entry.

## Phase 4: Remaining commands

- Preset list toolbar: `+ Add current` and `Populate...` as commands that take the layer from the selected node, as `layers.delete` does.
- Resume: a status line with a `Resume` button. `TRACK_PRESET_SWITCHING_RESUME` has `can_enter_move_mode=True`, so confirm where move mode is entered from before removing the row.
- Layers navigator row: a `+` icon running `layers.add`, built on the existing navigator toggle code.
- Section lock: buttons show the locked role. Delete layer stays available when locked, as today.

## Phase 5: Properties

- Extract `TextModalState` and its edit helpers from `modal.py` into `cleave/viz/text_edit.py`, and the field drawing from `modal_surface.py`. The text modal keeps using them.
- Add an inline editor controller. `input_dispatch.py` must check it alongside `modal_host.active`, so typing does not trigger hotkeys. Enter commits, Esc reverts, clicking away commits. Multi-line body text keeps the text modal's key behaviour.
- New affordances `VALUE_TEXT` and `VALUE_COLOUR` for the 8 overlay rows in `row_specs/overlays.py`.
- Colour rows: draw a swatch and hex value.
  - Clicking the swatch opens an ImGui colour picker through `top_layer.py`, updating live. Esc reverts.
  - Hex text uses the inline editor with `validate_hex_colour`.
  - Optional colours get a None button.
- Song markers: `VALUE_STEP` with `apply_action` for seek, and a delete icon built on `RowNavButton`.
- Remove `RowAffordance.ACTION`, `ACTION_ROW_KINDS`, `shows_enter_icon`, and the related branches in `help_content.py`.

## Phase 6: Timeline undo

- New `cleave/viz/timeline_history.py`: a bounded undo and redo stack of snapshots. Use `copy_lane` from `session.py`.
- Record before Generate, Reset, Snap, and Set cut type. Generate can also change preset lists and pattern mask, so its snapshot includes those.
- Clear the history on project switch and on layer add or delete, since lanes are keyed by slot. Disable undo while recording.
- Replace the disabled `timeline.undo_cut` with `Undo` (`Ctrl+Z`) and `Redo` (`Ctrl+Y`). Check that the keys are free.
- Drop "cannot be undone" from the Reset dialog. The dialogs stay, because they hold parameters. Delete layer keeps its confirm.

## Phase 7: Documentation

- Design page: make proposed mode the only mode, remove the Actions switch, and retitle section 7 as agreed.
- `menu-overhaul-design.md` and `menu-overhaul-and-mouse-support-plan.md`: remove "green means command", and update the theme roles.
- Update help text and any user docs that name the old rows.
- `CHANGELOG.md`: add `## [Unreleased]` bullets in the same edit as each user-visible phase, including a `### Fixed` bullet for Remove cuts.
- Stills: recapture once a browser is available.

## Tests

Follow `tests/cleave/viz/`. About 9 test files reference `ACTION`, and `test_row_spec.py`, `test_inspector.py`, and `test_commands.py` will need the most change.

New coverage:
- Form keyboard, pointer intents, draft isolation on Cancel, and conditional fields.
- Paired button focus in the inspector.
- Cut type correctness: removing only touches the chosen scope, and the count matches the result.
- Inline editor: commit, revert, and hotkey blocking.
- Undo, including history clearing.

## Verification

- After each phase, run the tests for that area:

```bash
/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py -k <name>
```

- Run the full suite after phases 1, 3, 5, and 6, because they cut across modules.
- Agents do not launch the editor, so each phase needs a manual check by you on Windows:
  - Run each command by mouse and by keyboard.
  - Compare against the matching `actions-*` or `dialog-*` view.
  - Check that a locked section refuses its buttons.
  - Check the frame rate is steady with a dialog and the colour picker open.

## Risks

- **Inline editing (phase 5)** is the riskiest input change, because it adds a focus state that competes with hotkeys.
- **Generate undo** must restore everything Generate touches, or undo will leave a half-reverted project.
- **Removing kinds** touches `TIMELINE_SECTION_KINDS` and other sets in `row_sections.py`. The `ROW_SPECS` registry assert should catch gaps at import.
