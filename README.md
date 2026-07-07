# `cleave`

[![Tests](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml/badge.svg)](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml)

Stem-separated music visualizer. 

Layer together drums, bass, vocal and other stems driving Milkdrop presets to create your own unique visual masterpieces. 

Comprehensive visual editor allows you to browse and tune presets in real time - automate preset switching, layer in effects, post processing and a whole bunch more. 

Render the final output in high defintion and high frame rates using `ffmpeg`.

Built on [projectM](https://github.com/projectM-visualizer/projectM) and [Demucs](https://github.com/facebookresearch/demucs) amongst [others](#attribution). Developed on WSL2; should run on any Linux with a display.

## Requirements

* Python 3.10+
* FFmpeg
* libprojectM 4.2+ (needs `_opengl_render_frame_fbo` and `_set_frame_time`)
* Optional: NVIDIA GPU + CUDA for faster Demucs separation
* WSL2: [wsl-builds](https://github.com/spoddycoder/wsl-builds) simplifies deps...

```bash
./wsl-stacker.sh spoddycoder dev-ai
./wsl-builder.sh media ffmpeg,libprojectm
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

Install dependencies...

```bash
# CUDA 13.0 (Linux + NVIDIA GPU)
pip install -r requirements-torch-cu130.txt
# or CPU-only
pip install -r requirements-torch-cpu.txt
# rest of deps
pip install -r requirements.txt
# for development and tests
pip install -r requirements-dev.txt
```

## Quick Start

### Get Some Milkdrop Presets

Clone or place Milkdrop preset packs in the default location...

```bash
mkdir -p ~/.local/share/cleave/presets
cd ~/.local/share/cleave/presets
git clone https://github.com/projectM-visualizer/presets-cream-of-the-crop
git clone https://github.com/projectM-visualizer/presets-milkdrop-original

mkdir -p ~/.local/share/cleave/textures
cd ~/.local/share/cleave/textures
git clone https://github.com/projectM-visualizer/presets-milkdrop-texture-pack
```

Note: There are many thousands of Milkdrop presets available, these are just a few of the best.

### `cleave` a track

```bash
./cleave.py play ~/music/mysong.wav
```

This will separate the track into its component stem tracks (bass, drums, vocals, other), perform some audio analysis, then launch the visualizer editor.

---

## Using `cleave`
Cleave uses the XDG standard for user data and configuration directories...

* User data: `~/.local/share/cleave/`
* Configuration: `~/.config/cleave/config.yaml`

### CLI

```bash
./cleave.py --help
```

Available commands...

* `play` play song in visualizer editor, accepts a source audio file or project slug/path.
* `separate` can be run on its own without launching the visualizer.
* `render` accepts a project slug or path (not a source audio file).
* `backup` archives a full project directory (mix, stems, configs, renders etc.) to a `.cleave-tar.gz` file.
* `restore` unpacks a `.cleave-tar.gz` archive into `projects/<slug>/` (slug from `project.yaml`).
* `scan` (experimental, WIP) classifies Milkdrop presets for load failures and output quality.

Note: use `--help` on any command for options.

### Project Directory

`cleave` creates a new directory under `~/.local/share/cleave/projects/` for each song.
The project directory stores all files required in a self-contained bundle...

* `project.yaml` - project metadata
* `cleave-viz.yaml` - visualizer & final render configuration. Not everything in here is surfaced in the visualizer UI just yet
* `signals.json` - audio analysis data used by `cleave effects`
* `mysong.wav` - original source audio is copied into the project directory
* `stems/` - separated audio stems
* `renders/` - final output renders
* `user-presets/` - presets used by the project are copied into the project directory

### Configuration

* Visualizer Editor Settings (preview quality, panel width, fade) live in `~/.config/cleave/config.yaml`.
* Override the data root with `CLEAVE_DATA` (e.g. `CLEAVE_DATA=.` for a dev checkout).
* When a project omits `paths`, preset browsing defaults to `~/.local/share/cleave/presets`.
  * `paths.preset_root` in `cleave-viz.yaml` overrides this default when set.

### Visualizer Editor

* This is where you can create your visual masterpieces.
* Press `h` to show context sensitive controls + help.
* The visualizer may run at low frame rates with lots of layers (Milkdrop presets use a lot of CPU), use the UI settings to render at lower quality in the editor - the final render will still be at full quality.

#### Visualizer Timeline
* TODO: Document

---

## Additional Details

### Compositing

* The visualizer supports up to eight libprojectM layers at tiered resolutions
* Composited to **1280x720** content by default (editable `cleave-viz.yaml`)
* Live preview upscales via `visualizer.upscale` and runs at display frame rate
* Offline render output resolution is set under `render.width` / `render.height` (default **1280x720**) and frame rate under `render.fps`
* Each layer's libprojectM instance receives PCM from its assigned stem; stereo stems are fed as stereo, mono as mono.
* Milkdrop draws on black, so cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default).

### Cleave effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%).

| Stem | Effects |
| --- | --- |
| Drums | pulse, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |

### Render overlay
* TODO: Document

### Post-processing
* TODO: Document

---

## Preset Scanning (Experimental, WIP)

Clone with submodules so preset packs are available for `cleave scan-golden --probe` and other preset work:

```bash
git submodule update --init --recursive
```

---

## Attribution

* [Milkdrop / projectM](https://github.com/projectM-visualizer/projectM) - visualizer engine
* [Demucs](https://github.com/facebookresearch/demucs) - audio separation
* [FFmpeg](https://ffmpeg.org) - video encoding
* [pygame](https://www.pygame.org/) - window, input, overlay UI, and SDL2 audio
* [OpenGL](https://www.opengl.org/) / [PyOpenGL](https://pyopengl.sourceforge.io/) - layer compositing and rendering
* [ModernGL](https://moderngl.readthedocs.io/) - GPU post-processing
* [librosa](https://librosa.org/) - audio analysis and feature extraction
* [NumPy](https://numpy.org/) - numerical arrays for audio and effects
* [PyYAML](https://pyyaml.org/) - configuration format
* [soundfile](https://python-soundfile.readthedocs.io/) - WAV I/O
