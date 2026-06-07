# Cleave effects plan

Signal-driven compositor effects for the Milkdrop visualizer. Each layer can expose a subset of effects under a collapsible **cleave effects** section in the live tuning overlay. Drivers are fixed per stem and effect in code; the user only sets depth (0-100%).

This plan covers the full stack, delivered in logical phases. No backward compatibility beyond updating repo-root [cleave.config.yaml](../cleave.config.yaml).

---

## Goals

- Modulate compositor output from existing `signals.json` time series (no new analysis fields yet).
- Keep libprojectM **beat sensitivity** outside cleave effects (PCM-driven preset reactivity, unchanged).
- Curate a small, useful effect set per stem rather than exposing open-ended signal picking.
- Give Cleave a distinct compositor signature (opacity pulse, bloom flare, per-layer flash, vocal hue, grit/aberration) on top of community presets.

---

## Locked decisions

| Topic | Decision |
| --- | --- |
| Delivery | Full stack; implement in phases below |
| UI parent row | `cleave effects` (lowercase), collapsed by default, bottom of track tree (after beat sensitivity) |
| UI parent row typography | Label `└─ cleave effects` in `LABEL`; expand arrow in `VALUE` (see [live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc)) |
| Child row pattern | `{effect} ({signal}): N%` e.g. `pulse (onset): 35%` |
| Config | Nested `layers.*.effects` map reflecting the tree; breaking rename from `cleave_pulse` |
| Migration | Update [cleave.config.yaml](../cleave.config.yaml) only; no snapshot migration |
| Locked layers | Normal rules: effects sub-rows `LOCKED` and non-adjustable; expand/collapse still allowed |
| projectM | No changes to PCM feed or beat sensitivity handling |

---

## Taxonomy

**Effect** = what visual parameter changes and how it responds.

**Driver** = which `signals.json` key modulates it (shown in parentheses, not user-selectable).

| Effect | Target | Response shape | Typical drivers |
| --- | --- | --- | --- |
| **pulse** | Layer opacity | Smoothed envelope follow | onset, sub_bass, mid_bass, rms, centroid |
| **flare** | Per-layer bloom | Hit burst (threshold + fast decay) | onset |
| **flash** | Per-layer flash overlay | Hit burst (threshold + fast decay) | onset, sub_bass, rms, centroid |
| **hue** | Per-layer color tint | Continuous map (hold when unvoiced) | pitch |
| **grit** | Per-layer grain + chromatic aberration | Envelope follow | onset, sub_bass, rms, centroid |

**pulse** uses multiplicative opacity (current [cleave/cleave_pulse.py](../cleave/cleave_pulse.py) behavior). **flare**, **flash**, **hue**, and **grit** require new compositor paths (Phase 6.2 direction in [cleave-build-plan.md](cleave-build-plan.md)).

---

## Per-stem effect roster

Fixed registry: only these rows appear per stem.

### Drums

| Row label | `signals.json` key | Notes |
| --- | --- | --- |
| `pulse (onset): N%` | `drums.onset_strength` | Shipped; refactor into effects tree |
| `flare (onset): N%` | `drums.onset_strength` | Bloom burst on transients |
| `flash (onset): N%` | `drums.onset_strength` | Brief layer flash on strong hits |
| `grit (onset): N%` | `drums.onset_strength` | Hit-driven grit/aberration |

### Bass

| Row label | `signals.json` key | Notes |
| --- | --- | --- |
| `pulse (sub_bass): N%` | `bass.sub_bass` | Slow pressure |
| `pulse (mid_bass): N%` | `bass.mid_bass` | Upper bass movement |
| `flash (sub_bass): N%` | `bass.sub_bass` | Burst on sub peaks |
| `grit (sub_bass): N%` | `bass.sub_bass` | Continuous grit from sub envelope |

### Vocals

| Row label | `signals.json` key | Notes |
| --- | --- | --- |
| `pulse (rms): N%` | `vocals.rms` | Presence-driven opacity |
| `hue (pitch): N%` | `vocals.pitch_hz` | Tint from pitch; hold last hue when unvoiced |
| `flash (rms): N%` | `vocals.rms` | Burst on loud syllables |
| `grit (rms): N%` | `vocals.rms` | Grit follows vocal level |

### Other

| Row label | `signals.json` key | Notes |
| --- | --- | --- |
| `pulse (centroid): N%` | `other.spectral_centroid` | Brightness wash on opacity |
| `flash (centroid): N%` | `other.spectral_centroid` | Burst on brightness spikes |
| `grit (centroid): N%` | `other.spectral_centroid` | Texture follows centroid |

Row counts when **cleave effects** is expanded: drums 4, bass 4, vocals 4, other 3.

---

## UI specification

### Track tree order (per stem)

1. Layer header (`Layer N: STEM`)
2. Preset dir
3. Preset
4. Blend mode
5. Opacity
6. Beat sensitivity
7. **cleave effects** (collapsible header; label in `LABEL`, arrow in `VALUE`; collapsed by default)
8. Effect sub-rows (visible only when cleave effects expanded and track expanded)

Track header expand/collapse still hides preset/blend/opacity/beat/effects rows together (existing behavior). **cleave effects** has its own expand/collapse independent of the track header.

### Navigation and adjustment

- Up/Down: skip collapsed effect sub-rows; include `cleave effects` header when track is navigable.
- Left/Right on `cleave effects` header: expand/collapse effect sub-rows (same pattern as preset dir).
- Left/Right on effect sub-rows: adjust N% by 1 (10 with Ctrl), clamped 0-100.
- Locked track: effect sub-rows `LOCKED`; Left/Right ignored; expand/collapse on `cleave effects` still works.

### Row count model

Replace fixed `ROWS_PER_TRACK` with per-stem row counts: base rows (header + 5 children + effects header) plus variable effect rows when effects section expanded. Footer rows unchanged.

---

## Config and YAML shape

Replace top-level `cleave_pulse` with nested `effects`. Only non-zero values need to be written in snapshots (same sparse style as today).

### Drums example

```yaml
layers:
  drums:
    preset: presets-cream-of-the-crop/Dancer/Aurora/
    enabled: true
    opacity: 0.3
    blend_mode: add
    effects:
      pulse:
        onset: 35
      flare:
        onset: 20
      flash:
        onset: 15
      grit:
        onset: 10
```

### Bass example

```yaml
  bass:
    effects:
      pulse:
        sub_bass: 40
        mid_bass: 25
      flash:
        sub_bass: 10
      grit:
        sub_bass: 5
```

### Vocals example

```yaml
  vocals:
    effects:
      pulse:
        rms: 45
      hue:
        pitch: 25
      flash:
        rms: 10
      grit:
        rms: 5
```

### Other example

```yaml
  other:
    effects:
      pulse:
        centroid: 30
      flash:
        centroid: 10
      grit:
        centroid: 5
```

### Config keys

- Effect names: `pulse`, `flare`, `flash`, `hue`, `grit`
- Signal slugs in YAML (match UI parentheses): `onset`, `sub_bass`, `mid_bass`, `rms`, `pitch`, `centroid`
- Values: integer 0-100 (depth / mix amount)

Rename `clamp_cleave_pulse_pct` to a neutral `clamp_effect_pct` (or similar) in [cleave/config.py](../cleave/config.py).

---

## Effect parameters

Tunable constants live at the top of the module that owns each effect family (or a shared `cleave/effects/constants.py`). No magic numbers buried in frame loops.

### Shared signal sampling

- Sample rate: 100 Hz from `signals.json`
- Normalization: 99th percentile via `Signals.normalized()` (existing)
- Interpolation: linear between samples at playback time (existing pattern in [cleave/cleave_pulse.py](../cleave/cleave_pulse.py))

### pulse (opacity envelope)

Formula (unchanged):

```
effective_opacity = base_opacity * (1 + (smoothed - 1) * (N / 100))
```

Envelope: `smoothed = max(smoothed * DECAY, raw * GAIN)`

| Driver | DECAY | GAIN | Rationale |
| --- | --- | --- | --- |
| onset | 0.92 | 1.0 | Fast punch (Phase 3/4) |
| sub_bass | 0.96 | 1.0 | Slow pressure |
| mid_bass | 0.94 | 1.0 | Slightly faster than sub |
| rms | 0.96 | 1.0 | Vocal presence |
| centroid | 0.98 | 1.0 | Slow brightness drift |

Bass **pulse** rows are independent: two envelopes, two opacity contributions combined multiplicatively or applied as separate factors (implementation choice in Phase 2; prefer multiplicative factors per pulse row).

### flare (per-layer bloom, drums only)

- Trigger: smoothed onset delta `> FLARE_DELTA` (start `0.10`) or onset `> FLARE_THRESHOLD` (start `0.55`)
- Burst envelope: attack instant, decay `FLARE_DECAY = 0.75` per frame
- Output: add bloom pass on layer FBO before composite; strength `N/100 * burst_envelope`
- Bloom radius / intensity: start with single-pass wide blur; constants `FLARE_BLUR_RADIUS`, `FLARE_INTENSITY_SCALE` at top of flare module

### flash (per-layer overlay)

- Trigger: same threshold pattern as [scripts/pulse_visualizer.py](../scripts/pulse_visualizer.py): `FLASH_THRESHOLD = 0.65` for onset; `0.50` for continuous drivers (sub_bass, rms, centroid) after normalization
- Burst: `FLASH_DECAY = 0.82` per frame
- Output: brief warm/white overlay on that layer's composited quad at `alpha = N/100 * burst * FLASH_PEAK` (`FLASH_PEAK = 1.0`)
- Per-layer only (not full-screen), drawn with layer during `draw_layer`

### hue (vocals only)

- Input: `vocals.pitch_hz`; unvoiced / NaN: hold `last_hue`, decay toward neutral with `HUE_DECAY_UNVOICED = 0.03` per frame
- Map: `PITCH_MIN_HZ = 80`, `PITCH_MAX_HZ = 800` to hue `0-300` (Phase 4 [layered_visualizer.py](../scripts/layered_visualizer.py))
- Smooth: `HUE_LERP = 0.06` toward target when voiced
- Output: multiply layer tint toward `hsv(hue, 0.55, 1.0)`; mix amount `N/100`

### grit (per-layer grain + aberration)

- Envelope: same attack/decay as **pulse** for that stem's grit driver (reuse driver row's DECAY/GAIN)
- Grain: film grain noise overlay; intensity `N/100 * envelope * GRIT_SCALE` (`GRIT_SCALE = 0.4` start)
- Aberration: RGB channel offset in pixels `ABERRATION_MAX_PX = 3 * envelope * (N/100)`
- Applied per layer after Milkdrop render to FBO, before compositor stack

---

## Architecture

### Module layout (target)

```
cleave/effects/
  __init__.py
  registry.py      # stem -> list of EffectDef (id, label, driver key, effect class)
  constants.py     # shared clamps, thresholds (or per-file tops per effect family)
  sampling.py      # sample_normalized, envelope helpers
  pulse.py         # opacity modulation (from cleave_pulse.py)
  flare.py
  flash.py
  hue.py
  grit.py
  runtime.py       # per-layer EffectRuntime state, tick(signals, t_sec) -> LayerModifiers
```

### Compositor integration

[cleave/gl_compositor.py](../cleave/gl_compositor.py) black-key stack plus [cleave/gl_post_process.py](../cleave/gl_post_process.py) per-layer passes:

1. Render libprojectM to layer FBO
2. Optional post on FBO texture: bloom (flare), grit, hue tint
3. `draw_layer` applies effective opacity (pulse), `blend_mode`, and flash overlay
4. Stack bottom-to-top per `layer_z_order`

`LayerModifiers` (per frame, per layer): `opacity`, `flash_alpha`, `bloom_strength`, `hue_shift`, `grit_strength`, `aberration_px`.

### Live tuning wiring

- [cleave/viz_tuning_overlay.py](../cleave/viz_tuning_overlay.py): dynamic rows from registry; `cleave effects` header row kind
- [cleave/viz_tuning_controls.py](../cleave/viz_tuning_controls.py): session holds `effects: dict[str, dict[str, dict[str, int]]]` or structured `EffectAmounts`
- [cleave/config_snapshot.py](../cleave/config_snapshot.py): read/write `effects` block
- [scripts/milkdrop_visualizer.py](../scripts/milkdrop_visualizer.py): load signals, tick effect runtime, apply modifiers before composite

---

## Implementation phases

### Phase 1: Foundation and UI tree

- Add `cleave/effects/registry.py` with per-stem effect definitions
- Replace `TRACK_CLEAVE_PULSE` with `TRACK_EFFECTS_HEADER` + per-effect row kinds (or dynamic effect rows)
- `cleave effects` header: lowercase label + value arrow (`_render_label_value_row`), collapsed by default, after beat sensitivity
- Config parse/dump for `layers.*.effects`; remove `cleave_pulse` from [cleave/config.py](../cleave/config.py)
- Update [cleave.config.yaml](../cleave.config.yaml) to new shape (drums `effects.pulse.onset` from current `cleave_pulse`)
- Rename [cleave/cleave_pulse.py](../cleave/cleave_pulse.py) into `cleave/effects/pulse.py`; keep drums behavior working
- Tests: registry, config round-trip, overlay row labels/counts, navigation with nested collapse

**Milestone:** UI shows full effect tree per stem; only `pulse` affects playback on drums.

### Phase 2: pulse on all stems

- Implement pulse drivers for bass (sub_bass, mid_bass), vocals (rms), other (centroid)
- Independent envelope state per pulse row on bass
- Combine multiple pulse factors into effective opacity per layer
- Enable Left/Right adjustment on all pulse rows (remove drums-only guard)
- Tests: per-stem envelope decay, effective opacity stacking

**Milestone:** All pulse rows live on all stems.

### Phase 3: flash (per layer, all stems)

- `cleave/effects/flash.py` + compositor overlay in `draw_layer`
- Driver-specific thresholds in constants
- Tests: trigger threshold, decay, per-layer isolation

**Milestone:** Flash rows work per layer.

### Phase 4: flare (drums)

- Bloom pass on drums FBO; onset-driven burst
- Tests: flare triggers on onset peaks, no-op at N=0

**Milestone:** `flare (onset)` on drums.

### Phase 5: hue (vocals)

- Pitch sampling with NaN handling; per-layer tint in compositor
- Tests: voiced pitch shifts tint; unvoiced holds/decays

**Milestone:** `hue (pitch)` on vocals.

### Phase 6: grit (per layer, all stems)

- Grain + chromatic aberration pass per layer FBO
- Tests: grit scales with envelope and N%

**Milestone:** Full effect roster implemented.

### Phase 7: Polish

- Session snapshot sparse write for all effect keys
- Manual sign-off on one dense track (e.g. `stems/buttercup-24`)
- Update [README.md](../README.md) and [cleave-build-plan.md](cleave-build-plan.md) with cleave effects summary (brief pointer to this doc)
- Update [.cursor/rules/live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc) row model description

**Milestone:** Full stack documented and tuned defaults in `cleave.config.yaml`.

---

## Testing strategy

| Area | Tests |
| --- | --- |
| Registry | Each stem exposes expected effect rows and driver slugs |
| Config | Parse/dump `effects` nested map; clamp 0-100 |
| Snapshots | Non-zero effects persist; zero keys omitted |
| pulse | `effective_opacity` formula; per-driver decay constants |
| flash / flare | Threshold trigger, decay toward zero |
| hue | Pitch map; NaN hold/decay |
| UI | Row visibility with track + effects collapse; locked layer tints effects `LOCKED`; labels match `pulse (onset): N%` |
| Integration | milkdrop frame loop applies modifiers (mock signals + fixed t_sec) |

---

## Out of scope (this plan)

- New `signals.json` fields or analysis changes
- libprojectM beat sensitivity or PCM path changes
- User-selectable signal drivers in the UI
- Global full-screen flash (flash is per layer only)
- Ripple effect (Phase 4 pygame only; not in roster)
- Web / Butterchurn port

---

## Reference: current state

- Drums-only `cleave pulse` row and `cleave_pulse` config key ([cleave/cleave_pulse.py](../cleave/cleave_pulse.py), [cleave/viz_tuning_overlay.py](../cleave/viz_tuning_overlay.py))
- Compositor: black-key stack, per-layer opacity, blend, and cleave effects ([cleave/gl_compositor.py](../cleave/gl_compositor.py), [cleave/gl_post_process.py](../cleave/gl_post_process.py))
- Signals available per stem: [cleave/analyse.py](../cleave/analyse.py)

Phase 1 of this plan is the immediate next step after this document is accepted.
