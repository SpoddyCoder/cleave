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
- Per-stem envelopes in `signals.json` drive live Cleave effects ([cleave/effects/](../cleave/effects/)), not timeline generation.

Gaps the ideas below target:

1. The arranger still emits level-only cues; it does not yet assign blend or role automatically.
2. The arranger is musically phrased but not stem-content-aware: it never looks at what the drums or vocals are doing.
3. Song form still needs manual markers for the best results.
4. Busy collisions often come from milk personality; role casting helps when pools are curated, but automatic pool fill needs Idea 3 fingerprints.
5. Nothing recurs. Chorus 2 gets a fresh roll of the dice, so the output reads as plausible-but-random rather than composed.

---

## Idea 1: Arrangement as a mix, not a gate (shipped: levels, blend, role)

**Shipped:** cues are level keyframes with optional blend and role (`SlotCue(t, level, blend?, role?)`), fade groups become constant-slope ramps on a piecewise-linear envelope, the strip draws variable-height bars, and crescendo ramps entrants in at `0.5` before a full stack. Layer opacity stays the static fader; the lane multiplies into `fbo.opacity` as before. Per-cue blend writes `LayerFbo.blend_mode` each frame ([cleave/blend_modes.py](../cleave/blend_modes.py)); per-cue role casts from `preset_root/roles/<role>/` on rises from zero. Blend and role are authored on on / visible cues (the next period), not on disable cues; off cues are stripped of both in `canonicalize`.

**Deferred** (still part of the mix vision, not implemented):

- Manual level authoring in the strip (record toggles still write `0.0` / `1.0`).
- Automatic blend/role assignment from the generative arranger (Idea 2 / Idea 3).

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
5. Generator: `cues_from_states` emits level mappings; crescendo uses `0.5` entrants.
6. Strip: polygon fill from breakpoints; committed eye alpha follows level.
7. Blend: held like level via `lane_blend_at`; applied per frame in `apply_layer_visibility` with layer static fallback.
8. Role: event property on on-transitions; seek-stable per-role pools in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py); empty pool falls back to the main rotation.
9. Strip authoring: `,` / `.` select on cues (`level > 0`, including mid-on changes; offs skipped); `b` / `c` cycle blend and cast on those only; selected tick highlight, role glyphs on on cues, and badge readout.

Overlaps [roadmap.md](roadmap.md) richer cue types; automatic assignment from stem content and fingerprints remains Idea 2 / Idea 3.

### User effort

None for 0/1 lanes. Partial levels come from generative Apply (crescendo). Blend and role are authorable on selected on cues in the strip; place milk files under `preset_root/roles/<role>/` for casting.

---

## Idea 2: Stem conductor

Treat each layer as a player that may only enter when its stem has something to say. Visibility becomes a consequence of audio, not only of motif vocabulary.

### Intent

- Tie lane activity to the Demucs split the user already paid for.
- Cap how much of the stack is hot at once so the composite stays readable.
- Keep Breathing / Dialogue / Arc / Pulse as feel knobs (switch rate, climax shape) while the conductor supplies who speaks and how loudly.

### Design sketch

1. From full-mix energy and onset novelty, build a **target weight curve** over time (sparse verse near one layer of weight, chorus two to three, drop to zero then punch back in).
2. **Gate and weight each slot** by its assigned stem using the `signals.json` envelopes that already exist at 100 Hz:

| Stem | Fields | Reads as |
| --- | --- | --- |
| drums | `onset_strength` | onset density, fills |
| bass | `rms`, `sub_bass`, `mid_bass` | foundation presence |
| vocals | `rms`, `pitch_hz` | lead activity, phrase ends |
| other | `spectral_centroid` | color and brightness |
| full_mix | `onset_strength`, `rms` | global energy, section contrast |

3. Apply **anti-busy rules** while filling the budget: prefer one bright accent over several; solo when one stem dominates; duck competing hot layers instead of cutting them (needs Idea 1 levels, which are available).
4. Emit ordinary lane cues. Phrase grid and song-marker walls still bound switch times.

### Fits existing code

- Arranger entry: [cleave/timeline_presets/arrange.py](../cleave/timeline_presets/arrange.py) `compose_timeline`, which already computes a per-phrase `budget` from the character envelope. The conductor replaces that scalar with an audio-derived curve and adds per-slot eligibility to motif scoring.
- Signal load: [cleave/signals.py](../cleave/signals.py); extract path: [cleave/extract.py](../cleave/extract.py). No new analyse output required.

### Libraries

Current stack; librosa envelopes are already written at analyse time. Optional later: [madmom](https://github.com/CPJKU/madmom) for cleaner onsets.

### User effort

Run `separate` (already required for beats), then Apply. No new markers.

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

## Companion: closed-loop visual limiter

Small, cheap, and catches collisions no offline classifier predicted. The post-FX stack in [cleave/gl_post_process.py](../cleave/gl_post_process.py) already resolves the composited frame, so a coarse mean-luma and frame-delta reduction per frame costs almost nothing. When the stack exceeds a busyness threshold, duck the lowest-priority hot layer; release when it drops. A sidechain compressor for the composite.

Depends on Idea 1 levels (available) and on offline determinism: the limiter must be a pure function of frame content so live preview and offline render in [cleave/viz/render.py](../cleave/viz/render.py) agree.

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
| 2 | Stem conductor (Idea 2) | Uses data already in `signals.json`; first thing that makes lanes song-tied | High | Medium (arranger plus signals) |
| 3 | Closed-loop limiter (companion) | Cheap once levels exist; buys headroom before casting lands | Medium | Low |
| 4 | Reactivity fingerprints and casting (Idea 3) | Probe harness exists; fixes busy-on-busy at the milk level | High | High (probe set, metrics, pools, casting) |
| 5 | Reprise and auto form (Idea 4) | Highest ceiling, most analysis risk; benefits from 1 to 4 being in place | High | High (analyse dependency, marker suggestions, arranger restructure) |

Sequencing notes:

- Levels (1) and stem conductor (2) are independently shippable and together cover most of the "feels tied to the song" goal.
- Step 4 can ship in halves: fingerprints and a scan report first, casting second.
- Step 5 can ship in halves: suggested markers first (useful alone), cluster reprise second.

---

## Non-goals

- Undo/redo (tracked in [roadmap.md](roadmap.md)).
- MIDI out, web or Butterchurn port, live sliding-window Demucs.
- Six-stem Demucs as a prerequisite; named guitar and piano voices would strengthen the conductor but are not required by any step above.
- Replacing manual timeline edit, arm and record, or snap tools. Generative Apply remains a starting point the user can polish.
- Per-cue arbitrary parameter automation (effect depths, post-FX). Idea 1 blend and preset role are shipped; further cue fields stay out of scope here.
