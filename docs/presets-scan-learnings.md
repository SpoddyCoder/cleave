# Preset scan tuning learnings

Notes from iterating on `cleave scan` classification heuristics. See [presets-scan-plan.md](presets-scan-plan.md) for command design and current status.

## What is in the branch today

Shipped on `presets-scan` (v1 through v3):

- `cleave scan` project and bulk modes, quick/`--slow` probe profiles, JSON report.
- v2: `--quarantine`, `--resume`, incremental and interrupt-safe report writes.
- v3: `--delete` with confirmation (`--yes` for non-TTY); stereo reference clip for `--slow`; report PCM metadata (`pcm_source`, `pcm_channels`, `reference_clip_path`).
- Classifier rework: clean boot per preset, full-frame luma sampling, peak max/mean/coverage across post-warmup frames, `washed_out` category, retuned thresholds.
- Golden harness: `cleave scan-golden` with committed slow-probe metrics cache; 29/30 eval accuracy (case 2 known mismatch; see below).
- Live visualizer: manual preset browse (`preset_switching` `none` or `user_defined`) forces a clean black boot via `load_manual_preset_clean()` in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py).

The scan harness in [cleave/preset_scan.py](../cleave/preset_scan.py):

- Clean boot every probe (`set_preset_start_clean(True)` before `load_preset`).
- Full-frame reads via [cleave/preset_scan_metrics.py](../cleave/preset_scan_metrics.py) `sample_frame_metrics`.
- Classification on peak max, mean, and coverage across all post-warmup frames.
- Quick mode: synthetic mono PCM (15 warmup + 75 window frames).
- `--slow`: stereo reference clip at [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) (90 warmup + 60 window frames).

Run `--slow` before bulk quarantine or delete. Quick mode remains useful for triage only.

## Golden eval (slow probe, reference audio)

Committed cache: [tests/fixtures/preset_scan_golden_metrics.json](../tests/fixtures/preset_scan_golden_metrics.json). Regenerate with `cleave scan-golden --probe --slow`.

Current eval: **29/30** (`cleave scan-golden --eval`). Known mismatch:

| ID | Preset | Expected | Actual | Notes |
| --- | --- | --- | --- | --- |
| 2 | Aderrasi - Airhandler (Principle of Sharing).milk | `black` | `washed_out` | Live manual review labels this preset broken (clean boot stays black). Slow probe with reference audio drives extreme white peaks (max 255, mean 227, full cov16). Classifier sees washed-out metrics, not black. |

Do not relabel case 2 without re-reviewing live behavior. Threshold tuning alone cannot reconcile reference-audio probe output with the manual black label for this preset.

## Timeline

### v1: center patch, mean-only threshold

First probe: 32x32 patch at frame center, peak mean luma only (`dim_mean_luma` 8), last post-warmup frame only.

On a COTC-scale run (~1007 presets), ~385 were quarantined. Manual review showed most were false positives. Bright-on-black presets (tunnels, kaleidoscopes, starfields) often have a dark center even when healthy.

### Coverage metric (explored, now shipped)

Sampling moved to full-frame reads. Peaks tracked across all post-warmup frames. Classification uses coverage (fraction of pixels at or above luma 16) alongside peak max and mean.

### Shared ProjectM: feedback state leak (verified, fixed)

`load_preset(smooth=False)` does not clear projectM's internal feedback framebuffer. The next preset inherits the previous preset's final frame as starting state.

Scan now forces clean boot per preset. Golden harness uses a fresh `ProjectM` per case.

### Live visualizer fix (committed)

Manual preset switching always clean-boots via `load_manual_preset_clean()`. Auto `projectm` rotation is unchanged (still uses the layer's `preset_start_clean` config).

### Reference audio (v3, shipped)

[assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) feeds `--slow` probes in both `cleave scan` and `cleave scan-golden`. Metrics shift vs synthetic PCM; thresholds and the golden cache were retuned against the new slow probe.

## Practical guidance

- Use live manual browse (clean boot) to build or verify labeled test sets.
- Run `--slow` before quarantine or delete.
- Golden-set metrics cache uses the slow profile (90 warmup + 60 window frames, reference stereo clip). Regenerate with `cleave scan-golden --probe --slow`.
- Read per-entry `luma` in the JSON report for borderline presets.
- Treat golden eval mismatches outside the known set as signals to retune or re-label.

## What not to do

- Do not go back to center-patch sampling.
- Do not rely on mean luma alone (false positives on bright-on-black).
- Do not rely on coverage alone (misses uniformly dim frames with scattered bright pixels).
- Do not reuse a single `ProjectM` across presets without forcing clean boot.
- Do not assume thresholds are frozen; check [cleave/preset_scan.py](../cleave/preset_scan.py) and re-run `cleave scan-golden --eval` after probe or classifier changes.
