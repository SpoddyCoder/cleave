# File picker plan

Phase 1 is shipped (loading-screen picker, optional `play` target, frozen no-args): [file-picker-phase-1.md](../plans-completed/file-picker-phase-1.md). Remaining: Phase 2 (`DROPFILE`) and Phase 3 (mid-session open / Ctrl+O).

Related: [editor-first.mdc](../../../.cursor/rules/editor-first.mdc), [architecture-principles.mdc](../../../.cursor/rules/architecture-principles.mdc), [structured-releases.md](../structured-releases.md), [windows-freeze.md](../windows-freeze.md).

---

## Problem

Cold start already opens in-window. `cleave play` with no target, frozen no-args (Start Menu, double-click), and checkout `cleave play` with no target browse for a wav or a project directory, then separate and launch. Drop onto the exe still works via `normalise_argv`.

Two gaps remain:

- No pygame `DROPFILE` handler on the GL window (loading-screen picker or live session).
- No way to switch song mid-session without quitting. Ctrl+O is not wired. [VisualizerApp.run](../../../cleave/viz/app.py) always `pygame.quit()` in `finally`.

Reuse [cleave/open_target.py](../../../cleave/open_target.py) and the Phase 1 picker. A chosen path still goes through `run_separate` then `continue_launch` (cold start) or the same pair after a live teardown (mid-session).

---

## Leave open (not this work)

- Persist last browse directory in global user config.
- Freeze-only native dialog as a shortcut into the same path object.
- Listing extra audio types (`mp3`, `flac`, and similar) that FFmpeg/Demucs can decode.
- Optional installer task for a "Play with Cleave" shell verb.
- Mouse in the picker and live overlay.
- File associations (deferred in [structured-releases.md](../structured-releases.md)).

---

## DROPFILE (Phase 2)

pygame 2 / SDL2 `DROPFILE` onto the GL window. Worth doing on the freeze; best-effort on WSL.

- Pump `DROPFILE` in the loading-screen picker loop and, in Phase 3, in the live event loop.
- `event.file` is a string path. Run the same accept helper. On accept, behave as if the user confirmed that row (cold start: leave picker and `run_separate`; mid-session: unsaved prompt then reload).
- WSL: if the string looks like `C:\...` and the Linux path does not exist, show an in-window message suggesting `/mnt/c/...` or the picker shortcuts. Do not shell out to `wslpath` as a hard dependency.
- Windows freeze: this is the in-window counterpart of drop-on-exe. Drop-on-exe remains argv normalisation and does not need the window open.

Do not use `DROPFILE` as the only open path.

---

## Mid-session reload (Phase 3)

Goal: Ctrl+O (and drop onto the live window) switches song without process exit.

[VisualizerApp.run](../../../cleave/viz/app.py) today: load GL, loop until quit, `finally` persist settings, destroy layers/compositor/post/mask, stop mix player, cleanup user presets, `pygame.quit()`.

Reload needs a loop around "live session" that does **not** call `pygame.quit()` until real quit:

1. User requests open (`Ctrl+O` in [input_dispatch.py](../../../cleave/viz/input_dispatch.py), or `DROPFILE`).
2. If dirty, reuse the unsaved-changes modal pattern in [ConfigSaveController](../../../cleave/viz/config_save.py) (`try_quit` / `UNSAVED_QUIT`). Generalise "pending action after save" rather than adding a second dirty flag. Cancel stays on the current project.
3. Stop mix player, destroy layer pipeline and GL objects that are per-project. Keep the display and the loading compositor (same adopt path used at boot: [_adopt_loading_compositor](../../../cleave/viz/app.py)). Projects can differ in editor display size; go through `adopt_display_size`.
4. Show picker (or use the dropped path). Esc returns to the **current** project only if teardown has not started; once teardown starts, picker cancel should quit or re-open the same project. Prefer: prompt and teardown only after a path is accepted, so Esc is cheap.
5. `run_separate` with loading-screen progress (wav may need stem split). Failure: error message, any key, back to the picker, window still up.
6. `build_runtime_base` + heavy GL init + live loop as today.

Help: add Open (`Ctrl+O`) to [help_content.py](../../../cleave/viz/help_content.py) navigation section.

Order inside Phase 3: accept-then-teardown so cancel is cheap. Do not destroy the live session until the picker returns a path.

Do not bolt file browsing onto [TuningControls](../../../cleave/viz/controls.py). Do not add a `RowKind` or fold the picker into `RowLayout`. Draw via [overlay_primitives](../../../cleave/viz/overlay_primitives.py); do not import `tuning_panel_draw`.

---

## Platform traps

- **Windows drive roots.** `Path("C:\\").parent` is still `C:\`. Without a drives listing, a wav on `D:\` is unreachable from the freeze. WSL can walk `/mnt` -> `d`; native Windows cannot.
- **WSL vs Windows paths.** The picker lists Linux paths (`/mnt/c/Users/...`). A Windows dialog or Explorer drop of `C:\...` will not open on Linux. Accept helper fails closed with a message, not raise into the frame loop.
- **WSLg drop.** Dropping from Windows Explorer onto a Linux pygame window is unreliable. The `/mnt/c/Users` and Drives shortcuts are the WSL answer; `DROPFILE` is extra.
- **Program Files.** Install dir is read-only for normal users. Never start the browser there. User data stays under `Documents\Cleave\` ([windows-freeze.md](../windows-freeze.md)).
- **Blocking native dialogs.** If a freeze-only `IFileOpenDialog` is added later, it blocks the pygame loop. Keep it off the frame path and off WSL.
- **Verification.** Unit tests for picker logic, accept helper, and CLI. Do not launch the editor for routine checks. Frozen Start Menu, `DROPFILE`, drives, and Program Files proof need a Windows box.

---

## What not to change

- Stem split, Demucs, analyse, `project.yaml` shape, persist, overlay row registry, Inno onedir layout, sidecar FFmpeg/libprojectM.
- Drop-on-exe argv normalisation.
- `continue_launch` contract: still takes an already-open `LoadingWindow` and a resolved `project_dir`.
- Live overlay stays keyboard-only. This work does not add mouse hit-testing.
- Phase 1 picker, CLI optional target, and frozen no-args behaviour.

---

## Tests

No editor / OpenGL window in unit tests ([agent-environment.mdc](../../../.cursor/rules/agent-environment.mdc)).

Phase 2: `DROPFILE` path string accepted or rejected; Windows-style path on POSIX does not raise.

Phase 3: unsaved prompt before switch; cancel keeps session; accept issues teardown then rebuild (mocks). Dirty tracking stays computed.
