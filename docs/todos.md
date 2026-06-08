# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Unified play command

One command from an audio file to a running visualizer:

```bash
python -m cleave play <file>
python -m cleave play <file> --stems-only   # skip separation when stems exist
python -m cleave play <file> --slow         # slow stem split when separating
```

Should run separate (if needed), analyse (if needed), then launch [cleave.py](../cleave.py) with the right project and mix path.

## Video export

Offline render to MP4 for uploads:

```bash
python -m cleave render <file> --output video.mp4
```

Capture frames at the configured resolution and fps, mux with the original audio via ffmpeg.
