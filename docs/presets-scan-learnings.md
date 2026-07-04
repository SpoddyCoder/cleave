# Preset scan tuning learnings

Notes from iterating on `cleave scan` classification heuristics. See [presets-scan-plan.md](presets-scan-plan.md) for command design, current status, and outstanding work.

## What is in the branch today

Committed on `presets-scan` (v1 + v2):

- `cleave scan` project and bulk modes, quick/`--slow` probe profiles, JSON report.
- v2: `--quarantine`, `--resume`, incremental and interrupt-safe report writes.
- Live visualizer: manual preset browse (`preset_switching` `none` or `user_defined`) forces a clean black boot via `load_manual_preset_clean()` in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) (`set_preset_start_clean(True)` for the load, then restore the layer value).

The scan harness in [cleave/preset_scan.py](../cleave/preset_scan.py) is still the v1 probe:

- One shared `ProjectM` for the whole run (`load_preset(smooth=False)` between presets).
- 32x32 center-patch luma sample (`_sample_center_luma`), not full-frame coverage.
- Classification on peak max and mean from the **last** post-warmup frame only (not peak across all sampled frames).
- Thresholds: `black_max_luma` 1.0, `dim_mean_luma` 8.0.
- Synthetic mono PCM for both quick and `--slow` (reference clip exists at [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) but is not wired yet; v3).

Classifier accuracy is not trusted yet. Do not quarantine large packs from current scan output without manual review.

## Timeline

### v1: center patch, mean-only threshold

First probe: 32x32 patch at frame center, peak mean luma only (`dim_mean_luma` 8), last post-warmup frame only.

On a COTC-scale run (~1007 presets), ~385 were quarantined. Manual review showed most were false positives. Bright-on-black presets (tunnels, kaleidoscopes, starfields) often have a dark center even when healthy.

### Coverage metric (explored, not committed)

Sampling moved to full-frame reads. Peaks tracked across all post-warmup frames. Classification used coverage (fraction of pixels at or above luma 16) alongside peak max:

| Constant | Value |
| --- | --- |
| `coverage_luma_min` | 16 |
| `black_coverage` | 0.0005 |
| `dim_coverage` | 0.01 |

Quick mode (~150 quarantined) looked mostly accurate. `--slow` roughly doubled quarantines; the first 20 manually checked were all healthy (false positives). That pointed at probe contamination, not audio.

### Shared ProjectM: feedback state leak (verified)

`load_preset(smooth=False)` does not clear projectM's internal feedback framebuffer. The next preset inherits the previous preset's final frame as starting state.

Effects observed in headless probes and live play:

- Scan order changes outcomes (order-dependent classification).
- Slow mode false positives: many presets collapsed to black over the long warmup while still inheriting a bright seed from the prior preset; quick mode sampled earlier before collapse.
- Live manual browse: a preset can "work" when the prior preset left an active frame, but stay black when booted cold.

Stereo reference PCM was ruled out; the artifact was framebuffer carry-over.

### Clean boot for probing (explored, reverted from scan)

Two ways to get a deterministic black boot, verified equivalent on sample presets:

1. Fresh `ProjectM` per preset.
2. `set_preset_start_clean(True)` before `load_preset`, then restore the configured value (consumed at load time).

A follow-up change combined clean boot with full-frame coverage, `dim_mean_luma` 10, and a bright-on-black guard (`max >= 100` and `coverage >= 0.02`). It under-detected badly (slow scan ~15 failures vs ~150 that looked plausible under the contaminated shared instance, though that count mixed real failures with artifacts). The scan changes were reverted; live clean boot was kept.

### Live visualizer fix (committed)

Manual preset switching now always clean-boots via `load_manual_preset_clean()`. Auto `projectm` rotation is unchanged (still uses the layer's `preset_start_clean` config). This lets you judge presets honestly while browsing before building a classifier test set.

## Classifier rework (next)

Current scan output is not reliable enough for bulk quarantine. Planned sequence:

1. **Manual labels** — With clean manual browse, pick a small set of presets across `ok`, `dim`, and broken (black / never develops). Record paths and labels.
2. **Harness requirements** — Clean boot every probe (`set_preset_start_clean(True)` or fresh `ProjectM`); full-frame sampling; peak max, mean, and coverage across all post-warmup frames (and likely from frame 0 so flash-then-fade is caught).
3. **Threshold tuning** — Fit rules against the manual set; re-run on a larger pack; iterate.
4. **Reference audio (v3)** — Wire [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav) for `--slow` after the luminance pipeline is stable.

Explored but not re-adopted without a labeled test set:

| Idea | Value | Risk |
| --- | --- | --- |
| Coverage + mean | Fixes center-patch false positives | Needs retune after clean boot |
| `dim_mean_luma` ~10 | Separates sparse dim from healthy low-mean | Misses without coverage guard |
| Bright-on-black guard | Keeps tunnels/kaleidoscopes out of `dim` | Threshold-sensitive |
| Shared contaminated `ProjectM` | Harsh stress test | Order-dependent, not deterministic |

## Practical guidance

- Use live manual browse (clean boot) to build a labeled test set before trusting scan quarantine.
- Run `--slow` before quarantine or delete once the classifier is reworked; quick mode is for triage only.
- When reviewing borderline presets, read per-entry `luma` in the JSON report once the harness emits it (not in v1/v2 reports today).
- Do not treat current scan JSON as ground truth for bulk moves.

## What not to do

- Do not go back to center-patch sampling for the final classifier.
- Do not rely on mean luma alone (v1 false positives on bright-on-black).
- Do not rely on coverage alone after clean-boot probing (misses uniformly dim frames with scattered bright pixels).
- Do not reuse a single `ProjectM` across presets without forcing clean boot (`load_preset(smooth=False)` leaves feedback state).
- Do not assume the reverted coverage retune is in the codebase; check [cleave/preset_scan.py](../cleave/preset_scan.py) before changing thresholds.
