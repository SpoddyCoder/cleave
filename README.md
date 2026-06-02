# Cleave

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own layer.

Built on WSL2, but should work on any Linux machine. A GPU with CUDA support is recommended for stem separation (Demucs is roughly 5 to 10 times faster on GPU).

**Current focus:** Phase 4 complete (layered visualizer); next up: [Phase 5 (Milkdrop)](docs/cleave-build-plan.md#phase-5--milkdrop-integration).

## Requirements

- Python 3.10+
- FFmpeg (used by Demucs and audio I/O)
- Optional: NVIDIA GPU with CUDA for faster separation
- On WSL2, [wsl-builds](https://github.com/spoddycoder/wsl-builds) can install the base stack (CUDA, Python, and related tools):

```bash
# setup a ai development stack: CUDA, Python, Anaconda + others
./wsl-stacker.sh spoddycoder dev-ai
# install ffmpeg system wide
./wsl-builder.sh media ffmpeg
```

## Setup

Create a virtual environment and install dependencies.

**GPU (CUDA 13.0 example):**

```bash
python3 -m venv cleave-env
source cleave-env/bin/activate

pip install torch torchcodec --index-url https://download.pytorch.org/whl/cu130
pip install -r requirements.txt
```

**CPU only:**

```bash
python3 -m venv cleave-env
source cleave-env/bin/activate

pip install torch torchcodec --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

**Or with Conda:**

```bash
conda create -n cleave python=3.10
conda activate cleave
conda install -c conda-forge ffmpeg
pip install -r requirements.txt
```

Verify GPU support:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

If this prints `False`, Demucs still runs on CPU, so separation will be slow (but it will work).

## Stem layout

Each track lives under `stems/<trackname>/` with four stem wavs and the analysis output co-located:

| File | Role |
| --- | --- |
| `drums.wav` | Drum stem |
| `bass.wav` | Bass stem |
| `vocals.wav` | Vocal stem |
| `other.wav` | Everything else |
| `signals.json` | Per-stem time-series signals (written by analyse) |

Run `python -m cleave separate` to write the four stem wavs directly to `stems/<trackname>/` (track name is taken from the source filename).

## Stem separation (Phase 2, complete)

Separate a track into stems under `stems/<trackname>/`:

```bash
python -m cleave separate <file>           # fast stem split (htdemucs, default)
python -m cleave separate <file> --slow    # slow stem split (htdemucs_ft)
python -m cleave separate <file> --force   # re-separate even if stems already exist
```

| Flag | Purpose |
| --- | --- |
| `--slow` | Use `htdemucs_ft` instead of `htdemucs` (higher quality, slower) |
| `--force` | Re-run Demucs and overwrite stems even when all four wavs already exist |

If stems are already present, the command exits without re-separating unless you pass `--force`.

End-to-end example (`sights-and-sounds-26`):

```bash
python -m cleave separate cleave-resources/source/sights-and-sounds-26.wav
python -m cleave analyse stems/sights-and-sounds-26 --source cleave-resources/source/sights-and-sounds-26.wav
python scripts/plot_onsets.py stems/sights-and-sounds-26
python scripts/pulse_visualizer.py stems/sights-and-sounds-26
python scripts/layered_visualizer.py stems/sights-and-sounds-26
```

**Advanced:** Demucs can be run directly (`python -m demucs -n htdemucs <file>`) if you need its default `separated/` layout; copy the four wavs into `stems/<trackname>/` manually before analyse.

## Signal analysis (Phase 2 analyse, complete)

Extract per-stem signals and write `signals.json` beside the stem wavs:

```bash
python -m cleave analyse "stems/<trackname>" --source "path/to/mix.wav"
```

| Flag | Purpose |
| --- | --- |
| `--source PATH` | Original mixed audio; adds `mix_onset_strength` to `signals.json` for drum vs mix comparison |
| `--slow` | Use `pyin` instead of `yin` for vocal pitch (slower, more accurate) |
| `--force` | Regenerate `signals.json` even if it already exists |

Without `--source`, analysis still runs; drum onsets are extracted from the isolated stem only.

Validate that drum onsets are sharper than mix onsets:

```bash
python scripts/plot_onsets.py "stems/<trackname>"
```

This writes `onset_comparison.png` next to `signals.json`. Pass `--source` to analyse first so the plot includes the full-mix overlay.

## Drum pulse visualizer (Phase 3, complete)

Pygame visualizer driven by drum onset strength from `signals.json`. Plays the original mix in sync with a glowing orb, expanding ripples on hits, and a brief full-screen flash on strong transients.

```bash
python scripts/pulse_visualizer.py stems/sights-and-sounds-26
```

Pass `--source path/to/mix.wav` to override the mix path stored in `signals.json` (required if analyse ran without `--source`).

| Key | Action |
| --- | --- |
| Esc | Quit |
| Space | Pause / resume playback |
| Left | Back 30 seconds |
| Right | Forward 30 seconds |

A controls panel in the top-left lists keys and state (PLAY / PAUSED). It stays visible for 10 seconds, then fades out over 2 seconds; press any key to show it again. Implemented in [cleave/viz_overlay.py](cleave/viz_overlay.py) for reuse across visualizers.

On WSL2, the window needs WSLg or an X11 display server; without one, pygame cannot open a window.

## Layered visualizer (Phase 4, complete)

Multi-stem compositor that blends four pygame layers, each driven by its stem in `signals.json`:

| Layer | Signal | Visual |
| --- | --- | --- |
| Other | Spectral centroid | Warm horizontal gradient band that shifts with brightness |
| Bass | `sub_bass` / `mid_bass` | Dual soft rings (deep red sub, amber mid) |
| Vocals | RMS + pitch | Radial glow sized by amplitude, hue from pitch |
| Drums | Onset strength | Pulse orb, ripples, and flash (same as drum-only visualizer, drawn on top) |

```bash
python scripts/layered_visualizer.py stems/sights-and-sounds-26
```

Pass `--source path/to/mix.wav` to override the mix path stored in `signals.json` (same as pulse visualizer).

| Key | Action |
| --- | --- |
| d | Toggle drums layer |
| b | Toggle bass layer |
| v | Toggle vocals layer |
| o | Toggle other layer |
| Space | Pause / resume playback |
| Left | Back 30 seconds |
| Right | Forward 30 seconds |
| Esc | Quit |

All four layers are on at startup. Toggle **d** / **b** / **v** / **o** during playback to isolate stems.

The same controls overlay as the drum pulse visualizer shows all keys plus layer ON/OFF state; it fades when idle and reappears on any keypress.

`scripts/pulse_visualizer.py` remains the objective drum-only baseline for comparing onset response without other stems in the mix.

On WSL2, same display requirement as the drum pulse visualizer (WSLg or X11).

After separate, analyse, and optional onset validation above, run `pulse_visualizer.py` for the drum baseline, then `layered_visualizer.py` for the full composited view.

See [docs/cleave-build-plan.md](docs/cleave-build-plan.md) for the full roadmap.
