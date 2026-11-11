# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The timeline strip zooms. Scroll the mouse wheel over the strip to zoom in or out around the time under the pointer, down to a one second window. When zoomed, drag a row sideways (or middle-drag anywhere on the time scale or rows) to move along the song, or use Shift + wheel. A scrollbar under the rows shows how much of the song is visible: drag its thumb, or click the track to jump there. During playback the view pages forward when the playhead reaches the right edge, and a seek while paused brings the playhead back into view. The strip is slightly taller to fit the scrollbar.
- The timeline strip shows a time scale above its top row, with labelled minute and second marks spaced to fit the strip width. Faint lines at the song start and end run down through every row.
- The preset directory row shows a folder icon, and the preset, preset list entries, and render output rows show a file icon.
- Drag a preset list entry by the handle in front of its name to reorder it. Esc during the drag puts it back.
- Drag a layer by the handle in front of its name in the navigator to change its z-order. Locked layers can't be dragged.
- View > Fullscreen (F11) switches the editor to borderless fullscreen and back.
- The editor window remembers its size and whether it was maximised, and opens centred. A saved size bigger than the screen opens maximised.
- The editor window has a minimum size, so the menu bar, columns, and timeline strip can't collapse. It grows with the UI scale.
- Resize the editor window by dragging its edges or corners, or maximise it. The menu bar, columns, timeline strip, and visualiser follow the new size, and a project switch keeps it.
- Settings > UI > UI scale (80% to 200%) resizes all editor text and the spacing around it: menus, navigator, inspector, help, transport, notifications, tooltips, dialogs, the file picker, the loading screen, and the timeline strip. It applies at once and is kept as an editor preference. Overlay cards in the visualiser keep their own font sizes.
- Drag the boundary between the navigator and the inspector to set how tall the navigator is, or step it with Settings > UI > navigator height. The height is kept as an editor preference. Fit to rows, the default, sizes the navigator to its tree as before, and stepping Left past the smallest height returns to it.
- Edit > Undo (Ctrl+Z) and Redo (Ctrl+Y) cover Generate timeline, Reset timeline, Snap cues, and Set cut type, including any preset lists and pattern mask settings Generate changed. Undo is unavailable after hand edits to cues, so it never discards them.
- Settings > Preview > preview quality has an output setting that renders the live preview at the full project resolution, to check how it will look in the render.
- File > New project (Ctrl+N) asks for an audio file, and File > Open project (Ctrl+O) asks for a project. Both switch the live session without quitting. A project with unsaved changes asks before leaving.
- The transport bar takes the mouse. Click PLAYING / PAUSED to play or pause. Drag the current time or BAR sideways to scrub by a second or a bar, or double-click either to type a time (M:SS or seconds) or a bar number. Each highlights on hover.
- The timeline strip takes the mouse. Click the time scale to move the playhead there, and drag along it to scrub. Click a row to select it, or on or near a cue to select that cue, without moving the playhead. Double-click a row to move the playhead there; hold the second click and drag to scrub. While recording, a click or drag fills the skipped range like a keyboard seek.
- Play/pause and record buttons sit in the timeline strip's top-left corner, above the row labels. They do what Space and R do. Record is labelled REC, and the label is part of the button. Both are white, and record turns red when a row is armed. While recording, the record button flashes red in step with the REC badge, even under the mouse, so a click shows at once. Otherwise buttons and row labels turn yellow on a wash on hover, like other editor buttons. Double-click a row's number or stem label to arm or disarm it, as A does. This also works mid-take to punch a row in or out. While the timeline is locked, record and arm are blocked, as they are from the keyboard.
- Click a timeline row's eye icon, next to its stem label, to show or hide that layer, as its number key does. While paused it toggles the preview.

### Changed

- The mouse pointer is larger, black with a white outline so it shows over any visual, and follows Settings > UI > UI scale. It changes shape over the editor's controls: a hand on buttons, icons, segments, dropdowns, and the timeline strip's play, REC, eye, and row labels; a text bar on text fields; left-right arrows on column boundaries, draggable transport values, and the timeline's time scale; and a four-way arrow on reorder handles.
- Pattern Mask opens in the navigator like Post-FX and Timeline. Its page keeps the on/off and lock switches; type, density, invert, and seed move to a Pattern child page, and feather and transition to Edges & Motion.
- Selecting a timeline strip row opens it in the inspector, titled like `Timeline > 1  Drums`, the way a navigator row opens its page. The selected cue's time, opacity, cut, blend, and role show there instead of above the strip, and can be edited there: Left/Right on time selects the previous or next cue and Enter seeks to it. The heading says whether it is a start cue (turns the layer on) or an end cue (turns it off). An end cue shows only time and cut, and with no cue selected the page shows no cue rows.
- The flashing playhead line on the timeline strip runs up through the time scale to the top of its ticks.
- The selected timeline row uses the same quiet highlight wash and outline as navigator and inspector rows.
- Editor text and spacing are 20% larger at the default 100% UI scale.
- A thin divider sits under the inspector's page title. Buttons on a page always sit at the bottom, below a divider, instead of among its settings.
- Left/Right on a choice stops at the first or last option instead of wrapping round, in the inspector and in dialogs. On/off rows go off with Left and on with Right, so pressing the same key again leaves them alone.
- Settings > Preview > preview quality lists ultra-performance first and output last, so Right raises quality. Generate timeline... lists cue snap as none, beats, bars.
- Choices look and work the same in the inspector and in dialogs. Up to three options show as segments: click one to choose it. Longer lists show as a dropdown: click it or press Enter (Space in a dialog) to open the list, pick with the mouse or Up/Down and Enter, and Esc closes it unchanged. Left/Right still step any choice. Number values keep their side arrows still as the number changes.
- The Project menu lists its pages as Resolution, Render, Compositor, then ProjectM. Render project... sits above Separate stems..., which is renamed Re-separate stems... (still disabled; use `cleave separate`).
- The navigator holds only the parts of the picture: Overlay, Post-FX, Pattern Mask, Timeline, and Layers. Settings and Project pages open from their menus into the inspector (Ctrl+, opens Settings > Preview). The menu bar is File, Edit (Undo, Redo), View (Fullscreen, timeline strip, preset curation mode), Project, Settings, and Help (Help, About). The Layers and Timeline menus are gone; add and delete layer and the timeline actions are buttons on their inspector pages.
- Song marker rows show the time, then a dropdown for the marker type, with the delete icon at the right edge, in place of a stepper over time and type together.
- Settings has two pages. Preview holds preview quality, residual latency, and Measure latency, replacing Editor Window and Latency Compensation. Navigator side and help side move to UI.
- Project > Compositor > hdr is labelled hdr compositing, and its help says the rendered video is 8-bit either way.
- The live preview takes its shape from Project > Resolution width and height, so it matches the rendered video, and letterboxes in the visualiser area. It renders only as many pixels as the visualiser area shows, up to the project resolution, so a 4K project no longer renders at 4K in a small window. The size follows window and column resizes. Overlay cards keep their size relative to the frame.
- Project > Render Project is split into Project > Resolution (width and height, shared by the live preview and the render) and Project > Render (output, fps, quality, start, end). Width and height are stored in `project.yaml` under `resolution:`; `render:` keeps fps. Existing `render.width` and `render.height` are no longer read, so projects return to 1920x1080 until they are set again.
- Hovering a menu bar title opens its menu without a click, and hovering another title switches to it.
- A layer's preset list has its own Preset List page in the navigator, indented under Preset Switching as its child. It is hidden while the switching trigger is Off.
- A layer's preset directory, preset, and beat sensitivity rows, the Add To Preset List button (renamed from + Add current, hidden while the switching trigger is Off), and the Switching paused / Resume row have their own Milkdrop Preset page in the navigator, above Preset Switching.
- The timeline strip fills the width of its panel, which has the same grey outline as the navigator and inspector instead of a white border. The panel is shorter, leaving more height for the visualiser, navigator, and inspector, and the selected-cue readout sits just above the first layer row. The strip's text, rows, and spacing are 20% smaller than the rest of the UI at every UI scale.
- The rule under the menu bar uses the same grey as the rule under the transport bar.
- Transport bar text is uppercase, and BAR and FPS are white like the clock.
- Overlay card title text and hex colours are edited in place in the inspector, and colour rows show a swatch that opens a colour picker with live preview. Esc reverts. Body text keeps its multi-line dialog. Song marker rows have a delete icon, and clicking a row seeks to the marker.
- The preset list has a toolbar under it with Add current and Populate buttons, and paused switching shows a status line with a Resume button. The Layers navigator row has a + icon for adding a layer. Buttons in a locked section show the locked colour.
- Timeline commands with parameters now open one dialog each, with a line showing what the choice will affect: Generate timeline (replaces the staged rows and Apply Timeline Preset), Snap cues (beats, bars, or song markers), and Set cut type (replaces the four Apply and Remove rows). Reset timeline and Populate presets also use this dialog. The Timeline Preset page is gone; Generate and Reset are on the Timeline page. Dialog values take effect only when confirmed, and Generate keeps its values in the project as before.
- Dialogs use buttons named for what they do, such as Delete layer and Cancel, in place of Yes and No. Destructive dialogs have a red button and start on Cancel. The Y and N keys no longer choose in a dialog.
- Add Layer and Add Current Preset run at once and report it in a notification, with no prompt. Folder and role names in dialogs keep their own capitalisation.
- Commands in the inspector are real buttons, and related commands sit side by side. Left and Right move between buttons in a row. Green is gone from the interface: menu commands, check marks, the play state, and active icons are white, and file picker shortcuts are light blue.
- Layer rows in the navigator are white, matching the top-level rows.
- Navigator sub-rows hang off tree lines that connect each row to its parent.
- Overlay, Post-FX, Pattern Mask, Timeline, and layer navigator rows have clickable on/off and lock icons, and Overlay and layers also have a solo icon. Opening and closing card rows have their own on/off icon, with a matching row at the top of the card's inspector page. Clicking an icon selects its row. Selecting one of those rows lists the same switches as value rows in the inspector, and the on, solo, and lock buttons are gone from the top of the inspector.
- The preset directory row has up and down arrows for the parent and first child directory, and they dim when there is no directory to move to. Clicking the row now only focuses it, and double-clicking opens the first child directory.
- Preset directory, preset, and preset list rows use two lines, so long names no longer overlap the label. The label line holds the markers and the position, and the path or filename sits alone on the line below. Preset list rows show the position without side arrows, since Left and Right do nothing there.
- The menu, navigator, and inspector stay visible. The auto-fade setting is gone.
- The timeline strip opens when a session starts with the timeline enabled. Closing the strip or turning the timeline off hides it.
- Dialog and file-picker highlights sit two pixels out from the text on every side.
- The file picker draws the dialog outline on the keyboard selection and on the row or shortcut under the pointer. Hovering a row or shortcut highlights only that item. Moving the pointer off it clears the highlight until the next hover or key move.
- Dialog options use the same outline as a highlighted navigator or inspector row.
- Inspector rows have 2px more space above and below, so a focused row's outline clears its segments and combo box.
- A text dialog keeps the caret until a click. Clicking Confirm or Cancel applies or discards the text and runs that action.
- The focus outline on the current row and the active panel uses the same colour at a lower intensity.
- Side arrows on adjustable inspector values highlight on hover, step once on click, and repeat while held like Left and Right.
- Help is a check on the Settings menu, and About Cleave is on the File menu. The Help menu and its Keyboard shortcuts item are gone.
- Help is not a Tab stop, and clicking the column does not move focus.
- Settings chooses the navigator column and the help column side separately. They start with the navigator and inspector on the left and help on the right. The Docked layout command is gone.
- The navigator holds all navigation and the inspector holds only the settings rows of the selected page. The roots are Settings, Project, Overlay, Post-FX, Pattern Mask, Timeline, and Layers, each with its own pages, and each layer has Preset Switching, Compositing, and Cleave Effects pages. Branches stay open or closed until you change them, with the arrow, Left and Right, or a click on the name. The Render row is gone. Inspector groups no longer collapse, and the deeper blocks, such as Title and Body on a card, are plain headings.
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
- Settings remembers the inspector and help widths in user editor settings (not the project file), opens a menu with Alt plus its underlined letter, and keeps a visible focus ring on the focused shell row when hovered.
- Mouse gestures: hover highlights, wheel scroll on the navigator and inspector, sideways drag on numeric values, and draggable column splitters.
- Timeline and song markers edit in the inspector, and the old tuning list is gone. The Timeline menu opens the strip, applies and resets the timeline, and snaps cues.
- Overlays, Post-FX, and Pattern mask edit in the inspector, and those sections are gone from the leftover panel.
- Each layer is a navigator node and edits in the inspector. Add layer (Ctrl+L) and Delete layer are on the Layers menu and the inspector. Keys 1-8 jump to layers when the timeline strip is not focused.
- The editor shell now has a navigator, an inspector, and a transport bar. Settings and Project edit in the inspector. Tab cycles regions, and Ctrl+Up/Down move between the top-level sections.
- The editor has a menu bar (File, Project, Layers, Timeline, Settings). Save, Render, Measure latency, and Preset curation moved from the panel to the menus. Ctrl+R starts a render.
- Agent rules and skills now work in both Claude Code and Cursor. Shared instructions are in `AGENTS.md`, and rules and skills live in `.claude/` with symlinks from `.cursor/`.

### Fixed

- Help text wraps whole sentences to the column width instead of breaking mid-sentence, with one sentence per line. Navigator help lists the page description and its keys first, with the navigator keys last, key names are spelled the same way throughout (Left/Right, PgUp/PgDn, Esc), and every help heading is in Capital Case.
- Help text uses short, plain sentences close to Simplified Technical English, and drops detail that the panel already shows. The global keys list Undo/Redo, timeline strip (T), help (H), and full screen (F11), and Alt shortcuts name the real menu letters (F, E, V, P, S, H).
- Resizing a side column while paused no longer turns the visualiser black. The paused frame now scales to the new size.
- The REC badge on the right of the timeline strip no longer overlaps the end of the time scale. It starts where the scale ends.
- The editor no longer freezes now and then when you pause, resume, close it, or switch projects. A freeze ignored Ctrl+C and needed `kill -9`. Pausing now keeps the audio device running and plays silence, and closing stops the audio callback safely first.
- The project now saves the bar phase and the show bar grid setting, so they no longer reset to +0 and off when it reopens.
- Placement snap to bars follows the bar phase, so cues and song markers land on the bar lines the strip draws and timeline generation uses.
- Placement snap no longer blocks timeline recording before the first bar or beat, or rewrites it after the last: intro and outro time outside the beat grid places freely, and every layer-key press flips the layer even when it snaps ahead to the next beat or bar.
- Opening a project from File > Open no longer shrinks the visualiser into one corner with a black gap beside it.
- Timeline on sections no longer draw a 1px line below the bar (or past its right end), so the strip sits centred.
- Menu dropdown labels sit centred in their highlight, and the menu-bar letter underline sits two pixels under the letter at every UI scale.
- Dragging or moving a preset in the Preset List carries the selection highlight with it, as layer reordering does, instead of leaving it on the old position.
- Every song marker row takes the mouse, not just the first, and its delete icon highlights on hover and asks to delete that marker.
- Bloom and chromatic aberration look the same in a reduced-size live preview as in the render, instead of growing larger as the preview gets smaller.
- A top menu dropdown no longer shows a second line a few pixels above its top border the first time it opens.
- The inspector scrolls to keep the keyboard-focused row in view, so moving down a long preset list no longer loses the highlight below the window. The navigator scrolls the same way, just far enough to show the selected row.
- Removing soft cuts no longer clears hard cuts as well, and the reverse. Set cut type now names the type and which cues it applies to.
- Arrow keys move the highlight in dialogs and the file picker even when the pointer stays on another row. Moving the mouse switches back to pointer highlighting.
- The file picker directory name lines up with the folder icon.
- The file picker row highlight keeps its left border, and its top border on the first row.
- The open file picker shows a scrollbar when the directory list is long, and the mouse wheel scrolls that list.
- The transport bar, navigator, and inspector share one horizontal rule where they meet. The focused outline draws above that shared rule.
- The first command in a menu popup sits 4px below the rule under the menu bar.
- Inspector values and their side arrows sit on the same line as the row label.
- Hovering a side arrow on an inspector value centers the highlight on the arrow character.
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
- Field labels use the label colour, stepped values show side arrows, and the inspector column is half again as wide.
- The live menu bar no longer crashes at startup when Wayland is set and the window is using an X11 OpenGL context.
- A launch failure after the editor has quit pygame is no longer replaced by a video-system error in the file picker.

### Removed

- Settings > Editor Window > upscale, display size, and visualiser width and height. The window size comes from the window itself, and the preview resolution from Project > Render.
- Settings > UI width mode, max width, and min width rows, and their `ui_width_mode`, `ui_width`, and `ui_min_width` keys in the user config. The shell layout no longer used them.
- The current time badge above the timeline strip. The transport bar shows the time. REC still shows there while recording.

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
