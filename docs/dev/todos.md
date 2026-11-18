# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

None.

---

## Backlog

In priority order. The ImGui shell refactor is done; its plans, design page, and stills are in [plans-completed/](plans-completed/) (`menu-overhaul-*`, `action-buttons-and-dialogs-plan.md`, `context-menus-plan.md`).

1. **Performance review and remediations.** Profile the editor at large and maximised window sizes and fix what grows with window area. The frame timer (F3), the strip's incremental compose and the per-frame fixes from [plans-completed/architecture-performance-review.md](plans-completed/architecture-performance-review.md) are done. What is left: on Windows, record F3 sections at 1920x1080 and maximised 5120x1440 on the same project, then, if `flip()` dominates, add borderless fullscreen and an explicit vsync setting, and if the ImGui build grows with window height, cache fitted row text and skip rows scrolled out of view (phases 3 and 4 of [plans-completed/large-window-performance-plan.md](plans-completed/large-window-performance-plan.md)). Target: the maximised window within about 1-2 fps of 1920x1080. Include the PyInstaller freeze smoke test of the shell (menus, context menus, Menu key, high DPI, UI scale 200%).

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [plans-completed/improved-timeline-presets.md](plans-completed/improved-timeline-presets.md)).

The strip edits clips (move, trim, split, cut in and cut out), and record keeps authored levels: [plans-completed/timeline-clips-plan.md](plans-completed/timeline-clips-plan.md), finished. Still open from that plan:

- **Bulk command names.** Snap cues, Snap cues to markers, and Set cut type on cues act on clip edges now; rename them for consistent wording.
- **Recast toggle.** A control on butted clips for whether the boundary switches the preset.
- **Multi-select, ripple delete, and copy/paste of clips.**

---

## Theme follow-ups

Settings > UI > Theme picks the live `Palette` in [cleave/viz/theme.py](../../cleave/viz/theme.py). The built-ins are Ultraviolet (the default), Chocolate, Mint, and Daylight (light); user theme files in the data folder's `themes/` add more ([cleave/viz/user_themes.py](../../cleave/viz/user_themes.py)). Draw code reads `palette()` at draw time, and `palette_generation()` rebuilds caches that hold drawn pixels.

- **Colour-blind-safe built-in theme.** Hover (violet) and selection (blue) are hard to tell apart with red-green colour blindness, and the navigator on (green), solo (red), and lock (amber) icons have the same problem. Separate them by lightness too, not only hue.
- **Pointer colours.** `pointer_cursor.py` still draws the mouse pointer in fixed black and white.
