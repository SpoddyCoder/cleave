# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

### Solo mode red eye icon
Solo mode on layers used to show a red background on the eye icon to indicate it was in solo mode, the other layers were put in disabled state - this is no longer happening - or it may be happening, but not immediately visible.
Think this occurred when we added caching to the UI during pref improvements. Suspect the visual state would update next time the cache is invalidated. We've seen this issue elsewhere.

---

## Architecture

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).
- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.
