# Cleave

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own layer.

Built on WSL2, but should work on any Linux machine. A GPU with CUDA support is recommended for stem separation (Demucs is roughly 5 to 10 times faster on GPU).

**Current focus:** [Phase 2](docs/cleave-build-plan.md#phase-2--per-stem-signal-analysis) — per-stem signal analysis. Extract time-series signals from stems to drive visuals.

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

## Stem separation (Phase 1, complete)

Until the `cleave separate` CLI lands in Phase 2, run Demucs directly.

| Mode | Command | When to use |
| --- | --- | --- |
| Fast stem split (default) | `python -m demucs -n htdemucs <file>` | Good quality; much faster |
| Slow stem split | `python -m demucs -n htdemucs_ft <file>` | Higher quality; slower, less bleed |

Stems are written to `separated/<model>/<trackname>/`:

| File | Stem |
| --- | --- |
| `drums.wav` | Drums |
| `bass.wav` | Bass |
| `vocals.wav` | Vocals |
| `other.wav` | Everything else |

Quote paths that contain spaces:

```bash
python -m demucs -n htdemucs "cleave-resources/source/sights & sounds.wav"
```

Phase 2 will wrap this as:

```bash
cleave separate track.mp3           # fast stem split (htdemucs)
cleave separate track.mp3 --slow    # slow stem split (htdemucs_ft)
```

## Phase 2 (in progress)

Extract per-stem signals and write `signals.json` for each track:

```bash
cleave analyse stems/<trackname>/   # coming in Phase 2
```

Goal: drum onsets from the isolated stem should be visibly sharper than onsets from the full mix. See [docs/cleave-build-plan.md](docs/cleave-build-plan.md) for the full roadmap.
