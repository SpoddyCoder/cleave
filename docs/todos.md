# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

### Dirty flag on config file takes a while to appear
* As user makes change the dirty asterisk does not immediately appear.
* It appears when a UI action that clears the cache happens - expanding a secion etc.
* Fixing this need to be careful not to introduce performance issues that the cache is used to mitigate.

---

## Features

### Timeline beat snap (v1)

Done. Batch-quantize committed timeline cues to a librosa beat grid from the drums stem (`beat_times` in `signals.json`). Green **snap to beats** ACTION row under Render: TIMELINE.

**v1.1**

- Optional bar snap: every Nth beat (default N=4, assume 4/4 phase).

---

## Architecture

### Timeline cues: per-track (or single-slot) model

Done. Each track owns a `TimelineLane` (explicit `baseline` plus ordered `SlotCue` transitions) in [cleave/timeline.py](../cleave/timeline.py). Persisted as `timeline.lanes` in YAML. Edits (`punch_lane`, snap, presets, record buffer) are lane-local, so armed recording cannot rewrite unarmed tracks. See [roadmap.md](roadmap.md) Timeline v2 for fades and richer cue types on this model.

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Done. See [projectm-api-coverage.md](projectm-api-coverage.md). Native playlist load path (no custom `preset_load` callback), switch-failed draining, optional debug logging.
