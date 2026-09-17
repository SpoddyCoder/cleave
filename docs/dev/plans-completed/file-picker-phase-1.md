# File picker Phase 1

Shipped: loading-screen picker, optional `play` target, frozen no-args. Outstanding DROPFILE and mid-session open: [file-picker-plan.md](../plans/file-picker-plan.md).

## Picker widget

New modules, names indicative:

- [cleave/open_target.py](../../../cleave/open_target.py): accept/reject a path (wav vs project dir vs neither). No viz import. Shared by the picker, `DROPFILE`, and tests.
- [cleave/viz/file_picker.py](../../../cleave/viz/file_picker.py): directory listing, view-state dataclass, and actions (`move`, `parent`, `enter`, `accept`, `cancel`, `goto_shortcut`). No pygame, no pygame key constants, fully unit-testable.
- [cleave/viz/file_picker_overlay.py](../../../cleave/viz/file_picker_overlay.py): draw the view state onto a surface, upload through the loading or live compositor. Uses `overlay_primitives` and theme roles already used by modal (`LABEL`, `VALUE`, `HIGHLIGHT`, scrim). Host maps pygame keys to picker actions.

### Listing

- Rows: parent `..` (when a parent exists), then directories, then `*.wav` files. Alphabetical within each group. Shortcuts are not rows; they are the header list described under Roots and shortcuts.
- At a Windows drive root (`C:\`) or WSL `/mnt/<letter>`, `..` goes to the **drives** listing, not a no-op.
- The drives listing is one row per mounted volume: `C:\`, `D:\`, ... on frozen Windows; `/mnt/c`, `/mnt/d`, ... on WSL when those dirs exist. Enter a drive row to browse it. Do not list Program Files or `install_dir()` here.
- Skip dotfiles except `..`.
- Directories that contain `project.yaml` are shown as projects (suffix or distinct value colour) but remain enterable so the user can inspect; Enter on the directory row accepts the project, Enter is not required on a nested `project.yaml`.
- Permission errors and unreadable dirs: skip or show a disabled row; do not crash.
- Cap a listing at 512 rows plus a truncated note. `project.yaml` probes are per listed directory, not a recursive walk. Do not hang the GL loop on `C:\` or `/`.

### Keys

Match live overlay list navigation and preset-directory tree keys ([help_content.py](../../../cleave/viz/help_content.py) Navigation / `TRACK_PRESET_DIR`). A list already shows siblings as rows, so unchorded Left/Right are tree walk (the overlay's Ctrl+Left/Right on a preset dir), not sibling-step.

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

Hold-to-repeat uses [KeyRepeatController](../../../cleave/viz/key_repeat.py) on Up/Down (and Left/Right if held on a long walk). Do not call `pygame.key.set_repeat`; that would leak into the live editor.

Ctrl+O is Phase 3 only (live session). Cold start has no other UI to focus.

### Chrome / help

First-run `projects_dir()` is often empty. Shortcuts and a legend are the UX, not an afterthought.

- Title: `Open a Cleave project or a wav`.
- Shortcut chips, then current path as a `VALUE` line directly above `..`. A long path keeps the tail (`…/current`).
- The shortcut for the directory being listed uses `HIGHLIGHT` (Projects on first show).
- Footer legend, always visible, using help-label colours (`LABEL` key including the colon, `VALUE` description): Enter: open, Right: enter folder, Left/Backspace: parent, Tab: shortcuts, Esc: quit (cold start) or Esc: cancel (mid-session).
- Rejection text on a status line; stay in the picker.

Do not import [help_content.py](../../../cleave/viz/help_content.py) into the loading-screen picker. Live help panel gains Open only in Phase 3.

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

One helper in [cleave/open_target.py](../../../cleave/open_target.py):

- File with suffix `.wav` (case-insensitive): accept as audio target.
- Directory containing `project.yaml`: accept as project target. Stricter than CLI `resolve_project` (any existing directory): Enter on `Documents` must not try to play it.
- Anything else: reject with a short in-window message (stay in the picker). Do not call `run_separate` on a rejected path.

The helper returns a `Path` suitable for `resolve_separate_target`.

### Host: loading screen

[LoadingWindow.update](../../../cleave/viz/loading.py) currently pumps only `QUIT`. Phase 1 adds a picker loop on the same window (a small helper next to loading, so `update` stays progress-only):

1. `open_loading_window()` (already first in `cmd_play`).
2. If `target` is missing, run the picker until accept, cancel/quit, or `QUIT`.
3. On accept, existing `run_separate(..., on_progress=window.update)` then `continue_launch`.
4. On `run_separate` or `continue_launch` failure: draw the error, wait for any key or `QUIT`. Any key returns to the picker (same window). `QUIT` closes. Do not `_exit_error` after a picker-driven attempt.

The picker loop must `tick` (same clock idea as the live app) so it does not busy-spin.

Three things in the current code block the retry loop and change in Phase 1:

- [continue_launch](../../../cleave/viz/__init__.py) reports boot failure by printing to stderr and calling `sys.exit(1)`. It raises a `LaunchError` instead, and the caller decides: an argv target still becomes `_exit_error`, a picker-driven attempt shows the error and returns to the picker.
- `LoadingWindow.close()` calls `pygame.quit()`, so the retry loop sits above `close()` and reuses one window for every attempt.
- `LoadingWindow.update` is the only event pump and drops every event except `QUIT`. The picker owns its own pump in the new host helper so `update` stays progress-only.

Caption can stay `Cleave` until `continue_launch` sets `Cleave -- {project}`.

---

## CLI

Today [main](../../../cleave/cli.py) prints help when argv is empty, and `play` requires `target`.

Changes:

- `play.target` becomes optional (`nargs="?"`).
- When frozen and argv is empty, treat as `play` with no target (insert `play` before parse, same idea as `normalise_argv`). Checkout empty argv still prints help.
- `cmd_play`: if `args.target` is None, run the loading-screen picker; if the user quits, return. Otherwise `Path(args.target)` as today.
- `cmd_play` with an argv target that fails `run_separate` keeps today's `_exit_error` (CLI / drop-on-exe). Picker-driven failures return to the picker as above.
- Top-level argparse `usage` still says a command is required; `play --help` must say target is optional and that omitting it opens the picker.

`normalise_argv` stays for drop-on-exe (`cleave.exe <path>`). Empty frozen argv is a separate branch in `main`, not a pretend path.

`--help` / `--version` unchanged. Headless CI smoke stays `--version` and `--help`; it must not open a window.

---

### Phase 1 - Loading-screen picker and optional play target (done)

User-facing: Start Menu and `cleave play` with no argument open the window, browse, pick a wav or project, then play (separate first if needed). Checkout `cleave` with no args still prints help.

Build order. Each step lands with its own tests and leaves the tree green.

**1. Accept helper.** New [cleave/open_target.py](../../../cleave/open_target.py), no viz import:

- `OpenTargetKind` enum: `AUDIO`, `PROJECT`.
- Frozen dataclass `OpenTarget` with `path` and `kind`.
- `classify_open_target(path)` returns an `OpenTarget` or `None`. Suffix `.wav` case-insensitive is `AUDIO`; a directory holding `project.yaml` is `PROJECT`; anything else is `None`.
- `open_target_rejection(path)` returns the short in-window message for a `None` result.

The returned path feeds `resolve_separate_target` with no further massaging. Nothing here may raise on a Windows-style path under POSIX.

**2. Path helpers.** [cleave/paths.py](../../../cleave/paths.py) has no drive support today. Add:

- `drive_roots()`: drive letters on native Windows, existing `/mnt/<letter>` directories plus `/` on POSIX.

The labelled shortcut header (Projects, Home, Drives, WSL Windows files when `/mnt/c/Users` exists, Documents when frozen) is built in the picker module, since the labels are UI copy. `install_dir()` is never a shortcut.

**3. Picker state.** New [cleave/viz/file_picker.py](../../../cleave/viz/file_picker.py) with no pygame import at all, not even key constants:

- `PickerAction` enum for the payload-free moves: `MOVE_UP`, `MOVE_DOWN`, `PAGE_UP`, `PAGE_DOWN`, `PARENT`, `ENTER`, `ACCEPT`, `CANCEL`, `TOGGLE_FOCUS`.
- `goto_shortcut(shortcut_id)` is a separate method because it carries a payload.
- `view_state()` returns a `PickerViewState` with rows, current path, shortcut header, focus, and status line.
- Listing follows the Listing section: group order, dotfiles skipped, 512-row cap plus a truncation note, `project.yaml` probed once per listed directory, `PermissionError` and `OSError` skipped rather than raised.
- The drives listing is a synthetic location rather than a `Path`, so both a Windows drive root and `/mnt/<letter>` can name it as their parent.

**4. Picker drawing.** New [cleave/viz/file_picker_overlay.py](../../../cleave/viz/file_picker_overlay.py), shaped like `modal_overlay.draw`: scrim at `MODAL_SCRIM_ALPHA`, centered panel from `overlay_panel_surface` plus `draw_panel_border`, title and path in `LABEL` and `VALUE`, highlighted row in `HIGHLIGHT`, unreadable rows in `DISABLED`, status line in `ERROR_NOTIFICATION`, footer help items as `LABEL` key plus `VALUE` description. No import of `tuning_panel_draw` or `help_content.py`.

**5. Picker host.** New [cleave/viz/file_picker_host.py](../../../cleave/viz/file_picker_host.py) next to loading, owning everything pygame:

- `run_file_picker(window)` returns an `OpenTarget`, or `None` when the user cancels or closes the window.
- `show_picker_error(window, message)` draws the message and waits for a key; it returns `False` when the event was `QUIT`.
- Maps pygame keys to `PickerAction`, drives repeat through [KeyRepeatController](../../../cleave/viz/key_repeat.py) rather than `pygame.key.set_repeat`, ticks a clock, and draws through the window's compositor and `overlay_surface`.

**6. Launch failure as an exception.** [continue_launch](../../../cleave/viz/__init__.py) raises `LaunchError` instead of printing and calling `sys.exit(1)`, so the caller chooses between exit and picker retry.

**7. CLI.** [cleave/cli.py](../../../cleave/cli.py):

- `play.add_argument("target", nargs="?", ...)`, with help saying that omitting it opens the picker.
- `main` treats empty argv as `play` only when `is_frozen()`. Checkout empty argv still prints help.
- `cmd_play` with no target loops: picker, then `run_separate(on_progress=window.update)`, then `continue_launch`; a failure at either step calls `show_picker_error` and goes back to the picker.
- `cmd_play` with an argv target behaves exactly as today, `_exit_error` included.

**8. Tests.** [tests/cleave/test_open_target.py](../../../tests/cleave/test_open_target.py) and new `tests/cleave/viz/test_file_picker.py`, `tests/cleave/viz/test_file_picker_overlay.py` (offscreen surface, like `test_modal_overlay.py`), plus additions to [tests/cleave/test_cli.py](../../../tests/cleave/test_cli.py). The host loop is exercised with a mock window and synthesized events; no real window anywhere. Cases are the Phase 1 list under Tests.

**9. Docs.** [README.md](../../../README.md) Windows zip / Start Menu, [windows-freeze.md](../windows-freeze.md) shortcut behaviour, [CHANGELOG.md](../../../CHANGELOG.md) Unreleased. Update the 3.2.1 "no arguments prints help" sentence in [structured-releases.md](../structured-releases.md) only as historical note plus current behaviour, or point at this plan; do not rewrite the done-when checklist.

CLI `--help` should say `play` opens a picker when target is omitted.

## Tests

No editor / OpenGL window in unit tests ([agent-environment](../../../.cursor/rules/agent-environment.mdc)).

Phase 1:

- Accept helper: wav file, project dir, reject `.txt`, reject empty dir, reject dir without `project.yaml`, case-insensitive `.WAV`, Windows-style path on POSIX does not raise.
- Picker state: listing order, `..`, enter dir, parent, Backspace parent, shortcut to `projects_dir()`, skip dotfiles, Esc cancel.
- Drives: Windows drive root parent is the drives listing; WSL `/mnt/c` parent can reach other letter mounts when present; `install_dir()` is not a shortcut.
- CLI: checkout empty argv still help; frozen empty argv becomes play; `play` with no target reaches picker hook (mock window); `play <wav>` and `play <project>` unchanged; `--help` / `--version` still headless.
- Picker-driven `run_separate` failure: error then any-key returns to picker (mock); argv-target failure still `_exit_error`.
- `normalise_argv` drop-on-exe unchanged.


---
