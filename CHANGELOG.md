# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Cleave has a logo. It shows on a short splash when Cleave starts, with a one-line summary, the credit, and the version (a key or click skips it), in the Welcome to Cleave step, in Help > About Cleave, and above the progress box while a project opens or a new one is created. The C mark sits at the left of the menu bar (click it for About Cleave) and is the icon for the window, the taskbar, `cleave.exe`, the installer, and the Start Menu and desktop shortcuts. On dark themes the logo's navy lettering shows in white so it stays readable.
- A preset browser for each layer. Press Enter or double-click a layer's preset row (or right-click it and choose Browse presets) to see every folder and preset in one list, with how many presets each folder holds. The layer plays each preset as you move to it; Enter (or the back arrow on its title bar) keeps it and Esc goes back to the one you started with. Its filter (click it, or highlight it and press Enter, then type; the list follows as you type) searches every preset in the current folder and the folders under it, or the whole library from the top. A spinner shows while a large folder or search is read. The browser sits over the navigator and inspector, so the preview stays in view.
- The preset directory row shows its path as folders you can click to go straight back to one, coloured like the preset browser's path. In a folder with no subfolders, Enter or a double-click on it opens the preset browser. The preset and preset directory rows, and the directory row's up and down arrows, have tooltips saying what they do.
- A red exclamation mark on a layer's navigator row, and in the icon line under its pages' titles, shows when the layer cannot do what it is set to do: preset switching is on but the preset list is empty or some of its presets cannot load, presets change on each clip but the timeline is off, the layer has no clips, or some clips have no preset, the layer's preset folder is not found, the layer's preset file is not found or failed to load (with switching off), or the layer's stem is silent in the song. Hover over it to see the problem; click it to go to the page where you fix it, with the row to fix selected (for a bad preset list entry, that entry). When a layer has more than one problem, the tooltip says so, and right-clicking the mark or the layer's row puts View all problems at the top of the menu: it lists each one with its own red mark, and choosing one goes to its row.
- A preset that is missing or failed to load shows the layer's red warning sign just left of its position number, on the layer's preset row and on its preset list entry. A missing preset folder shows the sign on the preset directory row instead, and the folders in its path that are not found show in red, there and in the preset browser's path. Hover over the sign to see why.
- Projects can split into 6 stems: drums, bass, vocals, guitar, piano, and other. When you open a new song, Cleave asks how to split it: 4 stems (the default), 4 stems HQ (the slower, cleaner Demucs HQ model, which before was only on the command line), or 6 stems. A 6-stem project starts with six layers, one per stem, and guitar and piano join the driving stem choices, with their own Pulse, Flash, and Grit effects and their own letters on the timeline. Piano separates less cleanly than the other stems, and there is no High Quality model for 6 stems. Demucs 6-stem is offered in the Welcome to Cleave step and Settings > Download packages. On the command line, `--stems 4` or `--stems 6` on `separate` and `play` picks the count (with `play`, a new song then skips the question, and `-hq` starts the question on 4 stems HQ).
- Project > Re-separate stems splits the open project's song again, into 4 stems, 4 stems HQ, or 6 stems, and re-extracts its signals, with progress in the window. Going from 6 stems to 4 moves guitar and piano layers to other and clears their Cleave Effects. Cleave asks to save unsaved changes first.
- Settings > Calibrate tap timing measures how late your key presses land after the beat you hear, including keyboard delay and the habit of tapping slightly early, and stores it as Settings > Latency > tap latency. Song markers dropped and clips recorded while the song plays move back by that much so they land on the beat. Tap latency can be below zero.
- Rewind and forward buttons either side of PLAYING / PAUSED in the transport bar. Click one to move 10 seconds back or forward, hold it down to seek quickly (speeding up the longer you hold), or double-click to go to the start or end of the song.
- Preset list editing: right-click a preset list entry to Cut, Copy, or Duplicate it, paste over, before, or after it from the Paste submenu, and replace it, either from the preset browser (Replace with, or a double-click on the entry, which opens the browser in the entry's folder; the preset you pick takes the entry's place and keeps playing as a preview, and Esc leaves the list as it was) or with the layer's current preset. The Current preset submenu replaces the entry with the current preset, inserts it after the entry, or adds it to the end of the list. Copy and paste work between layers and between projects; a pasted preset is copied into the project like any other list preset. The Milkdrop Preset row offers Copy, and Paste plays the copied preset as a preview without changing the list. Copy is also in the preset browser's right-click menu. The same commands are in the Edit menu, with Ctrl+X, Ctrl+C, Ctrl+V (paste over), Ctrl+Shift+V (paste after), and Ctrl+D (duplicate). On a layer whose presets change on each clip, the items that would add or remove an entry are disabled, since each entry belongs to a clip. Right-click the Preset List page away from its entries, even when the list is empty, to Paste at the end of the list, Add current preset, or Populate list.
- Clear list… in the preset list's right-click menu (on an entry, or on the page away from the entries) empties the layer's preset list after a confirmation. Ctrl+Z puts the list back.
- The Preset List page opens on the layer's preset directory row, the same row as on the Milkdrop Preset page, with its arrows, clickable folders, and preset browser, so you can see and change the folder Populate list takes presets from.
- Right-click menus on the navigator's sub-rows. A card, a Post-FX effect, a layer's page, or a Timeline or Pattern Mask page now lists the on/off, solo, preview, and lock switches that act for it (naming the layer or section they belong to, as Locked (Post-FX)), then the page's own buttons, such as Go to preset list, Snap clips, or Set cut type on clips. The Preset List row has the same menu as the page itself, and Song Markers adds Drop song marker at playhead.
- Presets on the timeline. While the timeline is on, every row shows on its clips what the layer's presets do: never names the layer's preset, on a timer names each preset where it plays with a faint line at each change, projectM decides says so, and each clip names the preset each clip holds. A hooked arrow marks a clip that continues the preset before it. Names are shortened to fit (hover for the full name; theme files set the text colour as `timeline_clip_text`). Right-click a timer layer's clip to replace the preset playing there, or to Convert to each clip.
- With each clip, a clip holds its own preset, or continues the clip it touches before it. Select a clip to change its preset in the inspector (preset: Enter opens the preset browser, Left/Right picks another by the clip's role or from the layer's folder) and whether it starts a new preset or continues; the clip's right-click menu has the same under Preset, and lists the spares to choose from. The Preset List page lists the clips' presets in order with each clip's start time, then the spares no clip holds. Edits to the list flow along the clips, and a message says how many clips changed; timeline edits leave the other clips' presets alone, a deleted clip's preset becomes a spare, and a new clip, whether added, recorded, or split off, takes the first spare (a split with no spares continues). Spare presets light an amber mark on the layer. A clip with no preset shows a red hooked arrow, carries on with the preset before it, and lights the layer's red mark.
- The first time the editor opens a project, a Set up audio latency dialog offers the two latency calibrations, Measure audio latency and Calibrate tap timing, both switched on. OK runs the ones you leave on, one after the other; Cancel skips them. The song stays paused until you finish. It shows only once, and both stay in the Settings menu.
- On a timer, the Preset List page shows when each preset first plays, or not shown for one that never does.

### Changed

- Help lists keys and mouse actions apart, under Keyboard and Mouse headings, everywhere it shows controls. The Keyboard Controls title is now Controls.
- Headings over groups of rows, in the inspector and in dialogs such as Generate timeline and Download packages, have their own colour in each theme instead of a grey that looked disabled. Theme files set it as `subheading`.
- The Preset Switching page's trigger row is now change presets, with the choices never, on a timer, projectM decides, and each clip (before: off, timer, projectm, timeline). Choosing each clip turns the timeline on; from on a timer, the row is cut into clips where the presets change, and with presets the timer never shows kept as spares, and otherwise the clips stay and take the list's presets in order, unless they already hold them. When that would cut clips, replace presets clips hold, or turn the timeline on, a dialog says exactly what will change before you go ahead.
- Turning the timeline on for the first time no longer changes what you see: every layer that is on gets one clip for the whole song. Turning the timeline on or off, and any change to a layer's change presets setting, are now undo steps.
- Generate timeline's refill preset lists option is now clip presets: every new clip on a layer whose presets change on each clip gets a preset, by clip roles, or shuffled or in order from the layer's folder. The dialog says which layers' preset lists it replaces.
- New projects start with every layer's preset list filled: as many presets as the song needs at the layer's preset duration, shuffled from the layer's preset folder. Every layer of a new project uses the Milkdrop Original pack's folder. New projects also start with placement snap off, all Post-FX off, larger card text (title 40 px, body 26 px), and the closing card in the bottom right with the title Credits.
- The preset directory row, the preset row, and preset list entries give each of their two lines a full row's height, so the path and filename no longer crowd the line above.
- In the Welcome to Cleave step, Milkdrop Original and Milkdrop Textures show Required instead of Off and On, and always download, even when you choose Skip. If they are still missing, the step comes back the next time Cleave starts.
- Downloaded packs whose content sits in a single inner folder (Milkdrop Original, Milkdrop Textures) install with that folder's content directly in the pack folder, so the presets list straight under `presets/presets-milkdrop-original` instead of one folder further down. New projects point every layer there.
- Shorter timeline right-click menus. On a clip, Split at playhead and Split here are now At playhead and Here under a Split submenu. On the ruler and on rows, Drop song marker here is now a Drop song marker submenu: At playhead (Ctrl+Enter) or Here. On the time ruler, Generate timeline, Snap clips, Snap clips to markers, Set cut type on clips, and Reset timeline sit under a Timeline submenu.
- Edit > Undo and Redo (Ctrl+Z, Ctrl+Y) now cover preset list edits too: adding, removing, moving, populating, pasting, and replacing entries. A step that changes a locked layer's presets or a locked timeline waits until you unlock it, or both, and Ctrl+Z says which.
- Remove from list (Delete on a preset list entry) removes the entry at once, without asking; Ctrl+Z brings it back.
- A click on a preset list entry now only selects it, and a double-click opens the preset browser to replace it. Enter (or Audition in the right-click menu) still previews the entry.
- In dialogs with settings, the values still line up in one column, but when the dialog is wider than its fields need, the column moves right so the widest value ends at the right edge, instead of leaving empty space after the values.
- Cleave's tagline is now "Stem-driven visualizer for making music videos", on the splash, in Help > About Cleave, and in `cleave --help`.
- The timeline's commands, help, and messages now talk about clips instead of cues: Snap clips, Snap clips to markers, Set cut type on clips, Timeline > Clip Fades, and clip roles in Populate and Generate timeline. Counts of moved or changed boundaries say clip edges, and Generate timeline and Reset timeline count the clips they replace.
- Picking a preset while a layer's switching is on is now a preview. The preset row reads "previewing", a yellow pause icon shows on the layer's navigator row and in the icon line under its pages' titles, and the notification points to it. Click the icon, or Resume switching (previously Resume), to end the preview: the layer jumps straight to the list entry scheduled for that point in the song (for the projectm trigger, the entry playing when the preview started), and a notification says switching has resumed. If a list entry was selected, the selection moves to the scheduled entry, so you can see where switching picked up. Enter on the scheduled entry does not start a preview (and ends one that is running). Before, it carried on from the preset you had been looking at.
- On a layer's Milkdrop Preset page, the preset row has a + button just left of its arrows that adds the preset to the preset list (P still does the same). A Go to preset list button at the left of the icon line under the page title, on this page and on the Preset Switching page, opens the layer's Preset List page.
- On a layer's Preset List page, the Populate button is now Populate list and sits at the left of the icon line under the page title, instead of at the bottom of the list. The icon line has a small gap under the title bar. The preset list entry's context menu item is renamed to match.
- Editing the preset list or the Preset Switching settings while previewing keeps the preview, instead of resuming switching.
- Previewing a preset list entry now shows the folder the preset came from on the preset directory row, so the arrows and the preset browser carry on from there, instead of the project folder Cleave copies list presets into. If the original has been moved, deleted, or edited, it shows the project's copy as before. List entries show the preset's own name, even when the copy had to be renamed. The preset list is saved in a new form, so a project whose layers have a preset list saved by an earlier version does not open.
- With switching on, browsing presets no longer changes the layer's saved preset or marks the project as changed. Turning switching off brings back the preset you chose with it off.
- The help for projectM decides now says it is live, so the editor and a render can switch at different moments.
- The inspector's page title now sits on its own line above a line of the page's icons (on/off, solo, lock, pause, and back and forward), so a long title is no longer squeezed by the icons.
- UI scale is now the first setting on Settings > UI, in its own group. Above 100%, the navigator and inspector column starts wider to fit the larger text: changing the scale sets it to the width for the new scale, and double-clicking its border or View > Reset panel layout puts it back at the width for your scale. At 100% and below it keeps its usual width.
- The < and > arrows on an inspector value, and on stepper settings in dialogs, are now square buttons, the same size as the icons in the inspector title and navigator rows, so they are easier to hit.
- The coloured bar that swipes in behind the inspector title when a new page opens now stays there instead of sliding away.
- The Building layers… step while a project opens now shows a progress bar that fills as each layer is built, like the other progress boxes under the Cleave logo.
- Audio latency and tap latency have their own page, Settings > Latency, with buttons for both tests. Applying a measurement opens the page on the value it set.
- Settings > Measure audio latency is now a flash-and-beep test: the preview flashes on a beep each bar, and you step the audio latency until the two land together. Audio latency only delays the live preview; tapped markers and recordings use tap latency instead. The setting is stored under a new name, so measure it again after updating.
- The Populate preset list dialog now asks where to **pick from**, with its choices listed one per line: clip roles (when presets change on each clip), shuffled (current directory), and in order (current directory). Generate timeline's clip presets choices are listed the same way, and say they fill from each layer's directory.
- The Set cut type on clips dialog now lists its **applies to** choices one per line, the same way as Populate, and names them all clips, except song markers, and song markers only.
- In dialogs, every setting's value now starts in one column after the longest label, like a table, instead of each sitting against the right edge.
- The Welcome to Cleave step lists the presets as separate projectM curated preset packs, one line each: Milkdrop Original and Milkdrop Textures (ticked by default), plus Cream of the Crop, projectM Classic, and En D (not ticked). projectM Classic and En D are new.
- Browsing to a preset folder that only holds subfolders no longer shows NO PRESETS FOUND. The preset row says how many subfolders lie below and how many presets they hold, so you know to go deeper; a folder whose presets are all blacklisted says so.
- Calibrate tap timing no longer needs an unbroken streak of matching taps. It averages your recent taps, ignores a stray one instead of starting over, and reports a value once at least six taps agree to within a few milliseconds, or after 16 taps however loose they are. The progress box shows how many taps it has kept and how settled the estimate is.
- Double-clicking a timeline row now always moves the playhead, the same on a clip or in a gap; it no longer adds a clip in a gap. Right-click a gap and choose Add clip here to add one.
- Right-clicking a clip on the timeline now offers Drop song marker after the clip's own items, the same as a gap, or a song marker's items when one is under the pointer. The clip stays selected, so Delete still deletes the clip.
- Clicking a song marker in a gap on a timeline row now moves the playhead to the marker, as clicking it on the time ruler does, and a double-click there lands on the marker instead of beside it.
- Locks cover presets on clips. A locked timeline refuses list edits that would change its clips, and switching a layer to each clip. A locked layer refuses timeline edits that would free or take its presets (deleting a clip, recording, Generate timeline, Reset timeline). A message says which lock to open.
- The help for a preset list entry is shorter, with the detail in the user guide, and help descriptions leave a small gap between paragraphs.

### Removed

- Seek here and Play from here are gone from the timeline right-click menus. Click the time ruler to move the playhead there, and press Space to play.

### Fixed

- Measure audio latency and Calibrate tap timing no longer leave the song further on than where they started. The song kept moving silently under the click track, so it picked up as far past where you left it as the test had taken.
- With presets changing on each clip, a layer that is on from the start of the song now counts that opening stretch as its first clip. Before, the next clip played the first preset in the list again, and Populate made one preset too few.
- Preset switching always starts at the first preset in the list, live and in renders. Before, it started from whichever preset the layer was last browsed to before saving, so looking at a list entry and saving could move where the song's presets began.
- Playing a preset list entry whose file is missing now shows that file's name on the preset row with the red missing mark, and tries to load it so the failure is reported. Before, the row read "All presets blacklisted" and nothing said what was wrong.
- A long warning or error message in the transport bar no longer covers the play, time, and bar controls or the frame rate. It stays between them and scrolls to show the rest of the message, like a long inspector title.
- Changing a layer's preset while the song is paused (in the preset browser, the preset list, or any other way) now shows the new preset in the preview straight away, instead of only once playback resumes.
- projectM is spelt with a lowercase p in Help > About Cleave and on the Project > projectM page.
- Measuring latency no longer reports 0 ms when your taps land ahead of the beat.
- Pressing Ctrl+C in the console to quit `cleave play` exits quietly instead of printing a traceback.
- Populate list and Generate timeline's clip presets no longer offer clip roles when no preset in your library has a role. Before, choosing it left the preset list empty.
- Stem separation uses the GPU straight after the Welcome to Cleave step downloads the CUDA Toolkit, instead of running on the CPU until Cleave is restarted.
- Resuming preset switching after browsing to another preset folder now takes the preset directory row back to the folder it showed before the preview, as it already did for the preset row. Before, the directory row stayed on the browsed folder, so the arrows stepped through a folder unrelated to what was playing.
- The highlight on the navigator's first and last rows is no longer cut off at the top and bottom of the list.

## [0.4.0] - 2026-11-19

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

- The editor has a new layout in place of the single tuning panel. A menu bar (File, Edit, View, Project, Settings, Help) runs across the top, with the transport bar under it. A navigator sits above an inspector in one column: the navigator lists Overlay, Post-FX, Pattern Mask, Timeline, and Layers and their pages, and the inspector edits the selected page. A project opens with Layers expanded, plus every section that is on or has a card or effect switched on. Settings (Preview, UI, Dev Tools) and Project (Resolution, Compositor, ProjectM) pages open from their menus into the inspector; Ctrl+, opens Settings > Preview. Tab cycles the navigator, inspector, preview, and timeline strip, Ctrl+Up/Down move between top-level sections, and 1-8 jump to layers. Menus open with Alt plus the underlined letter, or on hover. The panels stay visible; the auto-fade setting is gone.
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

[unreleased]: https://github.com/SpoddyCoder/cleave/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.4.0
[0.3.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.3.0
[0.2.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.2.0
[0.1.0]: https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0
