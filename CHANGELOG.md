# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The editor takes the mouse everywhere: hover highlights, click to select, double-click to open or edit, mouse wheel scrolling, sideways drag on numbers, and side arrows that step on click and repeat while held. Hover tooltips say what a control does; Settings > UI > tooltips turns them off. The mouse pointer is larger, black with a white outline, follows the UI scale, and changes shape over buttons, text fields, borders, and drag handles.
- Right-click menus on the preview, navigator rows, preset list entries, the current preset, the preset directory (Jump to directory), timeline strip rows, clips, the time scale, and song markers. Shift+F10 or the Menu key opens the same menu for the focused row. Menus can hold submenus, list each option's keyboard shortcut, and grey out options that can't be used, with a tooltip saying why.
- The timeline strip edits clips, the way video editors show a track's visible spans. A clip is a span where the layer is on, and the gaps between clips are off. Double-click a gap (or right-click > Add clip here) to add one, Delete to remove it, drag it to move it, drag an edge to trim it, and drag the join between two touching clips to move the boundary. Ctrl+K splits a clip at the playhead. C and Shift+C cycle a clip's cut in and cut out. Moves and trims follow placement snap, and Esc during a drag puts the clip back.
- Selecting a timeline strip row opens it in the inspector, where the selected clip's start, end, opacity, blend, role, cut in, and cut out can be edited. On the strip, Left/Right step between a row's clips and Enter seeks to the selected clip's start.
- Edit > Undo (Ctrl+Z) and Redo (Ctrl+Y) cover clip edits, recorded takes, opacity nudges, and the Generate timeline, Reset timeline, Snap cues, and Set cut type on cues commands.
- The timeline strip zooms with the mouse wheel, scrolls with Shift + wheel, a sideways drag, or the scrollbar under the rows, and pages forward during playback. A time scale above the rows shows labelled minute and second marks; click or drag it to move the playhead. Drag the strip's top edge to make it taller.
- Each timeline strip row has a header like a DAW track: number and stem, then arm, solo, an eye that shows or hides the layer (taking the row over from the timeline), and a back-to-timeline button. Play/pause and REC buttons sit in the strip's top-left corner. Each row draws its clips in its own colour.
- Click a song marker on the timeline strip to select it and show it on the Song Markers page.
- File > New project (Ctrl+N) and File > Open project (Ctrl+O) switch projects without quitting, and ask first if there are unsaved changes. A `*` after the project name in the menu bar and window title marks unsaved changes.
- The editor window can be resized, maximised, or made borderless fullscreen with View > Full Screen Editor (F11). It remembers its size and opens centred.
- View > Play Full Screen (Ctrl+F) shows only the visualiser across the whole display, so you can watch the show as it will look. Esc returns to the editor.
- Settings > UI > UI scale (80% to 200%) resizes all editor text and spacing.
- Settings > UI > Theme picks the editor colours: Ultraviolet (the default), Chocolate, Mint, or Daylight (light). Make your own themes as small text files in the themes folder in the Cleave data folder; Settings > UI has Open themes folder and Reload themes. The user guide lists the colour names.
- Drag the borders between the navigator, inspector, help column, preview, and timeline strip to resize them. Double-click a border, or use View > Reset panel layout, to put it back.
- Back and Forward arrows on the inspector title step through recently visited pages. Alt+Left/Alt+Right, the mouse back and forward buttons, and View > Back and View > Forward do the same.
- Drag a layer by its handle in the navigator to change its z-order, and drag a preset list entry by its handle to reorder the list.
- A "Welcome to Cleave" step on first launch gathers every one-time download in one place: the Milkdrop presets, the Demucs stem separation model, the BeatThis! beat detection model, and the optional Demucs HQ model, each with its own progress, Cancel, and Retry. Settings > Download packages opens it again to fetch anything you skipped.
- On Windows with an NVIDIA driver that supports CUDA 13.2 (driver 595 or newer), the Welcome to Cleave step offers the CUDA Toolkit (about 2 GB, off by default) for much faster stem separation. It needs no admin rights and works with both the installer and the zip.
- Settings > Rescan presets re-reads the presets folder without leaving the editor, so presets added while Cleave is open are picked up.
- Right-click the preview > Grab still saves the preview frame as a PNG in the project's `captures/` folder.
- Settings > Preview > preview quality has an output setting that renders the live preview at the full project resolution.
- Help > About Cleave shows the version, the GitHub link, and the author. `cleave --version` prints the same version, with the number of commits past the last release on a dev build.
- F3 shows a frame timer over the preview, splitting each frame's time into events, layer render, compositing, post-FX, the interface, and presenting. It replaces the overlay profiler that printed to the terminal.
- Settings > Dev Tools > crash log (off by default) writes `crash.log` beside `config.yaml` when Cleave crashes hard.
- Dialogs explain themselves in the help column, describing the highlighted setting and its choices.
- Settings > UI has a navigator expand setting for what a click on a navigator row with pages under it does, and a highlight new page setting for the flash on the inspector title when a new page shows.

### Changed

- The editor has a new layout in place of the single tuning panel. A menu bar (File, Edit, View, Project, Settings, Help) runs across the top, with the transport bar under it. A navigator sits above an inspector in one column: the navigator lists Overlay, Post-FX, Pattern Mask, Timeline, and Layers and their pages, and the inspector edits the selected page. Settings (Preview, UI, Dev Tools) and Project (Resolution, Compositor, ProjectM) pages open from their menus into the inspector; Ctrl+, opens Settings > Preview. Tab cycles the navigator, inspector, preview, and timeline strip, Ctrl+Up/Down move between top-level sections, and 1-8 jump to layers. Menus open with Alt plus the underlined letter, or on hover. The panels stay visible; the auto-fade setting is gone.
- Each layer has Milkdrop Preset, Preset Switching (with Preset List under it), Compositing, and Cleave Effects pages. Pattern Mask has Pattern and Edges & Motion pages.
- Help column descriptions and the user guide are rewritten for experienced users: natural paragraphs, the usual music and video terms, and notes on when you would change a setting.
- Help is a resizable column beside the panels instead of an overlay on the visualiser. It follows the focused region; H or Help > Help shows or hides it. Help text is rewritten in short, plain sentences.
- Navigator rows have clickable on/off, solo, and lock icons, and the inspector title shows the same icons for the page's owner. A page that is off or locked greys or reddens its controls, and hovering the icon says which switch or lock to change.
- The Overlay solo switch is now called preview (key V), since it holds the credits cards on screen at any playhead time.
- Fade, Highlight Rolloff, Chroma Boost, and Visual Limiter each have their own on/off switch. Highlight Rolloff and Chroma Boost no longer have an off mode: a project file that sets `mode: off` must use `enabled: false` instead.
- The editor has a new look: framed buttons with a soft sheen, violet hover, blue selection and focus, yellow for small signals, thicker panel rules, and no green. Editor text is 20% larger at the default UI scale.
- Choices look and work the same in the inspector and in dialogs: up to three options show as segments, longer lists as a dropdown. Left/Right stop at the first or last option instead of wrapping round.
- Dialogs take the mouse and use buttons named for what they do, such as Delete layer and Cancel. Destructive dialogs have a red button and start on Cancel. Every dialog opens on the choices you last confirmed in it until the editor closes, and dialogs that change cues say how many they will change.
- Timeline commands with settings each open one dialog: Generate timeline, Reset timeline, Snap cues, Snap cues to markers, Set cut type on cues, and Populate preset list. The Timeline Preset page is gone, and Generate timeline's choices are no longer saved in `project.yaml` (an existing `timeline: preset:` block is dropped on the next save).
- Every progress bar (opening a project, preparing a new song, rendering, rescanning presets, and downloads) shows in a dialog with a title and the current step.
- The file picker, the welcome step, and startup errors draw in the editor and take the mouse. The file picker has Open and Quit (or Cancel) buttons, a scrollbar, and selects the first entry of a folder it opens.
- Warning and error toasts draw centred on the transport bar. Click a toast or press Enter to clear it.
- The transport bar takes the mouse: click PLAYING / PAUSED to play or pause, drag the time or BAR to scrub, or double-click either to type a time or bar.
- Project > Render Project is split into Project > Resolution (width and height, shared by the live preview and the render) and Project > Render... (Ctrl+R), one dialog for fps, quality, start, and end. Width and height are stored under `resolution:` in `project.yaml`; existing `render.width` and `render.height` are no longer read, so projects return to 1920x1080 until they are set again.
- The live preview takes its shape from Project > Resolution and letterboxes in the visualiser area. It renders only as many pixels as it shows, so a 4K project no longer renders at 4K in a small window.
- Preset curation no longer moves, copies, or deletes preset files. Favourites, blacklist, and cue roles are kept in `cleave.db` in the data folder, keyed by each preset's contents, so they follow a preset that is renamed or moved. F favourites or unfavourites at once, B blacklists after a confirm, and C picks a role or None. Blacklisted presets are hidden from browsing, populate, and random picks.
- Left/Right on a top-level preset directory row also steps through Favourites, each cue role, and Blacklisted, which list matching presets from every folder.
- Preset markers are separate brackets: [F] [B] [L] [R:x]. The preset list marker is [L] (was [U]). Preset rows use two lines so long names no longer overlap the label.
- Opening a project re-indexes presets only when a preset pack folder is added, removed, or renamed, so a large collection opens in a fraction of a second.
- Add layer and Add to preset list act at once and report it in a notification, with no prompt.
- Recording a take keeps the opacity a row was authored at instead of writing full on and full off.
- Timeline visibility overrides start from a row's eye, its number key, its right-click menu, or Shift+Enter, and end from its back-to-timeline button, the menu, or Shift+Enter.
- The latency setting is called audio latency everywhere. Measure audio latency ends in a Detected audio latency dialog where you can adjust the measured value before Apply.
- Song marker rows show the time, a dropdown for the marker type, and a delete icon.
- Overlay card titles and hex colours are edited in place in the inspector, and colour rows open a colour picker with live preview.
- Updated Python to 3.14, libprojectM to 4.2.0, FFmpeg to 9.0.2, and PyTorch to 2.15.0 with CUDA 13.2. The Demucs stem separation models now download from Hugging Face, so Cleave downloads Demucs again the first time you split a song after updating (about 80 MB, or 320 MB with Demucs HQ).

### Fixed

- The Windows editor no longer crashes with an OpenGL "invalid operation" error just after it opens, or when the window or preview size changes.
- The editor no longer freezes now and then when you pause, resume, close it, or switch projects.
- The editor no longer slows down as layers gain preset list entries.
- The first separate no longer fails when the Beat This model host refuses the download. Cleave fetches the beat-tracking and Demucs weights from its own GitHub release first, checks them against a fixed hash, and falls back to the original host.
- The project now saves the bar phase and the show bar grid setting.
- Placement snap to bars follows the bar phase, so cues and song markers land on the bar lines the strip draws.
- Placement snap no longer blocks timeline recording before the first beat or after the last.
- While recording, the timeline strip no longer draws a false fade ramp.
- Removing soft cuts no longer clears hard cuts as well, and the reverse.
- Bloom and chromatic aberration look the same in a reduced-size live preview as in the render.
- Resizing the editor while paused no longer turns the visualiser black.
- projectM warnings and errors name the layer they came from.
- A launch failure is no longer replaced by a video-system error in the file picker.

### Removed

- Overlay and Post-FX no longer have a master on/off switch. Switch each credits card and each Post-FX effect on or off instead. A project's `render.post_fx.enabled` is ignored.
- The Windows installer's CUDA toolkit page and its `/CUDA=1` switch. The CUDA Toolkit download is in the Welcome to Cleave step instead.
- R (Remove from...) in preset curation. F, B, and C undo their own changes.
- The `favourites/`, `blacklist/`, and `roles/<role>/` folders under the preset root are no longer used, and existing ones are treated as ordinary preset folders. `.origin` restore files are gone.
- The `T` key to show the timeline strip. The strip shows when the timeline is on and hides when it is off.
- The timeline's paused preview snapshot. Override a row instead.
- Settings > Editor Window (upscale, display size, and visualiser width and height). The window size comes from the window, and the preview shape from Project > Resolution.
- Settings > UI width mode, max width, min width, and auto-fade, and their user config keys.
- The Y and N keys in dialogs.

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
