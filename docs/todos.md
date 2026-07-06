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

## Architecture

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Done. See [projectm-api-coverage.md](projectm-api-coverage.md). Native playlist load path (no custom `preset_load` callback), switch-failed draining, optional debug logging.
