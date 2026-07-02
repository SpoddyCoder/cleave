# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

### Solo mode red eye icon
Solo mode on layers used to show a red background on the eye icon to indicate it was in solo mode, the other layers were put in disabled state - this is no longer happening.
Think this occurred when we added caching to the UI during pref improvements. Suspect the visual state would update next time the cache is invalidated. We've seen this issue elsewhere.

---

## Architecture

### Render Width & Height Per Layer & Related Stuff...
Render should always use the final render width & height for every layer for best visual fidelity.
It's approx 20% slower on final render - so safe to assume user would want this when doing final renders
It should be opt-in to the old behaviour of using the per-layer w/h (--low-quality flag)
Food for thought: should we do away with per-layer w/h altogether? Downscaling each layer is only so the visual editor can run at reasonable frame rates -
so perhaps its just better we leave the downscaling each layer to the render mode setting in the visualizer. (sidenote: I hate that name render mode - so easy to confuse with the render command and render settings)

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).
- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.
