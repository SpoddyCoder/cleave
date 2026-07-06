# Preset scan proposal

Offline CLI to scan Milkdrop preset directories, classify each `.milk` file, and optionally quarantine or remove failures. Replaces the idea of skipping black presets at runtime during projectM auto-switching, which is hard to tune and risks false positives in live sessions.

**Status:** Implemented. CLI and scan-set design: [presets-scan-plan.md](presets-scan-plan.md). Golden labels: [presets-scan-golden-set.md](presets-scan-golden-set.md).

## Problem

Large preset packs (especially [presets-cream-of-the-crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop)) contain many presets that load in libprojectM but render black or fail silently. In projectM auto-switch mode, a bad preset can sit on screen for the full `preset_duration` (often 20-40 s per layer).

Runtime auto-skip (detect black after switch and advance immediately) shares the same heuristics but adds live false positives: warmup presets, legitimately dark output, soft-cut blends, and stem-specific behavior.

An offline batch pass lets the user review results before deleting anything.

## Command

See [presets-scan-plan.md](presets-scan-plan.md) for CLI (`cleave scan <project_dir>` and bulk `--presets-dir` mode), scan set derivation, phasing, and current status.

**Safety:** default is non-destructive. `--delete` requires an explicit flag (v3); `--quarantine` is the preferred cleanup action (v2, shipped).

## Per-preset behavior

### Shipped probe

Minimal harness (no Cleave compositor stack):

1. Open a hidden pygame OpenGL context once.
2. Create a [ProjectM](../cleave/projectm.py) instance (fresh per preset in golden harness) and a 480x270 RGBA FBO.
3. Set texture search paths from config or flags.
4. For each `.milk`: clean boot, load, feed synthetic mono PCM, render 15 warmup + 75 window frames, sample full-frame luma each frame.
5. Classify from load failures plus peak max, mean, and coverage across post-warmup frames.

See [presets-scan-plan.md](presets-scan-plan.md) and [presets-scan-learnings.md](presets-scan-learnings.md).

### Live visualizer (shipped)

Manual preset browse (`preset_switching` `none` or `user_defined`) forces a clean black boot so presets can be judged without feedback carry-over from the previous preset. Auto `projectm` rotation unchanged.

| Result | Meaning |
| --- | --- |
| `load_failed` | Parse or load error from libprojectM |
| `black` | Does not develop after warmup |
| `dim` | Too dim to use |
| `washed_out` | Extreme white blowout |
| `ok` | Passes thresholds |

Golden case 2 has a known visualizer vs scan label disparity; quarantine outcome is still correct. See [presets-scan-golden-set.md](presets-scan-golden-set.md).

## Runtime

Rough order of magnitude at 480x270, default probe:

| Scope | Presets | Time |
| --- | --- | --- |
| Single COTC subfolder | ~50-200 | ~1-3 min |
| One COTC category | ~500-800 | ~5-15 min |
| Full COTC | ~9,795 | ~1-3 hours |

Single GL context; no practical parallelism. Progress on stderr and `--resume` keep long runs tolerable.

## Architecture sketch

[cleave/preset_scan.py](../cleave/preset_scan.py) plus CLI in [cleave/cli.py](../cleave/cli.py). Reuses:

- [cleave/projectm.py](../cleave/projectm.py) for load, PCM, render
- [cleave/preset_playlist.py](../cleave/preset_playlist.py) `milk_files_in_dir` / directory walk
- [cleave/config.py](../cleave/config.py) for `paths.texture_paths` when a viz config is passed

Does not use [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) or multi-layer compositing; black-key blend is irrelevant because the probe reads the raw projectM FBO.

Shared infrastructure with the projectM robustness work (switch-failed callbacks, optional logging callback) benefits both live play and this tool.

## Phasing

Aligned with [presets-scan-plan.md](presets-scan-plan.md):

**v1 (done)** — report-only scan, load failure + luminance check, synthetic PCM, JSON report.

**v2 (done)** — `--quarantine`, `--resume`, incremental reports, config-driven texture paths in project mode.

**Classifier rework (done)** — clean-boot probe, full-frame metrics, golden harness, retuned thresholds.

**v3 (done)** — `--delete` with confirmation.

## Related work

- [preset-switching-proposal.md](legacy-plans/preset-switching-proposal.md) documents live projectM rotation; playlist retry and switch-failed callbacks were planned there but not fully wired in Cleave.
- [presets-scan-learnings.md](presets-scan-learnings.md) — feedback leak, explored fixes, live clean boot.
- [roadmap.md](roadmap.md) projectM PCM feeding note.

## Open questions

- Default thresholds for black vs dim (blocked on manual test set and classifier rework).
- Whether quarantine preserves relative directory structure or flattens with hashed names.
- CI: headless GL in GitHub Actions is unreliable; keep this a local/dev tool unless a GPU runner exists.
