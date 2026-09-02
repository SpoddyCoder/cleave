# Roadmap

Aspirational ideas. Not scheduled; revisit when the core workflow feels solid.


## Nuitka freeze

Phase 2 Windows MVP ships PyInstaller ([structured-releases.md](structured-releases.md)). Revisit Nuitka after a working Windows zip exists, for possible faster startup and a tighter native binary. Same onedir layout, sidecars, and data dirs; not a reason to reopen the Phase 2 freezer choice.

## Undo feature

Session undo/redo for timeline and config edits.

## Timeline richer cue types

Extend cues beyond visibility toggles so timeline events can control more layer and render parameters.

## Preset reactivity fingerprints

Classify presets by how they **respond** to audio, not only by how they look, then cast presets to the stem driving that slot. A preset that erupts on kick drums is a great drums layer and a dead bass bed; a static luma histogram cannot tell those apart.

From [completed/improved-timeline-presets.md](completed/improved-timeline-presets.md). Ship fingerprints first, then automatic casting.

### Intent

- Stop three dense presets from lighting at once under black-key (or any) blend.
- Make `preset_switching: timeline` content-aware instead of a shuffled bag.
- Know which presets can sit at low opacity as a bed without looking inert (needs a motion floor, not a brightness average).
- Reuse curation (`favourites/`) rather than asking users to tag files.
- Fill `preset_root/roles/<role>/` pools from fingerprints instead of hand curation; extend the generative arranger with automatic blend/role assignment on Apply.

### Design sketch

Classify each preset by how it responds to audio (silence, bass, transients, sustained tone) into a small vector: bass response, transient response, motion floor under silence, brightness, screen coverage, busyness. Derive pools from that vector, favourites first, then directory:

| Role | Vector signature | Casting rule |
| --- | --- | --- |
| Bed | low busyness, non-zero motion floor, mostly black | bass or other foundation slots |
| Pulse | high transient response, mid coverage | drums slots |
| Lead | high busyness or brightness | at most one hot at a time |
| Accent | short bright bursts, high delta | chorus hits, marker edges |

Cast on each on-transition in [cleave/viz/preset_switching.py](../cleave/viz/preset_switching.py) through the cue `role` field: when set, index `role_rotations[role]` by per-role occurrence; when unset or the pool is empty, use the main rotation.

Timeline rotation advance already keys off committed on-transitions.

Optional: CLIP or similar embeddings on short clips if heuristics mislabel calm versus chaotic too often.

### User effort

Curate favourites once. Casting is automatic on Apply and playback.

## Reprise and auto form

Detect song form automatically, and when the song repeats, bring back the **same** arrangement: same cast, same milk files, same blend plan, with one thing escalated. Recognition is what makes a video read as composed; random-but-musical still reads as random.

From [completed/improved-timeline-presets.md](completed/improved-timeline-presets.md). Can ship in halves: suggested markers first (useful alone), cluster reprise second.

### Intent

- Close the structure gap without asking the user to drop every marker by hand.
- Give section-scale drama (breakdown solo, chorus lift) that bar-only partitioning cannot invent.
- Make the visuals have motifs at song scale, not only at phrase scale.
- Bias the stem conductor curve by section role (intro, verse, chorus, bridge, and similar) rather than replacing it.

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

## MIDI out

Emit MIDI notes or CC from drum onsets (and other signals in `signals.json`) to drive hardware lighting, drum pads, or synths during playback or export.

## projectM beat sensitivity

Cleave multiplies PCM by beat sensitivity in [cleave/projectm.py](../cleave/projectm.py) `feed_pcm` (default 2.0). That is intentional: after projectM's 2023 audio rewrite ([69d2134](https://github.com/projectM-visualizer/projectm/commit/69d2134fa2c39901eb354eac546c09e1be5c794b)), `projectm_set_beat_sensitivity` became a store-only stub. Older projectM applied sensitivity as a PCM scale via `BeatDetect::GetPCMScale()` (see [issue #161](https://github.com/projectM-visualizer/projectm/issues/161)); Cleave recreates that outside the library so presets stay reactive.

Side effect: louder PCM also affects hard-cut detection, so the beat-sensitivity knob is not fully independent of hard-cut sensitivity.

Watch upstream: if libprojectM wires beat sensitivity back into the audio path, drop the PCM pre-scale and rely on the native API again. Until then, keep the workaround.

## Named hardcut profiles

Inspired by [MilkDrop3](https://github.com/milkdrop2077/MilkDrop3) hardcut modes: named profiles (bass/treb thresholds, minimum delay, load-next vs inject-effect) instead of only continuous `hard_cut_sensitivity`. Would sit beside existing projectM preset switching and stem-driven hard cuts.

## Geometric transition wipes

Layer-local wipe shaders (plasma, checkerboard, curtain, and similar) when a layer changes preset, beyond projectM's soft crossfade. Implement in the OpenGL compositor during A-to-B preset changes. Reuse the pattern-mask shader library ([cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py), [cleave/pattern_mask.py](../cleave/pattern_mask.py)); same generators, different trigger (preset change on one layer vs territory layout across the stack). See [completed/pattern-mask.md](completed/pattern-mask.md).

## Preset rotation history

Never-repeat (or short cooldown) in shuffle/random rotation, plus a "previous preset" step for browsing. Small UX win for long live sessions and offline renders.

## Pattern mask follow-ups

Core v1 is shipped: shader composite, four patterns (strips, radial, checker, plasma), feather, seed, conductor `pattern_mask` mode, and slot-set transition wipes. See [completed/pattern-mask.md](completed/pattern-mask.md).

### Dynamic masks

- Per-phrase pattern variation via conductor (pattern type and density as cue properties).
- Timeline automation of pattern type.
- Audio-reactive region weights from per-stem energy envelopes.

### Layout and mapping

- Explicit stem-role mapping (which region family the mix owns).
- Layer order control (visible stack order vs mix special-case).
- Radial mix-in-center option.

### Polish

- Tie Settings preview quality to mask generation resolution (full for `full-quality`, scaled for `balanced` / `performance` / `ultra-performance`; offline render stays full-res).
- Cache transition weight fields on mask param changes so layer visibility toggles reuse ready old/target weights when type/density/seed are unchanged.
- Weight-field morphs still generate at 1/4 content resolution during transitions; consider aligning with preview quality after settle.

## Web / browser port

Port playback and compositing to the browser. `signals.json` is already portable JSON; [Butterchurn](https://github.com/jberg/butterchurn) is a JS Milkdrop renderer that could replace libprojectM for a shareable viewer.

## Deeper stem separation with Demucs

Cleave today uses the standard four-stem split: drums, bass, vocals, other. Demucs can do more if you want finer control later.

**What is possible today (no new research required):**

| Capability | How | Cleave use |
| --- | --- | --- |
| Four-stem split | `htdemucs` (fast) or `htdemucs_ft` (higher quality) | Current default; one Milkdrop layer per stem |
| Six-stem split | `htdemucs_6s` model adds **guitar** and **piano** | Two extra layers or replace `other` with more targeted stems |
| Two-stem mode | `--two-stems=vocals` (or drums, etc.) | Quick vocal isolation pass; less useful when running a full multi-layer stack |
| Re-run on a stem | Separate `drums.wav` again with a different model | Experimental; quality varies; not a built-in kick/snare/hihat mode |

**Kick / snare / hihat:** HTDemucs does **not** ship a first-class drum-kit split. Getting individual drum pieces usually means either (a) running a specialised percussion model on the drum stem, (b) classical onset/spectral heuristics on `drums.wav`, or (c) a custom fine-tuned separator. All are feasible side projects but not drop-in Demucs flags.

**Other directions worth knowing about:**

- **Fine-tuned models** (`htdemucs_ft`): better bleed control on dense mixes; already exposed as `--high-quality` on `separate`.
- **GPU batching**: faster turnaround when separating many tracks before a visual session.
- **Shorter clips**: Demucs on full albums is slow; chunking or stem caching (already partially there via skip-if-exists) scales better for catalogue work.
- **Live-ish separation**: sliding-window Demucs on a ring buffer (high latency, heavy CPU/GPU) could feed stems to Cleave in near real time; see also MIDI out for lower-latency drum triggers without full re-separation.

None of the above is required for the current editor (default four layers, up to eight). Pick one when a concrete creative need shows up (e.g. guitar gets its own preset stack, or drum layers need independent bloom).
