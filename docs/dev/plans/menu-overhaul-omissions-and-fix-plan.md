# Menu overhaul follow-up: fix plan

Plan for closing every item in [menu-overhaul-omissions-and-fixes.md](menu-overhaul-omissions-and-fixes.md). Item numbers below refer to that document. The "Intentionally not done" list there stays out of scope; disabled menu commands stay disabled.

Each phase ships on its own, leaves the editor working, and has its own tests. Phases are ordered by dependency, but the early bug-fix phases and the late visual phases can be picked up in parallel with the migration track.

---

## How the items overlap

The eight items reduce to five root causes. Fixing the causes, not the symptoms, is what keeps the phase count down.

| Root cause | Items |
| --- | --- |
| Two UI stacks. Everything pygame-drawn is uploaded by `OverlayDrawer.draw_tuning` before `ShellHost.draw`, so it lands behind the ImGui shell and has no mouse hit testing. | 1, 2, 3, 4 |
| `TuningOverlay` in `tuning_panel_draw.py` is a god object: it owns the UI fade timer, toasts, the modal underlay, and the help draw. It cannot be deleted until all of those leave. | 1, 2, 3 |
| Focus has two sources of truth: `shell_focus.region` and `focus_cursor` being a `TimelineFocus`. `ShellHost._strip_has_scope` and `input_dispatch.timeline_submenu_routes_to_timeline` read the cursor, not the region. | 7, and 3 (help adds a region) |
| Theme roles are not mapped one-to-one onto ImGui colour pushes, so each surface drifts. Every new ImGui surface in this plan needs the same roles. | 5, 6, and the new surfaces from 2, 3, 4 |
| Inspector hides step arrows when the value text is `on` or `off` (`stepped = ... and value not in ("on", "off")` in `ShellHost._draw_inspector_row`), and drag is tied to the arrow hit target. | 8 |

Two corrections to the sequencing table in the source document:

- Items 2 and 4 share only the foundation. The launch flow runs in `LoadingWindow` before `ShellHost` exists, so the ImGui context has to move earlier for item 4 (Phase 3 below), but the dialogs themselves are separate work.
- Item 1 is two jobs. Moving toasts is small; deleting `tuning_panel_draw.py` is the last migration step, after modals and help have left it.

`RowLayout` is not dead code. `TuningViewState` still uses it for navigable descriptors, and `row_present_renderers.py` imports `TuningPanelCache`. Phase 7 decides its fate explicitly rather than deleting it with the draw path.

---

## Phase 1: Stepped off values (item 8)

Smallest, independent, and user-visible. Do it first.

- Stop deriving "stepped" from the display text. Use `spec.apply_horizontal is not None` (plus the locked-row rule from `row_spec.py`) so `off` keeps its arrows.
- Make the drag band the whole value cell, not only the arrows, so drag works even if a future row hides arrows.
- Audit row specs that format an off state (placement snap, overlay card toggles, post-FX toggles) for any that should genuinely not step; those get an explicit spec flag, not a string check.

**Tests.** `tests/cleave/viz/test_shell_mouse.py`: drag from `off` to on and back; arrows present at `off`; locked row still refuses drag. Parametrize over every `RowSpec` with `apply_horizontal` and an off value.

**Done when.** Sideways drag and Left/Right behave identically on every stepped row, at every value.

## Phase 2: One focus model with the strip open (item 7)

Make `ShellFocusState.region` the single source of truth for which region owns keys, with `Timeline` as a real region.

- Add `ShellRegion.TIMELINE` (or equivalent) and derive "strip has scope" from the region, not from `isinstance(focus_cursor, TimelineFocus)`. `TimelineFocus` becomes the cursor within the timeline region only.
- `input_dispatch.py`: route arrows, Enter, Esc, and cue-edit keys to `TimelineControls` only when the region is Timeline. Keep the documented globals (`h`, Ctrl/Shift+Left/Right seek, command shortcuts) working from any region.
- Clicking the inspector or navigator with the strip open moves the region there; clicking the strip moves it to Timeline.
- Opening the strip must not steal the region unless opened from the Timeline menu with intent to edit.

**Tests.** Dispatch tests in `tests/cleave/viz/`: with the strip open, Tab to Inspector then Left/Right steps the inspector value and leaves cues untouched; Tab to Timeline then Left/Right edits the cue. Mouse click region switch tests in `test_shell_mouse.py`.

**Done when.** The region cycle Menu, Navigator, Inspector, Timeline behaves the same whether or not the strip is open, apart from Timeline being skipped when closed. Update the keyboard dispatch section of [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc) if wording changes.

## Phase 3: ImGui overlay layer foundation

No user-visible feature on its own except the pilot; this is what Phases 4 through 8 build on.

- **Context lifetime.** Create the ImGui context, font atlas, and renderer with `LoadingWindow`, and hand it to `ShellHost` instead of `ShellHost.create` owning it. The launch, starter-pack, and loading screens can then draw ImGui in the same GL frame.
- **Layer order.** One ImGui frame per display frame, submitted in a fixed order: shell windows, then timeline focus border, then a top layer (modals, toasts, progress). Popups from the menu bar stay above the shell but below modals.
- **Input capture.** When a top-layer surface is modal, it captures mouse and keys before `input_dispatch.py`'s modal precedence check; the shell does not receive hover or clicks underneath. `_chrome_contains` (used to keep clicks off projectM) includes top-layer rects.
- **Theme bridge.** A single table in `theme.py` (or a small `imgui_theme.py`) mapping theme roles to ImGui colour slots, pushed once per frame. New surfaces use only this. Phase 9 tunes the values.
- **Pilot.** Move the tap-sync progress box (`OverlayDrawer.draw_tap_sync_progress`, which uses `modal_overlay.draw_info`) to the top layer. It is read-only and exercises draw order without input.

**Tests.** Headless renderer tests that the top layer submits after the shell windows; input capture tests that a click inside a modal rect does not reach the navigator.

**Done when.** Tap-sync progress draws above the shell; the shell still renders identically otherwise.

## Phase 4: Modals in ImGui (item 2)

- Keep `ModalHost`, `ModalRequest`, `ModalViewState`, and `TextModalState` as the model; every caller in `*_controls.py` is unchanged. Only presentation and input move.
- ImGui centred modal on the top layer: title, body, `labeled_lines`, option buttons (click or keyboard), and the text field (caret, selection, multi-line) driven from `TextModalState` rather than ImGui's own input widget, so existing key semantics and tests survive.
- Mouse: click an option to choose it, click outside or Esc to cancel where the modal allows cancel, hover moves the focused option.
- Remove the `modal_active` branch of `OverlayDrawer.draw_tuning` and the pygame chrome in `modal_overlay.py`. Starter-pack's `draw_info` use moves in Phase 8; keep `draw_info` until then or move it now if simpler.

**Tests.** One flow per `ModalKind` (confirm, choice, text) through the existing controls tests, plus mouse tests: click option, click outside, z-order above inspector. Re-run render confirm, layer delete, preset curation, and measure latency flows for unchanged mutation and dirty state.

**Done when.** No modal draws through the pygame overlay surface in the live editor.

## Phase 5: Notifications as ImGui toasts (item 1, part one)

- Keep `panel_notification.py` as the model (accent, elapsed, attention). Replace the `RowKind.PANEL_NOTIFICATION` row with a toast region on the top layer, anchored to the visualiser rect corner under the transport so it never covers navigator or inspector.
- Warning and error toasts stay until dismissed or timed out per existing rules; long-job failures still escalate to a modal (Phase 4) per [editor-first.mdc](../../../.cursor/rules/editor-first.mdc).
- Remove the `PANEL_NOTIFICATION` spec from `row_specs/transport.py`, the row kind if unused, and the notification draw branch in `tuning_panel_draw.py`.

**Tests.** Toast lifecycle tests against the model; layout test that the toast rect stays inside the visualiser rect for `shell-split` and `shell-docked`.

**Done when.** Toasts render without `TuningOverlay.compose_panel`.

## Phase 6: Help as a resizable third column (item 3)

Depends on Phase 2 (region model) and Phase 3 (theme bridge).

- `shell_layout.py`: optional help column right of the inspector, with its own splitter and persisted width in editor prefs (same path as the existing column widths). The visualiser shrinks; help never overlays projectM.
- Help region joins the Tab cycle only while open. Help menu commands and the existing `h` toggle open and close it.
- Restructure `help_content.py` output around the active region (Menu, Navigator, Inspector, Timeline) instead of the pre-shell navigation story. Keep the section data model; drop sections that described the removed main tree.
- Delete `help_overlay.py`, `help_panel_cache.py`, and the help branches in `OverlayDrawer.draw_tuning`.

**Tests.** Layout clamp tests with three columns at narrow and wide display sizes; persisted width round trip; region cycle with help open; content tests that each region yields its own shortcut section.

**Done when.** Help is ImGui, resizable, region-aware, and the visualiser is never covered by it. Update the help line in [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc).

## Phase 7: Retire the legacy panel stack (item 1, part two)

Only possible after Phases 4, 5, and 6.

- Extract the UI fade timer (`visibility`, `notify_input`, `hide_immediately`, `set_hold_idle_sec`) from `TuningOverlay` into a small standalone class used by `app.py`, `input_dispatch.py`, and `ShellHost`.
- Delete `OverlayDrawer.draw_tuning`, `tuning_panel_draw.py`, and `tuning_panel_cache.py`. Move anything `row_present_renderers.py` still needs from `TuningPanelCache` into the renderer module or `overlay_primitives.py`.
- Decide `RowLayout`: if the inspector still needs the flattened navigable-descriptor list, keep that part under an honest name (it is a navigation model, not a layout) and drop the draw-only parts; otherwise remove it. Either way, remove "RowLayout draws notification toasts only" from [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc).
- Remove the now-unused `OverlayTextureSlot` entries and upload coordinators for tuning and help.

**Tests.** Full unit suite (cross-cutting). A source-scan test that nothing under `cleave/viz/` imports the deleted modules.

**Done when.** The live editor has no pygame panel surface except the timeline strip.

## Phase 8: Launch, starter-pack, and loading screens in ImGui (item 4)

Depends on Phase 3 (context in `LoadingWindow`). Independent of Phases 4 to 7, so it can run in parallel with them.

- Rebuild `file_picker_overlay.py` as an ImGui window driven by the existing `FilePicker` / `PickerViewState` model: location line, shortcut chips, scrolling list, legend. Add mouse: click a row, double-click to open, click a chip, wheel scroll.
- Move the starter-pack prompt and loading progress (title, detail, bar) onto the same ImGui path, so every pre-project screen shares one stack.
- Behaviour stays as in [file-picker-plan.md](file-picker-plan.md); mid-session Open remains disabled.
- Delete `file_picker_overlay.py`, pygame draw in `loading.py`, and the last `modal_overlay.draw_info` use (and `modal_overlay.py` if empty).

**Tests.** Picker model tests stay; add headless draw tests for row hit rects and double-click open. Loading progress test that fraction maps to the bar.

**Done when.** From launch to quit, every window surface except projectM and the timeline strip is ImGui.

## Phase 9: Menu and highlight colour parity (item 6)

Best after Phases 4 to 8 so one audit covers every ImGui surface.

- Audit the theme bridge from Phase 3 against `menu-layers`, `inspector-card`, and `inspector-locked` in [menu-overhaul-design.md](menu-overhaul-design.md): menu bar, open popup, transport, focus ring, hover wash, plus modal, toast, help, and picker.
- Change theme constants only; remove any per-draw RGB in `shell_host.py` and `menu_bar.py`.

**Tests.** A test that ImGui colour pushes come only from the role table; a source scan for raw colour tuples in ImGui draw modules.

**Done when.** Side-by-side with the stills matches by role.

## Phase 10: Timeline strip visual parity (item 5)

Independent of the migration track; best after Phase 9 so it consumes final roles.

- Rework strip layout, typography, and colours in `timeline_overlay.py` to the `shell-split` and `hit-rects` timeline lane roles. Keep it its own host and keep cue editing on the strip.
- Keep the pygame-rendered strip for this phase. Porting the strip to ImGui draw lists is a separate decision, only worth it if it would remove the last pygame overlay texture slot.
- Focus border for the Timeline region (Phase 2) matches the other regions' ring.

**Tests.** Existing timeline overlay tests updated for geometry; lane rect tests against the design roles.

**Done when.** Strip matches the reference design in both shell layouts.

## Phase 11: Close out

- Move [menu-overhaul-and-mouse-support-plan.md](menu-overhaul-and-mouse-support-plan.md), the omissions document, and this plan to `docs/dev/plans-completed/`.
- Update [roadmap.md](../roadmap.md) and [docs/dev/todos.md](../todos.md).
- Windows freeze smoke on the PyInstaller build: launch picker, modal, help column, toast, and strip.

---

## Dependency summary

| Phase | Needs | Can run alongside |
| --- | --- | --- |
| 1 Stepped off values | none | anything |
| 2 Focus model | none | 1, 3 |
| 3 Overlay layer foundation | none | 1, 2 |
| 4 Modals | 3 | 8 |
| 5 Toasts | 3 (and 4 for failure escalation) | 6, 8 |
| 6 Help column | 2, 3 | 5, 8 |
| 7 Retire legacy panel | 4, 5, 6 | 8 |
| 8 Launch screens | 3 | 4 to 7 |
| 9 Colour parity | 4 to 8 preferred | 10 |
| 10 Timeline visuals | 2, 9 preferred | 9 |
| 11 Close out | all | none |

Each phase with a user-visible change adds its own bullet under `## [Unreleased]` in [CHANGELOG.md](../../../CHANGELOG.md).
