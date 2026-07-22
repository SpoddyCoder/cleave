# Roadmap

Aspirational ideas. Not scheduled; revisit when the core workflow feels solid.


## Undo feature

Session undo/redo for timeline and config edits.

## Timeline richer cue types

Extend cues beyond visibility toggles so timeline events can control more layer and render parameters.

## MIDI out

Emit MIDI notes or CC from drum onsets (and other signals in `signals.json`) to drive hardware lighting, drum pads, or synths during playback or export.

## projectM PCM feeding

Investigate PCM feeding strategy for the projectM buffer. Only the last ~11 ms (480 samples at 44.1 kHz) is actively used per render; at low FPS Cleave feeds a much longer timeslice per frame. Explore whether sampling or aggregating across the full frame timeslice (not just the tail) improves visual matchup with audio. Uncertain payoff; worth exploring.

## projectM beat sensitivity

Cleave multiplies PCM by beat sensitivity in [cleave/projectm.py](../cleave/projectm.py) `feed_pcm` (default 2.0). That is intentional: after projectM's 2023 audio rewrite ([69d2134](https://github.com/projectM-visualizer/projectm/commit/69d2134fa2c39901eb354eac546c09e1be5c794b)), `projectm_set_beat_sensitivity` became a store-only stub. Older projectM applied sensitivity as a PCM scale via `BeatDetect::GetPCMScale()` (see [issue #161](https://github.com/projectM-visualizer/projectm/issues/161)); Cleave recreates that outside the library so presets stay reactive.

Side effect: louder PCM also affects hard-cut detection, so the beat-sensitivity knob is not fully independent of hard-cut sensitivity.

Watch upstream: if libprojectM wires beat sensitivity back into the audio path, drop the PCM pre-scale and rely on the native API again. Until then, keep the workaround.

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
