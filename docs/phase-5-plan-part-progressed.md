# Phase 5 progress (session checkpoint)

Phase 5 goal: replace pygame placeholder visuals with libprojectM, one instance per stem, composited by Cleave. PCM audio drives each layer (not `signals.json` uniforms). `signals.json` / analyse stay for future use.

Reference plan: [docs/cleave-build-plan.md](docs/cleave-build-plan.md#phase-5--milkdrop-integration) (still describes the old signals-to-uniforms approach; needs updating when Phase 5 completes).

---

## Architecture decisions (locked in)

| Decision | Choice |
| --- | --- |
| Audio input | Stem PCM via `projectm_pcm_add_float` (mono), not `signals.json` |
| Python bridge | ctypes in [cleave/projectm.py](cleave/projectm.py) |
| Rendering | pygame + OpenGL (PyOpenGL); moderngl deferred to Phase 6 |
| GL layout | One shared context; one FBO per layer; composite then blit |
| Layer resolutions | drums 1280x720; bass/vocals 960x540; other 640x360 (upscale on composite) |
| Blend / z-order | other → bass → vocals → drums; alpha-over for bg layers, additive for drums |
| Audio sync | mix on `pygame.mixer`; preloaded stems for eyes; `t_sec` from [cleave/viz_playback.py](cleave/viz_playback.py) |
| Config | [cleave.config.yaml](cleave.config.yaml) (YAML, not TOML) |
| Entry script | [scripts/milkdrop_visualizer.py](scripts/milkdrop_visualizer.py) |
| Regression track | `sights-and-sounds-26` |

---

## Completed

### Step 1: ctypes wrapper

[cleave/projectm.py](cleave/projectm.py)

- Lazy library discovery (`PROJECTM_LIB`, pkg-config, common paths)
- Wrapped: create/destroy, window size, preset load/lock, texture paths, PCM feed/flush, FBO render, beat sensitivity, fps, frame time, hard-cut disable
- `ProjectM` context-manager class

Requires libprojectM **4.2+** (FBO render and frame time). Rebuilt to 4.2.0 on dev machine.

### Step 2: stem PCM loader

[cleave/stem_pcm.py](cleave/stem_pcm.py)

- `StemPcmBank` / `load_stem_pcm()`: preload all four stems at 44100 Hz mono float32
- `slice_pcm(stem, t_sec, n_samples)` for sample-accurate seeks
- `samples_per_frame(fps)` capped by `projectm_pcm_get_max_samples()`

### Step 3: OpenGL compositor

[cleave/gl_compositor.py](cleave/gl_compositor.py)

- `LayerFbo`: per-layer FBO + RGBA texture + depth RBO
- `GlCompositor`: tiered layer creation, alpha/add blend modes, composite to default FB
- Overlay upload/draw with panel positioning

**Bug fixes during integration:**

1. `_gl_name`: PyOpenGL returns 0-d numpy scalars from `glGenTextures`; fixed with try/except fallback
2. Overlay black screen: projectM leaves `GL_BLEND` off; full-window transparent overlay wrote black RGB. Fixed by re-enabling blend, drawing only the panel rect, restoring GL state, reusing one overlay texture via subimage upload ([cleave/viz_overlay.py](cleave/viz_overlay.py) `panel_rect`)

### Step 4: YAML config

[cleave/config.py](cleave/config.py), [cleave.config.yaml](cleave.config.yaml)

- Search order: `--config` → `./cleave.config.yaml` → `~/.config/cleave/cleave.config.yaml`
- Typed dataclasses: paths, per-layer preset/size/opacity/beat sensitivity, visualizer settings
- Preset path validation at load time

### Step 5: M1 spike script

[scripts/milkdrop_visualizer.py](scripts/milkdrop_visualizer.py)

- One `ProjectM` instance, one FBO, **drums** stem PCM
- Mix playback via `--source` or `signals.json` source
- `--preset` bypass for testing without full config preset install
- Playback controls: Esc, Space, Left/Right 30s skip (PCM flush on seek)
- Controls overlay (playback keys only; no layer toggles yet)

**Currently running at 640x360 @ 30 fps** in the script constants (local perf tuning during M1). Config template still specifies 1280x720 @ 60.

### Dependencies

[requirements.txt](requirements.txt): added `PyOpenGL`, `PyYAML`.

### Manual validation

- M1 runs with `--preset` on `buttercup-24` and `sights-and-sounds-26`
- Preset packs present locally (`presets-cream-of-the-crop/`, `milkdrop-presets/`)
- Overlay no longer blacks out the visual when shown or on keypress

---

## Outstanding

### M2: PCM sync validation (partially done in M1, not signed off)

- [ ] Confirm visual tracks mix across full track length on `sights-and-sounds-26`
- [ ] Verify pause freezes visual cleanly (no PCM feed while paused)
- [ ] Verify seek does not carry stale beat energy (flush + frame time reset)
- [ ] Restore target **1280x720 @ 60 fps** (or read from config `visualizer` section)

### M3: Four layers + compositor

- [ ] Four `ProjectM` instances, four FBOs at tiered resolutions
- [ ] Composite bottom-to-top: other → bass → vocals → drums
- [ ] Layer toggles **d** / **b** / **v** / **o** (reuse [cleave/viz_overlay.py](cleave/viz_overlay.py) `layered_rows`)
- [ ] Per-layer opacity and blend mode from config
- [ ] 60 fps sustained on WSL2; tune mesh size / bg resolution if needed

### M4: Config-driven presets

- [ ] Wire all four layers from [cleave.config.yaml](cleave.config.yaml) (remove drums-only hardcoding)
- [ ] Point config at real presets under local preset packs
- [ ] Per-layer `beat_sensitivity` override
- [ ] Texture search paths from config for all instances

### Documentation

- [ ] Update [docs/cleave-build-plan.md](docs/cleave-build-plan.md) Phase 5 to PCM architecture; add milestone checklist
- [ ] Update [README.md](README.md) Phase 5 section (full usage, preset setup, config)
- [ ] Update [.cursor/rules/project-context.mdc](.cursor/rules/project-context.mdc) current focus

### Unchanged (by design)

- [scripts/layered_visualizer.py](scripts/layered_visualizer.py) and [scripts/pulse_visualizer.py](scripts/pulse_visualizer.py) left as Phase 4 baselines
- `cleave analyse` / `signals.json` pipeline untouched

---

## Quick resume commands

```bash
# M1 smoke test (single preset, drums stem)
python scripts/milkdrop_visualizer.py stems/sights-and-sounds-26 \
  --source cleave-resources/source/sights-and-sounds-26.wav \
  --preset "path/to/preset.milk"

# With config (needs all four preset paths to exist)
python scripts/milkdrop_visualizer.py stems/sights-and-sounds-26 \
  --source cleave-resources/source/sights-and-sounds-26.wav
```

---

## Suggested next session pick-up

1. Bump `WIDTH`/`HEIGHT`/`FPS` in `milkdrop_visualizer.py` to match config (1280x720, 60) and confirm perf on WSL2
2. Extend script to M3: loop over `config.layers_in_z_order()`, one PM + FBO per layer
3. Add layer toggles and update overlay to `layered_rows`
4. Update build plan and README when M3/M4 validate on `sights-and-sounds-26`
