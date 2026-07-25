# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

- **`project.yaml` unknown-key wipe.** `write_manifest`, `save_song_markers`, and `rewrite_manifest_slug` in [cleave/project.py](../cleave/project.py) still rewrite via `ProjectManifest.to_dict()`, so any key not on the dataclass is dropped. Prefer dict-merge updates that only touch the fields each helper owns.
- **Incomplete render snapshot merge.** [`_snapshot_render_overlay`](../cleave/config_snapshot.py) hand-copies a field subset instead of applying the full `persist_render` payload. Session edits to at least `render.overlay.locked`, `render.post_fx.locked`, `highlight_rolloff.ceiling_pct`, and `highlight_rolloff.desaturation_pct` can fail to save (stale file values win). Apply the full render payload, or every descriptor field, while still preserving unknown keys.

---

## Timeline follow-ups

Rich cue levels are shipped (see [improved-timeline-presets.md](improved-timeline-presets.md) Idea 1). Remaining mix-cue work:

- **Per-cue blend mode.** Carry an optional blend on `SlotCue` and write `LayerFbo.blend_mode` from the active cue so the arranger can switch compositing per transition ([cleave/blend_modes.py](../cleave/blend_modes.py)).
- **Per-cue preset role.** Optional role on the cue for content-aware casting once reactivity fingerprints exist (Idea 3).
- **Manual level authoring.** Strip and record path still toggle `0.0` / `1.0`; add a way to set partial levels by hand without Apply.

---

## Architecture


### projectM

