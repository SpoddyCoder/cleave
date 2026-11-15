# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

None.

---

## Backlog

In priority order. The ImGui shell refactor is done; its plans, design page, and stills are in [plans-completed/](plans-completed/) (`menu-overhaul-*`, `action-buttons-and-dialogs-plan.md`, `context-menus-plan.md`).

1. **Timeline clips.** Edit the strip in clips, the way video editors show a track's visible spans, in place of separate on and off cues. Plan: [plans/timeline-clips-plan.md](plans/timeline-clips-plan.md), stages A to D.
   - Done: Stage A (the clip model in `cleave/timeline.py`) and Stage B (clip selection, `ClipEditor`, the inspector clip page, menus, and keys; edits record in `TimelineHistory`).
   - Done: Stage C, dragging clips on the strip (move, trim, roll), the clip outline, and edge handles.
   - Next: Stage D, record keeps authored levels.
   - Stage D folds in "Record still writes 0/1" below.
2. **Performance review and remediations.** Profile the editor at large and maximised window sizes and fix what grows with window area. Start from [plans/large-window-performance-plan.md](plans/large-window-performance-plan.md): the timeline strip's full-width CPU redraw every frame is measured, and the rest needs profiling on Windows. Include the PyInstaller freeze smoke test of the shell (menus, context menus, Menu key, high DPI, UI scale 200%).

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [plans-completed/improved-timeline-presets.md](plans-completed/improved-timeline-presets.md)).

- **Record still writes 0/1.** Armed record toggles punch full on/off only; partial opacities stay Apply or `,`/`.` on a selected cue. Planned as Stage D of [plans/timeline-clips-plan.md](plans/timeline-clips-plan.md).
