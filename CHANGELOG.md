# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Windows CI freeze prep: committed libprojectM 4.2 DLLs, LGPL license tree, and [packaging/windows/README.md](packaging/windows/README.md); [requirements-freeze.txt](requirements-freeze.txt) pins torch-free PyInstaller deps.
- Relocatable install and resource paths for frozen builds, Windows defaults under `Documents\cleave\` and `%APPDATA%\cleave\`, and a PyInstaller onedir skeleton ([docs/windows-freeze.md](docs/windows-freeze.md)).
- Manual Windows play/render freeze: unpack a zip, `cleave.exe play` an existing project, short `cleave.exe render` to MP4. Stem split is not in this build.
- FFmpeg lookup beside the frozen executable (checkout still uses PATH).

### Changed

- Land P0-P4 architecture work: session is the sole live layer authority, compositor live/offline share one contract, and the tuning panel is a RowSpec registry (`row_spec` / `row_specs/`). Config parse and defaults live in `config_schema/`.
- Document trunk-based releases: `main` is the integration trunk; user-visible notes land under Unreleased; tags are cut from `main` at milestones.
- Default preset and texture paths follow the data root on every OS (including `XDG_DATA_HOME` on Linux).
- Play and render no longer import librosa at load (stem types in `cleave.stems`, PCM resample via soxr). Frozen `separate` and raw-audio `play` fail with a short stem-split message.

### Fixed

- Frozen Windows `play` no longer crashes resolving Documents (`HRESULT` is not in `ctypes.wintypes` on Python 3.10).
- Frozen Windows `play` no longer crashes during pattern-mask plasma init (plasma uses a position-only vertex shader; NVIDIA no longer KeyErrors on stripped `in_uv`).

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
