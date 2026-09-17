# Improved timeline presets

Generative timeline authoring: visuals tied to the song, readable multi-layer compositing, and almost no user input beyond Apply.

**Status:** Done. Rich cues (levels, blend, role), stem conductor, and the closed-loop visual limiter are shipped. Follow-ups (preset reactivity fingerprints, reprise and auto form) moved to [roadmap.md](../roadmap.md). Record still punches 0/1 remains in [todos.md](../todos.md).

Related: [song-markers.md](song-markers.md), [roadmap.md](../roadmap.md), [cleave/timeline_presets/](../../cleave/timeline_presets/), [cleave/signals.py](../../cleave/signals.py).

Naming: **cue** remains a per-lane transition. **Song markers** remain project-scoped structure points in `project.yaml`.

---

## Shipped baseline

- Generative characters (Breathing, Dialogue, Arc, Pulse) in [cleave/timeline_presets/](../../cleave/timeline_presets/) arrange layer levels with phrase grids, motif voice-leading, density bias, and crescendos driven by song markers typed `crescendo` (optional `begin` / `sustain` set the rise window).
- Beat This! downbeats in `signals.json` drive the bar grid; manual song markers act as hard section walls and soft latch (~5s) at generation time.
- Each layer is its own projectM instance fed stem PCM; black-key (and other) blends stack them in [cleave/gl_compositor.py](../../cleave/gl_compositor.py).
- Cue levels drive continuous opacity: `lane_level_breakpoints` / `lane_level_envelope` in [cleave/timeline.py](../../cleave/timeline.py) feed `layer.timeline_level` via `apply_layer_visibility` in [cleave/viz/layer_visibility.py](../../cleave/viz/layer_visibility.py). The strip draws the same breakpoints as variable-height bars.
- `preset_switching: timeline` advances a seek-stable rotation on each rise from zero; per-cue `role` casts from `preset_root/roles/<role>/` when set.
- Per-stem envelopes in `signals.json` (version 4) drive live Cleave effects ([cleave/effects/](../../cleave/effects/)) and, when the staged conductor row is on, generative timeline Apply via [cleave/timeline_presets/conductor.py](../../cleave/timeline_presets/conductor.py).
- Closed-loop visual limiter ducks overlapping busyness at runtime ([cleave/viz/visual_limiter.py](../../cleave/viz/visual_limiter.py)).

---

## Idea 1: Arrangement as a mix, not a gate (done)

Cues are level keyframes with optional blend and role (`SlotCue(t, level, blend?, role?)`), fade groups become constant-slope ramps on a piecewise-linear envelope, the strip draws variable-height bars, and crescendo ramps entrants in from `LEVEL_QUANTUM` through every quantised step to a full stack. Layer opacity stays the static fader; the lane multiplies into `fbo.opacity` as before. Per-cue blend writes `LayerFbo.blend_mode` each frame ([cleave/blend_modes.py](../../cleave/blend_modes.py)); per-cue role casts from `preset_root/roles/<role>/` on rises from zero. Blend and role are authored on on / visible cues (the next period), not on disable cues; off cues are stripped of both in `canonicalize`.

### What landed

1. Cue model and persist: `level` required in YAML; optional `blend` / `role`; baseline is `float | None` ([cleave/config_schema.py](../../cleave/config_schema.py)).
2. Envelope: `lane_level_breakpoints` / `lane_level_envelope` replace edge-only fade alpha; rise completes at cue time, fall starts at cue time; slopes scale with level delta.
3. Runtime: `timeline_level` / `timeline_level_multiplier`; levels apply even when both fade groups are disabled (piecewise-constant envelope).
4. Preset-switch trigger: rise from zero only; `cue.t - fade_in * cue.level`.
5. Generator: `cues_from_states` emits level mappings; crescendo climbs each entrant from `LEVEL_QUANTUM` to full.
6. Strip: polygon fill from breakpoints; committed eye alpha follows level.
7. Blend: held like level via `lane_blend_at`; applied per frame in `apply_layer_visibility` with layer static fallback.
8. Role: event property on on-transitions; seek-stable per-role pools in [cleave/viz/preset_switching.py](../../cleave/viz/preset_switching.py); empty pool falls back to the main rotation.
9. Strip authoring: `,` / `.` select on cues (`level > 0`, including mid-on changes; offs skipped); `Shift` / `Ctrl` + `,` / `.` nudge selected cue timeline opacity by 1% / 10% (floor 10% so the cue is not erased; multiplies into the layer opacity fader; YAML field stays `level`); `b` / `c` cycle blend and cast on those only; selected tick highlight, role glyphs on on cues, and badge readout (`opacity N%`).

### User effort

None for 0/1 lanes. Partial timeline opacity comes from generative Apply (crescendo / conductor) or manual `Shift`/`Ctrl` + `,`/`.` on a selected on cue. Blend and role are authorable on selected on cues in the strip; place milk files under `preset_root/roles/<role>/` for casting.

---

## Idea 2: Stem conductor (done)

Opt-in staged `conductor` row under timeline preset. When on and `signals.json` is present (version 4), Apply builds a [StemConductor](../../cleave/timeline_presets/conductor.py) from full-mix energy ranks and per-slot stem presence, scales the character budget, biases solo rotation and chord picks toward active stems, emits continuous cue levels quantised to `LEVEL_QUANTUM` (active slots never land between 0 and 0.25; near-silent phrases keep one slot at 0.25), and assigns per-slot cast roles and blends on on-cues (`cast_for_state`: drums with activity -> pulse/add; highest non-pulse -> lead; rest -> bed; near-silent -> bed; one lead max). Missing signals notify and fall through to plain arrangement. `other` carries `rms` alongside `spectral_centroid`.

### What landed

1. Signals: `other.rms` in extract/analyse; `SIGNALS_VERSION = 4`; `Signals.window_mean` for phrase and state windows.
2. Conductor module: phrase energy ranks, per-slot activity, rotation hint, chord score, `level_states`, `cast_for_state`; staging helpers mirror density.
3. Arranger hooks: optional `signals` / `slot_stems` on all four builders into `compose_timeline`; UI toggle expressed by whether Apply passes those kwargs.
4. Panel: `timeline.preset.conductor` persisted; confirm modal lists `conductor: on|off`.

### Tuning notes

Raw stem envelopes are not comparable across stems: drum onset strength is
spiky and low-mean while rms is dense and high-mean, so a raw comparison hands
the same slot the lead in nearly every phrase. The conductor therefore
standardises each slot **within the song**: `slot_activity` is a rank fraction
across phrases, so activity reads as "busier than usual for this stem" and every
slot averages the same. A raw presence below `_SLOT_SILENCE_FLOOR` gates to
zero so a dead stem never ranks as a lead, and a flat envelope resolves to the
neutral midpoint instead of a spurious ranking.

| Constant | Role | Turn it when |
| --- | --- | --- |
| `CONDUCTOR_GAIN_MIN` / `CONDUCTOR_GAIN_MAX` | Budget multiplier by phrase energy rank; the pair sums to 2.0 so the mean gain is exactly 1.0 | Loud phrases should unlock denser chords (raise the max, lower the min to match) |
| `CONDUCTOR_CEILING_MIN` / `CONDUCTOR_CEILING_EXPONENT` | Lead level from phrase energy relative to the song peak, not its rank, so only genuinely quiet passages dim; exponent steeps the curve so compressed masters still span quantised steps | Quiet passages should read darker (lower the min) or mid-song levels stay pinned at 1.0 (raise the exponent) |
| `CONDUCTOR_SUPPORT_FLOOR_BY_BIAS` | Lowest fraction of the lead level a supporting slot may take, per density bias; kept below ~0.70 so dense stacks still duck into 0.5/0.75 | Overlap still reads as one layer plus ghosts (raise the table carefully; too high flattens to binary) |
| `AIRTIME_PENALTY` | Penalty on a slot's share of accumulated airtime above an even share | One slot still holds too much screen time |
| `CONDUCTOR_ACTIVITY_MIDPOINT` | Neutral point subtracted in `chord_score`, so chord size is scored on quality only and larger chords are not penalised | Never, it is fixed by the rank standardisation |

Crescendo shares the level model: entrants appear at `LEVEL_QUANTUM` and climb
through every quantised step to a full stack at `t_full`, spread over
`max(entrants + 1, 1 / LEVEL_QUANTUM)` evenly spaced times snapped to nearby
bars. Ramps are only visible when a timeline fade group is enabled; both groups
default to disabled, which turns every level change into a hard step.

### Stem presence keys

| Stem | Fields | Reads as |
| --- | --- | --- |
| drums | `onset_strength` | onset density, fills |
| bass | `rms`, `sub_bass`, `mid_bass` | foundation presence |
| vocals | `rms`, `pitch_hz` | lead activity, phrase ends |
| other | `rms`, `spectral_centroid` | presence plus color/brightness |
| full_mix | `onset_strength`, `rms` | global energy, section contrast |

### User effort

Run `separate` (required for beats and v4 envelopes; re-run on existing projects after the schema bump), stage conductor on, then Apply. No new markers.

---

## Closed-loop visual limiter (done)

Runtime sidechain-style limiter shared by live play and offline render. After the composite (and HDR display shoulder when active), [cleave/viz/visual_limiter.py](../../cleave/viz/visual_limiter.py) samples a downsampled luma grid, combines mean luma with mean absolute frame delta into busyness, and on the next frame multiplies a separate `StemLayer.limiter_gain` into opacity (authored `timeline_level` and strip eyes are unchanged). Active when timeline levels apply and `timeline.limiter.enabled` is true; skipped for blank visualizers, preset curation, solo, recording, preview, and when the panel toggle is off.

### Panel (Render: TIMELINE)

Sibling expandable section after **timeline preset** (before **reset timeline**), not under the Apply-staged preset knobs:

```
Render: TIMELINE
  ...
  └─ visual limiter
       └─ enabled: on / off
       └─ threshold
       └─ ratio
       └─ release
```

**Left/Right** on the header expands and collapses (`visual_limiter_expanded`, session-only). The **enabled** child is on/off; threshold, ratio, and release hide when off. Locked with the timeline section.

| Knob | YAML | Default | Range / display |
| --- | --- | --- | --- |
| enabled | `timeline.limiter.enabled` | `true` | on/off |
| threshold | `timeline.limiter.threshold` | `0.65` | 0.40-0.90; panel shows 40%-90%. Maps to trip-on; off-threshold stays 0.17 below |
| release | `timeline.limiter.release` | `0.45` | 0.15-1.5 s; panel shows seconds. Maps to release ramp; hold time scales at 0.75/0.45 |

Attack, duck gain, and delta weight stay fixed (not panel knobs).

### What landed

1. Sensor in [cleave/viz/frame_finish.py](../../cleave/viz/frame_finish.py) after the HDR shoulder, before highlight rolloff / chroma / fade / overlay.
2. Controller state on `VisualizerCore.visual_limiter` (gains / hysteresis; not YAML): role/z-order victim pick, playhead-timed attack/release ramps, seek reset. Trip and release times come from session `timeline.limiter`.
3. Actuator: `limiter_gain` on [cleave/viz/layer.py](../../cleave/viz/layer.py); opacity multiply in [cleave/viz/layer_pipeline.py](../../cleave/viz/layer_pipeline.py); gains applied in `tick_frame_core` after `apply_layer_visibility`.
4. Priority via `lane_role_at` in [cleave/timeline.py](../../cleave/timeline.py): duck `bed` before `accent` before `pulse` before `lead`; missing role ranks as `pulse`; ties break on lower level, then earlier `layer_z_order`.

### Fixed constants

| Constant | Value | Role |
| --- | --- | --- |
| `DELTA_WEIGHT` | 0.85 | Motion term in `mean_luma + k * mean_abs_delta` |
| `DUCK_GAIN` | 0.50 | Opacity multiplier floor while ducked |
| `ATTACK_SEC` | 0.15 | Playhead seconds to ramp gain down to `DUCK_GAIN` |
| `SEEK_JUMP_SEC` | 0.25 | Playhead jump that clears gains and prev grid |
| `GRID_WIDTH` x `GRID_HEIGHT` | 32 x 18 | Downsample readback grid |

Schema defaults for threshold / release match the tuned constants above. Attack and release are playhead-timed ramps (not wall-clock or fps) so live and offline stay aligned without instant opacity snaps.

---

## Implementation order (done)

| Order | Item | Status |
| --- | --- | --- |
| 1 | Rich cues: levels | Done |
| 1b | Rich cues: blend and role | Done |
| 2 | Stem conductor | Done |
| 3 | Closed-loop visual limiter | Done |
| 4 | Reactivity fingerprints and casting | [roadmap.md](../roadmap.md) |
| 5 | Reprise and auto form | [roadmap.md](../roadmap.md) |

Breathing / Dialogue / Arc / Pulse remain character profiles that bias switch rate, climax placement, and density, not the only intelligence in the system.

---

## Non-goals

- Undo/redo (tracked in [roadmap.md](../roadmap.md)).
- MIDI out, web or Butterchurn port, live sliding-window Demucs.
- Six-stem Demucs as a prerequisite; named guitar and piano voices would strengthen the conductor but are not required.
- Replacing manual timeline edit, arm and record, or snap tools. Generative Apply remains a starting point the user can polish.
- Per-cue arbitrary parameter automation (effect depths, post-FX). Blend and preset role are shipped; further cue fields stay out of scope.
