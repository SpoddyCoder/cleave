# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

- Settings > UI: notification time (until dismissed, or 1-20s). Enter dismisses a toast before it times out.

- Pattern mask: `bars` type (horizontal strips with 1D-cut transitions).
- Project > Render: width, height, and fps rows with increment controls. Values live in `project.yaml` under `render:` and are flushed on Save. Default is 1920x1080 at 60fps. `cleave-viz.yaml` no longer has `render.width` / `render.height` / `render.fps`.

- Project > ProjectM: default beat sensitivity lives in `project.yaml` under `milkdrop:` and is flushed on Save. `cleave-viz.yaml` no longer has an `editor:` block; window size stays in user config.

- Settings > Editor Window: preview quality, width, height, upscale, and a display-size readout. Width, height, and upscale persist on change; a warning toast notes that restart is required to apply the new window size.
- Project menu on the live overlay (below Settings): Save, plus a Render Project submenu for output path, quality, start/end, and a render action. Enter confirms the chosen settings, then encodes with a progress modal and a completion dialog.
- `cleave play` with no target, the Windows Start Menu shortcut, and double-clicking `cleave.exe` open the editor window and browse for a Cleave project or a wav. Keyboard only: arrows and Page Up/Down move, Right enters a folder, Left or Backspace goes to the parent (drive roots step out to a drives listing), Enter opens, Tab reaches the Projects, Home, Drives, and Windows-files shortcuts, Esc quits. A failed stem split or boot shows the error in the window and returns to the picker instead of exiting.
- First-run Demucs and Beat This weight downloads name the model, show a progress bar when byte size is known, and report a clear in-window or stderr error when a network is required the first time.
- Loading screen can show a secondary detail line and a determinate progress bar when a job reports a fraction. Named waits with no byte hook stay message-only.
- Windows installer can download pinned PyTorch CUDA wheels (about 2 GB) when it detects an NVIDIA GPU, for faster stem splitting. Default is No. Failure leaves CPU split. Silent setup does not download unless `/CUDA=1` is passed. Driver 580.88 or newer. The zip stays CPU-only.
- Windows x64 zip (`cleave-<version>-windows-x64.zip`) on tagged GitHub Releases ([`v0.1.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0) is source-only; the next tag attaches the zip and installer). `workflow_dispatch` on [.github/workflows/windows-freeze.yml](.github/workflows/windows-freeze.yml) uploads 5-day Actions artifacts until then. Unpack, SmartScreen "Run anyway", drop a wav onto `cleave.exe` (or `cleave.exe play <wav>`). First-run weights land in `Documents\cleave\models` with named progress in the loading window. CPU `separate` is slow.
- Relocatable install and resource paths for frozen builds, Windows defaults under `Documents\cleave\` and `%APPDATA%\cleave\`, and a PyInstaller onedir skeleton ([docs/windows-freeze.md](docs/windows-freeze.md)).
- Manual Windows freeze: unpack a zip, drop a wav onto `cleave.exe` or `cleave.exe play` an existing project, short `cleave.exe render` to MP4.
- FFmpeg lookup beside the frozen executable (checkout still uses PATH).
- Bare path or project slug on the CLI (`cleave song`, drop a file on `cleave.exe`) opens play. Frozen Windows builds pause on error when the process owns its console.
- Windows installer (`cleave-<version>-windows-x64-setup.exe`) on tagged GitHub Releases and `workflow_dispatch` (5-day Actions artifact). Default install dir is Program Files\Cleave. Unsigned: SmartScreen "Run anyway". Uninstall leaves `Documents\cleave\` and `%APPDATA%\cleave\` in place. The zip remains as a second asset.

### Changed

- New-install defaults: preview quality `full-quality`, UI width mode `fixed`, max width 140, notification time 10s, and ProjectM default beat sensitivity 1.0. Existing user config and `project.yaml` files keep their saved values.
- Default editor window size is 1920x1080 (user config; restart to apply). Existing user config files keep their saved size.
- Project menu section is ProjectM (was Milkdrop). The `project.yaml` key stays `milkdrop:`.
- Settings panel label is Settings; preview quality lives under Editor Window; change editor mode is a button at the bottom of Settings that opens a Visualizer / Preset Curation / Cancel modal. The Project folder icon matches the yellow directory icons in layer menus.
- Play on a wav or incomplete project opens the editor window first, then runs stem split and analyse with loading-screen phase messages, then continues into the live editor. `cleave separate` stays headless.
- Windows zip (`cleave-<version>-windows-x64.zip`) and setup exe (`cleave-<version>-windows-x64-setup.exe`) include CPU stem split.
- Stem split runs Demucs in-process (`get_model` + `apply_model`) instead of `python -m demucs`, so a frozen Windows build can separate without a Python interpreter. Weight downloads land in user data (`Documents\cleave\models` on Windows, XDG data dir `/models` on Linux) via `torch.hub.set_dir`.
- Land P0-P4 architecture work: session is the sole live layer authority, compositor live/offline share one contract, and the tuning panel is a RowSpec registry (`row_spec` / `row_specs/`). Config parse and defaults live in `config_schema/`.
- Document trunk-based releases: `main` is the integration trunk; user-visible notes land under Unreleased; tags are cut from `main` at milestones.
- Default preset and texture paths follow the data root on every OS (including `XDG_DATA_HOME` on Linux).
- Play and render on a complete project no longer import librosa at load (stem types in `cleave.stems`, PCM resample via soxr).

### Fixed

- Settings > UI notification time now hides toasts after the chosen duration, including when you change the value while a toast is showing. Enter dismisses the toast before the timer elapses.
- Opening Timeline > timeline cuts no longer crashes (`hard_cut_enabled_display` was missing from the cuts row formatters).
- Panel Render and `cleave render` at a non-16:9 output no longer stretch opening and closing cards (encode canvas matches output size). Editor export writes the session snapshot in the project directory so presets and `project.yaml` match CLI render.
- New projects created from a wav load the bundled viz template. `preset_switching` is quoted `"on"` / `"off"` (YAML 1.1 otherwise turns unquoted `on`/`off` into booleans), and parse accepts those booleans as well. The template still uses projectM as the switching trigger.
- Live playback opens the system default audio output device instead of the first device SDL happens to enumerate, which on Windows could send audio to a silent endpoint while the transport kept advancing. `CLEAVE_AUDIO_DEVICE` forces an endpoint by name and `CLEAVE_AUDIO_DEBUG=1` prints the device list and mix PCM levels ([docs/windows-freeze.md](docs/windows-freeze.md)).
- Live tuning, help, timeline, modal, and loading overlays use bundled DejaVu Sans Mono instead of the system monospace face, so Windows matches Linux and tree glyphs render instead of tofu.
- Frozen Windows `play` no longer crashes resolving Documents (`HRESULT` is not in `ctypes.wintypes` on Python 3.10).
- Frozen Windows `play` no longer crashes during pattern-mask plasma init (plasma uses a position-only vertex shader; NVIDIA no longer KeyErrors on stripped `in_uv`).
- Frozen Windows `separate` loads the mix with sidecar `ffmpeg.exe` (Demucs `load_track` cannot see a beside-the-exe binary, and falls back to TorchCodec FFmpeg DLLs we do not ship).
- Frozen Windows `separate` writes stem wavs with soundfile and runs Beat This on librosa-loaded audio (`Audio2Beats`), so TorchCodec is not used after Demucs `apply_model`.
- Play keeps the loading-screen OpenGL context for the live editor instead of destroying the compositor and creating a second GL stack on the same window.
- Pattern mask no longer draws back layers off-centre or black. Any preview quality below `full-quality` gives each layer a smaller framebuffer than the composite target, and the hard-mask path copied them at composite size instead of scaling them, so layers below the front one landed in a corner (black bars on the opposite edges) or dropped out entirely depending on the driver.

## [0.1.0] - 2026-08-31

### Added

- Live visual editor with up to eight Milkdrop/libprojectM layers (default four), stem-driven PCM, and real-time preset browsing and tuning.
- Offline render to MP4 via FFmpeg at configurable resolution and frame rate.
- Stem separation with Demucs (`cleave separate`) and `signals.json` analysis for effects and the timeline.
- Timeline: per-track lanes, song markers, beat/bar grid, and generative timeline presets.
- Cleave effects (pulse, flash, grit, vocal hue) and GPU post-FX (bloom, grit, highlight rolloff, chroma boost).
- Project backup and restore (`.cleave-tar.gz`).
- XDG user-data and config directories (`~/.local/share/cleave/`, `~/.config/cleave/`), with `CLEAVE_DATA` override.

[unreleased]: https://github.com/SpoddyCoder/cleave/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0
