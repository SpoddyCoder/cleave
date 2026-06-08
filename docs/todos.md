# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Unified play command

`python -m cleave play <project>` runs the visualizer for an existing project (slug or path). Flags: `--config`, `--preset`.

Follow-up: auto-pipeline from an audio file (separate + launch in one step):

```bash
python -m cleave play <file>
python -m cleave play <file> --stems-only   # skip separation when stems exist
python -m cleave play <file> --slow         # slow stem split when separating
```

Should run `separate` (if needed), then call `cleave.viz.launch(...)` with the right project and mix path.

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
