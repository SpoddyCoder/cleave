# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

---

## Architecture

### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Wire libprojectM health and playlist hooks Cleave does not use today: `projectm_set_preset_switch_failed_event_callback`, `projectm_set_texture_load_event_callback`, optional `projectm_set_log_callback`; in [cleave/projectm_playlist.py](cleave/projectm_playlist.py) bind `projectm_playlist_play_next`, `projectm_playlist_set_preset_switch_failed_event_callback`, and `projectm_playlist_get/set_retry_count`. Use load-failure callbacks in live preset switching (skip or retry bad presets during projectM rotation). Audit remaining exported symbols (mesh size get/set, preset switch requested, debug image, version queries) and document what Cleave should adopt vs ignore. Goal: a reference-quality projectM host; feeds [presets-check-proposal.md](presets-check-proposal.md) and fewer black-screen stalls in play mode.
