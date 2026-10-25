# Menu overhaul: omissions and follow-up fixes

Companion to [menu-overhaul-and-mouse-support-plan.md](menu-overhaul-and-mouse-support-plan.md). That plan is implemented for phases 1 through 7 (ImGui shell, navigator, inspector, menus, mouse gestures, docked layout, persisted column widths). This document records what was **intentionally left out** of that plan and **known gaps** to close next.

Design reference for chrome and colours: [menu-overhaul-design.html](menu-overhaul-design.html), [menu-overhaul-design.md](menu-overhaul-design.md), stills in [menu-overhaul-stills/](menu-overhaul-stills/).

---

## Intentionally not done (by plan)

These are not bugs; they were non-goals, disabled menu items, or deferred to other plans.

### Non-goals from the menu overhaul plan

- Native Win32 menu bar (ImGui menu in the OpenGL window is the product chrome).
- Full docking beyond `shell-split` and `shell-docked`, floating panels, user-rearranged workspaces, touch, or pen.
- Replacing the timeline strip with a full NLE.
- Swapping ImGui for another widget backend.
- In-window **Separate**, **Backup**, or **Restore** (CLI only unless a later plan adds editor-first progress for each).
- Rewriting the config schema except editor prefs already added for shell layout and column widths.

### Menu commands left disabled

| Menu path | Reason |
| --- | --- |
| File > Open project... (`Ctrl+O`) | Mid-session open stays [file-picker-plan.md](file-picker-plan.md) phase 3. |
| Project > Separate stems... | CLI `cleave separate` only. |
| Project > Backup... / Restore... | CLI `cleave backup` / `cleave restore` only. |
| Timeline > Undo last cut | No cut-undo command exists yet. |
| Help > About Cleave | No about command exists yet. |

### Other deferred product items

- **Undo/redo** for session edits ([roadmap.md](../roadmap.md)).
- **Hidden global** `F3` overlay profiler (not a menu item; unchanged).
- **Phase 1 Windows freeze** menu smoke on the PyInstaller build ([windows-freeze.md](../windows-freeze.md)): operational check, not a code gate.

### Explicit plan carve-outs (now follow-up)

The original plan said modals, help overlay, timeline strip cue editing, and loading/file-picker flows **stay on the pygame overlay path** for phases 1 through 7. That kept scope bounded but left a **second UI stack** beside ImGui. Items 1 through 4 below finish that migration.

---

## Follow-up fixes and migrations

Ordered roughly by dependency: retire legacy pygame panel surfaces first, then fix interaction bugs, then visual parity.

### 1. Legacy tuning panel and notification toasts

**Problem.** `tuning_panel_draw.py`, `tuning_panel_cache.py`, and `RowLayout` still exist. The main tree is gone, but **warning and error toasts** still render through the old panel path (`RowKind.PANEL_NOTIFICATION` in [row_layout.py](../../../cleave/viz/row_layout.py), draw in [tuning_panel_draw.py](../../../cleave/viz/tuning_panel_draw.py)).

**Goal.** Remove the legacy panel draw path from the live editor. Relocate notifications to a shell-appropriate surface (candidates: a slim strip under the menu or transport, navigator footer, or a dedicated ImGui toast region). Preserve editor-first behaviour: errors and long-job failures must not rely on stdout alone.

**Touchpoints.** [overlay_draw.py](../../../cleave/viz/overlay_draw.py), [app.py](../../../cleave/viz/app.py), [panel_notification.py](../../../cleave/viz/panel_notification.py), [row_specs/transport.py](../../../cleave/viz/row_specs/transport.py) (`PANEL_NOTIFICATION` spec).

### 2. Modal dialogs: mouse, z-order, ImGui

**Problem.** Confirm/save/choice modals still use the pygame overlay ([modal.py](../../../cleave/viz/modal.py) and callers). They are **not mouse-aware** in line with the shell, and they **draw behind** the ImGui navigator and inspector (z-order).

**Goal.** Replace modal UI with ImGui (or a single modal layer drawn after the shell with correct hit testing). Remove pygame modal chrome once parity exists. All `ModalHost` flows (render confirm, layer delete, preset curation, measure latency, etc.) must keep the same mutation and dirty semantics.

**Touchpoints.** [input_dispatch.py](../../../cleave/viz/input_dispatch.py) (modal precedence), [shell_host.py](../../../cleave/viz/shell_host.py) (draw order), `*_controls.py` modules that call `modal_host`.

### 3. Help: ImGui and layout

**Problem.** Help still uses the old full-screen-style overlay ([help_content.py](../../../cleave/viz/help_content.py) plus pygame draw). It consumes too much of the visualiser and does not match the shell model.

**Goal.** Rethink help as **ImGui**. Prefer a **resizable third column** beside the inspector (help panel in the region cycle when open), not a centered tree-style sheet over projectM. Context-sensitive shortcut lines should follow the active shell region (menu, navigator, inspector, timeline) without duplicating the pre-shell navigation story.

**Touchpoints.** Help menu commands in [commands.py](../../../cleave/viz/commands.py), [shell_focus.py](../../../cleave/viz/shell_focus.py) (optional Help region), [live-tuning-ui.mdc](../../../.cursor/rules/live-tuning-ui.mdc) after the model is chosen.

### 4. Launch / open-project UI

**Problem.** The prompt to open or create a project at launch still uses the legacy panel approach ([file_picker_overlay.py](../../../cleave/viz/file_picker_overlay.py) and related draw path).

**Goal.** ImGui launch flow consistent with the shell (same GL frame, mouse-aware, correct z-order). Remove legacy panel code paths used only for launch once migrated. Stay aligned with [file-picker-plan.md](file-picker-plan.md) for behaviour; this item is presentation and stack consistency, not necessarily enabling mid-session Open.

### 5. Timeline strip visual parity

**Problem.** The timeline strip ([timeline_overlay.py](../../../cleave/viz/timeline_overlay.py)) was out of scope for the menu overhaul; it still diverges from [menu-overhaul-design.html](menu-overhaul-design.html) (`shell-split` / `hit-rects` timeline lane roles).

**Goal.** Rework strip layout, typography, and colours to match the reference design. Cue editing stays on the strip; do not fold cue blocks into the inspector.

### 6. Menu and highlight colours

**Problem.** Menu bar, open menu popup, transport, focus ring, and hover wash do not fully match the mock's role mapping in [menu-overhaul-design.md](menu-overhaul-design.md).

**Goal.** Audit roles in [theme.py](../../../cleave/viz/theme.py) and ImGui colour pushes in [shell_host.py](../../../cleave/viz/shell_host.py) / [menu_bar.py](../../../cleave/viz/menu_bar.py) against `menu-layers`, `inspector-card`, and `inspector-locked`. Adjust theme constants only; avoid one-off RGB in draw paths.

### 7. Timeline strip scope traps inspector focus

**Problem.** When the timeline strip is visible, focus behaviour effectively **locks the user into timeline lane navigation** (up/down on lanes, arrow keys editing cues). Tab may cycle regions, but in practice users cannot edit inspector fields while the strip is open.

**Goal.** Match the plan's region model: with the strip open, **Inspector** must accept focus (Tab or explicit click) and allow value stepping and actions without forcing timeline-only arrow handling. Timeline keys apply only when **Timeline** is the active scope. Review [input_dispatch.py](../../../cleave/viz/input_dispatch.py), [focus_nav.py](../../../cleave/viz/focus_nav.py), and [timeline_overlay.py](../../../cleave/viz/timeline_overlay.py) for keys eaten globally while the strip is visible.

### 8. Stepped "off" values: mouse drag and side arrows

**Problem.** For enum/stepped rows where **off** is a valid value (e.g. placement snap and similar toggles), moving to **off** hides the side step arrows in the inspector. **Sideways mouse drag** then cannot step back to on; only keyboard Left/Right works. Reproduces on other rows that expose an off state, not only placement snap.

**Goal.** Keep a consistent hit target for horizontal stepping when the displayed value is off (arrows, drag band, or both), matching [apply_horizontal](../../../cleave/viz/row_spec.py) behaviour for locked vs unlocked rows. Align with phase 6 intent: drag repeats the same step as Left/Right.

**Touchpoints.** Inspector row draw in [shell_host.py](../../../cleave/viz/shell_host.py), [test_shell_mouse.py](../../../tests/cleave/viz/test_shell_mouse.py), row specs that format off states.

---

## Suggested sequencing

| Stage | Items | Notes |
| --- | --- | --- |
| A | 2, 4 | Fix z-order and input for anything modal-like; unblocks launch and render confirm. |
| B | 1 | Toasts off `tuning_panel_draw`; delete dead panel code. |
| C | 3 | Help column; update region cycle and help content structure. |
| D | 7, 8 | Focus and stepping bugs; mostly dispatcher and inspector row chrome. |
| E | 5, 6 | Visual parity; can proceed in parallel once interaction is stable. |

---

## Doc hygiene (optional)

- Move [menu-overhaul-and-mouse-support-plan.md](menu-overhaul-and-mouse-support-plan.md) to `docs/dev/plans-completed/` when this follow-up list is triaged into todos or a new plan.
- Update [roadmap.md](../roadmap.md): menu shell is shipped; link here for remaining UI stack work.

---

## Success criteria (this document)

- No live dependency on `tuning_panel_draw` for editor chrome (notifications, help, modals, file picker).
- Modals and launch UI are mouse-aware and draw above the shell.
- Help is an ImGui side panel, resizable, and does not blanket the visualiser.
- Timeline strip matches reference visuals; inspector and timeline scopes match the region cycle when the strip is open.
- Stepped off values remain draggable and keyboard-steppable like other values.
- Intentionally disabled menu commands stay disabled until their owning plans ship.
