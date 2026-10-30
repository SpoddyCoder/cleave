# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

- The navigator lists a single Overlays row. Opening and closing cards stay in the inspector.
- The navigator sits on top of the inspector in one column, and the visualiser uses the freed width.
- Timeline is a top-level navigator row, and Song markers sits under it.
- The menu bar lists commands and checks, and no longer repeats navigator destinations. Layer number keys and Ctrl+, still open the matching navigator page.
- Menu highlight, navigator and inspector focus, and transport readouts follow the same colour roles, with muted secondary transport text and black text on the open menu highlight.
- The starter-pack prompt and the launch error panels draw in the editor UI.
- The launch file picker draws in the editor UI and takes the mouse: click a row, double-click to open, click a shortcut, and wheel to scroll.
- Loading progress draws in the editor UI instead of a pygame overlay.
- Help is a resizable column beside the side column. It follows the focused region and no longer covers the visualiser.
- Warning and error toasts draw centered on the transport bar, only as wide as the message plus a space on each side, with the same colours and swipe. Enter or a click on the toast clears it. The bar no longer shows keyboard scope or record state, and frame rate sits at the right. The tuning panel no longer draws toasts.
- Dialogs draw above the navigator and inspector and respond to the mouse: click an option, click outside or press Esc to cancel, click the text field to place the caret.
- Settings switches to a docked layout (side column on the left), remembers the inspector and help widths in user editor settings (not the project file), opens a menu with Alt plus its underlined letter, and keeps a visible focus ring on the focused shell row when hovered.
- Mouse gestures: hover highlights, wheel scroll on the navigator and inspector, sideways drag on numeric values, and draggable column splitters.
- Timeline and song markers edit in the inspector, and the old tuning list is gone. The Timeline menu opens the strip, applies and resets the timeline, and snaps cues.
- Overlays, Post-FX, and Pattern mask edit in the inspector. The Render menu toggles them, and those sections are gone from the leftover panel.
- Each layer is a navigator node and edits in the inspector. Add layer (Ctrl+L) and Delete layer are on the Layers menu and the inspector. Keys 1-8 jump to layers when the timeline strip is not focused.
- The editor shell now has a navigator, an inspector, and a transport bar. Settings and Project edit in the inspector. Tab cycles regions, and Ctrl+Up/Down move between the top-level sections.
- The editor has a menu bar (File, Project, Layers, Render, Timeline, Settings, Help). Save, Render, Measure latency, and Preset curation moved from the panel to the menus. Ctrl+R starts a render.

### Fixed

- Page Up raises stepped values and Page Down lowers them.
- Menu underlines sit two pixels under the first letter, and popup row highlights are centered on the label with the same padding above and below as the navigator. Popup mouse-hover uses the same hover wash as the navigator and inspector.
- Clicking a menu title opens the dropdown without highlighting a command. Arrow keys start the opaque row highlight.
- The tap-sync detection box draws above the editor panels.
- With the strip open, navigator and inspector keep their keys until the user Tabs to Timeline or clicks the strip.
- Inspector stepped values keep side arrows and sideways drag when the value is off, including placement snap.
- An open menu draws over the focused row highlight.
- Menu and transport rows have more vertical padding. An open menu draws over the transport rule, and menu items use a lighter hover.
- With a menu already open, a click on another top label switches to that menu. A second click on the open label closes it.
- The menu bar rule is a solid white line under the menu names, and open menus draw above the side panels. The transport shows a green play or pause mark, an unbracketed clock, and bar, fps, and rec in the label colour, with a dark rule under the bar. The navigator has a dark border when idle, sits below that rule, and draws its rows in the label colour.
- Inspector groups show an expand or collapse arrow and highlight when focused, so they open and close. Field labels use the label colour, stepped values show side arrows, and the inspector column is half again as wide.
- The live menu bar no longer crashes at startup when Wayland is set and the window is using an X11 OpenGL context.
- A launch failure after the editor has quit pygame is no longer replaced by a video-system error in the file picker.

## [0.3.0] - 2026-10-12

### Added

- Timeline hard and soft cuts include Remove from Cues. It uses the same cue scope choices as Apply to Cues and sets the chosen cues' cut type to none.
- Open wav, mp3, flac, m4a, aac, ogg, aiff, and aif tracks from the file picker or by dropping them on cleave.exe. New projects store a PCM WAV mix and keep the original file path.
- Settings > UI min width row (default 80). Smallest the flexible panel shrinks to.
- Switching Paused row just below the preset file. Enter on a preset list item auditions it and pauses switching.
- Open-file picker: Ctrl+Q quits, same as Esc.
- Offer to download starter Milkdrop preset and texture packs on launch when the presets directory is empty.
- Auto-create user data directories (projects, presets, textures, models) on launch.

### Changed

- Timeline cue readout leaves a wider gap between each label and value pair.
- Shift + Left/Right skips 2s and Ctrl + Left/Right skips 30s from any row, the timeline strip, curation, and move mode. Recording fills the range. Modals keep their own arrows.
- Layer and render headers use E to enable or disable and S to solo (layers) or always on (overlays). PgUp/PgDn is the large value step. Preset directories use Enter to open a folder and Backspace for the parent.
- Timeline strip Left/Right steps cues (seek 10s while recording), Enter seeks to the selected cue, and , / . nudge cue opacity (Ctrl for 10%).
- Visual limiter ducks stacked layers from composite busyness with the timeline off. Its controls moved from the timeline section to Post FX and stay independent of the Post FX master switch and solo.
- Timeline cuts menu is Cue fades. Hard-cut fade in and fade out default to 0.2s; soft-cut fades default to 2.0s. Crossfade is Shift for crossfade.
- Timeline beat / bar grid sits above song markers. Snap Cues there asks whether to snap timeline cues to beats or bars. Snap Cues in the song markers menu pulls nearby cues onto markers.
- Apply to Cues sits at the bottom of each cut section and hides when that cut type is disabled.
- Post-FX fade is an expandable section with fade-in and fade-out start, end, and curve, replacing the two duration rows.
- The preset-switching pause toast omits the layer name. Switching Paused - Enter To Resume sits just below the preset file, at the same indent, so it stays visible when the switching menu is collapsed.
- Populate Presets help says Enter opens the directory selection modal. The choice modal title includes From, and directory options no longer repeat it.
- Layer blend mode and opacity live under a Compositing submenu. While Pattern Mask is enabled those rows are greyed out and ignored.
- New-install defaults: UI width mode `flexible`, max width 160, auto-fade 10s. Existing user config files keep saved values.
- Layer preset directory shows `[..]` when a parent is available and `>` before the counter when a child directory is available.
- Green Enter action rows use capital case, matching Add Layer and Switch to Preset Curation.
- Panel headers read Cleave Settings and Project Settings, with no blank line between them. Transport stays directly under Project Settings.
- Preset switching warnings name the layer: empty switching list, skipped preset, list too short or needing adjustment, populate while timeline is off, and timeline trigger while timeline is off.
- Settings editor-mode row reads Switch to Preset Curation or Switch to Visual Editor for the other mode. Enter asks to confirm with OK or Cancel.
- Open-file picker title asks for a project or an audio file. Up from the first entry focuses shortcuts (Left/Right only; Down returns to the first entry). A blank line sits above the help text, and the current directory shows a folder icon.
- Frozen Windows `cleave.exe` no longer opens a terminal window. Start Menu, desktop, and drop-on-exe stay window-only. Terminal users still get CLI output. Explorer-launched fatal errors use a message box.
- Layer preset switching Left/Right only expands or collapses. Trigger options are off, timer, projectM, and timeline; off hides the other switching rows.
- Windows user data and settings folders are `Documents\Cleave\` and `%APPDATA%\Cleave\` (same casing as `Program Files\Cleave`).

### Fixed

- A long tuning panel shortens while a timeline cue readout is showing, so it no longer covers the cue settings just above the timeline.
- Moving between preset directories selects the first preset in the directory you land on, so Left/Right on the preset file changes files instead of staying on a preset from the previous directory.
- Bar phase nudge keeps cues that start before the first detected beat near the song start. They move by one beat instead of jumping to that beat.
- Project Settings focus highlight spans the full row. The shorter width reserved for the FPS readout stays on Cleave Settings.
- Play no longer crashes when the current preset lives in the project presets folder.
- Warning and error toasts widen the flexible panel the same way other content does.
- Browsing and adding presets while timer, projectM, or timeline switching is on keeps the browsed preset loaded. Add Current Preset adds what is showing.
- Measure Latency counts Enter on the long low tone. The short click just before that tone no longer takes the beat, so the long tone itself registers.
- Frozen Windows `--version` / `--help` print to redirected stdout again (pipes and files), so headless freeze smoke can read `cleave X.Y.Z`.
- Starter pack download progress bar no longer disappears between updates.
- Preset switching list highlights the playing entry in yellow from launch, and Add current preset (Enter / P) copies that playing list preset after the list has advanced.

## [0.2.0] - 2026-09-17

### Added

- Credits card title text row under each card's title section in the panel. Enter opens a text dialog; Confirm updates the title; Save persists it. Section lock blocks editing.
- Credits card body text row under each card's body section in the panel. Enter opens a text dialog; Confirm updates the body; Save persists it. Section lock blocks editing.
- Credits card colours, background margin, and padding in the panel. Colour rows open a hex dialog; Confirm updates the colour; Save persists it. Empty Confirm clears optional backgrounds. Margin and padding are px value rows (Ctrl for x10). Section lock blocks editing.
- Settings > UI: notification time (until dismissed, or 1-20s). Enter dismisses a toast before it times out.
- Pattern mask: `bars` type (horizontal strips with 1D-cut transitions).
- Project > Render: width, height, and fps rows with increment controls. Values live in `project.yaml` under `render:` and are flushed on Save. Default is 1920x1080 at 60fps. `cleave-viz.yaml` no longer has `render.width` / `render.height` / `render.fps`.
- Project > ProjectM: default beat sensitivity lives in `project.yaml` under `milkdrop:` and is flushed on Save. `cleave-viz.yaml` no longer has an `editor:` block; window size stays in user config.
- Settings > Editor Window: preview quality, width, height, upscale, and a display-size readout. Width, height, and upscale persist on change; a warning toast notes that restart is required to apply the new window size.
- Project menu on the live overlay (just above the transport icons): Save, plus a Render Project submenu for output path, quality, start/end, and a render action. Enter confirms the chosen settings, then encodes with a progress modal and a completion dialog.
- `cleave play` with no target, the Windows Start Menu shortcut, and double-clicking `cleave.exe` open the editor window and browse for a Cleave project or a wav. Keyboard only: arrows and Page Up/Down move, Right enters a folder, Left or Backspace goes to the parent (drive roots step out to a drives listing), Enter opens, Tab reaches the Projects, Home, Drives, and Windows-files shortcuts, Esc quits. A failed stem split or boot shows the error in the window and returns to the picker instead of exiting.
- First-run Demucs and Beat This weight downloads name the model, show a progress bar when byte size is known, and report a clear in-window or stderr error when a network is required the first time.
- Loading screen can show a secondary detail line and a determinate progress bar when a job reports a fraction. Named waits with no byte hook stay message-only.
- Windows installer can download pinned PyTorch CUDA wheels (about 2 GB) when it detects an NVIDIA GPU, for faster stem splitting. Default is No. Failure leaves CPU split. Silent setup does not download unless `/CUDA=1` is passed. Driver 580.88 or newer. The zip stays CPU-only.
- Windows x64 zip (`cleave-<version>-windows-x64.zip`) on tagged GitHub Releases ([`v0.1.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0) is source-only; the next tag attaches the zip and installer). `workflow_dispatch` on [.github/workflows/windows-freeze.yml](.github/workflows/windows-freeze.yml) uploads 5-day Actions artifacts until then. Unpack, SmartScreen "Run anyway", drop a wav onto `cleave.exe` (or `cleave.exe play <wav>`). First-run weights land in `Documents\cleave\models` with named progress in the loading window. CPU `separate` is slow.
- Relocatable install and resource paths for frozen builds, Windows defaults under `Documents\cleave\` and `%APPDATA%\cleave\`, and a PyInstaller onedir skeleton ([docs/dev/windows-freeze.md](docs/dev/windows-freeze.md)).
- Manual Windows freeze: unpack a zip, drop a wav onto `cleave.exe` or `cleave.exe play` an existing project, short `cleave.exe render` to MP4.
- FFmpeg lookup beside the frozen executable (checkout still uses PATH).
- Bare path or project slug on the CLI (`cleave song`, drop a file on `cleave.exe`) opens play. Frozen Windows builds pause on error when the process owns its console.
- Windows installer (`cleave-<version>-windows-x64-setup.exe`) on tagged GitHub Releases and `workflow_dispatch` (5-day Actions artifact). Default install dir is Program Files\Cleave. Unsigned: SmartScreen "Run anyway". Uninstall leaves `Documents\cleave\` and `%APPDATA%\cleave\` in place. The zip remains as a second asset.

### Changed

- Text dialog hint is `Press Enter to confirm or ESC to cancel`. Enter while typing highlights Confirm; Esc discards the typed draft without closing. Invalid input shows a yellow error under the field and keeps the caret in the input.
- Overlay colour dialog CTA includes the accepted hex formats: `Change colour (#rgb or #rrggbb)...`.
- Blank row under Settings on the live overlay; Project sits just above the transport icons.
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

- Text dialog Up/Down while editing move the caret between lines instead of jumping to the start of the current line.
- Text dialog caret stays visible at the end of a long single-line draft when the panel grows past its minimum width.
- Settings > UI notification time now hides toasts after the chosen duration, including when you change the value while a toast is showing. Enter dismisses the toast before the timer elapses.
- Opening Timeline > timeline cuts no longer crashes (`hard_cut_enabled_display` was missing from the cuts row formatters).
- Panel Render and `cleave render` at a non-16:9 output no longer stretch opening and closing cards (encode canvas matches output size). Editor export writes the session snapshot in the project directory so presets and `project.yaml` match CLI render.
- New projects created from a wav load the bundled viz template. `preset_switching` is quoted `"on"` / `"off"` (YAML 1.1 otherwise turns unquoted `on`/`off` into booleans), and parse accepts those booleans as well. The template still uses projectM as the switching trigger.
- Live playback opens the system default audio output device instead of the first device SDL happens to enumerate, which on Windows could send audio to a silent endpoint while the transport kept advancing. `CLEAVE_AUDIO_DEVICE` forces an endpoint by name and `CLEAVE_AUDIO_DEBUG=1` prints the device list and mix PCM levels ([docs/dev/windows-freeze.md](docs/dev/windows-freeze.md)).
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

[unreleased]: https://github.com/SpoddyCoder/cleave/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.3.0
[0.2.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.2.0
[0.1.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0
