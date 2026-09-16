# Text input component plan

Add a reusable in-window text dialog so Windows users can edit overlay copy (and later hex colours) without opening YAML. First caller is the opening/closing card title; body and remaining YAML-only strings follow.

Related: [live-tuning-ui](../.cursor/rules/live-tuning-ui.mdc), [change-touchpoints](../.cursor/rules/change-touchpoints.mdc), [architecture principles](../.cursor/rules/architecture-principles.mdc), [editor-first](../.cursor/rules/editor-first.mdc).

---

## Problem

Credits card **copy and colours** still live only in `cleave-viz.yaml`. The live panel already nudges title/body font, size, margin, opacity, and border width, but `title.content` and `body.content` are merged from config, not session:

- [build_live_overlay_config](../cleave/viz/render_overlay.py) copies `base.title.content` / `base.body.content`.
- [overlays_persist_values](../cleave/config_schema/render/overlays.py) writes those same config fields back.
- The default body even says to edit YAML.

[ModalHost](../cleave/viz/modal.py) is Yes/No, choice, progress, and unsaved-quit. Options are a vertical list; Up/Down and Left/Right cycle the same index; Y/N jump focus. That type cannot host a caret, a draft buffer, or Confirm/Cancel on one row.

The live event loop ([cleave/viz/app.py](../cleave/viz/app.py)) pumps KEYDOWN / KEYUP / QUIT only. Typing needs `TEXTINPUT`.

---

## Principles

- **One text modal, many rows.** Keep the panel row a plain `ACTION` line. Enter opens the dialog. Do not embed an editor in `RowLayout`.
- **New modal kind, not Yes/No.** Nested navigate vs edit, horizontal Confirm/Cancel, and a draft string do not fit `prompt_yes_no` / `prompt_choice`.
- **Session owns live copy.** After Phase 1.3, title (then body, then colours) live on `RenderOverlayCardRuntime`. Config stays bootstrap. Persist only through `persisted_session_payload`.
- **Confirm commits; Cancel discards.** The dialog holds a draft. The card and dirty flag change only on Confirm.
- **Keyboard only.** No mouse hit-testing. Overlay chrome stays in [modal_overlay.py](../cleave/viz/modal_overlay.py) / [overlay_primitives.py](../cleave/viz/overlay_primitives.py); do not import `tuning_panel_draw`.
- **Host is generic from day one.** `single_line` is a callee flag. Phase 1 ships one single-line row; Phase 2 is a second row, not a second widget.

---

## Locked

| Question | Answer |
| --- | --- |
| Panel row | `ACTION`, mint (`ACTION` role), enter icon on highlight. Same chrome as "render the project" |
| First row | Render Overlays -> opening/closing card -> title -> **title text** (card-parameterized kind, like the other overlay rows) |
| Dialog regions | (1) CTA from the callee, display-only (2) multiline field, constrained to one line when asked (3) Confirm and Cancel on one row |
| Focus stops | Two: the field, and the Confirm/Cancel row. CTA is not a stop. Up/Down move 2 <-> 3. Left/Right on 3 only |
| Open | Field focused, already in edit mode, caret at end, current value shown. No extra Enter to start typing |
| Edit vs navigate | Esc or Enter leaves edit (keeps the draft, returns to field highlight). Does not confirm or revert |
| Newline | Shift+Enter while editing, and only when `single_line` is false. Ignored for title |
| Confirm / Cancel | Enter on a focused button. Esc while navigating (or Cancel) dismisses and restores the launch value |
| Typing | pygame `TEXTINPUT` plus `start_text_input` / `stop_text_input`. Do not trust KEYDOWN `unicode` |
| Globals while open | Modal consumes keys, including `h`, Space, Ctrl+S. Ctrl+Q / window close still go through unsaved-quit as today |
| Y/N | Do not inherit Yes/No letter shortcuts |
| Title renderer | Stays one `Font.render` in Phase 1. Title callee passes `single_line=True` |
| Body renderer | Already `splitlines()`. Phase 2 does not need a new layout path |
| Empty string | Allowed |
| Live preview while typing | Out. Scrim hides the card; apply on Confirm |
| Clipboard, selection, IME candidate UI | Out of v1. `TEXTINPUT` still lets composed characters in |
| Colour picker widget | Out. Phase 3 reuses this dialog for hex strings |

---

## Leave open

- Home / End / Delete, Ctrl+arrows, Shift-select, clipboard.
- Multiline titles (would need `splitlines()` on the title surface, like body).
- A real colour picker. Hex text is the bridge.
- Live punch-through so the card is visible while the dialog is open.
- `h` showing dialog-specific help (CTA line is the in-dialog hint).

---

## Dialog

Callee API (names indicative):

```
prompt_text(
    cta: str,
    initial: str,
    on_confirm: Callable[[str], None],
    on_cancel: Callable[[], None] | None = None,
    *,
    single_line: bool = False,
)
```

Title uses `cta="Change text..."`, `single_line=True`. Body uses the same CTA, `single_line=False`.

### Navigate

- Up/Down: field <-> button row.
- Left/Right on the button row: Confirm <-> Cancel.
- Enter on the field: enter edit mode (already true on open; also after Esc-from-edit).
- Enter on a button: run that action and close.
- Esc: dismiss, `on_cancel`, original value unchanged.

### Edit

- Field loses the navigate highlight; a caret shows the insert point.
- CTA gains a second line: `press ESC to stop editing` (exact copy locked above).
- Arrows move the caret (Up/Down are visual lines when multiline).
- Backspace deletes backward.
- Shift+Enter inserts a newline unless `single_line`.
- Printable input comes from `TEXTINPUT`.
- Esc or Enter: leave edit, keep draft, restore field highlight.
- Hold-repeat for arrows and Backspace via [KeyRepeatController](../cleave/viz/key_repeat.py). Extend `_REPEAT_KEYS` or arm a text-edit repeat set; do not call `pygame.key.set_repeat`.

Single-line overflow scrolls horizontally with the caret. Multiline wraps to the panel content width and scrolls vertically if needed. Cap panel height (about half the viewport, same idea as the current message cap) so a long body cannot cover the screen.

Buttons sit on one row, centered, Confirm then Cancel. Reuse `HIGHLIGHT` fill for the focused button. Do not stack them like Yes/No.

Theme: CTA in `LABEL`, field in `VALUE`, hint in `LABEL` or `DISABLED`, buttons `VALUE` / `HIGHLIGHT`. No new colour.

---

## Title row (Phase 1 caller)

Place first under the existing title expand section in [row_sections.py](../cleave/viz/row_sections.py) (before font / font size / margin).

- Kind: `RENDER_OVERLAY_CARD_TITLE_TEXT` (one kind, `RowDescriptor.card` selects opening vs closing).
- Affordance `ACTION`, `present_style=FULL_LINE`, `shows_enter_icon=True`, `parent_group="render_overlay_title"`.
- Label `title text`. Value is the current content, newlines shown as spaces, clipped with the existing fit helpers.
- Enter opens `prompt_text`. Confirm calls `RenderOverlayCardControls.set_title_content`.
- Overlay section lock: row stays visible and navigable; Enter no-ops; colour `LOCKED`. Same derived lock as other overlay value rows (`ACTION` must be in the blocking affordance set, or set `blocked_by_section_lock` on the spec).
- Help: `help_entries=(("Enter", "edit title"),)` plus a short description. The dialog does not toggle the help panel.

Touchpoints follow [change-touchpoints](../.cursor/rules/change-touchpoints.mdc): schema default already exists; add the session field; persist through `overlays_persist_values`; `RowKind` + spec + section; mutate in [render_overlay_controls.py](../cleave/viz/render_overlay_controls.py). Content does not gate row presence, so no structure-signature change.

---

## What not to change

- Existing Yes/No, choice, progress, and unsaved-quit layout or Y/N behaviour.
- Overlay animation, position, font cycle, numeric nudges already in the panel.
- Title card renderer in Phase 1 (still one line).
- Mouse, native OS text dialogs, or a second input path for CLI.

---

## Phases

### Phase 1 - Text modal and title row

User-facing: under each card's title section, **title text** opens a dialog, Confirm writes the title, Save persists it, the live card updates.

The host supports multiline internally. Only the title row ships. Each step below lands with tests and leaves the tree green.

**1.1 Modal host (no draw, no row).** Extend [cleave/viz/modal.py](../cleave/viz/modal.py):

- `ModalKind.TEXT`.
- Request fields: `cta`, `draft`, `single_line`, `editing`, `caret_index`, `focus_region` (`FIELD` or `BUTTONS`), `button_index` (Confirm=0, Cancel=1).
- `prompt_text(...)` as above. Open in edit mode, caret at `len(initial)`.
- `handle_keydown` branches: PROGRESS / YES_NO / CHOICE unchanged; TEXT implements navigate vs edit. Esc-in-edit does not call `on_dismiss`.
- `view_state()` grows optional text fields so draw stays a pure function. Existing kinds keep `options` / `message` / `labeled_lines`.

Tests in [tests/cleave/viz/test_confirm.py](../tests/cleave/viz/test_confirm.py) (or a sibling `test_text_modal.py`): open shows initial; type via a test hook that applies a text event; Shift+Enter inserts or no-ops; Esc-edit keeps draft; Esc-nav / Cancel restores; Confirm returns the draft; Left/Right only on the button row; Y/N do nothing; `single_line` rejects newlines in the draft.

**1.2 Draw.** Extend [cleave/viz/modal_overlay.py](../cleave/viz/modal_overlay.py):

- CTA, optional hint line when `editing`, field block, horizontal Confirm/Cancel.
- Caret when editing (pipe or invert at `caret_index`). Blink can wait until 1.3 if view state has no clock yet; a static caret is enough here.
- Measure panel from CTA + field + buttons; wrap field to content width; min width stays `_PANEL_MIN_SCREEN_FRACTION`.

Tests in [tests/cleave/viz/test_modal_overlay.py](../tests/cleave/viz/test_modal_overlay.py): offscreen surface, existing Yes/No still identical; TEXT shows CTA and initial; hint line only when editing; focused button highlighted. No product row yet; tests call `prompt_text` on the host.

**1.3 Event loop and repeat.** [cleave/viz/app.py](../cleave/viz/app.py) and [input_dispatch.py](../cleave/viz/input_dispatch.py):

- Pump `TEXTINPUT` into the modal host while `ModalKind.TEXT` and `editing`.
- `pygame.key.start_text_input()` on enter-edit, `stop_text_input()` on leave-edit and dismiss.
- Repeat arrows and Backspace while editing; do not repeat those keys for Yes/No.
- Optional caret blink from `ModalHost.tick` using overlay `dt` (same tick path as `KeyRepeatController`).

Tests with synthesized `TEXTINPUT` / KEYDOWN events (no window): Space inserts; `h` inserts rather than toggling help; Shift+Enter vs Enter; start/stop_text_input called on the edit transitions.

**1.4 Title content on the session.** No UI row yet.

- `title_content: str` on `RenderOverlayCardRuntime`; default from `DEFAULT_RENDER_OVERLAY_TITLE`.
- Load from cfg in `render_overlays_runtime_from_cfg`.
- `build_live_overlay_config` reads `runtime.title_content`.
- `_overlay_card_persist_values` writes `runtime.title_content` (not `base_card.title.content`).
- `set_title_content` on `RenderOverlayCardControls`. Dirty tracking stays computed.

Tests: session round-trip, persist payload, live merge uses the runtime string, mutating content dirties save. Update [tests/cleave/viz/test_render_overlay.py](../tests/cleave/viz/test_render_overlay.py) merge assertions. Architecture line "overlay card copy/colours stay on CleaveConfig" is no longer true for title; update [architecture-principles.mdc](../.cursor/rules/architecture-principles.mdc) when this step lands.

**1.5 Title text row.** `RowKind` + spec + section placement + Enter -> `prompt_text`. Truncated value on the row. Section lock. Help entries. [CHANGELOG.md](../CHANGELOG.md) Unreleased Added. Tests: row present under title, Enter opens TEXT modal, Confirm updates session, Cancel does not, lock blocks Enter.

After 1.5 a user can edit both cards' titles in the window and Save.

### Phase 2 - Body row (multiline)

User-facing: under each card's body section, **body text** opens the same dialog with `single_line=False`.

- Session field `body_content`, persist, live merge (same pattern as 1.4).
- Kind `RENDER_OVERLAY_CARD_BODY_TEXT`, first child under the body expand section.
- Confirm `set_body_content`. Body renderer already splits lines.
- Replace `DEFAULT_RENDER_OVERLAY_BODY` copy that tells the user to edit YAML.
- Changelog.

If 1.2 shipped a short field, this is when wrap + vertical scroll must be real: default body is two lines, users will add more. Tests: Shift+Enter inserts; Up/Down in edit move between lines; Up/Down in navigate still switch field vs buttons; a long body does not exceed the panel cap.

### Phase 3 - Remaining YAML-only overlay strings

Everything left on the credits card that is still config-only and is a string. That is hex colour, not more prose.

| YAML | Panel parent | Row (indicative) | Notes |
| --- | --- | --- | --- |
| `title.font-colour` | title | title colour | required hex |
| `title.background-colour` | title | title background | optional; empty Confirm clears |
| `body.colour` | body | body colour | required hex |
| `body.background-colour` | body | body background | optional; empty Confirm clears |
| `background.colour` | card (beside opacity) | background colour | required hex |
| `background.border.colour` | card (beside border width) | border colour | required hex |

Each row is `ACTION` + enter icon, opens `prompt_text` with `single_line=True` and CTA `Change colour (#rgb or #rrggbb)...`. Confirm runs `parse_hex_colour`; on failure stay in the dialog with a one-line error (do not close). Session fields + persist + `build_live_overlay_config` for each. Card-parameterized kinds, same as title.

Build order: one colour through session/persist/merge/row (prove the pattern), then the rest in one pass.

Not this widget, but the same "YAML-only overlay" gap: `background.margin` and `background.padding` should become `VALUE_STEP` rows (px, Ctrl for x10) in this phase so a Windows user never needs YAML for a credits card. They are not text fields.

Changelog once colours (and margin/padding if included) are in the panel. Update the architecture principle so overlay copy **and** colours are session-owned.

Each step below lands with tests and leaves the tree green.

**3.1 Validation error line in the text modal.** The text modal currently has no mechanism to reject a Confirm and show an error. Add a one-line error display.

- `TextModalState` gains `error: str | None = None`.
- On Confirm, the caller's `on_confirm` currently receives the draft directly. Add an optional `validate: Callable[[str], str | None]` parameter to `prompt_text`. When present, Confirm calls `validate(draft)` first. If it returns a non-None string (the error message), set `error` on `TextModalState` and stay open (do not dismiss). If it returns None, proceed as today.
- Draw: when `error` is set, show it below the field in `DISABLED` (or a warm accent if one exists in theme; reuse `ACTION` red if not). Clear `error` on the next `TEXTINPUT` or Backspace (any draft mutation) so stale errors disappear as the user types.
- `view_state()` exposes the error string so `modal_overlay.py` draw stays a pure function.

Tests: Confirm with a failing validator keeps the dialog open; draft edit clears the error; Confirm with a passing validator dismisses; Confirm with no validator still works as before (backward compatible).

**3.2 Hex-colour validation helper.** A thin wrapper around `parse_hex_colour` that returns the error string (or None) and the parsed tuple, suitable for the `validate` parameter.

- `cleave/viz/colour_parse.py` (new, small module):
  - `validate_hex_colour(draft: str) -> str | None` -- returns None on success, or a user-facing message like `"invalid hex colour (use #rgb or #rrggbb)"` on failure.
  - `validate_optional_hex_colour(draft: str) -> str | None` -- same, but also accepts an empty string (maps to `None` colour).
  - `parse_hex_colour_or_none(draft: str) -> tuple[int, int, int] | None` -- returns the tuple or None for an empty string; raises on bad input (callers already validated).

Tests in `tests/cleave/viz/test_colour_parse.py`: `#fff` ok, `#aabbcc` ok, `#gg0000` error, empty string ok for optional / error for required, missing `#` error.

**3.3 Session fields for all six colours.** No UI rows yet.

Add to `RenderOverlayCardRuntime`:
- `title_colour: tuple[int, int, int]` (default `DEFAULT_RENDER_OVERLAY_TEXT_COLOUR`)
- `title_background_colour: tuple[int, int, int] | None` (default `None`)
- `body_colour: tuple[int, int, int]` (default `DEFAULT_RENDER_OVERLAY_TEXT_COLOUR`)
- `body_background_colour: tuple[int, int, int] | None` (default `None`)
- `background_colour: tuple[int, int, int]` (default `DEFAULT_RENDER_OVERLAY_BACKGROUND_COLOUR`)
- `border_colour: tuple[int, int, int]` (default `DEFAULT_RENDER_OVERLAY_BORDER_COLOUR`)

Touchpoints:
- `default_render_overlay_card_runtime_values` adds the six keys.
- `_card_runtime_from_cfg` reads the colour values from cfg: `card.title.colour`, `card.title.background_colour`, `card.body.colour`, `card.body.background_colour`, `card.background.colour`, `card.background.border.colour`.
- `build_live_overlay_config` in [render_overlay.py](../cleave/viz/render_overlay.py) replaces the six `base.*` colour reads with `runtime.*` reads.
- `_overlay_card_persist_values` writes `runtime.title_colour` (etc.) instead of `base_card.title.colour` (etc.). The `base_card` parameter can be dropped entirely once all six colours and margin/padding are session-owned (step 3.6).
- Setters on `RenderOverlayCardControls`: `set_title_colour`, `set_title_background_colour`, `set_body_colour`, `set_body_background_colour`, `set_background_colour`, `set_border_colour`. Each takes a `tuple[int, int, int]` (or `| None` for the optional ones).

Tests: session round-trip, persist payload includes the colours, `build_live_overlay_config` uses runtime colours, mutating a colour dirties save. Update [test_render_overlay.py](../tests/cleave/viz/test_render_overlay.py) merge assertions that currently check `base.title.colour` pass-through.

**3.4 First colour row (title colour).** Prove the full pattern end to end before adding the remaining five.

- `RowKind.RENDER_OVERLAY_CARD_TITLE_COLOUR`.
- `RowSpec`: `ACTION`, `LABELED_VALUE`, `shows_enter_icon=True`, `blocked_by_section_lock=True`, `parent_group="render_overlay_title"`.
- `format_value`: `rgb_to_hex(runtime.title_colour)`.
- `apply_action`: check section lock, then call `prompt_text` with `cta="Change colour (#rgb or #rrggbb)..."`, `single_line=True`, `initial=rgb_to_hex(current)`, `validate=validate_hex_colour`. On confirm, parse and call `set_title_colour`.
- Section placement: child of the title expand section in `_build_render_overlay_card_section`, after title text (before font).
- Help: `help_entries=(("Enter", "edit colour"),)`.

Tests: row present under title, Enter opens TEXT modal, Confirm with `#ff0000` updates session, Confirm with `bad` stays open (error shown), Cancel does not change, section lock blocks Enter.

**3.5 Remaining five colour rows.** Same pattern as 3.4, one `RowKind` per colour.

| RowKind | Parent group | Placement |
| --- | --- | --- |
| `RENDER_OVERLAY_CARD_TITLE_BACKGROUND_COLOUR` | `render_overlay_title` | after title colour |
| `RENDER_OVERLAY_CARD_BODY_COLOUR` | `render_overlay_body` | after body text |
| `RENDER_OVERLAY_CARD_BODY_BACKGROUND_COLOUR` | `render_overlay_body` | after body colour |
| `RENDER_OVERLAY_CARD_BACKGROUND_COLOUR` | `render_overlay` | after opacity (beside it semantically) |
| `RENDER_OVERLAY_CARD_BORDER_COLOUR` | `render_overlay` | after border width (beside it semantically) |

Optional colours (`title_background_colour`, `body_background_colour`) use `validate_optional_hex_colour`; the row value shows `none` when `None` and the hex string otherwise. Empty-string Confirm clears the colour.

Format helpers and apply-action functions follow the title-colour template. One `_apply_overlay_card_colour_action` helper can be shared with a field-name parameter to reduce boilerplate.

Tests: one test per row for presence and Confirm/Cancel; optional rows also test empty-string -> None.

**3.6 Margin and padding VALUE_STEP rows.** These are not text fields but close the last YAML-only gap.

- `RowKind.RENDER_OVERLAY_CARD_BACKGROUND_MARGIN`, `RowKind.RENDER_OVERLAY_CARD_BACKGROUND_PADDING`.
- Session fields: `background_margin: int` and `background_padding: int` on `RenderOverlayCardRuntime`, defaults from `DEFAULT_RENDER_OVERLAY_BACKGROUND_MARGIN` / `DEFAULT_RENDER_OVERLAY_BACKGROUND_PADDING`.
- Load from cfg in `_card_runtime_from_cfg`: `card.background.margin`, `card.background.padding`.
- `build_live_overlay_config` reads `runtime.background_margin` / `runtime.background_padding` instead of `base.background.margin` / `base.background.padding`.
- `_overlay_card_persist_values` writes the runtime values. The `base_card` parameter can now be removed from `_overlay_card_persist_values` since every field is session-owned.
- Setters: `set_background_margin(margin: int)` and `set_background_padding(padding: int)` on `RenderOverlayCardControls`, clamped to `max(0, value)`.
- `RowSpec`: `VALUE_STEP`, `LABELED_VALUE`, `repeatable=True`, Ctrl for x10 step, `parent_group="render_overlay"`.
- Placement: margin after background colour; padding after margin.
- Help: standard Left/Right + Ctrl description.

Tests: row presence, Left/Right mutates, persist, `build_live_overlay_config` reads runtime.

After 3.6, `_overlay_card_persist_values` no longer needs `base_card`. Remove the parameter and the `render_overlays_base` call in `overlays_persist_values`.

**3.7 Architecture, changelog, cleanup.**

- [architecture-principles.mdc](../.cursor/rules/architecture-principles.mdc): replace "overlay card colours remain on config" with a statement that overlay card copy, colours, margin, and padding are all session-owned.
- [CHANGELOG.md](../CHANGELOG.md): one Unreleased Added bullet: "Credits card colours, margin, and padding editable in the panel".
- Confirm `build_live_overlay_config` no longer reads any field from `base` except those that are truly immutable (none remain after 3.6; the function should take only `runtime` or keep `base` as dead code guard).
- Run full test suite to confirm no regressions.

---

## Tests

No editor / OpenGL window ([agent-environment](../.cursor/rules/agent-environment.mdc)). Prefer `tests/cleave/viz/test_confirm.py`, `test_modal_overlay.py`, `test_render_overlay.py`, overlay row tests, and persist/config tests already used for overlay knobs.

Phase 1.1-1.3: host and draw only; no `RowKind`.

Phase 1.4: persist and live merge; no modal.

Phase 1.5 / 2: row presence, Enter opens TEXT, Confirm vs Cancel, section lock, dirty flag, Save payload.

Phase 3.1: validate callback on text modal; error display and clear on edit.

Phase 3.2: `test_colour_parse.py` for `validate_hex_colour`, `validate_optional_hex_colour`, and `parse_hex_colour_or_none`.

Phase 3.3: session round-trip for all six colour fields; persist payload includes colours; `build_live_overlay_config` uses runtime colours; mutating a colour dirties save. Update existing merge assertions in `test_render_overlay.py`.

Phase 3.4: title-colour row presence, Enter opens TEXT modal, Confirm with valid hex updates session, Confirm with invalid hex stays open (error set), Cancel does not change, section lock blocks.

Phase 3.5: one test per remaining colour row for presence and Confirm/Cancel; optional rows also test empty string -> None.

Phase 3.6: margin/padding row presence, Left/Right mutates session, persist payload, `build_live_overlay_config` reads runtime values.

Do not launch the editor for routine checks.

---

## Docs and copy

- [CHANGELOG.md](../CHANGELOG.md) Unreleased under Added, once per user-visible phase (title row, body row, colour rows).
- Default body string in [overlays.py](../cleave/config_schema/render/overlays.py) when Phase 2 ships.
- [architecture-principles.mdc](../.cursor/rules/architecture-principles.mdc) when copy (then colours) leave CleaveConfig.
- Do not bump `cleave.__version__` or cut a tag unless asked.
