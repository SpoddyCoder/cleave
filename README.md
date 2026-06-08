# Cleave

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own visualizer layer.

Built on [projectM](https://github.com/projectM-visualizer/projectM) and [Demucs](https://github.com/facebookresearch/demucs). Developed on WSL2; should run on any Linux with a display.

**Next up:** see [docs/todos.md](docs/todos.md). **Later ideas:** [docs/roadmap.md](docs/roadmap.md).

## Requirements

- Python 3.10+
- FFmpeg
- libprojectM 4.2+ (needs `_opengl_render_frame_fbo` and `_set_frame_time`)
- Optional: NVIDIA GPU + CUDA for faster Demucs separation
- WSL2: [wsl-builds](https://github.com/spoddycoder/wsl-builds) simplifies deps

```bash
./wsl-stacker.sh spoddycoder dev-ai
./wsl-builder.sh media ffmpeg
./wsl-builder.sh media libprojectm
```

WSL2 audio glitches: see [microsoft/wslg#1257](https://github.com/microsoft/wslg/issues/1257). Disabling `systemd-timesyncd` should help.

## Setup

Create a virtual environment...

```bash
# using venv
python3 -m venv cleave
source cleave/bin/activate

# or using conda
conda create -n cleave python=3.10
conda activate cleave
```

Install dependecies...

```bash
# install torch with CUDA support
pip install torch torchcodec --index-url https://download.pytorch.org/whl/cu130
# or install cpu version
pip install torch torchcodec --index-url https://download.pytorch.org/whl/cpu
# install the rest of the deps
pip install -r requirements.txt
```

Clone Milkdrop preset packs into `~/.local/share/cleave/presets/` (see [cleave.config.yaml](cleave.config.yaml) `paths.preset_root`). Optional texture pack: `~/.local/share/cleave/textures/`.

## Quick start

Each track is a **project** under `projects/<slug>/` with the original mix audio, four stem wavs (`drums.wav`, `bass.wav`, `vocals.wav`, `other.wav`), `project.yaml`, and `signals.json`. The slug is the audio filename stem (e.g. `sights-and-sounds-26.flac` becomes `sights-and-sounds-26`). `separate` copies the source file into the project (no transcode) and writes `project.yaml`.

```bash
python -m cleave separate ~/music/sights-and-sounds-26.flac
python -m cleave play sights-and-sounds-26
```

`separate` runs Demucs stem separation and writes `signals.json` in one step. Re-run on an existing project slug to analyse only (when stems exist but `signals.json` is missing). Use `--force` to redo both.

`python cleave.py` is an alias for `python -m cleave` (same subcommands).

To store projects under XDG instead, set `CLEAVE_DATA=~/.local/share/cleave`.

## CLI

| Command | Purpose |
| --- | --- |
| `python -m cleave separate <file or slug>` | Demucs split + `signals.json` (`--slow`, `--force`; idempotent when outputs exist) |
| `python -m cleave play <slug or path>` | Run the visualizer (`--config`, `--preset` for drums-only debug) |

`separate` extracts per-stem signals at 100 Hz (onsets, bass envelopes, vocal pitch, spectral centroid) into `signals.json`. The visualizer uses stem PCM for Milkdrop reactivity and `signals.json` for cleave effects.

## Visualizer

User-facing entry: `python -m cleave play` (or `python cleave.py play`, same CLI). Implementation lives under [cleave/viz/](cleave/viz/) (`VisualizerApp` loop, live overlay, bootstrap). Programmatic entry: `cleave.viz.launch(project_dir, ...)`.

Four libprojectM layers at tiered resolutions, composited to **1280x720 @ 30 fps** by default. Stack order is `layer_z_order` in [cleave.config.yaml](cleave.config.yaml).

**Presets:** set `paths.preset_root` to your presets root (the folder that contains packs like `presets-cream-of-the-crop`). Each `layers.*.preset` is a `.milk` file or directory (recursive scan).

**Compositing:** Milkdrop draws on black. Cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default). Per-layer `blend_mode`, opacity, and beat sensitivity live in config.

| Mode | Typical use |
| --- | --- |
| `black-key` | Background stems |
| `add` | Drums / highlights |
| `multiply`, `screen`, others | Experimental |

### Live tuning overlay

Arrow-key tree panel ([cleave/viz/overlay.py](cleave/viz/overlay.py)): browse presets, blend, opacity, beat, cleave effects, z-order, layer lock, transport, save.

- **Track rows:** one block per stem (header, preset dir/file, blend, opacity, beat, collapsible cleave effects).
- **Footer rows:** transport, **SAVE AS NEW CONFIG**, **OVERWRITE CONFIG** (when active config is not repo-root [cleave.config.yaml](cleave.config.yaml)).

| Key | Action |
| --- | --- |
| Up / Down | Move focus |
| Left / Right | Adjust field; hold to repeat on tuning rows |
| Enter | Descend preset dir / confirm z-order move / save |
| Ctrl + Enter | Toggle layer lock |
| Backspace | Parent preset dir |
| Space | Pause / resume (hidden) |
| Ctrl + Q | Quit |

Full row behaviour: [.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc).

**Save:** **SAVE AS NEW CONFIG** writes `unnamed-N.yaml` in the project directory. **OVERWRITE CONFIG** updates the active config file (hidden when the active file is the repo-root template). A project can also hold `cleave.config.yaml` as its default launch config.

Pass `--config` to use a different YAML. Drums-only debug:

```bash
python -m cleave play sights-and-sounds-26 --preset ~/.local/share/cleave/presets/.../some.milk
```

### Cleave effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%) under the **cleave effects** header in the overlay.

| Stem | Effects |
| --- | --- |
| Drums | pulse, flare, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |

Config: `layers.<stem>.effects.<effect>.<driver>` (integers 0-100; zero keys omitted in snapshots).

## Config

[cleave.config.yaml](cleave.config.yaml) is the repo template. At launch, config resolution is: `--config` override, then `cleave.config.yaml` in the project directory, then `~/.config/cleave/cleave.config.yaml`, then the repo template.

Default preset paths match [cleave/config.py](cleave/config.py): `~/.local/share/cleave/presets` and `~/.local/share/cleave/textures`.
