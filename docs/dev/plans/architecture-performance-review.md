# Architecture and performance review: plan

## Context

A from-scratch review of the `ui-refactor` branch before it merges to `main` (380 files changed against `main`). The emphasis is the UI code in `cleave/viz/`, plus anything on the frame path that costs FPS.

The goal is a codebase that takes future change well, not a perfect one. Low priority findings are left out on purpose. Each phase below stands alone: it can be applied, reviewed and merged without the others, in any order within its priority band.

This replaces the old `docs/dev/architecture-review.md`, which predated the shell rewrite.

Related: [docs/dev/plans/large-window-performance-plan.md](docs/dev/plans/large-window-performance-plan.md). Its frame timer and timeline strip phases are still open and are carried here as H1 and M1, so that plan can be retired once those land.

## How the numbers were measured

Headless on Linux (WSL2, Mesa llvmpipe software GL), Python 3.10, with a synthetic four-layer session built from the test fixtures and a hidden 1920x1080 GL window. Two harnesses: one times the pure-Python state builders, the other runs the real `draw_shell_frame` (ImGui build plus ImGui render) for 200 frames under `cProfile`.

What this does and does not show:

- Python CPU cost per frame is real and carries over to Windows. Filesystem calls are likely slower on Windows than measured here.
- GPU cost is not representative. llvmpipe rasterises on the CPU, and projectM, compositing and post-FX were not run. Nothing below claims a GPU saving that was measured.
- The synthetic preset paths do not exist on disk. Real paths resolve through more directory levels, so the path costs below are a floor.

No fix has been applied, so every FPS gain is an estimate until H1 lets it be measured in the editor.

## Summary

| Phase | Priority | Kind | What |
| --- | --- | --- | --- |
| H1 | High | Perf | Frame timer in the window, benchmark harness in the repo |
| H2 | High | Perf | Stop recomputing "unsaved changes" several times a frame |
| H3 | High | Perf and structure | Build navigator, view state and command context once per frame |
| H4 | High | Bug | `save_gl_state` records the wrong texture binding |
| H5 | High | Structure | Split `shell_host.py` and type its controller |
| M1 | Moderate | Perf | Timeline strip incremental compose |
| M2 | Moderate | Perf | Fewer GL state queries and readbacks per frame |
| M3 | Moderate | Structure | Extract the live frame loop from `VisualizerApp.run` |
| M4 | Moderate | Structure | One project snapshot for dirty tracking; less hand-copied view state |
| M5 | Moderate | Structure | Split `TimelineOverlay` |
| M6 | Moderate | Hygiene | Dead code, stale docs, shared test helpers |

Suggested order: H4 (tiny), H1, H2, H3, then H5. H2 alone is expected to be the largest FPS gain in this plan.

---

## High priority

### H1. Frame timer and a checked-in benchmark

**Status.** Done. Sections are Events, Controller ticks, Layer render (projectM plus per-layer effects), Composite and post-FX, Strip compose, Strip upload, ImGui build, ImGui render and Flip, with the untimed rest shown as Other. Benchmark: `/home/fernpa/anaconda3/envs/cleave/bin/python scripts/bench_shell_frame.py --layers 4 --preset-list 20`.

**Finding.** There is no way to see where a frame goes in the running editor. `OverlayProfiler` ([cleave/viz/overlay_profiler.py](cleave/viz/overlay_profiler.py)) times only the strip upload and present, and prints to stdout, which the frozen Windows build cannot show. Every perf item below was found with throwaway scripts.

**Change.**

- Extend `OverlayProfiler` into a whole-frame timer with sections around the `VisualizerApp.run` loop ([cleave/viz/app.py](cleave/viz/app.py)): events, controller ticks, projectM render, composite and post-FX, strip compose and upload, ImGui build, ImGui render, `pygame.display.flip()`.
- Show the averages in the window on F3 as a small ImGui panel. Keep `CLEAVE_OVERLAY_PROFILE=1` to start with it on.
- Add `scripts/bench_shell_frame.py`: a hidden GL window, a fixture session with a configurable layer count and preset list length, N frames of `draw_shell_frame`, and ms per frame printed. It needs only the test fixtures, so it runs in a checkout with no project.

**Verify.** F3 shows sections that sum to roughly the frame time. The script prints a stable number across runs.

### H2. "Unsaved changes" is recomputed four to six times a frame, hitting the disk

**Status.** Done. `config_dirty` is compared once per frame after `ConfigSaveController.tick()`; quit, project switch and the curation mode change call `compute_config_dirty()`. Paths go through the cached `config_relative_path` in [cleave/paths.py](cleave/paths.py). The inspector command rows use the frame's `CommandContext`. Benchmark, four layers, frame mean before and after: 8.2 to 5.4 ms at 0 entries, 21.8 to 5.8 ms at 20, 6.9 ms at 100. The display can trail an edit by one frame.

**Finding.** `ConfigSaveController.config_dirty` ([cleave/viz/config_save.py](cleave/viz/config_save.py)) has no cache. Every read rebuilds the whole persisted payload (`persisted_session_payload`), serialises it to JSON and compares strings. Inside that, `persist_layers` calls `_to_cfg_relative` ([cleave/config_schema/layers.py](cleave/config_schema/layers.py)) for every preset list entry, which runs `Path.resolve()` on the path and on the config directory: `lstat` calls on the filesystem, every time.

It is read on every frame from:

- the window caption check in the run loop ([cleave/viz/app.py](cleave/viz/app.py))
- `command_context` ([cleave/viz/commands.py](cleave/viz/commands.py)), built once in `draw_ui`
- `TuningViewStateBuilder.build` ([cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py))
- `ShellHost._draw_bar_project_label` ([cleave/viz/shell_host.py](cleave/viz/shell_host.py))
- twice more for each command button row on the open inspector page (`inspector_command_enabled` and `inspector_command_locked` each build their own `command_context`)

Measured, four layers:

| Preset list entries per layer | One `config_dirty` read | Whole shell frame |
| --- | --- | --- |
| 0 | 0.5 ms | 6.6 ms |
| 20 | 2.8 ms | 23.4 ms |
| 100 | not timed alone | 86.6 ms |

At 20 entries per layer, `config_dirty` was 83% of profiled frame time (8.46 s of 10.17 s over 200 frames), and 96,000 path resolves ran in those 200 frames. A project with preset lists pays this on every frame, playing or paused. The frame time includes llvmpipe drawing the UI, so the absolute values are high, but the growth with list length is pure Python and filesystem time.

**Change.** Dirty tracking stays computed (no `mark_config_dirty()`); it is only evaluated less often and more cheaply.

1. Evaluate at most once per frame. `ConfigSaveController` gets a `tick()` (called from `TuningControls.tick`) that drops a cached result; `config_dirty` computes on first read after that. Save, quit and project switch paths call an uncached method so they never act on a stale answer.
2. Take the filesystem out of the payload. Cache `cfg_dir.resolve()` once per controller, and cache the relative form per preset path (a small dict keyed on the path, or resolve once when the path enters the session). `to_config_relative` in [cleave/preset_playlist.py](cleave/preset_playlist.py) has the same shape and shows in the profile for the current preset of each layer.
3. Pass the one `CommandContext` built for the frame into the inspector command rows instead of rebuilding it per row (overlaps H3).

If step 1 and 2 still leave more than about 0.3 ms a frame, lower the display refresh to a few times a second (the caption star and the project label do not need frame accuracy), keeping the uncached path for save and quit.

**Verify.** `tests/cleave/viz/test_config_dirty.py` still passes unchanged. New tests: a counter shows one payload build across several reads in a frame, and a save immediately after an edit in the same frame still sees dirty. The H1 script at 20 entries per layer should land near the 0-entry time.

### H3. Navigator, view state and command context are rebuilt many times a frame

**Status.** Done. `ShellFrame` ([cleave/viz/shell_host.py](cleave/viz/shell_host.py)) holds the view state, the visible navigator nodes and the `CommandContext`, built once in `_draw_shell` and passed to the navigator and inspector. `CommandContext` carries the page history targets (`page_back_id`, `page_forward_id`) and the dirty flag, so the frame needs no separate id set. `all_navigator_ids` is one build, `NavigatorControls.history_targets` shares one filter, and `page_status` reuses the frame's nodes when they hold the page. The structure signature keeps its digests but caches them per list content. A frame is now three navigator builds, down from 12: one full build in `command_context`, one visible build in the frame, and one visible build in `nav_content_height_px`, which runs in the layout step before the draw and is left alone. Benchmark, four layers, frame mean before and after: 4.7 to 4.0 ms at 0 entries, 5.1 to 4.5 ms at 20, 6.4 to 5.4 ms at 100.

**Finding.** Draw code asks for derived state wherever it needs it, so the same structures are rebuilt inside one frame:

- `build_navigator` ([cleave/viz/navigator.py](cleave/viz/navigator.py)) ran 12 times per frame in the profile. Callers in [cleave/viz/shell_host.py](cleave/viz/shell_host.py): `_visible_nav_nodes` (twice: the height estimate and `_draw_navigator`), `_draw_inspector`, and `page_title` for tooltips. The rest come from `NavigatorControls.page_filter` ([cleave/viz/navigator_controls.py](cleave/viz/navigator_controls.py)), which calls `all_navigator_ids` (a full expanded build) each time it is asked for. `_page_history_buttons` asks once a frame, and every `command_context` asks twice more through `can_go_back` and `can_go_forward`, so the per-row contexts in H2 multiply this too.
- `command_context` is rebuilt per command row (see H2).
- `view_state_structure_signature` ([cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py)) runs every frame: a JSON dump plus a SHA-1 over every path in every layer's preset folder and preset list. 0.16 ms with 300 presets per folder, growing linearly with folder size.

With no preset lists (so H2's cost is at its minimum), the navigator rebuilds were about 20% of the profiled shell frame, roughly 1 ms. This is also a robustness problem: nothing guarantees two widgets in one frame saw the same navigator.

**Change.**

- Add a small frozen `ShellFrame` value built once at the top of `ShellHost._draw_shell`: the `TuningViewState`, the visible navigator nodes, the set of all navigator ids, the `CommandContext`, and the dirty flag. Pass it down; draw methods stop calling `build_navigator`, `command_context` and `config_dirty` themselves.
- `NavigatorControls.page_filter` takes the id set from the frame instead of rebuilding it, and `can_go_back` / `can_go_forward` share one filter.
- Replace the per-frame path digests in the structure signature with a cheap identity: a revision counter on the playlist and preset list bumped where they are replaced, or a digest cached against the list object and its length.

Keep `build_navigator` as the single pure builder. Event handlers that run outside the draw (key dispatch, context menu resolution) may still call it directly.

**Verify.** A test patches `build_navigator` with a counter and asserts one visible build and at most one full build per `draw_shell_frame`. Existing `test_view_state_structure.py` invalidation tests still pass, plus one for a preset folder change.

### H4. `save_gl_state` records the wrong texture binding

**Status.** Done. `save_gl_state` queries `GL_TEXTURE_BINDING_2D`. [tests/cleave/test_gl_state_gl_integration.py](tests/cleave/test_gl_state_gl_integration.py) binds a known texture, saves, binds another, restores and checks the binding; it fails on the old query. The GL integration tests pass. The live editor on Windows has not been checked yet.

**Finding.** In [cleave/gl_state.py](cleave/gl_state.py), `save_gl_state` sets `texture_binding=_gl_int(GL_TEXTURE_2D)`. `GL_TEXTURE_2D` queried through `glGetIntegerv` returns whether 2D texturing is enabled (0 or 1), not the bound texture. `restore_gl_state` then calls `glBindTexture(GL_TEXTURE_2D, state.texture_binding)`, so after every post-FX pass, masked composite and ImGui render the active unit is bound to texture name 0 or 1 instead of what was bound before.

It appears harmless today because the compositor binds its own textures before each draw, but it is a real state leak in the one module whose job is to prevent them, and the rule in `.claude/rules/gl-post-process.md` tells every new pass to rely on it.

**Change.** Query `GL_TEXTURE_BINDING_2D`. One line plus the import.

**Verify.** Add a GL integration test next to `tests/cleave/test_gl_state.py`: bind a known texture, save, bind another, restore, assert the binding. Run the existing `*_gl_integration.py` tests, and check the live editor once on Windows since this changes state every frame.

### H5. Split `shell_host.py` and give it a typed controller

**Status.** Done. `ShellHost` ([cleave/viz/shell_host.py](cleave/viz/shell_host.py), 711 lines, the class about 615) keeps the layout, the top layer, mouse event routing and context menu routing, and draws through one object per region: `MenuBarPanel` ([cleave/viz/shell_menu_bar.py](cleave/viz/shell_menu_bar.py)), `TransportBar` ([cleave/viz/shell_transport.py](cleave/viz/shell_transport.py)), `NavigatorPanel` ([cleave/viz/shell_navigator.py](cleave/viz/shell_navigator.py)), `InspectorPanel` ([cleave/viz/shell_inspector.py](cleave/viz/shell_inspector.py)), `SplitterDrag` ([cleave/viz/shell_splitters.py](cleave/viz/shell_splitters.py)) and `StripPointerRouter` ([cleave/viz/shell_strip.py](cleave/viz/shell_strip.py)). Three more modules than listed below, to meet the size target: the inspector's value controls ([cleave/viz/shell_inspector_values.py](cleave/viz/shell_inspector_values.py)), its title line ([cleave/viz/shell_inspector_title.py](cleave/viz/shell_inspector_title.py)), and the fixed windows and borders ([cleave/viz/shell_windows.py](cleave/viz/shell_windows.py)). Shared drawing helpers, the row drag and the inline text field are in [cleave/viz/shell_widgets.py](cleave/viz/shell_widgets.py). The regions share a typed `ShellContext` ([cleave/viz/shell_context.py](cleave/viz/shell_context.py)) holding the controller, menu state, top layer, layout and the frame's `CommandContext`. The largest module is 769 lines. `_draw_inspector_row` is now `draw_row`, the selectable, the value, the value cluster and the click outcome, with the row's facts and item flags in two small dataclasses. `controls` is typed `TuningControls` in the shell, [cleave/viz/commands.py](cleave/viz/commands.py), [cleave/viz/menu_bar.py](cleave/viz/menu_bar.py) and [cleave/viz/value_nudge.py](cleave/viz/value_nudge.py), and the `getattr` fallbacks are gone from the shell, `_live_shell_layout` and `input_dispatch`. Tests needed more than import-path edits: they reach region state through the host (`host.inspector.draw`, `host.splitters.active`, `host.context.controls`), and fake controllers now carry a `modal_host` and `inline_edit`. Benchmark, four layers and 20 entries: 4.2 ms, no change. No type checker runs in the repo, so the annotations are unchecked. The live editor on Windows has not been checked yet.

**Finding.** [cleave/viz/shell_host.py](cleave/viz/shell_host.py) is 4,001 lines. `ShellHost` is one class of about 2,300 lines holding roughly 40 mutable fields that belong to unrelated concerns: menu bar hover, splitter drags, value drags, nudge swallow, row drag reorder, the colour picker, choice lists, scroll follow, context menu routing, strip pointer forwarding and the transport bar. `_draw_inspector_row` is 180 lines with seven early exits and ordering rules held in comments. Its module docstring still describes `ImGuiHost`.

Every UI feature on this branch landed in this file, and the next ones will too. The typing makes it worse:

- `ShellHost.__init__` takes `controls: Any`; so do 39 function signatures across `cleave/viz/` (all of [cleave/viz/commands.py](cleave/viz/commands.py), for example). `_draw_inspector` takes `state: Any` and `_draw_inspector_row` takes `row: Any`, though the types are `TuningViewState` and `InspectorRow`.
- Because the controller is untyped, tests build it from `SimpleNamespace` and `MagicMock` (about 560 uses in `tests/cleave/viz/`), and the code defends with `getattr(self._controls, "modal_host", None)`. A renamed controller method fails at run time in the editor, not in a test or a type check.

**Change.** Mechanical, no behaviour change, one region per commit so each is reviewable:

1. Types first. Annotate `controls` as `TuningControls` under `TYPE_CHECKING` (or a `ShellControls` Protocol listing what the shell uses, if the import cycle bites), and fix `state` and `row`. Remove the `getattr` fallbacks that the type makes redundant, here and in `VisualizerApp._live_shell_layout` ([cleave/viz/app.py](cleave/viz/app.py)), which uses `getattr(shell, "insp_width", None)` for properties that always exist.
2. Move each region into its own module with its own small state object, leaving `ShellHost` as the coordinator that owns the layout, the top layer and event routing:
   - `shell_menu_bar.py`: `_draw_bar`, `_draw_dropdown`, `_draw_rows`, project label, hover state
   - `shell_transport.py`: `TransportReadout`, `transport_parts`, `_draw_transport*`, the notice chip
   - `shell_navigator.py`: `_draw_navigator`, `_draw_nav_node`, toggles, tree lines, label click state, layer drag
   - `shell_inspector.py`: title, rows, choice values, nudge, value drag, colour picker, preset drag
   - `shell_splitters.py`: splitter hit, drag and persist
3. Break `_draw_inspector_row` into the selectable, the value cluster, and the click outcome, with the per-frame item flags carried in a small dataclass instead of five loose locals.

Target: no module over about 1,000 lines, and `ShellHost` under about 600.

**Verify.** `tests/cleave/viz/test_shell_host.py`, `test_shell_mouse.py`, `test_shell_transport.py` and `test_inspector*.py` pass with only import-path edits. The H1 script shows no frame time change.

---

## Moderate priority

### M1. Timeline strip incremental compose

**Status.** Done. The upload surface keeps its pixels between frames. `compose_panel` clears it and lays the static panel and ruler (`_compose_static_layers`) only when the static panel was rebuilt or the surface was reallocated. Otherwise `_patch_live_overlay` first restores every rect the last live pass drew (playhead, transport buttons, flashes, role glyphs) with `_restore_upload_rect`, which repeats the full compose's clear, panel and ruler blits clipped to the rect, so a restored pixel matches a full rebuild. That also fixes the old restores, which blended the static panel over itself. When the live signature is unchanged, the patch is skipped. `compose_panel` alone, four rows, before and after: 1.0 to 0.09 ms paused and 0.22 ms playing at 1920 wide, 2.3 to 0.09 and 0.23 ms at 5120. Tests compare incremental and fresh composes byte for byte across playhead, hover, arm flash and marker flash changes, and check that an unchanged frame neither clears nor patches. The live editor on Windows has not been checked yet.

**Finding.** Still open from the large window plan and confirmed in the current code: `TimelineOverlay.compose_panel` ([cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py)) runs `upload.fill((0, 0, 0, 0))` and blits the whole cached static panel every frame, even when the static panel was reused and only the playhead moved, and while paused. `_patch_live_overlay` already restores just the dirty rects. Measured in that plan: 0.5 ms at 1920 wide with four rows, 2.2 ms at 5120 wide with eight.

**Change.** Clear and blit the full surface only when the static panel was rebuilt or the scratch surface was reallocated. Skip patching when the live signature is unchanged.

**Verify.** After a playhead move the incremental surface matches a full rebuild pixel for pixel; a paused frame does no fill or blit.

### M2. Fewer GL state queries and readbacks per frame

**Status.** Done. `GlPostProcess.batch()` saves GL state on the first pass inside it and restores once at the end; a batch with no pass touches no state. `render_frame` now has projectM draw every layer first, then runs all per-layer passes (bloom, grit, the rolloff and chroma copies and passes) in one batch; layers are separate textures, so the order between them does not change the output. `finish_content_frame` batches the HDR shoulder, the limiter sample, rolloff and chroma boost. With four layers and every effect on, that is 4 save/restore pairs a frame instead of 30 (counted from the code, not timed). The limiter reads its luma grid through a pixel buffer a frame late (`queue_luma_grid`), so the CPU no longer waits for the GPU; the limiter now trails the picture by one more frame, and a seek or a gap in sampling drops the queued grid. PyOpenGL error checking is off in the frozen build ([cleave/gl_error_checking.py](cleave/gl_error_checking.py)); `CLEAVE_GL_ERROR_CHECKING=1` turns it back on. [tests/cleave/test_post_process_batch_gl_integration.py](tests/cleave/test_post_process_batch_gl_integration.py) checks on real GL that batched passes give the same pixels as unbatched ones, that a batch restores the state from before it, and that the queued grid arrives on the next call. The masked composite and ImGui render keep their own pair. The live editor on Windows has not been checked yet, and the F3 comparison there is still to do.

**Finding.** Not measured on a real GPU; treat as candidates to confirm with H1.

- Each `save_gl_state` / `restore_gl_state` pair is about 16 `glGet` / `glIsEnabled` queries and cost 95 microseconds here. It wraps every pass separately: bloom and grit per layer, per-layer rolloff and chroma, the frame fade, the limiter sample, the masked composite and the ImGui render ([cleave/gl_post_process.py](cleave/gl_post_process.py), [cleave/gl_masked_compositor.py](cleave/gl_masked_compositor.py), [cleave/viz/imgui_host.py](cleave/viz/imgui_host.py)). Four layers with effects is 10 to 15 pairs, about 1 to 1.5 ms. On drivers with threaded optimisation, state queries can also force a sync with the driver thread.
- The visual limiter reads the content back every frame it is on: `read_luma_grid` in [cleave/viz/visual_limiter.py](cleave/viz/visual_limiter.py) ends in a synchronous `fbo.read`, which makes the CPU wait for the GPU to finish the frame.
- PyOpenGL checks `glGetError` after every call unless `OpenGL.ERROR_CHECKING` is turned off before the first import. Simple calls dropped from about 0.8 to 0.5 microseconds with it off. The ImGui renderer is PyOpenGL in Python, so it pays this per draw command. Small, but nearly free.

**Change.**

- Save once around a run of consecutive passes (all per-layer passes for a frame, then the finish chain) instead of once per pass, keeping the per-pass wrapper for callers outside a batch.
- Sample the limiter every second or third frame (its envelope already smooths over time), or read through a pixel buffer object one frame late.
- Turn PyOpenGL error checking off in the frozen build only, behind an environment variable to turn it back on for bug reports.

**Verify.** The GL integration tests pass. The limiter tests in `tests/cleave/viz/test_visual_limiter.py` cover the new cadence. Compare F3 sections before and after on Windows.

### M3. Extract the live frame loop from `VisualizerApp.run`

**Status.** Done. `LiveFrameLoop` ([cleave/viz/live_frame_loop.py](cleave/viz/live_frame_loop.py)) builds the shell and holds the frame's typed state (`overlay_dt`, `display_fps`, the clock, the frame rate meter, the projectM fps governor, the caption). Its steps are `handle_events()`, `tick(dt)`, `render(t_sec)` and `draw_ui()`, put together with their profiler sections in `run_frame()`, plus `draw_first_frame()` for the warm-up frame. `VisualizerApp.run` ([cleave/viz/app.py](cleave/viz/app.py)) is down to about 60 lines: setup, the `while`, teardown, and one local import that keeps ImGui out of offline render. The tap sync panel, modal and project picker surfaces, and their pointer handling after the frame, are `ShellPrompts` ([cleave/viz/shell_prompts.py](cleave/viz/shell_prompts.py)). `VisualizerApp._shell` is gone: the layout functions (`live_shell_layout`, `publish_shell_layout`, `begin_live_frame`) are module functions that read `runtime.shell_host`. `_live_overlay_ui_active` and `_timeline_strip_visible` are gone, `_tick_frame_live_overlay` is the public `draw_live_overlay`, and `_apply_window_requests` moved to the loop module as `apply_window_requests`. One small change: the frame clock now starts after loading, not before it, so the first frame's dt no longer includes load time. Tests needed patch-target edits (`pygame`, `current_sec`, `draw_shell_frame` and `draw_live_overlay` are patched in `cleave.viz.live_frame_loop`). New [tests/cleave/viz/test_live_frame_loop.py](tests/cleave/viz/test_live_frame_loop.py) drives `draw_ui` with a fake shell and an active modal, and holds the window request tests. The live editor on Windows has not been checked yet.

**Finding.** `VisualizerApp.run` ([cleave/viz/app.py](cleave/viz/app.py)) is about 260 lines: GL setup, shell construction, a 70-line `draw_ui` closure, the event loop, window requests, controller ticks, the frame, and teardown. It carries state in a one-element list (`display_fps`), sets `self._shell = None` untyped, imports seven modules inside the function, and has two wrappers that only return their argument (`_live_overlay_ui_active`, `_timeline_strip_visible`). The modal, picker and tap-sync surface wiring lives in the closure, so it cannot be tested without a window. H1's timer sections need seams this function does not have.

**Change.** Move the loop body into a `LiveFrameLoop` (or similar) object in its own module with `handle_events()`, `tick(dt)`, `render(t_sec)` and `draw_ui()` methods and typed fields; `run` keeps setup, the `while`, and teardown. Move the top-layer surface assembly next to `ShellHost`. Drop the pass-through wrappers.

**Verify.** `tests/cleave/viz/test_app.py` and `test_session_loop.py` pass. Add one test that drives `draw_ui` with a fake shell and an active modal.

### M4. One project snapshot for dirty tracking; less hand-copied view state

**Status.** Done. `ConfigSaveController` ([cleave/viz/config_save.py](cleave/viz/config_save.py)) keeps one frozen `ProjectSavedState` (song markers, Milkdrop beat, compositor HDR, resolution width and height, render fps) built by `project_saved_state(session)`, and Save writes it through one `write_project_saved_state`, so a new project setting is a field plus a line in that writer. Each view block has a `from_session` or `from_runtime` constructor, and `TuningViewStateBuilder.build` makes every section block that way each frame; the cached structure now holds only the track blocks, and `invalidate_structure()` replaces the direct reset in `controls.py`. New tests in `tests/cleave/viz/test_config_dirty.py` fail when a `ProjectSavedState` field has no mutator, check each field marks and clears dirty, and check song markers reach `project.yaml`. Benchmark, four layers and 20 entries: ImGui build 3.2 ms before and after.

**Finding.** Two places where adding a field means remembering several unrelated edits:

- `ConfigSaveController` keeps seven `_saved_*` fields for project values outside the session payload (song markers, Milkdrop beat, compositor HDR, resolution width and height, render fps). Each is listed three times: in `__init__`, in `config_dirty`, and in `clear_config_dirty`. A new project setting that misses one of the three silently never marks the project dirty, or never clears.
- `TuningViewStateBuilder.build` copies session values into view blocks field by field with nested `dataclasses.replace` (about 70 `replace` calls a frame), and the same fields appear again in `_build_structure`. A new value row needs both.

**Change.**

- Replace the seven fields with one `project_saved_state(session)` tuple or frozen dataclass, compared and stored as a unit.
- Give each view block a `from_runtime` constructor (the limiter and fade blocks already build this way) so `build` and `_build_structure` share one mapping per block.

**Verify.** Existing dirty and view-state tests pass. Add a test that enumerates the project snapshot's fields and fails when one is not covered by a dirty test.

### M5. Split `TimelineOverlay`

**Status.** Done. [cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py) is down to 378 lines: `TimelineOverlay` keeps `compose_panel`, the panel cache, the upload surface and the public pointer queries. The rest sits in six modules: view state and per-row data ([cleave/viz/timeline_strip_state.py](cleave/viz/timeline_strip_state.py)), geometry ([cleave/viz/timeline_strip_layout.py](cleave/viz/timeline_strip_layout.py)), the static panel and ruler ([cleave/viz/timeline_strip_static.py](cleave/viz/timeline_strip_static.py)), the live patch ([cleave/viz/timeline_strip_live.py](cleave/viz/timeline_strip_live.py)), blink timing ([cleave/viz/timeline_strip_flash.py](cleave/viz/timeline_strip_flash.py)) and hit testing ([cleave/viz/timeline_strip_hit.py](cleave/viz/timeline_strip_hit.py)). The largest is 636 lines. `_TimelineLayout` is now the public `StripLayout`, which carries the padding and row gap and answers row, header button, transport and playhead geometry, so draw and hit code take a layout instead of the overlay. The hit caches are one frozen `StripHitMap` built at the end of a compose. `StaticLayers` holds the cached panel and ruler with `lay` and `restore`. No re-exports: importers use the new modules. Tests needed more than import-path edits: `overlay._hit_layout` is `overlay.layout`, `_transport_rects` is `layout.transport_rects()`, `_live_flash_signature` is the module function `live_flash_signature`, the skip test patches `StaticLayers.lay` and `patch_live_overlay`, and the REC blink tests pin `pygame.time.get_ticks` instead of patching `rec_flash_visible`, which is now read from two modules. `compose_panel` alone, four rows, before and after: 0.09 to 0.08 ms paused and 0.15 to 0.12 ms playing at 1920 wide.

**Finding.** [cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py) is 2,427 lines, and the `TimelineOverlay` class alone is about 1,335: layout, static panel drawing, live patching, upload planning and hit testing in one class with shared mutable caches. The clips plan in [docs/dev/plans/timeline-clips-plan.md](docs/dev/plans/timeline-clips-plan.md) will add to it.

**Change.** Separate along the seams that already exist in the method names: layout (`_compute_layout`, `_TimelineLayout`), static draw (`_build_static_panel`, `_build_ruler`), live patch (`_patch_live_overlay` and its rect helpers), and hit testing (`hit_at`, `StripHit`). `TimelineOverlay` keeps `compose_panel` and the cache. Do this after M1 so the compose change is reviewed on its own.

**Verify.** `tests/cleave/viz/test_timeline_overlay.py` and `test_timeline_pointer.py` pass with only import-path edits.

### M6. Hygiene: dead code, stale docs, shared test helpers

**Finding.**

- [cleave/viz/focus_context.py](cleave/viz/focus_context.py) has no importers. `FocusContext` is still named as the example in `.claude/rules/architecture-principles.md`.
- [AGENTS.md](AGENTS.md) points agents at things that no longer exist: `tuning_panel_draw.py` and `RowLayout`. `row_present_renderers.py` is listed as the draw entry point but now holds colour helpers and the strip's header icons; the draw path is `shell_host.py`.
- Stale docstrings: `shell_host.py` describes `ImGuiHost`, and `TuningControls` is "Keyboard focus machine for the live tuning tree overlay".
- [cleave/viz/layer_pipeline.py](cleave/viz/layer_pipeline.py) has two module functions that only forward to a static method of the same name (`_apply_layer_highlight_rolloff`, `_apply_layer_chroma_boost`).
- Test modules import private helpers from each other (`from tests.cleave.viz.test_controls import _make_controls`, and about 110 similar lines), so moving a test breaks unrelated files. `tests/support/viz.py` already has a public `make_controls`.

**Change.** Delete `focus_context.py` and fix the rule's example. Update the "Locate, then search" list in `AGENTS.md` and `.claude/rules/live-tuning-ui.md` to the modules H5 produces (do this with or after H5). Fix the docstrings. Inline the two forwarders. Move shared test builders into `tests/support/` and import them from there.

**Verify.** Full unit suite: `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py`.

---

## Looked at and left alone

These came up and are deliberately not in the plan:

- **Rebuilding inspector rows every frame.** `build_inspector_rows` costs about 0.01 ms. Not worth a cache.
- **`menus_for_session` per frame.** 0.003 ms.
- **`config_schema` and the persist path.** Descriptor-driven and consistent. The only issue found is the path resolve in H2.
- **Effects registry and `frame_finish`.** The shared live/offline path holds; no parallel branches found.
- **`LayerFramePipeline` as a class of static methods.** Unusual, but consistent and well tested. Renaming it is churn.
- **120 `assert` statements in `cleave/`.** Mostly narrowing optional GL resources after `_ensure_init`. Fine as long as the frozen build does not run with `-O` (not checked here).
- **ImGui row culling for tall windows** (large window plan, phase 4). Unmeasured; revisit only if H1 shows the ImGui build growing with window height after H2 and H3.
- **Presentation and vsync** (large window plan, phase 3). Depends on the Windows compositor and cannot be assessed from here; H1's `flip()` section decides it.
