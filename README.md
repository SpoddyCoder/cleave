# Cleave

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own visualizer layer.

Built on the following two awesome open-source projects;

- [projectM](https://github.com/projectM-visualizer/projectM) visualizer, which provides access to thousands of community generated Milkdrop presets.
- [Demucs](https://github.com/facebookresearch/demucs) audio separation library, which uses AI to split an audio file into its constituent stems.

Built on WSL2, but should work on any Linux machine.

**Current focus:** Phase 5 Milkdrop visualizer with live tuning overlay (four layers at 1280x720 / 30 fps); Phase 6 compositor aesthetics next. Phase 4 layered visualizer remains the pygame baseline. See [docs/cleave-build-plan.md](docs/cleave-build-plan.md#phase-56--live-tuning-console).

## Requirements

- Python 3.10+
- FFmpeg
- LibprojectM v4.2.0+ (not officially released yet, cleave requires `_opengl_render_frame_fbo` and `_set_frame_time`)
- Optional: NVIDIA GPU with CUDA for faster audio separation (Demucs is roughly 5 to 10 times faster on GPU)
- On WSL2, [wsl-builds](https://github.com/spoddycoder/wsl-builds) makes installing these dependencies very easy

```bash
# setup an ai development stack: CUDA, Python, Anaconda + others
./wsl-stacker.sh spoddycoder dev-ai
# install ffmpeg system wide
./wsl-builder.sh media ffmpeg
# install libprojectm from latest master branch (apt lags too far behind)
./wsl-builder.sh media libprojectm
```

NOTE: There is a [known issue with WSL2 audio](https://github.com/microsoft/wslg/issues/1257), if you are experiencing glitches / dropouts...

```bash
sudo systemctl stop systemd-timesyncd
```

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

If you chose CUDA, verify GPU support...

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

If this prints `False`, Demucs still runs on CPU.

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
| Ctrl + Q | Quit |
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
| Ctrl + Q | Quit |

All four layers are on at startup. Toggle **d** / **b** / **v** / **o** during playback to isolate stems.

The same controls overlay as the drum pulse visualizer shows all keys plus layer ON/OFF state; it fades when idle and reappears on any keypress.

`scripts/pulse_visualizer.py` remains the objective drum-only baseline for comparing onset response without other stems in the mix.

On WSL2, same display requirement as the drum pulse visualizer (WSLg or X11).

After separate, analyse, and optional onset validation above, run `pulse_visualizer.py` for the drum baseline, then `layered_visualizer.py` for the full composited view.

## Milkdrop visualizer (Phase 5 + 5.6, complete)

Four libprojectM layers, each fed stem PCM at 44100 Hz mono, composited with OpenGL FBOs at tiered resolutions and upscaled to **1280x720 @ 30 fps**. Stack order comes from `layer_z_order` in [cleave.config.yaml](cleave.config.yaml) (bottom to top). Requires libprojectM **4.2+**, community presets, and a display (WSLg or X11 on WSL2).

**Preset install:** clone or symlink community packs under `paths.preset_root` in [cleave.config.yaml](cleave.config.yaml). Set `preset_root` to the milkdrop-presets root (the directory that contains `presets-cream-of-the-crop`, not that subfolder alone). Each `layers.*.preset` may be a **single `.milk` file** or a **directory** (recursive `*.milk` scan at startup, before the window opens; stderr reports preset counts per layer). Layer paths are relative to `preset_root` and should include each pack name once, e.g. `presets-cream-of-the-crop/Drawing/foo.milk`. Example layout:

```bash
ln -s ~/milkdrop-presets ~/cleave/milkdrop-presets   # optional repo symlink
# cleave.config.yaml: preset_root: ~/milkdrop-presets
```

**Run** (after separate; mix path from `signals.json` or `--source`):

```bash
python scripts/milkdrop_visualizer.py stems/sights-and-sounds-26 \
  --source cleave-resources/source/sights-and-sounds-26.wav
```

### Live tuning overlay

A focus-driven tree panel ([cleave/viz_tuning_overlay.py](cleave/viz_tuning_overlay.py), [cleave/viz_tuning_controls.py](cleave/viz_tuning_controls.py)) has two sections:

- **Track rows section** (upper): one six-row block per stem (header, directory, filename, blend, opacity, beat). Headers show as `Layer N: STEM`.
- **Footer rows section** (lower, separated by a gap): transport (drawn transport controls (skip / play-pause / skip) and elapsed time), **SAVE AS NEW CONFIG**, and **OVERWRITE CONFIG** when the active config is not the repo-root template [cleave.config.yaml](cleave.config.yaml).

Navigate with the arrow keys; the focused row is highlighted in orange. **SAVE AS NEW CONFIG** is always shown. **OVERWRITE CONFIG** is hidden only while the active config is the repo-root [cleave.config.yaml](cleave.config.yaml); it appears for any other active path, including after save-as-new updates the active config to a snapshot under [saved-cleave-configs/](saved-cleave-configs/).

| Key | Action |
| --- | --- |
| Up / Down | Move focus between rows (track rows section and footer rows section) |
| Left / Right | Adjust the focused field (see below); hold to repeat on directory, filename, blend, opacity, and beat rows |
| Ctrl + Left / Right | Larger steps on opacity and beat; on filename row, jump ±10 presets in the current directory (wraps) |
| Enter | On directory row: descend into first alphabetical child directory with presets; on track header: enter z-order move mode; on SAVE AS NEW CONFIG: write snapshot; on OVERWRITE CONFIG (when shown): confirm then overwrite launch config |
| Backspace | On directory row: go to parent directory (no-op at the layer's configured preset pack root, the first path segment under `preset_root`) |
| Enter (move mode) | Confirm z-order after Up/Down swaps |
| Up / Down (move mode) | Swap focused stem up/down in `layer_z_order` |
| Space | Pause / resume playback (hidden shortcut, not shown in overlay) |
| Ctrl + Q | Quit |

**Focused field behaviour**

The directory row shows the path relative to `preset_root` with `(N/TOTAL)` among sibling directories under the parent (only dirs with presets in their subtree; hidden dirs excluded). The filename row shows the current `.milk` name with `(N/TOTAL)` in the current directory, or `NO PRESETS FOUND` in dim text when the directory has no presets.

| Row | Left / Right | Ctrl + Left / Right |
| --- | --- | --- |
| Track header | Collapse / expand child rows | Disable / enable layer |
| Directory | Previous / next sibling directory (wraps) | (same step size) |
| Filename | Previous / next `.milk` in current directory only (wraps); no-op when empty | Jump ±10 presets in current directory (wraps); no-op when empty |
| Blend mode | Cycle blend modes (see below) | (same step size) |
| Opacity | −1% / +1% | −10% / +10% (0% disables the layer) |
| Beat sensitivity | −0.01 / +0.01 | −0.1 / +0.1 |
| Transport | Seek back / forward 10s | Seek back / forward 30s |

Z-order move mode highlights the track header in blue; Up/Down reorders that stem in the compositor stack (bottom-to-top per `layer_z_order`).

Pause stops PCM feed and freezes layer FBOs (no projectM render); seek flushes projectM buffers. The overlay stays visible for 10 seconds after input, then fades out over 2 seconds; any keypress shows it again (same timing as Phase 4 [cleave/viz_overlay.py](cleave/viz_overlay.py)).

### Config and save

Per-layer preset, size, opacity, `blend_mode`, and optional beat sensitivity live under `layers.*` in [cleave.config.yaml](cleave.config.yaml). Global compositor stack order is `layer_z_order` (list of stem names, bottom to top).

**Blend modes** (`layers.*.blend_mode`): cycled in this order in the live tuning overlay (Left/Right on the blend row):

| Mode | Role |
| --- | --- |
| `alpha` | Standard over compositing. Background layers (other, bass, vocals): controlled stacking, readable motion underneath. |
| `add` | Additive with alpha weighting. Drums / transient layer: flash, strobe, color blow-out. |
| `multiply` | Darkens the stack. Moody background (often other at low opacity); use sparingly on one layer. |
| `screen` | Soft lift between alpha and add. Gentle haze on vocal/other without full blow-out. |
| `subtract` | Source minus destination (clamped). Chaotic with full-color presets and four layers. |
| `difference` | Destination minus source (clamped). Chaotic; paired inverse of subtract, not true `\|a - b\|`. |
| `exclusion` | Soft inverted multiply. Chaotic with saturated Milkdrop layers. |
| `max` | Per-channel max of source and destination. Competing highlights across stems. |
| `pure-add` | Full-strength additive (`ONE`, `ONE`). Opacity still applies; clips quickly with several bright layers. |

**SAVE AS NEW CONFIG** writes a full reproducible snapshot to [saved-cleave-configs/](saved-cleave-configs/) as `unnamed-N.cleave.config.yaml` (next unused N; see [cleave/config_snapshot.py](cleave/config_snapshot.py)). Snapshots include current presets (individual `.milk` paths relative to `preset_root`), opacity, blend modes, beat values, and z-order. The launch config is never touched by save-as-new.

**OVERWRITE CONFIG** (when shown) writes the same snapshot to the active config file after a yes/no confirm. Use it when you want the current tuning session to become the default for the next run. It is hidden only while the active config is the repo-root [cleave.config.yaml](cleave.config.yaml); save-as-new switches the active path to a snapshot and enables overwrite for that file.

Override config location with `--config`. Checkpoint detail: [docs/phase-5-plan-part-progressed.md](docs/phase-5-plan-part-progressed.md).

**M1 debug** (drums layer only, skips four-preset validation):

```bash
python scripts/milkdrop_visualizer.py stems/sights-and-sounds-26 \
  --source cleave-resources/source/sights-and-sounds-26.wav \
  --preset ~/milkdrop-presets/presets-cream-of-the-crop/Drawing/some-preset.milk
```

`--preset` accepts a `.milk` file or a directory (same recursive scan as layer config). The same live tuning overlay applies: focus the drums directory or filename row to browse sibling directories (Left/Right) and step `.milk` files (Ctrl+Left/Right for ±10 on the filename row); Enter/Backspace on the directory row to descend or ascend. SAVE AS NEW CONFIG writes to [saved-cleave-configs/](saved-cleave-configs/) when a launch config exists; without `--config`, save-as-new still uses the default unnamed snapshot path.

See [docs/cleave-build-plan.md](docs/cleave-build-plan.md) for the full roadmap.
