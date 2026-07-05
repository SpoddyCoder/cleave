# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

### Preset scan: golden case 2 visualizer vs probe disparity

Golden case 2 (Aderrasi - Airhandler): stays **black** in the live visualizer (clean boot, including at the reference-clip offset ~82 s). Scan classifies **`washed_out`** in both quick and slow probe profiles. Quarantine outcome is acceptable; root cause of the visualizer vs scan split is unknown. Investigate probe environment (raw projectM vs compositor, PCM feeding, resolution, timing) and whether classification rules need a distinct path for this failure mode.

---

## Architecture

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Done. See [projectm-api-coverage.md](projectm-api-coverage.md). Native playlist load path (no custom `preset_load` callback), switch-failed draining, optional debug logging.
