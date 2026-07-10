# Roadmap

Aspirational ideas. Not scheduled; revisit when the core workflow feels solid.


## Timeline v2
- Fade in/out on layer transitions
- External timeline file for very long cue lists

### Beat detection (cue snap) v2

Investigate [madmom](https://github.com/CPJKU/madmom): trained beat and downbeat models for stronger bar alignment and tempo-map quality than librosa alone. Same persisted grid feeds timeline snap and MIDI out; heavier analyse step and new dependency. (v1 librosa snap is in [todos.md](todos.md).)

## MIDI out

Emit MIDI notes or CC from drum onsets (and other signals in `signals.json`) to drive hardware lighting, drum pads, or synths during playback or export.

## projectM PCM feeding

Investigate PCM feeding strategy for the projectM buffer. Only the last ~11 ms (480 samples at 44.1 kHz) is actively used per render; at low FPS Cleave feeds a much longer timeslice per frame. Explore whether sampling or aggregating across the full frame timeslice (not just the tail) improves visual matchup with audio. Uncertain payoff; worth exploring.

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
