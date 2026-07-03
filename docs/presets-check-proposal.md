# Preset scan proposal

Offline CLI to scan Milkdrop preset directories, classify each `.milk` file, and optionally quarantine or remove failures. Replaces the idea of skipping black presets at runtime during projectM auto-switching, which is hard to tune and risks false positives in live sessions.

**Status:** Superseded for CLI and scan-set design by [presets-scan-plan.md](presets-scan-plan.md). This doc keeps problem statement, probe heuristics, and runtime estimates.

## Problem

Large preset packs (especially [presets-cream-of-the-crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop)) contain many presets that load in libprojectM but render black or fail silently. In projectM auto-switch mode, a bad preset can sit on screen for the full `preset_duration` (often 20–40 s per layer).

Runtime auto-skip (detect black after switch and advance immediately) shares the same heuristics but adds live false positives: warmup presets, legitimately dark output, soft-cut blends, and stem-specific behavior.

An offline batch pass lets the user review results before deleting anything.

## Command

See [presets-scan-plan.md](presets-scan-plan.md) for CLI (`cleave scan <project_dir>` and bulk `--presets-dir` mode), scan set derivation, and phasing.

**Safety:** default is non-destructive. `--delete` requires an explicit flag; `--quarantine` is the preferred cleanup action.

## Per-preset behavior

Minimal harness (no Cleave project, stems, or compositor stack):

1. Open a hidden pygame OpenGL context once.
2. Create one [ProjectM](../cleave/projectm.py) instance and a small RGBA FBO (e.g. 480×270).
3. Set texture search paths from config or flags.
4. For each `.milk`:
  - Load preset; record libprojectM load/parse failures via switch-failed callbacks (see [todos.md](todos.md) projectM robustness item).
  - Feed synthetic PCM (test tone or brief noise burst, not silence, so reactive presets get energy).
  - Advance frame time and render for the active probe profile (quick by default; longer with `--slow`; see [presets-scan-plan.md](presets-scan-plan.md)).
  - After warmup, sample FBO luminance (small `glReadPixels` patch, not full resolution).
5. Classify and record result.



### Result categories


| Result        | Meaning                                                                | Confidence                       |
| ------------- | ---------------------------------------------------------------------- | -------------------------------- |
| `load_failed` | Parse or load error from libprojectM                                   | High                             |
| `black`       | Max/mean luminance below threshold after warmup                        | High for shader/texture failures |
| `dim`         | Low but non-zero output (optional warning, not quarantined by default) | Medium                           |
| `ok`          | Passes thresholds                                                      | —                                |


**Not reliably detected in quick mode:** presets that flash then fade to black over several seconds, presets that only work on a specific stem, legitimately dark presets that are intentional. Use `--slow` for better coverage on fade-to-black cases.

## Runtime

Rough order of magnitude at 480×270, quick probe (default):


| Scope                 | Presets  | Time       |
| --------------------- | -------- | ---------- |
| Single COTC subfolder | ~50–200  | ~1–3 min   |
| One COTC category     | ~500–800 | ~5–15 min  |
| Full COTC             | ~9,795   | ~1–3 hours |


Single GL context; no practical parallelism. Progress on stderr and `--resume` keep long runs tolerable.

## Architecture sketch

New module (e.g. [cleave/preset_scan.py](../cleave/preset_scan.py)) plus CLI wiring in [cleave/cli.py](../cleave/cli.py). Reuses:

- [cleave/projectm.py](../cleave/projectm.py) for load, PCM, render
- [cleave/preset_playlist.py](../cleave/preset_playlist.py) `milk_files_in_dir` / directory walk
- [cleave/config.py](../cleave/config.py) for `paths.texture_paths` when a viz config is passed via `--config`

Does not use [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) or multi-layer compositing; black-key blend is irrelevant because the probe reads the raw projectM FBO.

Shared infrastructure with the projectM robustness work (switch-failed callbacks, optional logging callback) benefits both live play and this tool.

## Phasing

**v1**

- Report-only scan of a single directory
- Load-failure detection + luminance check (quick default, `--slow` optional; see scan plan)
- Synthetic PCM
- JSON report

**v2**

- `--quarantine`, `--recursive`, `--resume`
- Config-driven texture paths

**v3 (optional)**

- `--delete` with confirmation
- Import report into a user-defined rotation blocklist
- Optional project PCM clip instead of synthetic tone



## Related work

- [preset-switching-proposal.md](legacy-plans/preset-switching-proposal.md) documents live projectM rotation; playlist retry and switch-failed callbacks were planned there but not fully wired in Cleave.
- [roadmap.md](roadmap.md) projectM PCM feeding note: batch scan may later use a real audio slice for more realistic classification.



## Open questions

- Default thresholds for black vs dim (may need tuning per pack).
- Whether quarantine preserves relative directory structure or flattens with hashed names.
- CI: headless GL in GitHub Actions is unreliable; keep this a local/dev tool unless a GPU runner exists.

