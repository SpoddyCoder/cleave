# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

None.

---

## Backlog

In priority order. The ImGui shell refactor is done; its plans, design page, and stills are in [plans-completed/](plans-completed/) (`menu-overhaul-*`, `action-buttons-and-dialogs-plan.md`, `context-menus-plan.md`).

1. **Performance review and remediations.** Profile the editor at large and maximised window sizes and fix what grows with window area. Start from [plans/large-window-performance-plan.md](plans/large-window-performance-plan.md): the timeline strip's full-width CPU redraw every frame is measured, and the rest needs profiling on Windows. Include the PyInstaller freeze smoke test of the shell (menus, context menus, Menu key, high DPI, UI scale 200%).

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [plans-completed/improved-timeline-presets.md](plans-completed/improved-timeline-presets.md)).

The strip edits clips (move, trim, split, cut in and cut out), and record keeps authored levels: [plans/timeline-clips-plan.md](plans/timeline-clips-plan.md), finished. Still open from that plan:

- **Bulk command names.** Snap cues, Snap cues to markers, and Set cut type on cues act on clip edges now; rename them for consistent wording.
- **Recast toggle.** A control on butted clips for whether the boundary switches the preset.
- **Multi-select, ripple delete, and copy/paste of clips.**
