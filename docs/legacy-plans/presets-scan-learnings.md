# Preset scan tuning learnings

Notes from iterating on `cleave scan` classification. See [presets-scan-plan.md](presets-scan-plan.md) for command design.

## Shipped behavior

- `cleave scan` project and bulk modes; JSON report.
- `--quarantine`, `--resume`, `--delete` (with confirmation).
- Classifier: clean boot per preset, full-frame luma, peak max/mean/coverage across post-warmup frames, `washed_out` category.
- Golden harness: `cleave scan-golden` with committed metrics cache ([tests/fixtures/preset_scan_golden_metrics.json](../tests/fixtures/preset_scan_golden_metrics.json)).
- Live visualizer: manual preset browse forces clean black boot via `load_manual_preset_clean()` in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py).

Probe harness ([cleave/preset_scan.py](../cleave/preset_scan.py)):

- Clean boot every probe (`set_preset_start_clean(True)` before `load_preset`).
- Full-frame reads via [cleave/preset_scan_metrics.py](../cleave/preset_scan_metrics.py).
- **Probe profile:** 15 warmup + 75 window frames; synthetic mono PCM.

## Visualizer vs scan (case 2)

Golden case 2 (Aderrasi - Airhandler): **black** in the live visualizer (clean boot, stays black). Committed golden cache classifies **`black`**. Probe frame metrics can still look bright on synthetic PCM; quarantine outcome matches the visualizer label.

## Design notes (historical)

- Center-patch sampling caused false positives on bright-on-black presets; replaced with full-frame peaks plus coverage.
- Shared `ProjectM` without clean boot leaked feedback between presets; both `cleave scan` and `cleave scan-golden --probe` now use a fresh instance per preset.

## Practical guidance

- Use live manual browse (clean boot) to build or verify labeled test sets.
- Read per-entry `luma` in scan JSON reports for borderline presets.
- Unexpected golden eval mismatches signal threshold or label review.

## What not to do

- Do not use center-patch sampling.
- Do not rely on mean luma or coverage alone.
- Do not reuse one `ProjectM` across presets; create a fresh instance per preset.
- Re-run `cleave scan-golden --eval` after probe or classifier changes.
