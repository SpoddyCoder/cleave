# Preset scan plan

Implementation plan for `cleave scan`: offline batch classification of Milkdrop presets (load failures, black output). Background and heuristics live in [presets-check-proposal.md](presets-check-proposal.md). Investigation notes: [presets-scan-learnings.md](presets-scan-learnings.md).

## Status

| Phase | State | Notes |
| --- | --- | --- |
| v1 | Done | Project/bulk scan, quick/`--slow` profiles, JSON report, v1 classifier |
| v2 | Done | `--quarantine`, `--resume`, incremental/interrupt-safe reports |
| Live clean boot | Done | Manual preset browse forces black boot ([cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) `load_manual_preset_clean`) |
| Classifier rework | Done | Clean-boot probe, full-frame metrics, peak-across-frames rules, golden-set tuning |
| v3 | Done | `--delete`, reference clip for `--slow`, report PCM metadata |

**Classifier:** Shipped probe uses clean boot per preset, full-frame luma sampling, peak max/mean/coverage across post-warmup frames, and retuned thresholds validated against the 30-case golden set ([presets-scan-golden-set.md](presets-scan-golden-set.md)). See [presets-scan-learnings.md](presets-scan-learnings.md) for tuning notes.

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
| (default) | Quick probe: 15 frames warmup + 75 window; synthetic mono PCM; report on stderr, optional JSON |
| `--slow` | 90 frames warmup + 60 window; stereo reference clip ([assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav)) |
| `--report <path>` | JSON report path; written incrementally so a run can be resumed |
| `--recursive` | Bulk mode only: scan subdirectories |
| `--quarantine <dir>` | Move failed presets to DIR; DIR must be outside the scan set |
| `--delete` | Remove failed presets after the scan; prompts unless `--yes` |
| `--yes` | Skip confirmation for `--delete` (required when stdin is not a TTY) |
| `--resume` | Skip presets already in the `--report` file; requires `--report PATH` |

Record `probe_mode`: `quick` | `slow` in the JSON report.

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

## Per-preset probe (shipped)

Hidden pygame GL context, one fresh [ProjectM](../cleave/projectm.py) per preset (both `cleave scan` and `cleave scan-golden --probe`), 480x270 RGBA FBO. Switch-failed callbacks from the projectM robustness work ([todos.md](todos.md)).

Per preset:

1. `set_preset_start_clean(True)` then `load_preset(path, smooth=False)` then restore clean-boot flag.
2. Render `warmup_frames + window_frames` at 30 fps with probe PCM (synthetic mono for quick; stereo reference clip for slow).
3. After warmup, full-frame `glReadPixels` each frame; per frame record max luma, mean luma, and coverage at luma cutoffs (8, 16, 32, 64, 128, 192).
4. Classify from load failures plus peak max, peak mean, and peak coverage across all post-warmup frames.

**Quick (default):** 15 warmup + 75 window frames; synthetic mono PCM.

**`--slow`:** 90 warmup + 60 window frames; stereo reference clip at [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) (10 s excerpt from `projects/sights-and-sounds-26/sights-and-sounds-26.wav` starting at 82 s).

Result categories: `load_failed`, `black`, `dim`, `washed_out`, `ok` (see proposal).

### Classification thresholds (shipped)

Recorded in each report under `thresholds`. Constants live in [cleave/preset_scan.py](../cleave/preset_scan.py) (`SCAN_THRESHOLDS`). Tuned against the golden set; see [presets-scan-golden-set.md](presets-scan-golden-set.md).

Per-preset `luma: { max, mean, coverage }` in JSON reports holds the peak values used for classification.

### Destructive actions

When `--quarantine` or `--delete` is used **without** `--slow`, print a clear stderr warning that quick mode has more false positives and recommend re-running with `--slow` before moving or deleting files. Do not block the action. Prefer `--slow` before bulk quarantine or delete.

## JSON report

Include environment metadata:

- `scan_mode`: `project` | `bulk`
- `probe_mode`: `quick` | `slow`
- `pcm_source`: `synthetic` | `reference-clip`
- `pcm_channels`: 1 (quick) or 2 (slow)
- `reference_clip_path`: absolute path to the reference wav when `probe_mode` is `slow`
- `complete`: `true` on normal finish, `false` if interrupted (v2)
- `project_dir`, `config_path` (project mode)
- `preset_root`, `texture_paths` (resolved absolute)
- `layers`: slot -> list of contributing paths or dirs
- `thresholds`, `probe_frames`, `probe_fps`, `fbo_size`
- `presets`: deduplicated entries with `path`, `result`, `layers[]`, optional `luma`, timings/errors

### Incremental writes and resume (v2, done)

- Flush every 10 probed presets and once at end (`REPORT_FLUSH_EVERY = 10`); only when `--report` is set.
- Atomic write via temp file + `os.replace`.
- `KeyboardInterrupt`: flush partial report, `complete: false`, print resume hint, exit non-zero.
- `--resume` requires `--report PATH`; skip paths already in the report; warn on `scan_mode` / `probe_mode` mismatch.
- Incomplete report without `--resume`: error with resume command before probing.
- Complete report with `--resume`: error before probing.

### Quarantine and delete checks (v2/v3, done)

- Target must be a directory (create with parents if missing) for quarantine.
- Reject quarantine dir inside the scanned preset tree.
- Only `load_failed`, `black`, `dim`, `washed_out` are moved or deleted.
- `--delete` prompts for confirmation unless `--yes`; requires `--yes` when stdin is not a TTY.
- `--delete` and `--quarantine` are mutually exclusive.

## Architecture

| Piece | Location |
| --- | --- |
| Scan harness + classification | [cleave/preset_scan.py](../cleave/preset_scan.py) |
| Scan set builder | [cleave/preset_scan_targets.py](../cleave/preset_scan_targets.py) |
| Golden harness | [cleave/preset_scan_golden.py](../cleave/preset_scan_golden.py) |
| CLI | [cleave/cli.py](../cleave/cli.py) `cmd_scan`, `cmd_scan_golden` |
| Live clean manual load | [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) `load_manual_preset_clean` |
| Config | [cleave/config.py](../cleave/config.py) load + `paths.texture_paths` |

Does not use [layer_pipeline.py](../cleave/viz/layer_pipeline.py) or the compositor; probe reads raw projectM FBO output.

## Phasing

**v1 (done)**

- Project scan + bulk scan (`--presets-dir` + required `--texture-path`)
- Scan set derivation as above
- Dedup + layer attribution in report
- Report-only, synthetic PCM, load failure + luminance check
- Quick probe (default) and `--slow` profile

**v2 (done)**

- `--quarantine`, `--resume`
- Stderr warning when `--quarantine` runs without `--slow`
- Incremental + interrupt-safe report writes

**Live (done, parallel to scan)**

- Manual preset browse clean boot for honest preset review

**Classifier rework (done)**

- Clean-boot probe, full-frame coverage metrics, peak-across-frames, retuned thresholds
- Manual labeled test set + golden harness validation
- Per-preset `luma` in JSON report

**v3 (done)**

- `--delete` with confirmation (`--yes` to skip prompt; required when stdin is not a TTY); same `--slow` warning as quarantine; mutually exclusive with `--quarantine`
- Bundled stereo reference clip for `--slow` probes ([assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav)); quick mode stays synthetic mono
- Report fields: `pcm_source`, `pcm_channels`, `reference_clip_path` when slow

## Runtime expectations

Project scan: typically tens to low hundreds of presets (per-layer rotation dirs). Bulk COTC: see proposal runtime table; quick default is roughly 2-3x faster than `--slow` on the same set. Progress on stderr; `--resume` for long bulk runs.

## Open questions

- Golden case 2 visualizer vs scan disparity (see [todos.md](todos.md)).
- Final coverage and mean thresholds per pack beyond the golden set.
- Quarantine: preserve directory structure vs flat hashed names.
- CI: headless GL unreliable; keep local/dev tool unless GPU runner exists.
- Whether auto `projectm` rotation should optionally force clean boot (today only manual browse does).

## Related work

- [presets-scan-learnings.md](presets-scan-learnings.md) — investigation arc and threshold tuning notes
- [presets-check-proposal.md](presets-check-proposal.md) — problem statement and classification heuristics
- [presets-scan-golden-set.md](presets-scan-golden-set.md) — manual labels and golden harness
- [projectm-api-coverage.md](projectm-api-coverage.md) — libprojectM symbol audit and live failure handling
- [preset-switching-proposal.md](legacy-plans/preset-switching-proposal.md) — live rotation design
- [todos.md](todos.md) — projectM robustness callbacks (shared with scan)
- [.cursor/rules/preset-scan-scope.mdc](../.cursor/rules/preset-scan-scope.mdc) — update scan derivation when `preset_switching_scope` changes
