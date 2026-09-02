# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

- **Windows overlay font and tofu glyphs.** Live tuning text uses `SysFont("monospace")` in [cleave/viz/overlay_primitives.py](../cleave/viz/overlay_primitives.py), so Windows Courier New looks unlike Linux DejaVu and often lacks `▶` / `▼` / `└`. Material Icons are already bundled (`assets/fonts/MaterialIcons-Regular.ttf` via `resource_dir()`). Ship a Latin plus box-drawing monospace TTF the same way and point `overlay_font` at it so the freeze matches checkout.

- **`project.yaml` unknown-key wipe.** `write_manifest`, `save_song_markers`, and `rewrite_manifest_slug` in [cleave/project.py](../cleave/project.py) still rewrite via `ProjectManifest.to_dict()`, so any key not on the dataclass is dropped. Prefer dict-merge updates that only touch the fields each helper owns.

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [completed/improved-timeline-presets.md](completed/improved-timeline-presets.md)).

- **Record still writes 0/1.** Armed record toggles punch full on/off only; partial opacities stay Apply or `Shift`/`Ctrl` + `,`/`.` on a selected cue.
