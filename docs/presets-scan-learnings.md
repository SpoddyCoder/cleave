# Preset scan tuning learnings

Notes from iterating on `cleave scan` classification heuristics. See [presets-scan-plan.md](presets-scan-plan.md) for the command design and [presets-check-proposal.md](presets-check-proposal.md) for the original problem statement.

## Timeline

### v1: center patch, mean-only threshold

The first probe sampled a 32x32 patch at the frame center and classified on peak mean luma only (`DIM_MEAN_LUMA=8`). Only the last rendered frame was read.

Result: ~385 of 1007 presets quarantined. Manual review showed most were false positives. Bright-on-black presets (tunnels, kaleidoscopes, starfields) often have a dark center even when the preset is healthy.

### Coverage metric fix

Sampling moved to full-frame `_sample_frame_luma`. Peaks are tracked across all sampled frames after warmup (not just the last frame). Classification uses coverage (fraction of pixels at or above luma 16) alongside peak max:

| Constant | Value |
| --- | --- |
| `coverage_luma_min` | 16 |
| `black_coverage` | 0.0005 |
| `dim_coverage` | 0.01 |

Quick mode (~150 quarantined, mostly genuinely bad) looked successful. `--slow` roughly doubled quarantines; the first 20 manually checked were all healthy presets (false positives).

### Shared ProjectM: root cause of slow false positives

One `ProjectM` instance was reused across presets. `load_preset(smooth=False)` does not clear the internal feedback framebuffer. Feedback-loop presets inherit the previous preset's final frame as their starting state.

Effects:

- Order-dependent results (scan order changed outcomes).
- Slow mode false positives: many presets collapsed to black over the long slow warmup (sample window frames 90-149). Quick mode sampled earlier (frames 15-29) before collapse.
- Stereo reference PCM and the reference clip were exonerated; the artifact came from framebuffer carry-over, not audio.

### Fresh ProjectM per preset

`_make_probe_projectm()` creates and destroys a `ProjectM` for each preset in `run_scan()`. This fixed order-dependence and slow-mode false positives.

Trade-off: under-detection. After the fix, quick mode reported ~35 failures and slow ~31, versus ~150 that looked accurate under the shared-instance probe (though that count mixed real failures with contamination artifacts).

Some quarantined presets were still false positives, but many genuinely dark or dim presets now passed as `ok`.

### Key insight

The shared, contaminated `ProjectM` accidentally acted as a harsh stress test. Many presets look worse (or black) when booted into a random feedback state. A fresh clean boot is the correct architecture for deterministic probing, but broken presets can appear more active than they are in live rotation where feedback persists across preset switches.

Classification must combine multiple signals (coverage and mean luma), and thresholds need retuning for clean-boot probing.

## Current thresholds (post retune)

After fresh ProjectM per preset, coverage-only classification on a slow scan of 986 presets yielded only 15 non-load failures (8 black, 7 dim) versus 958 `ok`. Analysis of `tmp/scan-report.json`:

| Group | `mean` median | `coverage` median | Notes |
| --- | --- | --- | --- |
| black (8) | 0.0 | 0.0 | Truly empty or near-empty output |
| dim (7) | 0.35 | 0.003 | Low coverage, some with high peak max |
| ok (958) | 83.7 | 0.98 | Wide spread; 59 `ok` presets had `mean` below 10 |

False negatives clustered at low mean with coverage just above `dim_coverage` (0.01): sparse bright pixels on an otherwise dark frame. Bright-on-black healthy presets share that signature but typically have peak max at or above 100 and coverage at or above 0.02.

Retuned values:

| Constant | Value | Rationale |
| --- | --- | --- |
| `black_max_luma` | 1.0 | Unchanged |
| `black_coverage` | 0.0005 | Unchanged |
| `dim_coverage` | 0.01 | Unchanged |
| `dim_mean_luma` | 10.0 | Re-added; ok p10 is ~16.5, current dim cluster is 0-2.6, gap around 8-10 |
| `coverage_luma_min` | 16.0 | Unchanged |
| bright-on-black guard | max >= 100, coverage >= 0.02 | Keeps tunnel/kaleidoscope presets out of dim when mean is low |

Peak max, mean, and coverage now accumulate from frame 0 (warmup frames still run so presets can develop, but early brightness is not discarded). This catches presets that flash bright then fade.

On the existing slow report (without re-scanning), the retuned rules reclassify roughly 12 additional `ok` presets as `dim` while preserving bright-on-black cases. A full re-scan with frame-0 peak accumulation should raise the failure count further.

## Practical guidance

- Run `--slow` before quarantine or delete; quick mode is for triage only.
- Read the `luma` block in the JSON report (`max`, `mean`, `coverage`) when reviewing borderline presets.
- Fresh `ProjectM` per preset is correct; do not revert to a shared instance.
- Threshold tuning is ongoing; expect to adjust `dim_mean_luma` and coverage constants per preset pack.

## What not to do

- Do not go back to center-patch sampling.
- Do not rely on mean luma alone (v1 false positives).
- Do not rely on coverage alone after clean-boot probing (misses uniformly dim frames with scattered bright pixels).
- Do not reuse a single `ProjectM` across presets (`load_preset(smooth=False)` leaves feedback state).
