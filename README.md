# `cleave`

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own visualizer layer.

Built on [projectM](https://github.com/projectM-visualizer/projectM) and [Demucs](https://github.com/facebookresearch/demucs). Developed on WSL2; should run on any Linux with a display.

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

Install dependencies...

```bash
# install torch with CUDA support
pip install torch torchcodec --index-url https://download.pytorch.org/whl/cu130
# or install cpu version
pip install torch torchcodec --index-url https://download.pytorch.org/whl/cpu
# install the rest of the deps
pip install -r requirements.txt
```

## Quick Start

### Download Some Milkdrop Presets

```bash
# make a preset_root
mkdir ~/milkdrop-presets
cd ~/milkdrop-presets

# there are thousands of community written presets to choose from...
git clone https://github.com/projectM-visualizer/presets-cream-of-the-crop
git clone https://github.com/projectM-visualizer/presets-milkdrop-original
git clone https://github.com/projectM-visualizer/presets-milkdrop-texture-pack
```

`preset_root` is defined in [cleave-viz-default.yaml](./cleave-viz-default.yaml)

### `cleave` a track

```bash
python -m cleave play ~/music/mysong.wav
```

This will separate the track into its component stem tracks (bass, drums, vocals, other), perform some audio analysis, then launch the visualizer.

---

## Using `cleave`

### Project Directory

`cleave` creates a new directory under `projects/` for each song, containing...
* `project.yaml` - project metadata
* `cleave-viz.yaml` - visualizer configuration. Not everything in here is surfaced in the visualizer UI just yet
* `signals.json` - audio analysis data used by `cleave effects`
* `mysong.wav` - original source audio is copied into the project (makes a project self contained)
* `stems/` - separated audio stems
* `renders/` - final renders

### CLI

* `python -m cleave --help`
* `play` accepts a source audio file or project slug/path.
  * It will only re-run the seperation and analysis if they're not already in the project directory
    * Use `--force` if you want to redo these.
* `separate` can be run on its own without launching the visualizer
* `render` accepts a project slug or path (not a source audio file). 
  * `-o` for output (`.mp4` only)
    * If omitted outputs to `projects/<slug>/renders/<visualizer.name>.mp4`
  * `-c` for config
  * `-fi` / `-fo` for visual fade-in and fade-out.
* Pass `--high-quality` to either command for higher-quality separation.
* To store projects under XDG instead, set `CLEAVE_DATA=~/.local/share/cleave`.
* `python cleave.py` is an alias for `python -m cleave` (same subcommands).

### Visualizer
Controls...

* `Up` / `Down`
  * move up / down menu items
* `CTRL` + `Up` / `Down`
  * move up / down layers
* `Right` / `Left`
  * expand / collapse
  * increment / decrement value by 1
  * forward / back 10 secs
  * next / previous milkdrop preset
* `CTRL` + `Right` / `Left`
  * enable / disable layer
  * increment / decrement value by 10
  * forward / back 30 secs
  * up / down the preset directory tree 
* `SHIFT` + `Right` / `Left`
  * Solo / unsolo layer
* `Enter`
  * move a layer up or down the z-order
* `CTRL` + `Enter`
  * lock / unlock layer
* `CTRL` + `q`
  * quit

#### Compositing

* The visualizer is four libprojectM layers at tiered resolutions, composited to **1280x720 @ 30 fps** by default (editable `cleave-viz.yaml`)
* Milkdrop draws on black, so cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default).

| Mode | Typical use |
| --- | --- |
| `black-key` | Background stems |
| `add` | Drums / highlights |
| `multiply`, `screen`, others | Experimental |

#### Cleave effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%).

| Stem | Effects |
| --- | --- |
| Drums | pulse, flare, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |
