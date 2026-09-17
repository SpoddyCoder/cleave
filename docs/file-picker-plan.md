# File picker plan

Phase 1 is done (loading-screen picker, optional `play` target, frozen no-args). Phase 2 (`DROPFILE`) and Phase 3 (mid-session open) are still open.

Let the user open a wav or a Cleave project from inside the visualizer, on WSL2 checkout and on the frozen Windows zip or installer, without a terminal.

Related: [editor-first](../.cursor/rules/editor-first.mdc), [architecture principles](../.cursor/rules/architecture-principles.mdc), [structured-releases.md](structured-releases.md), [windows-freeze.md](windows-freeze.md).

---

## Problem

Open is CLI-only. [cleave/cli.py](../cleave/cli.py) `play` requires `target`. A Windows user who launches from the Start Menu or double-clicks `cleave.exe` hits empty argv, which prints help to a console and exits ([cleave.iss](../packaging/windows/cleave.iss) shortcut has no arguments). Drop onto the exe works via `normalise_argv` (3.2.1). There is no in-window open, no `DROPFILE` handler, and no way to switch song without quitting.

The rest of the pipeline already accepts either kind of target. [cleave/separate.py](../cleave/separate.py) `resolve_separate_target` treats a file as audio (project slug from the filename stem) and a directory or slug as a project. [cmd_play](../cleave/cli.py) opens the loading window first, runs `run_separate` with progress, then [continue_launch](../cleave/viz/__init__.py). The picker only has to produce a path.

---

## Principles

- **In-window first.** Overlay, centered panel, or loading screen. No native menu bar. One picker implementation for WSL2 and the freeze.
- **Do not invent a second open pipeline.** A chosen path goes through `run_separate` then `continue_launch` (cold start) or the same pair after a live teardown (mid-session).
- **Thin controller.** New `*_controls` / picker module. Do not bolt file browsing onto [TuningControls](../cleave/viz/controls.py). Do not add a `RowKind` or fold the picker into `RowLayout`.
- **Overlay chrome stays off the tuning panel.** Draw via [overlay_primitives](../cleave/viz/overlay_primitives.py), same rule as modal and help: do not import `tuning_panel_draw`.
- **Errors and progress stay in the window.** Stem split reports through `LoadingWindow.update`. Picker rejections stay in the picker. After a failed `run_separate` or boot, show the error, wait for any key, then return to the picker (cold start) instead of `_exit_error` / `sys.exit`.
- **Keyboard only.** Same as the live overlay. No mouse in the picker. Mouse in Cleave is a later-lifetime release, not this work.
- **Program Files stays read-only.** Default browse root is [projects_dir()](../cleave/paths.py), never `install_dir()`.

---

## Locked

| Question | Answer |
| --- | --- |
| Primary UI | In-window keyboard file browser, not a native OS dialog |
| Mouse | Out. Keyboard only, matching the live overlay |
| Accept | `*.wav` file, or a directory that contains `project.yaml` |
| Default root | `projects_dir()` (`~/.local/share/cleave/projects` on Linux/WSL, `Documents\Cleave\projects` when frozen) |
| Walk off root | Yes, so a wav on the Desktop or another drive is reachable |
| Drives | First-class. Frozen Windows lists drive letters; WSL lists `/mnt/<letter>` mounts. `C:\`.parent is a drives listing, not a dead end |
| Frozen no-args | Becomes `play` with no target: open window, then picker |
| Checkout no-args | Unchanged: print help (CLI, CI) |
| `cleave play` with no target | Always picker (checkout and freeze) |
| Native `IFileOpenDialog` / zenity / tkinter | Out of v1. Freeze-only native dialog is optional polish after Phase 1, not a substitute for WSL |
| File associations | Stay out (already deferred in [structured-releases.md](structured-releases.md)) |
| Other audio extensions | Filter `*.wav` to match current product copy. Widening is a filter change later; `run_separate` already copies any file as the mix |
| Failed separate / boot | Message on the loading screen, any key returns to the picker; window close still quits |
| Mid-session open | Phase 3. Phase 1 does not tear down a live session |

---

## Leave open

- Persist last browse directory in global user config. Phase 1 may remember in-process only.
- Freeze-only native dialog as a shortcut into the same path object.
- Listing extra audio types (`mp3`, `flac`, and similar) that FFmpeg/Demucs can decode.
- Optional installer task for a "Play with Cleave" shell verb.
- Mouse in the picker and live overlay. Out of this work.

---

## Why not a native OS dialog

A Windows `IFileOpenDialog` (ctypes) is fine in the freeze and would look native. It cannot be called from the WSL2 process: that is a Linux pygame/OpenGL app under WSLg.

From WSL you would need a second stack (zenity or xdg-desktop-portal, tkinter, or PowerShell `OpenFileDialog` plus `wslpath`). Those are extra deps, flaky focus on a GL window, and two code paths. Tkinter stays out of the freeze.

[ModalHost](../cleave/viz/modal.py) is Yes/No/choice buttons. A filesystem list does not fit that type. The in-window browser is closer to preset-directory browse (`TRACK_PRESET_DIR`) than to a confirm modal.

---

## Two jobs

### 1. Cold start (Phase 1)

Make `play`'s target optional. No-args Start Menu, zip double-click, and `cleave play` with no argument open the loading window, pick a wav or project, then follow the existing separate-then-launch path. This is the Windows product gap.

### 2. Open while already playing (Phase 3)

Tear down the live runtime without `pygame.quit()`, prompt unsaved changes, stop the mix player, destroy layers/GL, optionally separate a new wav, rebuild `VisualizerSeed` and heavy GL init, keep the same window. [VisualizerApp.run](../cleave/viz/app.py) currently always `pygame.quit()` in `finally`. That is a reload loop, not a small hook.

Phase 1 does not require Phase 3. Phase 3 reuses the same picker widget.

---

## Picker widget

New modules, names indicative:

- [cleave/open_target.py](../cleave/open_target.py): accept/reject a path (wav vs project dir vs neither). No viz import. Shared by the picker, `DROPFILE`, and tests.
- [cleave/viz/file_picker.py](../cleave/viz/file_picker.py): directory listing, view-state dataclass, and actions (`move`, `parent`, `enter`, `accept`, `cancel`, `goto_shortcut`). No pygame, no pygame key constants, fully unit-testable.
- [cleave/viz/file_picker_overlay.py](../cleave/viz/file_picker_overlay.py): draw the view state onto a surface, upload through the loading or live compositor. Uses `overlay_primitives` and theme roles already used by modal (`LABEL`, `VALUE`, `HIGHLIGHT`, scrim). Host maps pygame keys to picker actions.

### Listing

- Rows: parent `..` (when a parent exists), then directories, then `*.wav` files. Alphabetical within each group. Shortcuts are not rows; they are the header list described under Roots and shortcuts.
- At a Windows drive root (`C:\`) or WSL `/mnt/<letter>`, `..` goes to the **drives** listing, not a no-op.
- The drives listing is one row per mounted volume: `C:\`, `D:\`, ... on frozen Windows; `/mnt/c`, `/mnt/d`, ... on WSL when those dirs exist. Enter a drive row to browse it. Do not list Program Files or `install_dir()` here.
- Skip dotfiles except `..`.
- Directories that contain `project.yaml` are shown as projects (suffix or distinct value colour) but remain enterable so the user can inspect; Enter on the directory row accepts the project, Enter is not required on a nested `project.yaml`.
- Permission errors and unreadable dirs: skip or show a disabled row; do not crash.
- Cap a listing at 512 rows plus a truncated note. `project.yaml` probes are per listed directory, not a recursive walk. Do not hang the GL loop on `C:\` or `/`.

### Keys

Match live overlay list navigation and preset-directory tree keys ([help_content.py](../cleave/viz/help_content.py) Navigation / `TRACK_PRESET_DIR`). A list already shows siblings as rows, so unchorded Left/Right are tree walk (the overlay's Ctrl+Left/Right on a preset dir), not sibling-step.

| Key | Action | Overlay analogue |
| --- | --- | --- |
| Up / Down | Move highlight | move row |
| Ctrl+Up / Ctrl+Down | Jump a page | jump section |
| Page Up / Page Down | Jump a page | same as Ctrl+Up/Down |
| Left | Parent directory or drives listing | Ctrl+Left on preset dir |
| Right | Enter directory (including a project directory, without accepting) | Ctrl+Right on preset dir |
| Backspace | Parent directory or drives listing | Backspace on preset dir |
| Enter | Accept wav or project directory; enter a non-project directory | confirm |
| Tab | Move focus between the shortcut header and the file list | (picker only) |
| Esc | Cancel. Cold start: quit the app. Mid-session: dismiss picker, stay on current project | Esc |

Hold-to-repeat uses [KeyRepeatController](../cleave/viz/key_repeat.py) on Up/Down (and Left/Right if held on a long walk). Do not call `pygame.key.set_repeat`; that would leak into the live editor.

Ctrl+O is Phase 3 only (live session). Cold start has no other UI to focus.

### Chrome / help

First-run `projects_dir()` is often empty. Shortcuts and a legend are the UX, not an afterthought.

- Title: `Open a Cleave project or a wav`.
- Shortcut chips, then current path as a `VALUE` line directly above `..`. A long path keeps the tail (`…/current`).
- The shortcut for the directory being listed uses `HIGHLIGHT` (Projects on first show).
- Footer legend, always visible, using help-label colours (`LABEL` key including the colon, `VALUE` description): Enter: open, Right: enter folder, Left/Backspace: parent, Tab: shortcuts, Esc: quit (cold start) or Esc: cancel (mid-session).
- Rejection text on a status line; stay in the picker.

Do not import [help_content.py](../cleave/viz/help_content.py) into the loading-screen picker. Live help panel gains Open only in Phase 3.

### Roots and shortcuts

Always start in `projects_dir()` (create it if missing, same as the rest of user data). `CLEAVE_DATA` is already respected.

Shortcuts are a header list above the file rows, not rows mixed into the listing. Tab moves focus between the header and the file list, so a shortcut is always one keystroke away and the listing stays a plain filesystem view:

- **Projects** (`projects_dir()`)
- **Home** (`Path.home()`)
- **Drives** (the drives listing above)
- **WSL Windows files** when `/mnt/c/Users` exists (the important WSL path; Windows Explorer drop onto a WSLg window is unreliable)
- Frozen Windows: Documents (`windows_documents_dir()`) in addition to Home; Home covers Desktop as a child

Do not list Program Files or `install_dir()` as a shortcut.

### Accept / reject

One helper in [cleave/open_target.py](../cleave/open_target.py):

- File with suffix `.wav` (case-insensitive): accept as audio target.
- Directory containing `project.yaml`: accept as project target. Stricter than CLI `resolve_project` (any existing directory): Enter on `Documents` must not try to play it.
- Anything else: reject with a short in-window message (stay in the picker). Do not call `run_separate` on a rejected path.

The helper returns a `Path` suitable for `resolve_separate_target`.

### Host: loading screen

[LoadingWindow.update](../cleave/viz/loading.py) currently pumps only `QUIT`. Phase 1 adds a picker loop on the same window (a small helper next to loading, so `update` stays progress-only):

1. `open_loading_window()` (already first in `cmd_play`).
2. If `target` is missing, run the picker until accept, cancel/quit, or `QUIT`.
3. On accept, existing `run_separate(..., on_progress=window.update)` then `continue_launch`.
4. On `run_separate` or `continue_launch` failure: draw the error, wait for any key or `QUIT`. Any key returns to the picker (same window). `QUIT` closes. Do not `_exit_error` after a picker-driven attempt.

The picker loop must `tick` (same clock idea as the live app) so it does not busy-spin.

Three things in the current code block the retry loop and change in Phase 1:

- [continue_launch](../cleave/viz/__init__.py) reports boot failure by printing to stderr and calling `sys.exit(1)`. It raises a `LaunchError` instead, and the caller decides: an argv target still becomes `_exit_error`, a picker-driven attempt shows the error and returns to the picker.
- `LoadingWindow.close()` calls `pygame.quit()`, so the retry loop sits above `close()` and reuses one window for every attempt.
- `LoadingWindow.update` is the only event pump and drops every event except `QUIT`. The picker owns its own pump in the new host helper so `update` stays progress-only.

Caption can stay `Cleave` until `continue_launch` sets `Cleave -- {project}`.

---

## CLI

Today [main](../cleave/cli.py) prints help when argv is empty, and `play` requires `target`.

Changes:

- `play.target` becomes optional (`nargs="?"`).
- When frozen and argv is empty, treat as `play` with no target (insert `play` before parse, same idea as `normalise_argv`). Checkout empty argv still prints help.
- `cmd_play`: if `args.target` is None, run the loading-screen picker; if the user quits, return. Otherwise `Path(args.target)` as today.
- `cmd_play` with an argv target that fails `run_separate` keeps today's `_exit_error` (CLI / drop-on-exe). Picker-driven failures return to the picker as above.
- Top-level argparse `usage` still says a command is required; `play --help` must say target is optional and that omitting it opens the picker.

`normalise_argv` stays for drop-on-exe (`cleave.exe <path>`). Empty frozen argv is a separate branch in `main`, not a pretend path.

`--help` / `--version` unchanged. Headless CI smoke stays `--version` and `--help`; it must not open a window.

---

## DROPFILE (Phase 2)

pygame 2 / SDL2 `DROPFILE` onto the GL window. Not a Phase 1 gate (same stance as [structured-releases.md](structured-releases.md) 3.2.1). Worth doing on the freeze; best-effort on WSL.

- Pump `DROPFILE` in the loading-screen picker loop and, in Phase 3, in the live event loop.
- `event.file` is a string path. Run the same accept helper. On accept, behave as if the user confirmed that row (cold start: leave picker and `run_separate`; mid-session: unsaved prompt then reload).
- WSL: if the string looks like `C:\...` and the Linux path does not exist, show an in-window message suggesting `/mnt/c/...` or the picker shortcuts. Do not shell out to `wslpath` as a hard dependency.
- Windows freeze: this is the in-window counterpart of drop-on-exe. Drop-on-exe remains argv normalisation and does not need the window open.

Do not use `DROPFILE` as the only open path.

---

## Mid-session reload (Phase 3)

Goal: Ctrl+O (and drop onto the live window) switches song without process exit.

[VisualizerApp.run](../cleave/viz/app.py) today: load GL, loop until quit, `finally` persist settings, destroy layers/compositor/post/mask, stop mix player, cleanup user presets, `pygame.quit()`.

Reload needs a loop around "live session" that does **not** call `pygame.quit()` until real quit:

1. User requests open (`Ctrl+O` in [input_dispatch.py](../cleave/viz/input_dispatch.py), or `DROPFILE`).
2. If dirty, reuse the unsaved-changes modal pattern in [ConfigSaveController](../cleave/viz/config_save.py) (`try_quit` / `UNSAVED_QUIT`). Generalise "pending action after save" rather than adding a second dirty flag. Cancel stays on the current project.
3. Stop mix player, destroy layer pipeline and GL objects that are per-project. Keep the display and the loading compositor (same adopt path used at boot: [_adopt_loading_compositor](../cleave/viz/app.py)). Projects can differ in editor display size; go through `adopt_display_size`.
4. Show picker (or use the dropped path). Esc returns to the **current** project only if teardown has not started; once teardown starts, picker cancel should quit or re-open the same project. Prefer: prompt and teardown only after a path is accepted, so Esc is cheap.
5. `run_separate` with loading-screen progress (wav may need stem split). Failure: error message, any key, back to the picker, window still up.
6. `build_runtime_base` + heavy GL init + live loop as today.

Help: add Open (`Ctrl+O`) to [help_content.py](../cleave/viz/help_content.py) navigation section.

Order inside Phase 3: accept-then-teardown so cancel is cheap. Do not destroy the live session until the picker returns a path.

---

## Platform traps

- **Windows drive roots.** `Path("C:\\").parent` is still `C:\`. Without a drives listing, a wav on `D:\` is unreachable from the freeze. WSL can walk `/mnt` -> `d`; native Windows cannot.
- **WSL vs Windows paths.** The picker lists Linux paths (`/mnt/c/Users/...`). A Windows dialog or Explorer drop of `C:\...` will not open on Linux. Accept helper fails closed with a message, not raise into the frame loop.
- **WSLg drop.** Dropping from Windows Explorer onto a Linux pygame window is unreliable. The `/mnt/c/Users` and Drives shortcuts are the WSL answer; `DROPFILE` is extra.
- **Program Files.** Install dir is read-only for normal users. Never start the browser there. User data stays under `Documents\Cleave\` ([windows-freeze.md](windows-freeze.md)).
- **Blocking native dialogs.** If a freeze-only `IFileOpenDialog` is added later, it blocks the pygame loop. Keep it off the frame path and off WSL.
- **Verification.** Unit tests for picker logic, accept helper, and CLI. Do not launch the editor for routine checks. Frozen Start Menu, `DROPFILE`, drives, and Program Files proof need a Windows box.

---

## What not to change

- Stem split, Demucs, analyse, `project.yaml` shape, persist, overlay row registry, Inno onedir layout, sidecar FFmpeg/libprojectM.
- Drop-on-exe argv normalisation.
- `continue_launch` contract: still takes an already-open `LoadingWindow` and a resolved `project_dir`.
- Live overlay stays keyboard-only. This work does not add mouse hit-testing.

---

## Phases

### Phase 1 - Loading-screen picker and optional play target (done)

User-facing: Start Menu and `cleave play` with no argument open the window, browse, pick a wav or project, then play (separate first if needed). Checkout `cleave` with no args still prints help.

Build order. Each step lands with its own tests and leaves the tree green.

**1. Accept helper.** New [cleave/open_target.py](../cleave/open_target.py), no viz import:

- `OpenTargetKind` enum: `AUDIO`, `PROJECT`.
- Frozen dataclass `OpenTarget` with `path` and `kind`.
- `classify_open_target(path)` returns an `OpenTarget` or `None`. Suffix `.wav` case-insensitive is `AUDIO`; a directory holding `project.yaml` is `PROJECT`; anything else is `None`.
- `open_target_rejection(path)` returns the short in-window message for a `None` result.

The returned path feeds `resolve_separate_target` with no further massaging. Nothing here may raise on a Windows-style path under POSIX.

**2. Path helpers.** [cleave/paths.py](../cleave/paths.py) has no drive support today. Add:

- `drive_roots()`: drive letters on native Windows, existing `/mnt/<letter>` directories plus `/` on POSIX.

The labelled shortcut header (Projects, Home, Drives, WSL Windows files when `/mnt/c/Users` exists, Documents when frozen) is built in the picker module, since the labels are UI copy. `install_dir()` is never a shortcut.

**3. Picker state.** New [cleave/viz/file_picker.py](../cleave/viz/file_picker.py) with no pygame import at all, not even key constants:

- `PickerAction` enum for the payload-free moves: `MOVE_UP`, `MOVE_DOWN`, `PAGE_UP`, `PAGE_DOWN`, `PARENT`, `ENTER`, `ACCEPT`, `CANCEL`, `TOGGLE_FOCUS`.
- `goto_shortcut(shortcut_id)` is a separate method because it carries a payload.
- `view_state()` returns a `PickerViewState` with rows, current path, shortcut header, focus, and status line.
- Listing follows the Listing section: group order, dotfiles skipped, 512-row cap plus a truncation note, `project.yaml` probed once per listed directory, `PermissionError` and `OSError` skipped rather than raised.
- The drives listing is a synthetic location rather than a `Path`, so both a Windows drive root and `/mnt/<letter>` can name it as their parent.

**4. Picker drawing.** New [cleave/viz/file_picker_overlay.py](../cleave/viz/file_picker_overlay.py), shaped like `modal_overlay.draw`: scrim at `MODAL_SCRIM_ALPHA`, centered panel from `overlay_panel_surface` plus `draw_panel_border`, title and path in `LABEL` and `VALUE`, highlighted row in `HIGHLIGHT`, unreadable rows in `DISABLED`, status line in `ERROR_NOTIFICATION`, footer help items as `LABEL` key plus `VALUE` description. No import of `tuning_panel_draw` or `help_content.py`.

**5. Picker host.** New [cleave/viz/file_picker_host.py](../cleave/viz/file_picker_host.py) next to loading, owning everything pygame:

- `run_file_picker(window)` returns an `OpenTarget`, or `None` when the user cancels or closes the window.
- `show_picker_error(window, message)` draws the message and waits for a key; it returns `False` when the event was `QUIT`.
- Maps pygame keys to `PickerAction`, drives repeat through [KeyRepeatController](../cleave/viz/key_repeat.py) rather than `pygame.key.set_repeat`, ticks a clock, and draws through the window's compositor and `overlay_surface`.

**6. Launch failure as an exception.** [continue_launch](../cleave/viz/__init__.py) raises `LaunchError` instead of printing and calling `sys.exit(1)`, so the caller chooses between exit and picker retry.

**7. CLI.** [cleave/cli.py](../cleave/cli.py):

- `play.add_argument("target", nargs="?", ...)`, with help saying that omitting it opens the picker.
- `main` treats empty argv as `play` only when `is_frozen()`. Checkout empty argv still prints help.
- `cmd_play` with no target loops: picker, then `run_separate(on_progress=window.update)`, then `continue_launch`; a failure at either step calls `show_picker_error` and goes back to the picker.
- `cmd_play` with an argv target behaves exactly as today, `_exit_error` included.

**8. Tests.** [tests/cleave/test_open_target.py](../tests/cleave/test_open_target.py) and new `tests/cleave/viz/test_file_picker.py`, `tests/cleave/viz/test_file_picker_overlay.py` (offscreen surface, like `test_modal_overlay.py`), plus additions to [tests/cleave/test_cli.py](../tests/cleave/test_cli.py). The host loop is exercised with a mock window and synthesized events; no real window anywhere. Cases are the Phase 1 list under Tests.

**9. Docs.** [README.md](../README.md) Windows zip / Start Menu, [windows-freeze.md](windows-freeze.md) shortcut behaviour, [CHANGELOG.md](../CHANGELOG.md) Unreleased. Update the 3.2.1 "no arguments prints help" sentence in [structured-releases.md](structured-releases.md) only as historical note plus current behaviour, or point at this plan; do not rewrite the done-when checklist.

CLI `--help` should say `play` opens a picker when target is omitted.

### Phase 2 - DROPFILE

Pump `DROPFILE` in the Phase 1 picker loop. Same accept helper. WSL Windows-path message. Tests with fake events (no window). Changelog if user-visible on Windows.

### Phase 3 - Mid-session open

`Ctrl+O`, unsaved prompt, accept-then-teardown, reload without `pygame.quit()` until real quit. Help text. Changelog.

---

## Tests

No editor / OpenGL window in unit tests ([agent-environment](../.cursor/rules/agent-environment.mdc)).

Phase 1:

- Accept helper: wav file, project dir, reject `.txt`, reject empty dir, reject dir without `project.yaml`, case-insensitive `.WAV`, Windows-style path on POSIX does not raise.
- Picker state: listing order, `..`, enter dir, parent, Backspace parent, shortcut to `projects_dir()`, skip dotfiles, Esc cancel.
- Drives: Windows drive root parent is the drives listing; WSL `/mnt/c` parent can reach other letter mounts when present; `install_dir()` is not a shortcut.
- CLI: checkout empty argv still help; frozen empty argv becomes play; `play` with no target reaches picker hook (mock window); `play <wav>` and `play <project>` unchanged; `--help` / `--version` still headless.
- Picker-driven `run_separate` failure: error then any-key returns to picker (mock); argv-target failure still `_exit_error`.
- `normalise_argv` drop-on-exe unchanged.

Phase 2: `DROPFILE` path string accepted or rejected; Windows-style path on POSIX does not raise.

Phase 3: unsaved prompt before switch; cancel keeps session; accept issues teardown then rebuild (mocks). Dirty tracking stays computed.

---

## Docs and copy when Phase 1 ships

- README Windows zip: Start Menu / double-click opens the editor, then pick a wav or project. Drop-on-exe and `cleave.exe play <wav>` remain.
- [windows-freeze.md](windows-freeze.md): Start Menu shortcut still has no arguments; that now means picker, not help.
- Help panel: only once Phase 3 adds a live shortcut. Phase 1 help is the picker footer legend.
- Do not bump `cleave.__version__` or cut a tag for this work unless asked.
