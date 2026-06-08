# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Video export

Offline render to MP4 for uploads:

```bash
python -m cleave render <file> --output video.mp4
```

Drive frames at the configured resolution and fps via `VisualizerApp.tick_frame()` in [cleave/viz/app.py](../cleave/viz/app.py), then mux with the original audio via ffmpeg.

## CI

GitHub Actions workflow on push and pull request:

```bash
./tests/run_unit_tests.py
```

- Linux runner (headless; pygame is initialized in [tests/conftest.py](../tests/conftest.py) without opening a Milkdrop window)
- Install from [requirements.txt](../requirements.txt) (includes `pytest`)
- Optional later: `-m "not slow"` once librosa/audio integration tests are marked `@pytest.mark.slow`
