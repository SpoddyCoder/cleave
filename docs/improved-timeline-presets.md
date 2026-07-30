# Improved timeline presets

Aspirational directions for generative timeline authoring. Goal: visuals that feel tied to the song, avoid stacking too many busy presets, keep multi-layer compositing as the core of Cleave, and need almost no user input beyond Apply.

Related: [completed/song-markers.md](completed/song-markers.md), [roadmap.md](roadmap.md), [cleave/timeline_presets/](../cleave/timeline_presets/), [cleave/signals.py](../cleave/signals.py).

Naming: **cue** remains a per-lane transition. **Song markers** remain project-scoped structure points in `project.yaml`.

---

## Current baseline

What works today:

- Generative characters (Breathing, Dialogue, Arc, Pulse) in [cleave/timeline_presets/](../cleave/timeline_presets/) arrange layer levels with phrase grids, motif voice-leading, density bias, and optional crescendo.
- Beat This! downbeats in `signals.json` drive the bar grid; manual song markers act as hard section walls and soft latch (~5s) at generation time.
- Each layer is its own projectM instance fed stem PCM; black-key (and other) blends stack them in [cleave/gl_compositor.py](../cleave/gl_compositor.py).
- Cue levels drive continuous opacity: `lane_level_breakpoints` / `lane_level_envelope` in [cleave/timeline.py](../cleave/timeline.py) feed `layer.timeline_level` via `apply_layer_visibility` in [cleave/viz/layer_visibility.py](../cleave/viz/layer_visibility.py). The strip draws the same breakpoints as variable-height bars.
- `preset_switching: timeline` advances a seek-stable rotation on each rise from zero; the milk file is not chosen per cue.
- Per-stem envelopes in `signals.json` (version 4) drive live Cleave effects ([cleave/effects/](../cleave/effects/)) and, when the staged conductor row is on, generative timeline Apply via [cleave/timeline_presets/conductor.py](../cleave/timeline_presets/conductor.py).

Gaps the ideas below target:

1. The arranger still does not assign blend or role automatically (levels and stem gating are shipped; automatic mix assignment remains deferred).
2. Song form still needs manual markers for the best results.
3. Busy collisions often come from milk personality; role casting helps when pools are curated, but automatic pool fill needs Idea 3 fingerprints.
4. Nothing recurs. Chorus 2 gets a fresh roll of the dice, so the output reads as plausible-but-random rather than composed.

---

## Idea 1: Arrangement as a mix, not a gate (shipped: levels, blend, role)

**Shipped:** cues are level keyframes with optional blend and role (`SlotCue(t, level, blend?, role?)`), fade groups become constant-slope ramps on a piecewise-linear envelope, the strip draws variable-height bars, and crescendo ramps entrants in from `LEVEL_QUANTUM` through every quantised step to a full stack. Layer opacity stays the static fader; the lane multiplies into `fbo.opacity` as before. Per-cue blend writes `LayerFbo.blend_mode` each frame ([cleave/blend_modes.py](../cleave/blend_modes.py)); per-cue role casts from `preset_root/roles/<role>/` on rises from zero. Blend and role are authored on on / visible cues (the next period), not on disable cues; off cues are stripped of both in `canonicalize`.

**Deferred** (still part of the mix vision, not implemented):

- Record toggles still write `0.0` / `1.0` (partial timeline opacity is Apply or strip nudge).
- Automatic blend/role assignment from the generative arranger (Idea 3).

### Intent

- Let the arranger duck a layer instead of muting it. A chorus becomes one lead at full weight and a bed at half, rather than "four layers on".
- Turn the anti-busy rule into a mix rule (total visual weight budget) instead of a layer count.
- Reuse compositing capability the renderer already has but the timeline could not address with booleans alone.
- Let a cue pick a milk personality via role without replacing the whole layer rotation.

### What landed

1. Cue model and persist: `level` required in YAML; optional `blend` / `role`; baseline is `float | None` ([cleave/config_schema.py](../cleave/config_schema.py)).
2. Envelope: `lane_level_breakpoints` / `lane_level_envelope` replace edge-only fade alpha; rise completes at cue time, fall starts at cue time; slopes scale with level delta.
3. Runtime: `timeline_level` / `timeline_level_multiplier`; levels apply even when both fade groups are disabled (piecewise-constant envelope).
4. Preset-switch trigger: rise from zero only; `cue.t - fade_in * cue.level`.
5. Generator: `cues_from_states` emits level mappings; crescendo climbs each entrant from `LEVEL_QUANTUM` to full.
6. Strip: polygon fill from breakpoints; committed eye alpha follows level.
7. Blend: held like level via `lane_blend_at`; applied per frame in `apply_layer_visibility` with layer static fallback.
8. Role: event property on on-transitions; seek-stable per-role pools in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py); empty pool falls back to the main rotation.
9. Strip authoring: `,` / `.` select on cues (`level > 0`, including mid-on changes; offs skipped); `Shift` / `Ctrl` + `,` / `.` nudge selected cue timeline opacity by 1% / 10% (floor 10% so the cue is not erased; multiplies into the layer opacity fader; YAML field stays `level`); `b` / `c` cycle blend and cast on those only; selected tick highlight, role glyphs on on cues, and badge readout (`opacity N%`).

Overlaps [roadmap.md](roadmap.md) richer cue types; automatic blend/role assignment from stem content and fingerprints remains Idea 3.

### User effort

None for 0/1 lanes. Partial timeline opacity comes from generative Apply (crescendo / conductor) or manual `Shift`/`Ctrl` + `,`/`.` on a selected on cue. Blend and role are authorable on selected on cues in the strip; place milk files under `preset_root/roles/<role>/` for casting.

---

## Idea 2: Stem conductor (shipped: opt-in audio-aware arrange)

**Shipped:** an opt-in staged `conductor` row under timeline preset. When on and `signals.json` is present (version 4), Apply builds a [StemConductor](../cleave/timeline_presets/conductor.py) from full-mix energy ranks and per-slot stem presence, scales the character budget, biases solo rotation and chord picks toward active stems, and emits continuous cue levels quantised to `LEVEL_QUANTUM` (active slots never land between 0 and 0.25; near-silent phrases keep one slot at 0.25). Missing signals notify and fall through to plain arrangement. `other` now carries `rms` alongside `spectral_centroid`.

**Deferred** (still part of the conductor vision, not implemented):

- Section-role bias from auto form (Idea 4).
- Automatic blend or role assignment from stem content (Idea 1 deferred / Idea 3).

### Intent

- Tie lane activity to the Demucs split the user already paid for.
- Cap how much of the stack is hot at once so the composite stays readable.
- Keep Breathing / Dialogue / Arc / Pulse as feel knobs (switch rate, climax shape) while the conductor supplies who speaks and how loudly.

### What landed

1. Signals: `other.rms` in extract/analyse; `SIGNALS_VERSION = 4`; `Signals.window_mean` for phrase and state windows.
2. Conductor module: phrase energy ranks, per-slot activity, rotation hint, chord score, `level_states`; staging helpers mirror density.
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

The rest of the curve exists to keep the conductor a redistribution rather than
a global attenuator:

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

## Idea 3: Preset reactivity fingerprints

Classify presets by how they **respond** to audio, not only by how they look, then cast presets to the stem driving that slot. A preset that erupts on kick drums is a great drums layer and a dead bass bed; a static luma histogram cannot tell those apart.

### Intent

- Stop three dense presets from lighting at once under black-key (or any) blend.
- Make `preset_switching: timeline` content-aware instead of a shuffled bag.
- Know which presets can sit at low opacity as a bed without looking inert (needs a motion floor, not a brightness average).
- Reuse curation (`favourites/`) and the existing scan harness rather than asking users to tag files.

### Design sketch

The probe harness is most of the way there already. [cleave/preset_scan.py](../cleave/preset_scan.py) boots headless projectM into a 480x270 FBO, feeds PCM per frame, and reads back per-frame metrics with a warmup window and a metrics cache.

1. Replace the single constant probe (`_synthetic_pcm_burst`, a sine plus noise that is never silent) with a **probe set**: silence baseline, sub-bass sine, kick impulse train at fixed tempo, hi-hat noise bursts, sustained vocal-band tone.
2. Extend `FrameMetrics` in [cleave/preset_scan_metrics.py](../cleave/preset_scan_metrics.py) beyond luma and coverage with temporal frame delta and an edge or high-frequency energy proxy. Bump the metrics cache version.
3. Reduce to a per-preset vector: response to bass, response to transients, motion floor under silence, brightness, screen coverage, busyness.
4. Derive pools from that vector, favourites first, then directory:

| Role | Vector signature | Casting rule |
| --- | --- | --- |
| Bed | low busyness, non-zero motion floor, mostly black | bass or other foundation slots |
| Pulse | high transient response, mid coverage | drums slots |
| Lead | high busyness or brightness | at most one hot at a time |
| Accent | short bright bursts, high delta | chorus hits, marker edges |

5. Cast on each on-transition in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) through the cue `role` field (Idea 1b): when set, index `role_rotations[role]` by per-role occurrence; when unset or the pool is empty, use the main rotation. Idea 3 fills those role pools from fingerprints instead of hand curation. Keep play and scan in agreement on the rotation set (see [.cursor/rules/preset-scan-rotation-set.mdc](../.cursor/rules/preset-scan-rotation-set.mdc)).

### Fits existing code

- Scan CLI, golden set, and threshold tuning: [completed/presets-check-proposal.md](completed/presets-check-proposal.md), [completed/presets-scan-plan.md](completed/presets-scan-plan.md).
- Timeline rotation advance already keys off committed on-transitions.

### Libraries

Heuristic frame stats inside the existing harness should be enough. Optional: CLIP or similar embeddings on short clips if heuristics mislabel calm versus chaotic too often.

### User effort

Curate favourites once, run the scan once per pack (cached). Casting is automatic on Apply and playback.

---

## Idea 4: Reprise, and form from self-similarity

Detect song form automatically, and when the song repeats, bring back the **same** arrangement: same cast, same milk files, same blend plan, with one thing escalated. Recognition is what makes a video read as composed; random-but-musical still reads as random.

### Intent

- Close the structure gap without asking the user to drop every marker by hand.
- Give section-scale drama (breakdown solo, chorus lift) that bar-only partitioning cannot invent.
- Make the visuals have motifs at song scale, not only at phrase scale.

### Design sketch

1. At analyse time in [cleave/extract.py](../cleave/extract.py) and [cleave/analyse.py](../cleave/analyse.py), compute a beat-synchronous self-similarity matrix from chroma plus MFCC (librosa, no new heavy dependency), and write segment boundaries plus similarity cluster ids into `signals.json` (schema version bump).
2. Boundaries become **suggested song markers**, shown as today's red ticks and saved to `project.yaml` under the same deferred-write model as [completed/song-markers.md](completed/song-markers.md). The user corrects a few if needed.
3. `compose_timeline` generates one arrangement **per cluster**, not per section, and replays it at each recurrence with a deterministic variation seeded by occurrence index: add a layer, raise the lead, tighten switch rate.
4. Non-repeating material (bridge, breakdown) is identifiable precisely because it is unlike everything else in the matrix, so it gets the contrast treatment: solo one stem, or cut to black and re-enter on the next bar.
5. Section roles bias the conductor curve rather than replacing it:

| Section | Visual role |
| --- | --- |
| Intro / outro | single calm foundation layer |
| Verse | two layers, slow switches |
| Pre-chorus | rising weight toward the next wall |
| Chorus | peak weight, still under the busyness cap |
| Bridge / breakdown | solo one stem, others ducked |
| Drop | hard cut to black, re-entry on the next bar |

6. Hard walls, soft latch, and exclusive marker claiming stay as today; auto markers simply feed the same walls.

### Libraries

librosa first (chroma, MFCC, `segment.recurrence_matrix`, `agglomerative`). Escalate only if that misfires: [all-in-one](https://github.com/mir-aidj/all-in-one) (structure plus beats), [msaf](https://github.com/urinieto/msaf), or Essentia. Prefer one analyse-time dependency writing into the existing marker list rather than a parallel timeline format.

### User effort

Run `separate`, glance at suggested markers, Apply. Manual drop remains for stubborn tracks.

---

## Companion: closed-loop visual limiter (shipped)

**Shipped:** a runtime sidechain-style limiter shared by live play and offline render. After the composite (and HDR display shoulder when active), [cleave/viz/visual_limiter.py](../cleave/viz/visual_limiter.py) samples a downsampled luma grid, combines mean luma with mean absolute frame delta into busyness, and on the next frame multiplies a separate `StemLayer.limiter_gain` into opacity (authored `timeline_level` and strip eyes are unchanged). Active when timeline levels apply and `timeline.limiter.enabled` is true; skipped for blank visualizers, preset curation, solo, recording, preview, and when the panel toggle is off.

### Panel (Render: TIMELINE)

Sibling expandable section after **timeline preset** (before **reset timeline**), not under the Apply-staged preset knobs:

```
Render: TIMELINE
  ...
  └─ visual limiter: enabled / disabled
       └─ threshold
       └─ release
```

**Right** enables and expands (threshold and release visible). **Left** disables and collapses. Expand follows `timeline.limiter.enabled` (no separate flag). Header value shows enabled/disabled. Locked with the timeline section.

| Knob | YAML | Default | Range / display |
| --- | --- | --- | --- |
| enabled | `timeline.limiter.enabled` | `true` | on/off |
| threshold | `timeline.limiter.threshold` | `0.65` | 0.40-0.90; panel shows 40%-90%. Maps to trip-on; off-threshold stays 0.17 below |
| release | `timeline.limiter.release` | `0.45` | 0.15-1.5 s; panel shows seconds. Maps to release ramp; hold time scales at 0.75/0.45 |

Attack, duck gain, and delta weight stay fixed (not panel knobs).

### What landed

1. Sensor in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py) after the HDR shoulder, before highlight rolloff / chroma / fade / overlay.
2. Controller state on `VisualizerCore.visual_limiter` (gains / hysteresis; not YAML): role/z-order victim pick, playhead-timed attack/release ramps, seek reset. Trip and release times come from session `timeline.limiter`.
3. Actuator: `limiter_gain` on [cleave/viz/layer.py](../cleave/viz/layer.py); opacity multiply in [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py); gains applied in `tick_frame_core` after `apply_layer_visibility`.
4. Priority via `lane_role_at` in [cleave/timeline.py](../cleave/timeline.py): duck `bed` before `accent` before `pulse` before `lead`; missing role ranks as `pulse`; ties break on lower level, then earlier `layer_z_order`.

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

## Combined pipeline

Strongest end state with almost no UX surface:

1. **Form** proposes markers and similarity clusters at analyse time.
2. **Stem conductor** builds a visual weight budget and per-stem gates inside those sections.
3. **Rich cues** express the result as a mix: levels and blends, not just on and off.
4. **Role casting** fills each active slot from a reactivity-matched pool so only one Lead is hot.
5. **Reprise** replays each cluster's arrangement with escalation on recurrence.
6. **Limiter** cleans up whatever still collides.

Breathing / Dialogue / Arc / Pulse remain character profiles that bias switch rate, climax placement, and density, not the only intelligence in the system.

---

## Suggested implementation order

| Order | Item | Why here | Payoff | Effort |
| --- | --- | --- | --- | --- |
| 1 | Rich cues: levels (Idea 1, shipped) | Enabler; everything else wants levels, not booleans | Better output immediately, even with today's arranger | Done |
| 1b | Rich cues: blend and role (Idea 1, shipped) | Completes the mix vision; casting uses the cue role field | Medium | Done |
| 2 | Stem conductor (Idea 2, shipped) | Uses data already in `signals.json`; first thing that makes lanes song-tied | High | Done |
| 3 | Closed-loop limiter (companion, shipped) | Cheap once levels exist; buys headroom before casting lands | Medium | Done |
| 4 | Reactivity fingerprints and casting (Idea 3) | Probe harness exists; fixes busy-on-busy at the milk level | High | High (probe set, metrics, pools, casting) |
| 5 | Reprise and auto form (Idea 4) | Highest ceiling, most analysis risk; benefits from 1 to 4 being in place | High | High (analyse dependency, marker suggestions, arranger restructure) |

Sequencing notes:

- Levels (1) and stem conductor (2) are shipped and together cover most of the "feels tied to the song" goal.
- Step 4 can ship in halves: fingerprints and a scan report first, casting second.
- Step 5 can ship in halves: suggested markers first (useful alone), cluster reprise second.

---

## Non-goals

- Undo/redo (tracked in [roadmap.md](roadmap.md)).
- MIDI out, web or Butterchurn port, live sliding-window Demucs.
- Six-stem Demucs as a prerequisite; named guitar and piano voices would strengthen the conductor but are not required by any step above.
- Replacing manual timeline edit, arm and record, or snap tools. Generative Apply remains a starting point the user can polish.
- Per-cue arbitrary parameter automation (effect depths, post-FX). Idea 1 blend and preset role are shipped; further cue fields stay out of scope here.
