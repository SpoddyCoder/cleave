# Preset scan tuning learnings

Notes from iterating on `cleave scan` classification. See [presets-scan-plan.md](presets-scan-plan.md) for command design.

## Shipped behavior

- `cleave scan` project and bulk modes; quick (default) and `--slow` probe profiles; JSON report.
- `--quarantine`, `--resume`, `--delete` (with confirmation).
- Classifier: clean boot per preset, full-frame luma, peak max/mean/coverage across post-warmup frames, `washed_out` category.
- Golden harness: `cleave scan-golden` with committed quick-probe metrics cache.
- Live visualizer: manual preset browse forces clean black boot via `load_manual_preset_clean()` in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py).

Probe harness ([cleave/preset_scan.py](../cleave/preset_scan.py)):

- Clean boot every probe (`set_preset_start_clean(True)` before `load_preset`).
- Full-frame reads via [cleave/preset_scan_metrics.py](../cleave/preset_scan_metrics.py).
- **Quick:** 15 warmup + 75 window frames; synthetic mono PCM.
- **`--slow`:** 90 warmup + 60 window frames; stereo [assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav).

Run `--slow` before bulk quarantine or delete. Quick mode is useful for triage and golden eval against the committed cache.

## Visualizer vs scan (case 2)

Golden case 2 (Aderrasi - Airhandler): **black** in the live visualizer (clean boot, stays black); **washed_out** in scan (quick and slow). This is an accepted eval disparity, not a mis-label. Quarantine outcome is correct; scan category is not trustworthy for this preset. Cause unknown; backlog in [todos.md](todos.md).

## Design notes (historical)

- Center-patch sampling caused false positives on bright-on-black presets; replaced with full-frame peaks plus coverage.
- Shared `ProjectM` without clean boot leaked feedback between presets; scan and golden harness now clean-boot per preset (golden uses a fresh instance per case).
- Reference audio for `--slow` shifts metrics vs synthetic PCM; thresholds tuned separately per profile.

## Practical guidance

- Use live manual browse (clean boot) to build or verify labeled test sets.
- Run `--slow` before quarantine or delete.
- Read per-entry `luma` in scan JSON reports for borderline presets.
- Unexpected golden eval mismatches (outside case 2) signal threshold or label review.

## What not to do

- Do not use center-patch sampling.
- Do not rely on mean luma or coverage alone.
- Do not reuse one `ProjectM` across presets without clean boot.
- Re-run `cleave scan-golden --eval` after probe or classifier changes.
