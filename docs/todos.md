# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

- **`project.yaml` unknown-key wipe.** `write_manifest`, `save_song_markers`, and `rewrite_manifest_slug` in [cleave/project.py](../cleave/project.py) still rewrite via `ProjectManifest.to_dict()`, so any key not on the dataclass is dropped. Prefer dict-merge updates that only touch the fields each helper owns.

---

## Timeline follow-ups

Rich cue levels, per-cue blend/role, stem conductor, visual limiter, and manual timeline-opacity nudges are shipped (see [completed/improved-timeline-presets.md](completed/improved-timeline-presets.md)).

- **Record still writes 0/1.** Armed record toggles punch full on/off only; partial opacities stay Apply or `Shift`/`Ctrl` + `,`/`.` on a selected cue.

---

## Architecture

- **Preview quality drives pattern-mask resolution.** Hard-mode masks look soft or blocky when generated below content size, but full-res generation still costs when params change (especially plasma / soft). Tie Settings -> preview quality to the mask gen size (full for `full-quality`, scaled down for `balanced` / `performance` / `ultra-performance`) so live editing can trade sharpness for speed without a separate control. Offline render stays full-res.
- **Cache pattern-mask transition weights.** Explore pre-generating / caching weight fields on mask param changes so layer visibility toggles reuse ready old/target weights when type/density/seed are unchanged. Trade-off: memory and combinatorial cost if many layers toggle independently.

### projectM

