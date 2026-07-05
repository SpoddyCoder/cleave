# Preset scan golden set

Manual classifier labels for tuning `cleave scan`. Source: layer 1 preset comments in [projects/sights-and-sounds-26/](../projects/sights-and-sounds-26/) `unnamed-1.yaml` through `unnamed-30.yaml`, reviewed with clean manual preset boot.

Machine-readable fixture: [tests/fixtures/preset_scan_golden_set.yaml](../tests/fixtures/preset_scan_golden_set.yaml).

Metrics cache (slow probe, reference audio): [tests/fixtures/preset_scan_golden_metrics.json](../tests/fixtures/preset_scan_golden_metrics.json).

## Review context

- **Preset root:** `~/milkdrop-presets`
- **Texture paths:** `~/milkdrop-presets/presets-milkdrop-texture-pack`
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

## Known eval mismatch (slow probe)

Golden eval targets **29/30** accuracy. One case is an accepted mismatch under the reference-audio slow probe:

| ID | Preset | Expected | Slow-probe actual | Notes |
| --- | --- | --- | --- | --- |
| 2 | Aderrasi - Airhandler (Principle of Sharing).milk | `black` | `washed_out` | Live clean boot shows a broken preset (stays black). Reference-audio slow probe produces extreme white metrics (max 255, mean 227). Classifier labels `washed_out`, not `black`. |

Unit test: [tests/cleave/test_preset_scan_golden.py](../tests/cleave/test_preset_scan_golden.py) (`GOLDEN_MIN_ACCURACY = 29`, `GOLDEN_KNOWN_MISMATCH_IDS = {2}`).

## Cases

| ID | Preset | Expected | Notes |
| --- | --- | --- | --- |
| 1 | BrainStain-Blackwidow.milk | `dim` | Working, but too dim |
| 2 | Aderrasi - Airhandler (Principle of Sharing).milk | `black` | Not working (see known mismatch above) |
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
2. Probe all 30 cases with clean boot and full-frame metrics.
3. Compare classifier output to `expected_result`; report mismatches and accuracy per category.
4. Tune thresholds in [cleave/preset_scan.py](../cleave/preset_scan.py) until eval passes (29/30 with case 2 accepted); spot-check on a larger pack.

**Probe profile:** slow cache uses 90 warmup + 60 window frames at 30 fps (150 frames total), stereo reference clip ([assets/audio/scan-reference-10s.wav](../assets/audio/scan-reference-10s.wav)). Golden harness uses a fresh `ProjectM` per preset.

**Commands:**

```bash
# Regenerate committed slow cache (needs GL)
cleave scan-golden --probe --slow

# Evaluate classifier against labels (GL-free)
cleave scan-golden --eval

# Grid search warmup/window (GL-free)
cleave scan-golden --sweep
```

- **Probe:** `cleave scan-golden --probe` without `--slow` uses the quick profile; warns when overwriting the committed slow cache.
- **Eval:** `cleave scan-golden --eval` reads warmup/window from the cache automatically; mismatched `--warmup` / `--window` flags error.
- **Legacy v1 caches:** eval infers profile from frame count (90=quick, 150=slow) with a stderr warning.

See [presets-scan-plan.md](presets-scan-plan.md) and [presets-scan-learnings.md](presets-scan-learnings.md).
