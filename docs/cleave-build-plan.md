# Cleave — Incremental Build Plan

**Cleave** is a stem-driven music visualizer. It splits audio into stems using Demucs, analyses each stem independently, and routes the resulting signals to layered visual effects — with the drum stem primarily driving pulse/beat response.

---

## Architecture Overview

```
Audio File
    │
    ▼
[Demucs] ── offline stem separation
    │
    ├── drums.wav  ──► onset / transient detection   ──► libprojectM (preset A) ──► layer 1
    ├── bass.wav   ──► low-freq amplitude envelope   ──► libprojectM (preset B) ──► layer 2
    ├── vocals.wav ──► pitch / amplitude             ──► libprojectM (preset C) ──► layer 3
    └── other.wav  ──► spectral content              ──► libprojectM (preset D) ──► layer 4
                                                                                        │
                                                                 [Cleave compositor] ◄──┘
                                                                         │
                                                                    final output
```

From Phase 5 onward, each libprojectM instance receives its stem's PCM audio (`projectm_pcm_add_float`), so presets react to isolated drums, bass, vocals, and other without custom uniform wiring. The `signals.json` pipeline from Phase 2 remains for analysis and future use.

---

## Phase 1 — Stem Separation Pipeline ✅
*Goal: get clean stems out of your own tracks. Validate quality before touching visuals.*

**1.1 — Environment setup** ✅
- Python 3.10+ virtual environment
- Install: `demucs`, `librosa`, `numpy`, `soundfile`, `torchcodec`
- FFmpeg (system or conda-forge) for Demucs and torchaudio I/O
- Verify CUDA if you have a GPU (Demucs is ~5–10x faster with one)

**1.2 — Run Demucs on a test track** ✅
- Output: `drums.wav`, `bass.wav`, `vocals.wav`, `other.wav` in a named folder per track
- Test on 2–3 of your own tracks with varying density

**1.3 — Validate drum stem quality** ✅
- Listen critically: is kick/snare bleed acceptable? Is the transient snap intact?
- Compared `htdemucs` (fast, good quality) vs `htdemucs_ft` (slow, higher quality)

**Stem split modes** (exposed via `python -m cleave separate`):

| Mode | Demucs model | CLI flag | Notes |
| --- | --- | --- | --- |
| Fast stem split | `htdemucs` | default | Good quality; much faster |
| Slow stem split | `htdemucs_ft` | `--slow` | Higher quality; use when bleed is unacceptable |

**✅ Milestone: stems folder with clean-ish drum, bass, vocal, other wavs for 3 tracks**

---

## Phase 2 — Per-Stem Signal Analysis ✅
*Goal: extract meaningful numbers from each stem that can drive visuals. Separate + analyse complete.*

**2.0 — `cleave separate` CLI** ✅
- Wrap Demucs: `cleave separate <audiofile>` → outputs stems to `stems/<trackname>/`
- **Fast stem split** (default): `-n htdemucs`
- **Slow stem split**: `--slow` → `-n htdemucs_ft`
- Reuse existing stems when present (skip re-separation unless `--force`)

**2.1 — Drum stem: onset detection**
- Use `librosa.onset.onset_strength()` on the drum stem
- Extract: onset strength envelope (continuous signal at native hop rate, resampled to 100 Hz in `signals.json`)
- Compare against running the same analysis on the *mixed* track — this is your proof of concept moment. The onsets on the drum stem should be dramatically cleaner for dense mixes.

**2.2 — Bass stem: low-frequency envelope**
- RMS amplitude over short windows (e.g. 20ms hops)
- Optionally: sub-bass vs mid-bass split (lowpass at ~120Hz)

**2.3 — Vocals: amplitude + rough pitch**
- RMS envelope
- `librosa.yin()` or `librosa.pyin()` for pitch tracking (useful for colour mapping later)

**2.4 — Other: spectral centroid / brightness**
- `librosa.feature.spectral_centroid()` — gives a sense of harshness/texture over time

**2.5 — Package it**
- Build `cleave analyse <stemsfolder>` → outputs a `signals.json` per track
- JSON contains time-series arrays for each signal at a consistent sample rate (e.g. 100 values/sec)
- This file is your interface between the audio world and the visual world — keep it clean

**✅ Milestone: `signals.json` for each track, plottable in matplotlib, drum onsets visibly sharper than mix onsets**

---

## Phase 3 — First Visual: Drum Pulse ✅
*Goal: the simplest possible visual driven by the drum stem. Prove the concept works.*

**3.1 — Choose your rendering stack**
- Recommendation for this phase: **pygame** (Python, minimal setup, immediate feedback)
- Later phases can graduate to a shader-based renderer — but start here to keep iteration fast

**3.2 — Basic pulse visualizer**
- Load `signals.json`, load and play the original mixed audio (via `pygame.mixer`)
- Each frame: read current playback time → look up onset strength from drum signal
- Draw a simple shape (circle, flash, radial burst) whose size/brightness maps to onset strength
- Aim for < 200 lines of code for this first version

**3.3 — Tune the feel**
- Attack/decay envelope: raw onset strength feels jittery — apply a fast-attack, slow-decay envelope (like a VU meter). Tweak until it *feels* punchy.
- Test on your densest, noisiest track. Does it pulse on the hits? That's the win.

**✅ Milestone: a window opens, music plays, something pulses visibly and correctly on the drum hits**

---

## Phase 4 — Add Layers ✅
*Goal: bring in bass and vocal/other signals as additional visual layers.*

**4.1 — Bass layer**
- Underneath the pulse layer: a slow, breathing warp or colour shift driven by bass RMS
- Keep it subtle — bass is continuous, not punchy, so it should feel like pressure not flicker

**4.2 — Vocal/other layer**
- Background texture or colour temperature driven by spectral centroid of "other"
- Pitch from vocals (where present) can shift hue — gives the visual a harmonic feel

**4.3 — Compositor**
- Render each layer to its own surface, blend with alpha
- Experiment with blend modes: additive blending works well for grungy/industrial aesthetics
- Keep layers togglable with keypresses (d=drums, b=bass, v=vocals, o=other) for live testing

**✅ Milestone: 3–4 visual layers running simultaneously, each noticeably responding to its stem**

---

## Phase 5 — Milkdrop Integration ✅
*Goal: replace pygame placeholder visuals with libprojectM, unlocking the full community preset library.*

By this point you have a working layered system you understand. Milkdrop becomes load-bearing infrastructure rather than a first-day gamble. Stem **PCM** drives each libprojectM instance (not `signals.json` uniforms). See [docs/phase-5-plan-part-progressed.md](docs/phase-5-plan-part-progressed.md) for session checkpoint detail.

**Target spec**

| Setting | Value |
| --- | --- |
| Window | 1280 x 720 |
| Frame rate | 30 fps |
| M1 spike stem | drums |
| Layer FBO sizes | other 640x360, bass/vocals 960x540, drums 1280x720 (upscale on composite) |
| Z-order (bottom to top) | other, bass, vocals, drums |
| Blend | alpha-over for bg layers; additive for drums |
| Config | [cleave.config.yaml](cleave.config.yaml) (YAML) |
| Entry script | [scripts/milkdrop_visualizer.py](scripts/milkdrop_visualizer.py) |
| Regression track | `sights-and-sounds-26` |

**5.1 — Embed libprojectM** (M1 done)
- libprojectM 4.2+ with ctypes bridge in [cleave/projectm.py](cleave/projectm.py)
- pygame + OpenGL (PyOpenGL); one shared GL context
- One FBO per layer; render preset to texture, composite, blit to window
- M1 spike: one `ProjectM` instance, one preset, **drums** stem PCM at target resolution and fps

**5.2 — Stem PCM sync**
- Preload all four stem wavs at 44100 Hz mono ([cleave/stem_pcm.py](cleave/stem_pcm.py))
- Mix on `pygame.mixer` for ears; shared `t_sec` from [cleave/viz_playback.py](cleave/viz_playback.py)
- Each frame: slice PCM per stem, `projectm_pcm_add_float`, render FBO
- On pause: stop feeding PCM and skip projectM render (reuse last FBO); on seek: flush buffers and reset frame time

**5.3 — One libprojectM instance per layer**
- Four instances, four FBOs at tiered resolutions ([cleave/gl_compositor.py](cleave/gl_compositor.py))
- Composite bottom-to-top per `layer_z_order`; per-layer opacity gates visibility (Phase 5.6 live tuning overlay)

**5.4 — Preset selection via config**
- Per-layer preset path, size, opacity, beat sensitivity in `cleave.config.yaml`
- Align config `visualizer` width/height/fps with target spec when fully wired (M4)
- Percussive preset on drums, fluid on bass, abstract on other; browse community packs

**5.5 — Validate the upgrade**
- Run `sights-and-sounds-26` (same regression track as Phase 4)
- Confirm sync across full track length, clean pause, seek without stale beat energy
- Sustain **30 fps** at 1280x720 on dev hardware (WSL2); tune bg layer mesh size if needed

**✅ Milestone: 4 Milkdrop presets running simultaneously, each driven by its own stem PCM, composited by Cleave**

---

## Phase 5.6 — Live Tuning Console ✅
*Goal: replace ad-hoc key chords with a focus-driven overlay for in-session preset and compositor tuning.*

**Layout terms:** the overlay panel splits into the **track rows section** (upper: `layer_z_order` × six rows per stem via `ROWS_PER_TRACK` / `TrackBlock`) and the **footer rows section** (lower: transport, save, optional overwrite via `footer_row_count` and `FOOTER_ROWS_*`). A visual `footer_gap` separates the two. On-screen headers say "Layer N"; code uses "track" for the same blocks.

**5.6.1 — Focus-driven tree overlay**
- [cleave/viz_tuning_overlay.py](cleave/viz_tuning_overlay.py): track rows section (per-stem tree: header, preset dir, preset, blend, opacity, beat); footer rows section (drawn transport controls (skip / play-pause / skip) and elapsed time, SAVE CONFIG, optional OVERWRITE CONFIG)
- [cleave/viz_tuning_controls.py](cleave/viz_tuning_controls.py): Up/Down row focus; Left/Right adjust the focused field; hold-to-repeat on preset/blend/opacity/beat rows ([cleave/viz_key_repeat.py](cleave/viz_key_repeat.py))
- Same idle behaviour as Phase 4 overlay: 10s hold after input, 2s fade ([cleave/viz_theme.py](cleave/viz_theme.py))

**5.6.2 — Per-layer tuning**
- Directory row: path relative to `preset_root` with `(N/TOTAL)` among sibling dirs (presets in subtree, hidden excluded); Left/Right previous/next sibling (wraps); Enter descends to first alphabetical child with presets; Backspace goes to parent (no-op at the layer's configured preset pack root, the first path segment under `preset_root`; sibling listing never scans above `preset_root`)
- Filename row: Left/Right previous/next `.milk` in current directory only (wraps); Ctrl+Left/Right ±10 presets in directory (wraps); empty dir shows `NO PRESETS FOUND` (dim), L/R no-op
- Blend mode: cycle per-layer blend modes in fixed order (`alpha`, `add`, `multiply`, `screen`, `subtract`, `difference`, `exclusion`, `max`, `pure-add`; see README); stored as `layers.*.blend_mode` in config
- Opacity: 1% steps (10% with Ctrl); 0% disables the layer
- Beat sensitivity: 0.01 steps (0.1 with Ctrl)

**5.6.3 — Z-order move mode**
- Enter on a track header enters move mode (blue highlight); Up/Down swap that stem in `layer_z_order`; Enter confirms
- Compositor re-orders bottom-to-top from live `layer_z_order` each frame

**5.6.4 — Footer rows (transport and save)**
- Transport row: Left/Right seek ±10s (±30s with Ctrl); drawn transport controls (skip / play-pause / skip)
- Space toggles pause/play (not shown in overlay)
- Enter on SAVE CONFIG writes a full snapshot via [cleave/config_snapshot.py](cleave/config_snapshot.py) to [saved-cleave-configs/](saved-cleave-configs/) as `unnamed-N.cleave.config.yaml` (never overwrites the launch config)
- Ctrl+Q quits

**✅ Milestone: tune presets, blend, opacity, beat, and z-order in-session; save reproducible YAML snapshots without touching the launch config**

---

## Phase 6 — Visual Quality & Aesthetic Pass
*Goal: make it look like something you'd actually want to watch.*

**6.1 — Curate presets per layer role**
The drum layer needs presets that respond well to sharp transients — look for ones that flash, burst or strobe on `bass_att`. The bass layer suits slow, fluid presets. The background/other layer suits ones with continuous motion that's modulated rather than triggered.

Preset curation happens in-session via the Phase 5.6 live tuning overlay ([scripts/milkdrop_visualizer.py](scripts/milkdrop_visualizer.py)): browse presets per layer, tune blend/opacity/beat, reorder z-order, and save snapshots to [saved-cleave-configs/](saved-cleave-configs/). Promote a winning snapshot into [cleave.config.yaml](cleave.config.yaml) manually when ready.

**6.2 — Compositor aesthetics**
- Per-layer blend modes (see README): `alpha` and `add` for everyday stacking; `multiply` / `screen` for mood; experimental modes (`subtract`, `difference`, `exclusion`, `max`, `pure-add`) for chaotic passes
- Add post-processing in the compositor itself: film grain, scanlines, chromatic aberration, bloom
- These sit *above* the Milkdrop layers and give Cleave its own visual signature on top of community presets

**6.3 — Aesthetic direction for Cleave**
Grunge/noise rock sits well with: high contrast, monochromatic with occasional colour blow-out, heavy bloom on transients, desaturated palette that flares on hits. The compositor is where this character lives — presets provide the motion, Cleave's compositor provides the colour grading and grit.

**✅ Milestone: looks intentional. You'd be happy to play it behind a live set.**

---

## Phase 7 — Usability & Packaging
*Goal: make it easy to use for your own workflow.*

**7.1 — CLI interface**
```
cleave separate <file>           # fast stem split (htdemucs, default)
cleave separate <file> --slow    # slow stem split (htdemucs_ft)
cleave analyse <stemsfolder>     # generate signals.json
cleave play <file>               # full pipeline + launch visualizer
cleave play <file> --stems-only  # skip separation if stems exist
cleave play <file> --slow        # use slow stem split when separating
```

**7.2 — Config file**
- `cleave.toml` per-project or global: Milkdrop preset per layer, layer weights, blend modes, compositor FX
- Lets you tune per-track without touching code

**7.3 — Video export (optional)**
- `cleave render <file> --output video.mp4`
- Use `ffmpeg` (via subprocess) to encode frames + mux with audio
- Useful for putting visuals behind YouTube/Bandcamp uploads

**✅ Milestone: single command goes from audio file to running visualizer**

---

## Phase 8 — Future / Nice To Have
Ideas to revisit once the core is solid:

- **Realtime mode**: run Demucs on a short lookahead buffer for live performance (latency ~1–2s is acceptable for live visuals)
- **MIDI out**: emit MIDI from drum onsets → drive hardware lighting, synths
- **Preset randomiser**: auto-select and cycle Milkdrop presets per layer on a timer or at song boundaries
- **Web version**: port signal playback + WebGL shaders to the browser (signals.json is already portable; Butterchurn is a JS Milkdrop renderer that could replace libprojectM here)
- **Demucs sub-stem drums**: HTDemucs can separate kick, snare, hihat individually — map each to its own Milkdrop uniform or even its own layer

---

## Suggested Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Stem separation | `demucs` (`htdemucs` / `htdemucs_ft`) | Fast default; slow mode when bleed is bad |
| Audio analysis | `librosa` | Industry standard, excellent onset detection |
| Prototype visuals (Phase 3–4) | `pygame` | Fast to iterate, easy audio sync |
| Milkdrop renderer (Phase 5+) | `libprojectM` + ctypes ([cleave/projectm.py](cleave/projectm.py)) | 50,000+ community presets; stem PCM in, FBO out |
| Compositor post-FX (Phase 6+) | `moderngl` + GLSL | GPU-accelerated grain, bloom, colour grade |
| Video export | `ffmpeg` via subprocess | Universal, no extra deps |
| Config | `tomllib` (stdlib in 3.11+) | Simple, readable |
| CLI | `click` or `argparse` | Either works fine |

---

## Completed Phases Checklist

### Phase 1 — Stem Separation Pipeline ✅

- [x] Create env, install deps, install FFmpeg
- [x] Run Demucs: `python -m demucs -n htdemucs your_track.mp3`
- [x] Listen to `separated/htdemucs/<trackname>/drums.wav`
- [x] Compare with `htdemucs_ft` on tracks where bleed matters

### Phase 2 — Per-Stem Signal Analysis ✅

- [x] `python -m cleave separate` (2.0): Demucs wrapper, `htdemucs` / `--slow` (`htdemucs_ft`), skip unless `--force`, output to `stems/<trackname>/`
- [x] Drum stem onset detection and strength envelope (2.1)
- [x] Bass RMS envelope with sub/mid-bass split at 120 Hz (2.2)
- [x] Vocal RMS + pitch via `yin` (default) or `pyin` with `--slow` (2.3)
- [x] Other stem spectral centroid (2.4)
- [x] `python -m cleave analyse` writes `signals.json` at 100 Hz (2.5)
- [x] Validation plot: `python scripts/plot_onsets.py` → `onset_comparison.png` (use `--source` on analyse for mix overlay)

### Phase 3 — First Visual: Drum Pulse ✅

- [x] pygame added to requirements
- [x] `cleave/signals.py` for loading and sampling signals.json
- [x] `scripts/pulse_visualizer.py` — glow, ripples, hit flash, audio sync
- [x] End-to-end example on `sights-and-sounds-26`

### Phase 4 — Add Layers ✅

- [x] `cleave/signals.py` `normalized()` helper for per-stem signal scaling
- [x] `scripts/layered_visualizer.py` — four-layer compositor (other centroid gradient, bass sub/mid rings, vocal RMS + pitch hue, drum pulse on top); all layers on by default; d/b/v/o toggles
- [x] `cleave/viz_overlay.py` — reusable controls panel (key, label, state); 10s hold then 2s fade; refresh on keypress
- [x] `cleave/viz_playback.py` — shared playback clock, pause/resume, Left/Right skip 30s (both visualizers)
- [x] `scripts/pulse_visualizer.py` — drum-only baseline; overlay and skip wired via shared helpers
- [x] End-to-end: `layered_visualizer.py` on `sights-and-sounds-26` after separate + analyse

### Phase 5 — Milkdrop Integration ✅

- [x] ctypes wrapper for libprojectM 4.2+ ([cleave/projectm.py](cleave/projectm.py))
- [x] Stem PCM preload and per-frame slicing ([cleave/stem_pcm.py](cleave/stem_pcm.py))
- [x] OpenGL compositor: FBO per layer, alpha/add blend ([cleave/gl_compositor.py](cleave/gl_compositor.py))
- [x] YAML config loader ([cleave/config.py](cleave/config.py), [cleave.config.yaml](cleave.config.yaml))
- [x] M1 spike: [scripts/milkdrop_visualizer.py](scripts/milkdrop_visualizer.py) (drums-only via `--preset`)
- [x] M2: PCM sync validation on `sights-and-sounds-26` (full track, pause, seek)
- [x] M3: four layers + compositor + per-layer opacity visibility
- [x] M4: all layers and visualizer settings from config (fps 30)
- [x] M5 docs: README Phase 5, preset_root path guidance, project-context

### Phase 5.6 — Live Tuning Console ✅

- [x] Focus-driven tree overlay ([cleave/viz_tuning_overlay.py](cleave/viz_tuning_overlay.py), [cleave/viz_tuning_controls.py](cleave/viz_tuning_controls.py))
- [x] Up/Down row navigation; Left/Right field adjust; hold-to-repeat on tuning rows
- [x] Per-layer preset, blend mode, opacity, beat sensitivity
- [x] Z-order move mode on track headers (Enter, Up/Down, Enter)
- [x] Transport row with drawn transport controls (skip / play-pause / skip; ±10s / ±30s with Ctrl)
- [x] SAVE CONFIG snapshots to `saved-cleave-configs/unnamed-N.cleave.config.yaml` ([cleave/config_snapshot.py](cleave/config_snapshot.py))
- [x] `layer_z_order` and `layers.*.blend_mode` in [cleave.config.yaml](cleave.config.yaml)
- [x] Docs: README tuning guide, build plan 5.6, project-context

**Next:** Phase 6 visual quality and compositor aesthetics.
