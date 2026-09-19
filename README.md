# `Cleave`

[![Tests](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml/badge.svg)](https://github.com/SpoddyCoder/cleave/actions/workflows/tests.yml)

Stem-separated music visualizer. Layer together drums, bass, vocal and other stems - each driving Milkdrop presets to create your own unique visual masterpieces.

The visual editor lets you browse and tune presets in real time - automate preset switching, layer in effects, post processing and more. Render the final output in high definition and high frame rates using FFmpeg.

Built on [projectM](https://github.com/projectM-visualizer/projectM) and [Demucs](https://github.com/facebookresearch/demucs) amongst [others](#attribution).

## Download & Install

Grab the latest release from the [releases page](https://github.com/SpoddyCoder/cleave/releases).

**Windows** - download the installer or standalone zip. See [Windows Install Details](#windows-install-details) below for more info.

**Linux** - no standalone package yet. See [Linux Setup](#linux-setup) for how to install from source.

Cleave is in active development. It is very usable, but may not maintain backward compatibility until v1.0.0.

## Getting Started

### Get Some Milkdrop Presets

Cleave needs Milkdrop preset packs to display visualizations. On first launch, when none are present, the editor offers to download starter preset and texture packs (about 60 MB). You can skip this and add packs later; see [Project & Data Locations](#project--data-locations).

### Open a Track

Windows - drop a `.wav` file onto `cleave.exe`, or launch it and browse for a file from the editor window.

Linux:
```bash
./cleave.py play ~/music/mysong.wav
```

This will separate the track into its component stems (bass, drums, vocals, other), perform audio analysis, then open the editor. First run downloads model weights and shows progress in the loading window.

## Using the Editor

* Press `h` at any time to show context-sensitive help and controls.
  * The help changes as you move around the interface with the arrow keys.
* If you are using CPU rendering, the editor may run at low frame rates with multiple layers.
  * Change `Settings` > `Editor Window` > `preview quality` to help with this.
  * The final render will still be at full quality and full frame rate.

### Preset Curation

The editor has a preset curation mode for sorting presets into folders.
`Settings` > `change editor mode` > `preset curation`. While focused on a preset **file** row:
* `f` - **copy** the preset into `favourites/` (original stays in the pack).
* `c` - **copy** the preset into a cast role directory.
* `b` - **move** the preset into `blacklist/` (permanently removed from pack).
* Browse curated folders in the editor like any other pack folder.
* Subdirectories inside `favourites/` or `blacklist/` appear as destination choices in the confirm modal, so you can categorise however you like:
```
favourites/a-tier/
favourites/b-tier/
favourites/lots-of-black/
favourites/full-colour-wash/
```

### Timeline

The timeline automates layer visibility, preset choice, opacity and blend over the course of a song. When enabled, the standard layer visibility controls are disabled and the timeline takes over.

**Song Markers** - mark specific points in the song for preset cuts. Press `Ctrl + Enter` to drop a marker. These act as snap points and anchor points for timeline preset generation.

**Beat / Bar Grid** - powered by Beat This!, an AI beat detection library. By default it uses the full-mix stem for analysis. Choose a different stem with the `--beat-detection-stem` switch. You can snap cues to the grid during or after recording.

**Timeline Presets** - generate a complete layered visualisation of a song. For best results, curate presets into Roles and place song markers first. See [docs/user-guide/compositing-and-effects.md](docs/user-guide/compositing-and-effects.md) for details on song marker types (crescendo, diminuendo, etc).

## CLI

```bash
./cleave.py --help
```

Available commands:

* `play` - open a song in the editor. Accepts a source audio file or project slug/path. Omit the target to browse from the editor window.
* `separate` - run stem separation without opening the editor.
* `render` - render a project to video. Accepts a project slug or path.
* `backup` - archive a project directory to a `.cleave-tar.gz` file.
* `restore` - unpack a `.cleave-tar.gz` archive into `projects/<slug>/`.

Use `--help` on any command for more options.

---

## Windows Install Details

The installer (`cleave-<version>-windows-x64-setup.exe`) defaults to `Program Files\Cleave`. Uninstall removes only the program folder; it does not delete your data or settings. The zip (`cleave-<version>-windows-x64.zip`) is the same thing without an installer - unpack and run from that folder.

Launch from the Start Menu or double-click `cleave.exe` to open the editor. You can also drop a `.wav` onto `cleave.exe`, or run from the command line:

```
cleave.exe play
cleave.exe play <wav>
cleave.exe play <project>
cleave.exe render <project>
```

The build is unsigned. If SmartScreen warns on the setup exe or the zip, choose "Run anyway".

### CUDA (NVIDIA GPU)

Stem separation on CPU is slow. The installer can download CUDA files from PyTorch (about 2 GB) for much faster splitting when it detects an NVIDIA GPU (driver 580.88 or newer). Default answer is No. Skip or fail leaves CPU split working fine. Silent setup does not download CUDA unless you pass `/CUDA=1`. The zip stays CPU-only.

---

## Linux Setup

Developed on WSL2, but should work on any Linux with a display.

### Requirements

* Python 3.10+
* FFmpeg
* libprojectM 4.2+ (needs `_opengl_render_frame_fbo` and `_set_frame_time`)
* Optional: NVIDIA GPU + CUDA for faster Demucs separation
* WSL2: [wsl-builds](https://github.com/spoddycoder/wsl-builds) simplifies deps...

```bash
./wsl-stacker.sh spoddycoder dev-ai
./wsl-builder.sh media ffmpeg,libprojectm
```

### Python Dependencies

Create a virtual environment:

```bash
# using venv
python3 -m venv cleave
source cleave/bin/activate

# or using conda
conda create -n cleave python=3.10
conda activate cleave
```

Install dependencies:

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

### WSL2 Troubleshooting

If you experience audio glitches, try disabling `systemd-timesyncd`.
[microsoft/wslg#1257](https://github.com/microsoft/wslg/issues/1257).

If the editor feels sluggish and CPU-bound, check that Mesa is using the GPU (not software `llvmpipe`):

```bash
glxinfo | grep "OpenGL renderer"
# bad:  llvmpipe
# good: D3D12

# if you see llvmpipe, force Mesa's D3D12 driver:
export GALLIUM_DRIVER=d3d12
```
[microsoft/wslg#1332](https://github.com/microsoft/wslg/issues/1332)

---

## Project & Data Locations

Cleave creates a project directory for each song, storing stems, configs and renders together.

**Windows**: `Documents\Cleave\` (projects, presets, textures). Settings: `%APPDATA%\Cleave\config.yaml`.

**Linux**: `~/.local/share/cleave/` (projects, presets, textures). Settings: `~/.config/cleave/config.yaml`.

Override the data root with `CLEAVE_DATA` on any OS.

To add starter packs yourself (instead of the first-launch download), clone them into those folders:

Windows:
```
cd %USERPROFILE%\Documents\Cleave\presets
git clone https://github.com/projectM-visualizer/presets-cream-of-the-crop
git clone https://github.com/projectM-visualizer/presets-milkdrop-original
```

Linux:
```bash
mkdir -p ~/.local/share/cleave/presets
cd ~/.local/share/cleave/presets
git clone https://github.com/projectM-visualizer/presets-cream-of-the-crop
git clone https://github.com/projectM-visualizer/presets-milkdrop-original
```

Optionally grab the texture pack too:
```bash
# Windows: cd %USERPROFILE%\Documents\Cleave\textures
# Linux:
mkdir -p ~/.local/share/cleave/textures
cd ~/.local/share/cleave/textures
git clone https://github.com/projectM-visualizer/presets-milkdrop-texture-pack
```

There are many thousands of Milkdrop presets available online - these are just a few of the best.

A project directory contains:
* `project.yaml` - metadata, song markers, render settings
* `cleave-viz.yaml` - layers, timeline, overlays, post-FX (saved from the editor)
* `signals.json` - audio analysis data used by effects and the timeline conductor
* The original audio file, plus `stems/`, `renders/`, and `presets/` folders

For compositing, effects, and rendering internals see [docs/user-guide/compositing-and-effects.md](docs/user-guide/compositing-and-effects.md). For the Windows build process see [docs/dev/windows-freeze.md](docs/dev/windows-freeze.md).

---

## License

Cleave is source-available under the [Apache License 2.0](LICENSE) with
[Commons Clause](LICENSE). You may use it freely for any purpose, including
work whose output you sell. Commercial distribution of Cleave itself (selling
the software, or a product whose value comes substantially from Cleave) is
not permitted. Output you create with Cleave is yours. See [LICENSE](LICENSE)
for the full text.

## Attribution

* [Milkdrop / projectM](https://github.com/projectM-visualizer/projectM) - visualizer engine
* [Demucs](https://github.com/facebookresearch/demucs) - audio separation
* [Beat This!](https://github.com/CPJKU/beat_this) - beat and downbeat detection
* [FFmpeg](https://ffmpeg.org) - video encoding
* [pygame](https://www.pygame.org/) - window, input, overlay UI, and SDL2 audio
* [OpenGL](https://www.opengl.org/) / [PyOpenGL](https://pyopengl.sourceforge.io/) - layer compositing and rendering
* [ModernGL](https://moderngl.readthedocs.io/) - GPU post-processing
* [librosa](https://librosa.org/) - audio analysis and feature extraction
* [NumPy](https://numpy.org/) - numerical arrays for audio and effects
* [PyYAML](https://pyyaml.org/) - configuration format
* [soundfile](https://python-soundfile.readthedocs.io/) - WAV I/O
