# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

- **`project.yaml` unknown-key wipe.** `write_manifest`, `save_song_markers`, and `rewrite_manifest_slug` in [cleave/project.py](../cleave/project.py) still rewrite via `ProjectManifest.to_dict()`, so any key not on the dataclass is dropped. Prefer dict-merge updates that only touch the fields each helper owns.
- **Incomplete render snapshot merge.** [`_snapshot_render_overlays`](../cleave/config_snapshot.py) hand-copies a field subset instead of applying the full `persist_render` payload. Session edits to at least `render.overlays.locked`, `render.post_fx.locked`, `highlight_rolloff.ceiling_pct`, and `highlight_rolloff.desaturation_pct` can fail to save (stale file values win). Apply the full render payload, or every descriptor field, while still preserving unknown keys.

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, and manual timeline-opacity nudges are shipped (see [improved-timeline-presets.md](improved-timeline-presets.md) Idea 1). Remaining mix-cue work:

- **Record still writes 0/1.** Armed record toggles punch full on/off only; partial opacities stay Apply or `Shift`/`Ctrl` + `,`/`.` on a selected cue.
- **Automatic blend/role assignment** from the generative arranger once reactivity fingerprints exist (Idea 3).

---

## Architecture

- **Preview quality drives pattern-mask resolution.** Hard-mode masks look soft or blocky when generated below content size, but full-res generation still costs when params change (especially plasma / soft). Tie Settings -> preview quality to the mask gen size (full for `full-quality`, scaled down for `balanced` / `performance` / `ultra-performance`) so live editing can trade sharpness for speed without a separate control. Offline render stays full-res.

### projectM

