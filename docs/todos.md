# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Unified play command

One command from an audio file to a running visualizer:

```bash
python -m cleave play <file>
python -m cleave play <file> --stems-only   # skip separation when stems exist
python -m cleave play <file> --slow         # slow stem split when separating
```

Should run separate (if needed), analyse (if needed), then call `cleave.viz.launch(...)` with the right project and mix path. Users can still run `python cleave.py` directly.

## Video export

Offline render to MP4 for uploads:

```bash
python -m cleave render <file> --output video.mp4
```

Drive frames at the configured resolution and fps via `VisualizerApp.tick_frame()` in [cleave/viz/app.py](../cleave/viz/app.py), then mux with the original audio via ffmpeg.
