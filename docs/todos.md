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

## Beat grid and cue snap

Low user effort is the goal: improve the automatic grid before adding manual
workflow. Existing projects must re-run analyse (rewrite `signals.json`) after
beat-detection changes; Demucs stems can stay.

### Stronger beat and downbeat detection
* Done: [Beat This!](https://github.com/CPJKU/beat_this) on the mix writes
  `beat_times` and `downbeat_times` in `signals.json` (version 3). Timeline snap
  uses those grids; onset envelopes for effects are unchanged. Plan:
  [BeatThis-plan.md](BeatThis-plan.md).
* Re-analyse existing projects with `cleave separate <slug>` or `cleave play`
  (stems reused; only `signals.json` rewrites).
* Known remaining weak spots: quiet intros / drum-sparse sections, half-time and
  double-time flips, unusual meters.

### Sparse song anchors (after the grid is solid)
* Manual "drop song cue" at major transitions for guaranteed pops solves a
  different problem from beat snap (structure vs pulse).
* Prefer automation: auto-suggested anchors (energy / novelty / structure), with
  optional manual drop only to correct or pin a few points.
* Do not make dense hand-cueing the normal path.

---

## Architecture

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Done. See [projectm-api-coverage.md](projectm-api-coverage.md). Native playlist load path (no custom `preset_load` callback), switch-failed draining, optional debug logging.
