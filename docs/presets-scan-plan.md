# Preset scan plan

Implementation plan for `cleave scan`: offline batch classification of Milkdrop presets (load failures, black output). Background and heuristics live in [presets-check-proposal.md](presets-check-proposal.md).

**Status:** Planned. Not implemented.

## Goals

- Match Cleave CLI semantics (`render`-style project + optional `-c`).
- Derive the scan set from the same yaml play uses, including `paths.texture_paths`.
- Keep a separate bulk mode for pack-wide audits.
- Default to report-only; quarantine/delete stay opt-in (see proposal).

## Command

### Project scan (primary)

```bash
cleave scan <project_dir> [-c cleave-viz.yaml] [options]
```

- Resolves the project via [cleave/paths.py](../cleave/paths.py) `resolve_project` (same as `render`).
- Loads config via [cleave/config.py](../cleave/config.py) `find_config_path` (CLI `-c`, else `<project>/cleave-viz.yaml`, then global/template fallbacks).
- Does **not** run `separate` or require stems/signals.

Examples:

```bash
./cleave.py scan projects/sights-and-sounds-26/
./cleave.py scan projects/sights-and-sounds-26/ -c cleave-viz.yaml
./cleave.py scan projects/sights-and-sounds-26/ --slow
```

### Bulk scan (escape hatch)

```bash
cleave scan --presets-dir <dir> --texture-path <dir> [--texture-path ...] [options]
```

- `--presets-dir` and `--texture-path` are mutually exclusive with the project positional (document in help).
- **`--texture-path` is required** when using `--presets-dir` alone. Exit with a clear error if omitted: bulk scans without texture search paths produce false black/dim results.
- Optional `-c` may supply `paths.texture_paths` instead of explicit `--texture-path` flags when both are given (union or config wins: pick one rule at implementation time and test it).
- `--recursive` applies only in bulk mode (walk subdirectories). Project scan never recurses beyond what live rotation implies (see below).

### Shared flags

| Flag | Purpose |
| --- | --- |
| (default) | Quick probe: short frames + short warmup; report only on stderr, optional JSON report. Faster; may flag slow-starting or legitimately dark presets (more false positives). |
| `--slow` | Longer frames + longer warmup before luminance sample. Slower; fewer false positives. Use before acting on results (quarantine/delete) or for a final bulk audit. |
| `--report <path>` | JSON report path |
| `--recursive` | Bulk mode only: scan subdirectories |
| `--quarantine <dir>` | Move failed presets (v2) |
| `--delete` | Remove failed presets (v3) |
| `--resume <report>` | Skip presets already in a prior report (v2) |

Probe timing is a single profile (no separate `--frames` / `--warmup-sec` flags). Internal values TBD at implementation (e.g. quick ~15 frames / ~0.5 s warmup; slow ~60 frames / ~3 s warmup). Record `probe_mode`: `quick` | `slow` in the JSON report.

## Scan set derivation (project mode)

Build the preset list from parsed [CleaveConfig](../cleave/config.py) **on disk** (not live session). For each layer in `layer_z_order` (including **disabled** layers):

1. **Anchor directory** — resolve `layers.<slot>.preset` under `paths.preset_root` via [scan_preset_playlist](../cleave/preset_playlist.py); take `playlist.current_dir`. Collect all `*.milk` files **directly in that directory** (non-recursive), same as projectM rotation in [apply_preset_switching](../cleave/viz/preset_switching.py) (`add_path(..., recurse=False)`).
2. **Include anchor directory even when `preset_switching` is `none`** — user may enable projectM later; scanning only the locked file would miss siblings they will rotate into.
3. **projectM rotation** — when `preset_switching` is `projectm`, step 1 already matches live rotation (`scope == "directory"` today).
4. **User-defined rotation** — when `preset_switching` is `user_defined`, add every path in `layers.<slot>.preset_switching_presets` (resolved relative to project dir per [config_schema](../cleave/config_schema.py)).
5. **Deduplicate** by resolved absolute `.milk` path. Keep metadata: which layer slot(s) referenced each file.

Do **not** scan `browse_floor`, full `preset_root`, or subfolders under the anchor directory unless bulk mode with `--recursive`.

### Texture paths

Project mode: always apply `paths.texture_paths` from the loaded config.

Bulk mode: require at least one texture path (`--texture-path` and/or from `-c`). Record paths used in the report.

## Per-preset probe

Same harness as [presets-check-proposal.md](presets-check-proposal.md#per-preset-behavior): hidden pygame GL context, one [ProjectM](../cleave/projectm.py), small FBO, synthetic PCM, luminance sample after warmup. Switch-failed callbacks from the projectM robustness work ([todos.md](todos.md)).

**Quick (default):** short render + short warmup. Intended for iteration and smoke tests.

**`--slow`:** longer render + longer warmup. Better for presets that need time to develop and for fade-to-black cases; fewer false positives.

Result categories: `load_failed`, `black`, `dim`, `ok` (see proposal).

### Destructive actions

When `--quarantine` or `--delete` is used **without** `--slow`, print a clear stderr warning that quick mode has more false positives and recommend re-running with `--slow` before moving or deleting files. Do not block the action.

## JSON report (v1)

Include environment metadata:

- `scan_mode`: `project` | `bulk`
- `probe_mode`: `quick` | `slow`
- `project_dir`, `config_path` (project mode)
- `preset_root`, `texture_paths` (resolved absolute)
- `layers`: slot -> list of contributing paths or dirs
- `presets`: deduplicated entries with `path`, `result`, `layers[]`, optional timings/errors

## Architecture

| Piece | Location |
| --- | --- |
| Scan harness + classification | [cleave/preset_scan.py](../cleave/preset_scan.py) (new) |
| Scan set builder | `preset_scan.py` or `cleave/preset_scan_targets.py` (new); reuse [preset_playlist.py](../cleave/preset_playlist.py) `scan_preset_playlist`, `milk_files_in_dir` |
| CLI | [cleave/cli.py](../cleave/cli.py) `cmd_scan` |
| Config | [cleave/config.py](../cleave/config.py) load + `paths.texture_paths` |

Does not use [layer_pipeline.py](../cleave/viz/layer_pipeline.py) or the compositor; probe reads raw projectM FBO output.

## Phasing

**v1**

- Project scan + bulk scan (`--presets-dir` + required `--texture-path`)
- Scan set derivation as above
- Dedup + layer attribution in report
- Report-only, synthetic PCM, load failure + luminance check
- Quick probe (default) and `--slow` profile

**v2**

- `--quarantine`, `--resume`
- Stderr warning when `--quarantine` runs without `--slow`

**v3 (optional)**

- `--delete` with confirmation; same `--slow` warning as quarantine
- Import report into rotation blocklist
- Optional project PCM clip instead of synthetic tone

## Runtime expectations

Project scan: typically tens to low hundreds of presets (per-layer rotation dirs). Bulk COTC: see proposal runtime table; quick default is roughly 2-3x faster than `--slow` on the same set. Progress on stderr; `--resume` for long bulk runs.

## Open questions

- Default black vs dim thresholds (tune per pack).
- Quarantine: preserve directory structure vs flat hashed names.
- CI: headless GL unreliable; keep local/dev tool unless GPU runner exists.

## Related work

- [presets-check-proposal.md](presets-check-proposal.md) — problem statement and classification heuristics
- [projectm-api-coverage.md](projectm-api-coverage.md) — libprojectM symbol audit and live failure handling
- [preset-switching-proposal.md](legacy-plans/preset-switching-proposal.md) — live rotation design
- [todos.md](todos.md) — projectM robustness callbacks (shared with scan)
- [.cursor/rules/preset-scan-scope.mdc](../.cursor/rules/preset-scan-scope.mdc) — update scan derivation when `preset_switching_scope` changes
