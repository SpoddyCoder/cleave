# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

None.

---

## Backlog

In priority order. The ImGui shell refactor is done; its plans, design page, and stills are in [plans-completed/](plans-completed/) (`menu-overhaul-*`, `action-buttons-and-dialogs-plan.md`, `context-menus-plan.md`).

1. **Unsaved changes indicator.** Nothing in the editor shows that the project has unsaved changes. The menu bar's `Project: <slug>` label (`menu_bar_project_label` in `cleave/viz/shell_host.py`) and the window caption should mark a dirty session, for example with a trailing `*`. The mark should clear on save and on a project switch. Dirty state is already computed in the session.
2. **Cue management overhaul.** The timeline strip can select, seek, scrub, zoom, and arm, but cues only come from recording, Generate, or nudging in the inspector. Add direct cue editing on the strip:
   - Drag a cue to move it in time, respecting snap and the bar grid.
   - Add a cue by double-click or from the row's right-click menu.
   - Delete a cue: a key, plus a cue context-menu item. There is no cue-delete action in `cleave/viz/timeline_cue_edits.py` yet.
   - Decide how single cue edits record in `TimelineHistory`. Today any hand edit turns undo off.
   - Fold in "Record still writes 0/1" below.
3. **Performance review and remediations.** Profile the editor at large and maximised window sizes and fix what grows with window area. Start from [plans/large-window-performance-plan.md](plans/large-window-performance-plan.md): the timeline strip's full-width CPU redraw every frame is measured, and the rest needs profiling on Windows. Include the PyInstaller freeze smoke test of the shell (menus, context menus, Menu key, high DPI, UI scale 200%).

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [plans-completed/improved-timeline-presets.md](plans-completed/improved-timeline-presets.md)).

- **Record still writes 0/1.** Armed record toggles punch full on/off only; partial opacities stay Apply or `Shift`/`Ctrl` + `,`/`.` on a selected cue.
