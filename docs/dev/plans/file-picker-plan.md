# File picker plan

Phase 1 is shipped (loading-screen picker, optional `play` target, frozen no-args): [file-picker-phase-1.md](../plans-completed/file-picker-phase-1.md). Phase 3 is shipped (File > New project and File > Open project on one window). Remaining: Phase 2 (`DROPFILE`).

Related: [editor-first.mdc](../../../.cursor/rules/editor-first.mdc), [architecture-principles.mdc](../../../.cursor/rules/architecture-principles.mdc), [structured-releases.md](../structured-releases.md), [windows-freeze.md](../windows-freeze.md).

---

## Problem

Cold start already opens in-window. `cleave play` with no target, frozen no-args (Start Menu, double-click), and checkout `cleave play` with no target browse for an audio file or a project directory, then separate and launch. Supported audio is wav, mp3, flac, m4a, aac, ogg, aiff, and aif. A new project stores a PCM WAV mix; stem split, playback, and render use that WAV. Drop onto the exe still works via `normalise_argv`.

One gap remains:

- No pygame `DROPFILE` handler on the GL window (loading-screen picker or live session).

File > New project (Ctrl+N) and File > Open project (Ctrl+O) switch the live session on the same window. Accept, then tear down: Esc cancels and leaves the session up. A dirty project reuses the unsaved-changes prompt. Audio goes through `run_separate` on the loading window; a project directory launches directly. [VisualizerApp.run](../../../cleave/viz/app.py) returns the switch request and does not call `pygame.quit()`; the session loop closes the window on quit.

---

## Leave open (not this work)

- Persist last browse directory in global user config.
- Freeze-only native dialog as a shortcut into the same path object.
- Optional installer task for a "Play with Cleave" shell verb.
- Mouse in the live overlay.
- File associations (deferred in [structured-releases.md](../structured-releases.md)).

---

## DROPFILE (Phase 2)

pygame 2 / SDL2 `DROPFILE` onto the GL window. Worth doing on the freeze; best-effort on WSL.

- Pump `DROPFILE` in the loading-screen picker loop and in the live event loop.
- `event.file` is a string path. Run the same accept helper. On accept, behave as if the user confirmed that row (cold start: leave picker and `run_separate`; mid-session: unsaved prompt then reload).
- WSL: if the string looks like `C:\...` and the Linux path does not exist, show an in-window message suggesting `/mnt/c/...` or the picker shortcuts. Do not shell out to `wslpath` as a hard dependency.
- Windows freeze: this is the in-window counterpart of drop-on-exe. Drop-on-exe remains argv normalisation and does not need the window open.

Do not use `DROPFILE` as the only open path.

---

## Mid-session reload (Phase 3)

Shipped. File > New project (Ctrl+N) asks for an audio file. File > Open project (Ctrl+O) asks for a project. Both run in the live window.

Accept, then tear down. Esc cancels and keeps the session. A dirty project uses the unsaved-changes prompt; save or discard marks the switch and keeps the target, and cancel drops it. The session loop keeps the display and the loading compositor, stem-splits audio with loading progress, and launches the project. Failure shows an error on the window and returns to the picker in that request's mode. Quit closes the window once.

`DROPFILE` onto the live window is still Phase 2.

---

## Platform traps

- **Windows drive roots.** `Path("C:\\").parent` is still `C:\`. Without a drives listing, an audio file on `D:\` is unreachable from the freeze. WSL can walk `/mnt` -> `d`; native Windows cannot.
- **WSL vs Windows paths.** The picker lists Linux paths (`/mnt/c/Users/...`). A Windows dialog or Explorer drop of `C:\...` will not open on Linux. Accept helper fails closed with a message, not raise into the frame loop.
- **WSLg drop.** Dropping from Windows Explorer onto a Linux pygame window is unreliable. The `/mnt/c/Users` and Drives shortcuts are the WSL answer; `DROPFILE` is extra.
- **Program Files.** Install dir is read-only for normal users. Never start the browser there. User data stays under `Documents\Cleave\` ([windows-freeze.md](../windows-freeze.md)).
- **Blocking native dialogs.** If a freeze-only `IFileOpenDialog` is added later, it blocks the pygame loop. Keep it off the frame path and off WSL.
- **Verification.** Unit tests for picker logic, accept helper, and CLI. Do not launch the editor for routine checks. Frozen Start Menu, `DROPFILE`, drives, and Program Files proof need a Windows box.

---

## What not to change

- Stem split, Demucs, analyse, `project.yaml` shape, persist, overlay row registry, Inno onedir layout, sidecar FFmpeg/libprojectM.
- Drop-on-exe argv normalisation.
- `continue_launch` still takes an already-open `LoadingWindow` and a resolved `project_dir`. It returns a switch request, or None for quit. `LaunchError` is unchanged.
- Live overlay stays keyboard-only. This work does not add mouse hit-testing.
- Phase 1 picker, CLI optional target, and frozen no-args behaviour.

---

## Tests

No editor / OpenGL window in unit tests ([agent-environment.mdc](../../../.cursor/rules/agent-environment.mdc)).

Phase 2: `DROPFILE` path string accepted or rejected; Windows-style path on POSIX does not raise.

Phase 3: unsaved prompt before switch; cancel keeps the session; accept switches on the same window (mocks). Dirty tracking stays computed.
