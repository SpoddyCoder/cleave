# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Document trunk-based releases: `main` is the integration trunk; user-visible notes land under Unreleased; tags are cut from `main` at milestones.

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
