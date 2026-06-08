# Roadmap

Aspirational ideas. Not scheduled; revisit when the core workflow feels solid.

## MIDI out

Emit MIDI notes or CC from drum onsets (and other signals in `signals.json`) to drive hardware lighting, drum pads, or synths during playback or export.

## Preset randomiser

Auto-pick or cycle Milkdrop presets per layer on a timer, at section boundaries, or when beat energy crosses a threshold. Useful for long sessions without manual browsing.

## Web / browser port

Port playback and compositing to the browser. `signals.json` is already portable JSON; [Butterchurn](https://github.com/jberg/butterchurn) is a JS Milkdrop renderer that could replace libprojectM for a shareable viewer.

## Audio performance

Today heard audio goes through `pygame.mixer.music` on the same process and main thread as OpenGL/projectM rendering. Heavy presets can cause clicks or dropouts even when average CPU and GPU use stay low (tail latency and small default mixer buffers, not sustained overload).

**Target design:**

- Preload the mix to PCM at startup (same idea as stem PCM for libprojectM).
- Play out via `sounddevice` or an SDL audio callback on a dedicated thread, with a ring buffer and a larger device buffer.
- Drive the visual loop from the audio clock: `t_sec = samples_played / sample_rate` instead of wall-clock `pygame.time.get_ticks()`.
- Drop `pygame.mixer` entirely once the new path covers play, pause, and seek.

This decouples frame rate from playback and should eliminate preset-dependent glitches without sacrificing A/V sync.

## Deeper stem separation with Demucs

Cleave today uses the standard four-stem split: drums, bass, vocals, other. Demucs can do more if you want finer control later.

**What is possible today (no new research required):**

| Capability | How | Cleave use |
| --- | --- | --- |
| Four-stem split | `htdemucs` (fast) or `htdemucs_ft` (higher quality) | Current default; one Milkdrop layer per stem |
| Six-stem split | `htdemucs_6s` model adds **guitar** and **piano** | Two extra layers or replace `other` with more targeted stems |
| Two-stem mode | `--two-stems=vocals` (or drums, etc.) | Quick vocal isolation pass; less useful for the four-layer stack |
| Re-run on a stem | Separate `drums.wav` again with a different model | Experimental; quality varies; not a built-in kick/snare/hihat mode |

**Kick / snare / hihat:** HTDemucs does **not** ship a first-class drum-kit split. Getting individual drum pieces usually means either (a) running a specialised percussion model on the drum stem, (b) classical onset/spectral heuristics on `drums.wav`, or (c) a custom fine-tuned separator. All are feasible side projects but not drop-in Demucs flags.

**Other directions worth knowing about:**

- **Fine-tuned models** (`htdemucs_ft`): better bleed control on dense mixes; already exposed as `--slow` on separate.
- **GPU batching**: faster turnaround when separating many tracks before a visual session.
- **Shorter clips**: Demucs on full albums is slow; chunking or stem caching (already partially there via skip-if-exists) scales better for catalogue work.
- **Live-ish separation**: sliding-window Demucs on a ring buffer (high latency, heavy CPU/GPU) could feed stems to Cleave in near real time; see also MIDI out for lower-latency drum triggers without full re-separation.

None of the above is required for the current four-layer visualizer. Pick one when a concrete creative need shows up (e.g. guitar gets its own preset stack, or drum layers need independent bloom).
