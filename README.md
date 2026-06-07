# Cleave

Stem-separated music visualizer: drums drive the pulse, bass drives the warp, each stem gets its own visualizer layer.

Built on the following two awesome open-source projects;

- [projectM](https://github.com/projectM-visualizer/projectM) visualizer, which provides access to thousands of community generated Milkdrop presets.
- [Demucs](https://github.com/facebookresearch/demucs) audio separation library, which uses AI to split an audio file into its constituent stems.

Built on WSL2, but should work on any Linux machine.

**Current focus:** Phase 5 Milkdrop visualizer (four layers, black-key compositing, live tuning overlay, cleave effects at 1280x720 / 30 fps); Phase 7 usability and packaging next. Phase 4 layered visualizer remains the pygame baseline. See [docs/cleave-build-plan.md](docs/cleave-build-plan.md) and [docs/cleave-effect-plan.md](docs/cleave-effect-plan.md).

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
sudo systemctl stop systemd-timesyncd     # disable until next boot
sudo systemctl disable systemd-timesyncd  # disable permanently
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

Four pygame layers stacked with per-surface alpha, each driven by its stem in `signals.json`:

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

Four libprojectM layers, each fed stem PCM at 44100 Hz mono, rendered to tiered OpenGL FBOs and upscaled to **1280x720 @ 30 fps**. Stack order is `layer_z_order` in [cleave.config.yaml](cleave.config.yaml) (bottom to top). Requires libprojectM **4.2+**, community presets, and a display (WSLg or X11 on WSL2).

### Compositing

Milkdrop presets draw on black. Cleave stacks layer textures with **black-key** blending in [cleave/gl_compositor.py](cleave/gl_compositor.py): black pixels are invisible, and each RGB channel's brightness sets how much of that layer contributes. Layer opacity scales the texture before the blend.

Default `blend_mode` is `black-key`. Optional modes per layer:

| Mode | Use |
| --- | --- |
| `black-key` | Default stack. Background stems (other, bass, vocals). |
| `add` | Highlights and transients. Drums. |
| `multiply` | Darken the stack. One layer at a time. |
| `screen` | Soft lift / haze. |
| `subtract`, `difference`, `exclusion`, `max`, `pure-add` | Experimental. |

The live tuning overlay uses SRCALPHA blending separately (real alpha channel, not black-key).

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

- **Track rows section** (upper): one block per stem (header, directory, filename, blend, opacity, beat, then collapsible **cleave effects** with per-effect depth rows when expanded). Headers show as `Layer N: STEM`.
- **Footer rows section** (lower, separated by a gap): transport (drawn transport controls (skip / play-pause / skip) and elapsed time), **SAVE AS NEW CONFIG**, and **OVERWRITE CONFIG** when the active config is not the repo-root template [cleave.config.yaml](cleave.config.yaml).

Navigate with the arrow keys; the focused row is highlighted in orange. Row typography uses light blue labels (`LABEL`), white values (`VALUE`), dimmed inactive text (`DISABLED`), and a locked tint on non-editable sub-rows (`LOCKED`); expand arrows follow value color. See [.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc). **SAVE AS NEW CONFIG** is always shown. **OVERWRITE CONFIG** is hidden only while the active config is the repo-root [cleave.config.yaml](cleave.config.yaml); it appears for any other active path, including after save-as-new updates the active config to a snapshot under [saved-cleave-configs/](saved-cleave-configs/).

| Key | Action |
| --- | --- |
| Up / Down | Move focus between rows (track rows section and footer rows section) |
| Left / Right | Adjust the focused field (see below); hold to repeat on directory, filename, blend, opacity, and beat rows |
| Ctrl + Left / Right | On directory row: go to parent / descend into child (same as Backspace / Enter); larger steps on opacity and beat; on filename row, jump ±10 presets in the current directory (wraps) |
| Enter | On directory row: descend into first alphabetical child directory with presets; on track header: enter z-order move mode (blocked when layer is locked); on SAVE AS NEW CONFIG: write snapshot; on OVERWRITE CONFIG (when shown): confirm then overwrite launch config |
| Ctrl + Enter | On track header: toggle layer lock |
| Backspace | On directory row: go to parent directory (no-op at `preset_root`) |
| Enter (move mode) | Confirm z-order after Up/Down swaps |
| Esc / Backspace (move mode) | Cancel move mode and restore previous z-order |
| Up / Down (move mode) | Swap focused stem up/down in `layer_z_order` |
| Space | Pause / resume playback (hidden shortcut, not shown in overlay) |
| Ctrl + Q | Quit |

**Focused field behaviour**

The directory row shows the path relative to `preset_root` with `(N/TOTAL)` among sibling directories under the parent (only dirs with presets in their subtree; hidden dirs excluded). The filename row shows the current `.milk` name with `(N/TOTAL)` in the current directory, or `NO PRESETS FOUND` in `DISABLED` when the directory has no presets.

| Row | Left / Right | Ctrl + Left / Right |
| --- | --- | --- |
| Track header | Collapse / expand child rows | Disable / enable layer |
| Directory | Previous / next sibling directory (wraps) | Go to parent / descend into child (same as Backspace / Enter; no hold-to-repeat) |
| Filename | Previous / next `.milk` in current directory only (wraps); no-op when empty | Jump ±10 presets in current directory (wraps); no-op when empty |
| Blend mode | Cycle blend modes (see below) | (same step size) |
| Opacity | −1% / +1% | −10% / +10% (0% disables the layer) |
| Beat sensitivity | −0.01 / +0.01 | −0.1 / +0.1 |
| cleave effects header | Collapse / expand effect sub-rows | (no Ctrl variant) |
| Effect sub-row | −1% / +1% depth | −10% / +10% (0-100%) |
| Transport | Seek back / forward 10s | Seek back / forward 30s |

Z-order move mode highlights the track header in blue; Up/Down reorders that stem in the compositor stack (bottom-to-top per `layer_z_order`).

Locked layers show a red padlock on the track header. Lock blocks enable/disable (Ctrl + Left / Right) and move mode (Enter) on that header. When expanded, sub-rows remain visible but are skipped in Up/Down navigation and drawn `LOCKED`; Left / Right expand/collapse on the header still works.

Pause stops PCM feed and freezes layer FBOs (no projectM render); seek flushes projectM buffers. The overlay stays visible for 10 seconds after input, then fades out over 2 seconds; any keypress shows it again (same timing as Phase 4 [cleave/viz_overlay.py](cleave/viz_overlay.py)).

### Config and save

Per-layer preset, size, opacity, `blend_mode`, optional beat sensitivity, `effects` (nested effect and driver depths 0-100%), and `locked` (bool, default false) live under `layers.*` in [cleave.config.yaml](cleave.config.yaml). Stack order is `layer_z_order`. Cycle blend modes Left/Right on the blend row (order matches the compositing table above).

**SAVE AS NEW CONFIG** writes a full reproducible snapshot to [saved-cleave-configs/](saved-cleave-configs/) as `unnamed-N.cleave.config.yaml` (next unused N; see [cleave/config_snapshot.py](cleave/config_snapshot.py)). Snapshots include current presets (individual `.milk` paths relative to `preset_root`), opacity, blend modes, beat values, non-zero effect depths, lock state, and z-order. The launch config is never touched by save-as-new.

**OVERWRITE CONFIG** (when shown) writes the same snapshot to the active config file after a yes/no confirm. Use it when you want the current tuning session to become the default for the next run. It is hidden only while the active config is the repo-root [cleave.config.yaml](cleave.config.yaml); save-as-new switches the active path to a snapshot and enables overwrite for that file.

Override config location with `--config`. Checkpoint detail: [docs/phase-5-plan-part-progressed.md](docs/phase-5-plan-part-progressed.md).

**M1 debug** (drums layer only, skips four-preset validation):

```bash
python scripts/milkdrop_visualizer.py stems/sights-and-sounds-26 \
  --source cleave-resources/source/sights-and-sounds-26.wav \
  --preset ~/milkdrop-presets/presets-cream-of-the-crop/Drawing/some-preset.milk
```

`--preset` accepts a `.milk` file or a directory (same recursive scan as layer config). The same live tuning overlay applies: focus the drums directory or filename row to browse sibling directories (Left/Right) and step `.milk` files (Ctrl+Left/Right for ±10 on the filename row); Enter/Backspace or Ctrl+Right/Ctrl+Left on the directory row to descend or ascend. SAVE AS NEW CONFIG writes to [saved-cleave-configs/](saved-cleave-configs/) when a launch config exists; without `--config`, save-as-new still uses the default unnamed snapshot path.

### Cleave effects

Signal-driven compositor modifiers on top of libprojectM layers. Each stem exposes a fixed roster of effect rows under the **cleave effects** header in the live tuning overlay (expand with Left/Right on that row). Depth is 0-100%; drivers are fixed per row and shown in parentheses (not user-selectable). libprojectM beat sensitivity stays separate (PCM-driven preset reactivity).

| Stem | Effect rows (when expanded) |
| --- | --- |
| Drums | pulse, flare, flash, grit (all onset-driven) |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit (centroid-driven) |

Config shape: `layers.<stem>.effects.<effect>.<driver>` with integer 0-100. Snapshots omit zero keys (sparse). Full taxonomy, constants, and per-stem roster: [docs/cleave-effect-plan.md](docs/cleave-effect-plan.md).

**Verify on a dense track:** after separate and analyse, run the Milkdrop visualizer on a track with strong transients (e.g. `stems/buttercup-24`), expand **cleave effects** per stem, tune non-zero depths, save a snapshot, and confirm playback matches the saved YAML. Manual sign-off is user-run.

See [docs/cleave-build-plan.md](docs/cleave-build-plan.md) for the full roadmap.
