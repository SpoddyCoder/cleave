# Preset scan golden set

Manual labels for tuning `cleave scan`. Source: layer 1 preset in [projects/sights-and-sounds-26/](../projects/sights-and-sounds-26/) `unnamed-1.yaml` through `unnamed-30.yaml`, reviewed in the live visualizer with clean manual preset boot.

Machine-readable fixture: [tests/fixtures/preset_scan_golden_set.yaml](../tests/fixtures/preset_scan_golden_set.yaml).

Committed metrics cache: [tests/fixtures/preset_scan_golden_metrics.json](../tests/fixtures/preset_scan_golden_metrics.json).

## Review context

- **Preset root:** [assets/milkdrop-presets/](../assets/milkdrop-presets/) (git submodules; see [README](../README.md))
- **Texture paths:** `assets/milkdrop-presets/presets-milkdrop-texture-pack`
- **Pack:** `presets-milkdrop-original/Milkdrop-Original/`
- **Method:** Live browse with `load_manual_preset_clean` (black boot per switch)
- **Beat sensitivity:** 2.0 on layer 1 in most configs; ~0.9 in unnamed-8 through unnamed-10

## Expected results

| Result | Meaning | Quarantine? |
| --- | --- | --- |
| `ok` | Healthy preset; may look dim or start slow | No |
| `dim` | Runs but too dim to use | Yes |
| `black` | Does not develop from clean boot | Yes |
| `washed_out` | Extreme white blowout | Yes |

Shipped scan categories map as: `ok` -> `ok`; `dim` -> `dim`; `black` and `load_failed` -> `black`; `washed_out` -> `washed_out`.

## Summary

| Expected | Count |
| --- | ---: |
| `ok` | 21 |
| `dim` | 3 |
| `black` | 3 |
| `washed_out` | 3 |

**Quarantine targets:** 9 (`dim` 3, `black` 3, `washed_out` 3).

## Visualizer vs scan (case 2)

Golden case 2 (Aderrasi - Airhandler) is an accepted **eval disparity**, not a mis-label:

| Source | Label | Notes |
| --- | --- | --- |
| Live visualizer | `black` | Clean boot; stays black |
| Scan probe | `washed_out` | Synthetic PCM can drive extreme white metrics |

Both labels describe the same non-working preset. The visualizer label is ground truth for appearance; scan still **quarantines** it (`washed_out` is a quarantine category), but **scan classification cannot be trusted** for this preset.

Root cause is not understood. See [todos.md](todos.md).

Unit test: [tests/cleave/test_preset_scan_golden.py](../tests/cleave/test_preset_scan_golden.py) (`test_golden_case_2_not_washed_out_with_v3_cache`).

## Cases

| ID | Preset | Expected | Notes |
| --- | --- | --- | --- |
| 1 | BrainStain-Blackwidow.milk | `dim` | Working, but too dim |
| 2 | Aderrasi - Airhandler (Principle of Sharing).milk | `black` | Not working (see visualizer vs scan above) |
| 3 | BrainStain-re entry.milk | `ok` | May appear dim but clearly working |
| 4 | Eo.S. + Phat - chasers 11 sentinel C_poltergeist_mix response daemon.milk | `ok` | May appear dim but clearly working |
| 5 | Eo.S. - angels of decay.milk | `washed_out` | Highly washed out to white |
| 6 | Eo.S. - glowsticks v2 03 music.milk | `ok` | May appear dim but clearly working |
| 7 | Eo.S.+Phat - spectrum bubble new colors_v2.milk | `ok` | May appear dim but clearly working |
| 8 | Esotic & Rozzer - The Dark Side Of My Moon.milk | `washed_out` | Washed out to white |
| 9 | Esotic & Rozzor - Pixie Party Light (...).milk | `washed_out` | Washed out to white |
| 10 | Flexi + Martin - dive.milk | `ok` | Clear pass |
| 11 | Flexi + Geiss - pogo-cubes on tokamak matter [mind over matter remix].milk | `ok` | Clear pass |
| 12 | Flexi + Geiss - pogo-cubes on tokamak matter.milk | `ok` | Clear pass |
| 13 | Flexi + fiShbRaiN - witchcraft [...].milk | `ok` | May start slow, clearly works |
| 14 | Flexi - mindblob [shiny mix].milk | `ok` | Clear pass; slow start |
| 15 | Flexi - smashing fractals [Geiss' bas relief finish].milk | `ok` | Dim / slow start but working |
| 16 | Flexi - working with infinity.milk | `ok` | Clear pass; slow start |
| 17 | Flexi, Rovastar + Geiss - Fractopia vs bas relief.milk | `ok` | Dim / slow start but working |
| 18 | Flexi, fishbrain + Martin - witchery.milk | `ok` | Starts dim, then works |
| 19 | Flexi, martin + geiss - dedicated to the sherwin maxawow.milk | `ok` | Dim at centre; grows from edge |
| 20 | Fvese - Snowflake Like 2.milk | `ok` | Clear pass |
| 21 | Geiss - Explosion 2.milk | `ok` | Slow start |
| 22 | Goody - Acid Angel - Fallen Angel.milk | `ok` | Slow start |
| 23 | Goody - Lights in the Sky.milk | `ok` | Slow start |
| 24 | Goody - Need - Transcendance remix.milk | `ok` | Clear pass; high luma but usable (not washed_out) |
| 25 | Mstress & Juppy - Dancer.milk | `ok` | May appear dim but clearly working |
| 26 | Rovastar & Zylot - Crystal Ball (Many Visions Mix).milk | `black` | Does not work |
| 27 | Fast transition to black - levels effect ... Isosceles edit.milk | `black` | Does not work |
| 28 | Jc - Lungs.milk | `dim` | Too dim |
| 29 | EoS + Phat - chasers 11 sentinel C (Jelly V2).milk | `ok` | May appear dim but clearly working |
| 30 | only glimpses of the reality you once knew ... .milk | `dim` | Too dim |

## Harness usage

1. Load [tests/fixtures/preset_scan_golden_set.yaml](../tests/fixtures/preset_scan_golden_set.yaml).
2. Probe all 50 cases with clean boot and full-frame metrics.
3. Compare classifier output to `expected_result` (`cleave scan-golden --eval`).

**Committed cache profile:** 15 warmup + 75 window frames at 30 fps, synthetic mono PCM. Regenerate with `cleave scan-golden --probe`.

**Commands:**

```bash
# Regenerate committed cache (needs GL)
cleave scan-golden --probe

# Evaluate classifier against visualizer labels (GL-free)
cleave scan-golden --eval

# Grid search warmup/window (GL-free)
cleave scan-golden --sweep
```

- **Eval:** reads warmup/window from cache metadata; mismatched `--warmup` / `--window` flags error.

See [presets-scan-plan.md](presets-scan-plan.md) and [presets-scan-learnings.md](presets-scan-learnings.md).
