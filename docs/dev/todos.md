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
- **Multi-select, ripple delete, and copy/paste of clips.**

Generate timeline was rebuilt around song sections and intensity: [plans-completed/section-intensity-and-recall.md](plans-completed/section-intensity-and-recall.md). Still open:

- **Recall repeated sections.** A Generate option, off by default, so a section type that comes back looks like its first time.
  - **Dialog:** field `repeated sections`, after density, with **new each time** (default), **same look**, and **same look, building**. Both modes, session only, hidden when no section type comes back. When no layer will change presets on each clip, the option help says only the layers come back.
  - **What comes back:** which layers play, their timing, roles and blends, and presets on each-clip layers. Intensity is not matched: a recalled part uses its own marker's intensity and `LEVELS` row, so an intensity change still shows. **Building** adds one layer per recall within the intensity bounds, unless that marker's intensity is not normal.
  - **Matching:** a run is one or more back-to-back markers of one type (a `Part` run from `section_parts`). The first run of a type is the source, and later runs recall it part by part, by position in the run. A part with no source part is planned fresh and becomes a source. Plain markers never recall. Timing maps by bar offset from the part start: a shorter target truncates, a longer one loops the source, and with no bars it maps by seconds.
  - **Where:** a small `cleave/timeline_presets/recall.py` holds the `(source Part, target Part)` pairs and the bar-offset time map, used by both modes. In `plan_timeline`, a recalled part copies its source's `Target`s (phrase offsets by bars, active layers, lead, rank order, roles when the conductor is on); levels come from its own intensity; then `weave` runs as usual so spacing and crossfade rules hold. `weave._place_preset_changes` mirrors the source's recasts at markers and mapped bar offsets. Pattern mask copies section-level counts and swaps the same way.
  - **Presets:** after `PresetListController.repopulate` and `deal_list_onto_clips`, give the k-th switching clip of each recalled part the k-th preset of its source, by order rather than time (snap moves edges), then rebuild `preset_list` as clip order plus spares so `sync_each_clip_layers` leaves it alone. This stays inside the Generate edit, so undo and rollback cover it; `on_repopulate` needs the pairs. With preset list on use current list, this reorders the list but never changes which presets are in it.
  - **Verify:** equal, shorter, and longer parts; runs of different lengths; off-grid markers; no bars; a source past the last bar. Building stops at the bounds and an explicit intensity beats it. Recalled clips get the source's presets, undo restores, locked layers refuse, and other layers are untouched. Rerun the brightness and pacing rules in `tests/cleave/test_timeline_plan.py` with recall on, and every dialog combination on a real project through the controller with the snap passes. Update the changelog, the guide (Generate and Song Markers), and help.

---

## Theme follow-ups

Settings > UI > Theme picks the live `Palette` in [cleave/viz/theme.py](../../cleave/viz/theme.py). The built-ins are Ultraviolet (the default), Chocolate, Mint, and Daylight (light); user theme files in the data folder's `themes/` add more ([cleave/viz/user_themes.py](../../cleave/viz/user_themes.py)). Draw code reads `palette()` at draw time, and `palette_generation()` rebuilds caches that hold drawn pixels.

- **Colour-blind-safe built-in theme.** Hover (violet) and selection (blue) are hard to tell apart with red-green colour blindness, and the navigator on (green), solo (red), and lock (amber) icons have the same problem. Separate them by lightness too, not only hue.
- **Pointer colours.** `pointer_cursor.py` still draws the mouse pointer in fixed black and white.
