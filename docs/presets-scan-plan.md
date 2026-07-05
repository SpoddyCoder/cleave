# Preset scan plan

Implementation plan for `cleave scan`: offline batch classification of Milkdrop presets (load failures, black output). Background and heuristics live in [presets-check-proposal.md](presets-check-proposal.md). Investigation notes: [presets-scan-learnings.md](presets-scan-learnings.md).

## Status

| Phase | State | Notes |
| --- | --- | --- |
| v1 | Done | Project/bulk scan, quick/`--slow` profiles, JSON report, v1 classifier |
| v2 | Done | `--quarantine`, `--resume`, incremental/interrupt-safe reports |
| Live clean boot | Done | Manual preset browse forces black boot ([cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) `load_manual_preset_clean`) |
| Classifier rework | Outstanding | Clean-boot probe, full-frame metrics, manual test set, threshold retune |
| v3 | Outstanding | `--delete`, reference clip for `--slow`, report PCM metadata |

**Classifier:** v1/v2 ship a center-patch, mean-only probe with a shared `ProjectM`. Results are useful for smoke tests but not trusted for bulk quarantine. See [Classifier rework](#classifier-rework) and [presets-scan-learnings.md](presets-scan-learnings.md).

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
| (default) | Quick probe: 15 frames, 0.5 s warmup; synthetic mono PCM; report on stderr, optional JSON |
| `--slow` | 60 frames, 3 s warmup; same synthetic mono PCM today (reference clip planned for v3) |
| `--report <path>` | JSON report path; written incrementally so a run can be resumed |
| `--recursive` | Bulk mode only: scan subdirectories |
| `--quarantine <dir>` | Move failed presets to DIR; DIR must be outside the scan set |
| `--delete` | Remove failed presets after the scan (v3); prompts unless `--yes` |
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

## Per-preset probe (shipped v1/v2)

Hidden pygame GL context, one shared [ProjectM](../cleave/projectm.py) for the run, small RGBA FBO (480x270). Switch-failed callbacks from the projectM robustness work ([todos.md](todos.md)).

Per preset:

1. `load_preset(path, smooth=False)` then `lock_preset(True)` (no clean-boot flag today; feedback can carry from the previous preset).
2. Render `warmup_frames + profile.frames` at 30 fps with synthetic mono PCM.
3. After warmup, sample a 32x32 luma patch at the frame center each frame; keep max and mean from the **last** post-warmup frame only.
4. Classify from load failures plus those two values.

**Quick (default):** 15 frames, 0.5 s warmup.

**`--slow`:** 60 frames, 3 s warmup. Same PCM as quick until v3 wires [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) (10 s excerpt from `projects/sights-and-sounds-26/sights-and-sounds-26.wav` starting at 82 s).

Result categories: `load_failed`, `black`, `dim`, `ok` (see proposal).

### Classification thresholds (shipped)

Recorded in each report under `thresholds`:

| Key | Default | Use |
| --- | --- | --- |
| `black_max_luma` | 1.0 | Peak max luma below this => `black` |
| `dim_mean_luma` | 8.0 | Peak mean luma below this (but not black) => `dim` |

No `luma` block per preset in v1/v2 reports. No coverage metrics.

### Destructive actions

When `--quarantine` or `--delete` is used **without** `--slow`, print a clear stderr warning that quick mode has more false positives and recommend re-running with `--slow` before moving or deleting files. Do not block the action. Treat quarantine as safe only after classifier rework and manual spot checks.

## JSON report

Include environment metadata:

- `scan_mode`: `project` | `bulk`
- `probe_mode`: `quick` | `slow`
- `complete`: `true` on normal finish, `false` if interrupted (v2)
- `project_dir`, `config_path` (project mode)
- `preset_root`, `texture_paths` (resolved absolute)
- `layers`: slot -> list of contributing paths or dirs
- `thresholds`, `probe_frames`, `probe_fps`, `fbo_size`
- `presets`: deduplicated entries with `path`, `result`, `layers[]`, optional timings/errors

### Incremental writes and resume (v2, done)

- Flush every 10 probed presets and once at end (`REPORT_FLUSH_EVERY = 10`); only when `--report` is set.
- Atomic write via temp file + `os.replace`.
- `KeyboardInterrupt`: flush partial report, `complete: false`, print resume hint, exit non-zero.
- `--resume` requires `--report PATH`; skip paths already in the report; warn on `scan_mode` / `probe_mode` mismatch.
- Incomplete report without `--resume`: error with resume command before probing.
- Complete report with `--resume`: error before probing.

### Quarantine checks (v2, done)

- Target must be a directory (create with parents if missing).
- Reject quarantine dir inside the scanned preset tree.
- Only `load_failed`, `black`, `dim` are moved.

## Classifier rework

Target behavior for the next scan harness change (not yet implemented):

1. **Clean boot** — `set_preset_start_clean(True)` before each `load_preset`, or fresh `ProjectM` per preset. Matches live manual browse and removes order-dependent feedback contamination.
2. **Full-frame sampling** — `glReadPixels` over the probe FBO; per frame record max luma, mean luma, coverage (fraction of pixels >= `coverage_luma_min`).
3. **Peak across frames** — Classification uses peak max, peak mean, and peak coverage across all post-warmup frames (consider frame 0 as well so flash-then-fade is caught).
4. **Combined rules** — Coverage for bright-on-black; mean for uniformly dim output; bright-on-black guard for tunnel/kaleidoscope presets. Starting constants from exploration: `coverage_luma_min` 16, `black_coverage` 0.0005, `dim_coverage` 0.01, `dim_mean_luma` 10, guard `max >= 100` and `coverage >= 0.02`. Tune against a manual set.
5. **Report fields** — Optional per-preset `luma: { max, mean, coverage }` with the peak values used.

### Manual test set workflow

1. Set layer `preset_switching` to `none` (or `user_defined`) and browse presets with Left/Right (clean boot is automatic).
2. Label examples: `ok`, `dim`, broken (black / never develops). Save paths and notes. Golden set: [presets-scan-golden-set.md](presets-scan-golden-set.md) ([tests/fixtures/preset_scan_golden_set.yaml](../tests/fixtures/preset_scan_golden_set.yaml), 30 cases from `projects/sights-and-sounds-26/unnamed-*.yaml`).
3. Implement harness changes above; add a small test or script that classifies the labeled set and reports mismatches.
4. Tune thresholds; run `--slow` on a larger pack; spot-check before `--quarantine`.

## Architecture

| Piece | Location |
| --- | --- |
| Scan harness + classification | [cleave/preset_scan.py](../cleave/preset_scan.py) |
| Scan set builder | [cleave/preset_scan_targets.py](../cleave/preset_scan_targets.py) |
| CLI | [cleave/cli.py](../cleave/cli.py) `cmd_scan` |
| Live clean manual load | [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) `load_manual_preset_clean` |
| Config | [cleave/config.py](../cleave/config.py) load + `paths.texture_paths` |

Does not use [layer_pipeline.py](../cleave/viz/layer_pipeline.py) or the compositor; probe reads raw projectM FBO output.

## Phasing

**v1 (done)**

- Project scan + bulk scan (`--presets-dir` + required `--texture-path`)
- Scan set derivation as above
- Dedup + layer attribution in report
- Report-only, synthetic PCM, load failure + luminance check
- Quick probe (default) and `--slow` profile (timing only; same PCM)

**v2 (done)**

- `--quarantine`, `--resume`
- Stderr warning when `--quarantine` runs without `--slow`
- Incremental + interrupt-safe report writes

**Live (done, parallel to scan)**

- Manual preset browse clean boot for honest preset review

**Classifier rework (next)**

- Clean-boot probe, full-frame coverage metrics, peak-across-frames, retuned thresholds
- Manual labeled test set + harness validation before bulk quarantine
- Per-preset `luma` in JSON report

**v3**

- `--delete` with confirmation (`--yes` to skip prompt; required when stdin is not a TTY); same `--slow` warning as quarantine; mutually exclusive with `--quarantine`
- Bundled stereo reference clip for `--slow` probes ([assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav)); quick mode stays synthetic mono
- Report fields: `pcm_source`, `pcm_channels`, `reference_clip_path` when slow

## Runtime expectations

Project scan: typically tens to low hundreds of presets (per-layer rotation dirs). Bulk COTC: see proposal runtime table; quick default is roughly 2-3x faster than `--slow` on the same set. Progress on stderr; `--resume` for long bulk runs.

## Open questions

- Final coverage and mean thresholds per pack (blocked on manual test set).
- Quarantine: preserve directory structure vs flat hashed names.
- CI: headless GL unreliable; keep local/dev tool unless GPU runner exists.
- Whether auto `projectm` rotation should optionally force clean boot (today only manual browse does).

## Related work

- [presets-scan-learnings.md](presets-scan-learnings.md) — investigation arc and threshold tuning notes
- [presets-check-proposal.md](presets-check-proposal.md) — problem statement and classification heuristics
- [projectm-api-coverage.md](projectm-api-coverage.md) — libprojectM symbol audit and live failure handling
- [preset-switching-proposal.md](legacy-plans/preset-switching-proposal.md) — live rotation design
- [todos.md](todos.md) — projectM robustness callbacks (shared with scan)
- [.cursor/rules/preset-scan-scope.mdc](../.cursor/rules/preset-scan-scope.mdc) — update scan derivation when `preset_switching_scope` changes
