# `cleave`

[![Tests](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml/badge.svg)](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml)

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
  * `-hq` / `--high-quality` for `veryslow` libx264 encode (default uses ffmpeg's libx264 preset).
* Pass `-hq` / `--high-quality` to `separate` or `play` for higher-quality Demucs separation.
* To store projects under XDG instead, set `CLEAVE_DATA=~/.local/share/cleave`.
* `python cleave.py` is an alias for `python -m cleave` (same subcommands).

#### Render overlay

Optional title and body text burned into the MP4. Configure under `render.overlay` in [cleave-viz-default.yaml](cleave-viz-default.yaml) (copied to each project's `cleave-viz.yaml` on first `separate` / `play`).

* `enabled` — turn the overlay on or off.
* `start_delay` — when the overlay begins fading in (seconds).
* `display_time` — how long the overlay is on screen, including the 2s fade-in and fade-out.
* `position` — `top-left`, `top-right`, `centre`, `bottom-left`, or `bottom-right`.
* `title` / `body` — nested text blocks, each with:
  * `content` — multiline string (`|` block scalar).
  * `font-size` — text size in pixels (title is rendered bold).
  * `font-colour` (title) or `colour` (body) — hex text colour.
  * `background-colour` — optional hex fill behind each line of text only (stops at the glyph width). Omit the key or leave empty for no text background.
  * `margin-bottom` (title only) — gap in pixels between the title and body blocks.
* `background.margin` — gap from the frame edge to the panel (ignored when `position: centre`).
* `background.padding` — gap from the panel edge to the text.
* `background.colour`, `background.opacity`, `background.border` — outer panel fill and border (border opacity matches background; border grows outward from the fill, margin is measured to the outer border edge).

In the live visualizer, a blank gap row separates the four stem layers from **Render: OVERLAY**. Same eye / expand / solo semantics as stem layers (solo forces the overlay on; solo is not saved). Tunable in the panel: position, opacity, border width, start delay, display time, and per-block font size and title margin-bottom under expandable **title** / **body** submenus. Content, colours, margin, and padding are YAML-only. Saved with **SAVE AS NEW CONFIG** / **OVERWRITE CONFIG**.

#### Post-processing fade

Whole-frame fade applied after the render overlay (GL fade on the composited image). Configure under `render.post_fx` in [cleave-viz-default.yaml](cleave-viz-default.yaml).

* `enabled` — turn whole-frame fade on or off.
* `fade_in` — seconds to fade from black at the start of the video.
* `fade_out` — seconds to fade to black at the end.

Fade easing uses a smoothstep curve.

In the live visualizer, **Render: POST FX** sits below overlay with the same eye / expand / solo semantics (solo forces fade on; solo is not saved). Tunable in the panel: fade in, fade out. Saved with **SAVE AS NEW CONFIG** / **OVERWRITE CONFIG**.

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
  * move a stem layer up or down the z-order (not available on **Render: OVERLAY**)
* `CTRL` + `Enter`
  * lock / unlock stem layer
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
