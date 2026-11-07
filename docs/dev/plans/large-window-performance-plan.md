# Large window performance: plan

## Context

The editor window can now be resized. On a 5120x1440 monitor, a maximised window runs about 8-10 fps slower than the default 1920x1080 window.

Drawing black is not the cost. The letterbox and other empty areas are a single `glClear` per frame, under 0.1 ms even at 5120x1440. The visualiser still renders at the configured content size (`editor.width/height`), so projectM, compositing and post-FX cost the same at any window size. At 5120x1440 the visualiser is limited by the window height, so it is shown only slightly larger, and that scaling costs the GPU almost nothing.

The extra cost comes from work that grows with the window size. Only the timeline strip cost below has been measured. The rest is likely but unproven until profiled on Windows.

Outcome: a large or maximised window costs close to the same frame time as 1920x1080, and an in-window frame timer shows where each frame's time goes.

## Findings

### 1. Timeline strip redraws its full width on the CPU every frame (measured)

The strip is as wide as the window (`ShellLayout.compute`, [cleave/viz/shell_layout.py](cleave/viz/shell_layout.py)). Every frame, `TimelineOverlay.compose_panel` ([cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py)) clears the whole upload surface and alpha-blends the whole cached static panel onto it:

```python
upload.fill((0, 0, 0, 0))
upload.blit(static_panel, (0, layout.badge_reserve))
```

This runs even when the static panel is reused (`incremental=True`) and only the playhead moved. It also runs while playback is paused, when the upload is skipped entirely. That work is redundant: in incremental mode, `_patch_live_overlay` already restores just the changed areas from the static panel (`_restore_upload_rect_from_static` for the previous playhead, plus the badge, flash and glyph rects). The upload is planned from those dirty rects.

Headless timings for the clear plus blend (pygame, `SDL_VIDEODRIVER=dummy`):

| Rows | Strip height | 1920 wide | 5120 wide |
|---|---|---|---|
| 4 | 193 px | 0.50 ms | 1.34 ms |
| 8 | 321 px | 0.81 ms | 2.18 ms |

At about 50-60 fps, an extra 1-1.5 ms is roughly 3-5 fps.

### 2. Showing a 7.4-megapixel frame on Windows (likely)

A maximised OpenGL window that isn't exclusive fullscreen usually goes through the Windows desktop compositor. The compositor copies the whole back buffer every frame, which costs about 2.7x as much at 5120x1440 as at 1920x1080. The driver can also stall inside `pygame.display.flip()`. How much this costs depends on the GPU, and matters more on integrated graphics.

### 3. A taller window builds more ImGui rows in Python (guess)

1440 instead of 1080 pixels is about 33% more visible navigator, inspector and help rows. Each row runs Python layout and text fitting in `shell_host.py`. This is probably under 1 ms a frame, but it hasn't been measured.

### Not a cause

`ProjectMFpsGovernor` ([cleave/viz/frame_rate.py](cleave/viz/frame_rate.py)) lowers projectM's frame rate when the measured display fps drops. It reacts to the slowdown and doesn't cause it, but it makes the visuals a little choppier at the larger size.

## Plan

### Phase 1: In-window frame timer

Measure before optimising anything except the timeline fix.

- Extend `OverlayProfiler` ([cleave/viz/overlay_profiler.py](cleave/viz/overlay_profiler.py)) into a whole-frame timer. Today it times only the overlay `upload` and `overlay_present`.
- Sections, each timed with `time.perf_counter` around the matching part of the `VisualizerApp.run` loop ([cleave/viz/app.py](cleave/viz/app.py)):
  - event handling
  - projectM render
  - composite and post-FX (`finish_content_frame`)
  - timeline compose and upload
  - ImGui build (`draw_ui` up to `end_frame`)
  - ImGui render
  - `pygame.display.flip()`
- Show the averaged times in the window on F3, for example as a small ImGui panel over the visualiser. Today the profiler prints only to stdout, which the frozen Windows build can't show (see "Editor first" in [AGENTS.md](AGENTS.md)). Keep `CLEAVE_OVERLAY_PROFILE=1` to start with it on.
- Reading the results: a large `flip()` time means the frame waits on the GPU or the swap (finding 2). Large CPU sections point to findings 1 and 3.
- Compare a 1920x1080 window with a maximised 5120x1440 window on the same project.

### Phase 2: Timeline strip incremental compose

- In `compose_panel`, clear and blit the full upload surface only when the static panel was rebuilt (`incremental=False`), or when the upload scratch surface was reallocated by `_ensure_upload_scratch`.
- In incremental mode, keep the upload surface from the last frame. `_patch_live_overlay` already restores the dirty rects.
- When `live_sig == cache.last_live_signature` (paused, nothing changed), skip patching entirely.
- Tests in `tests/cleave/viz/`: after a playhead move, the incremental upload surface matches a full rebuild pixel for pixel. A paused frame does no fill or blit (patch `pygame.Surface.blit` or count with the profiler counters).

### Phase 3: Presentation (only if `flip()` dominates)

- Add a borderless fullscreen toggle in the View menu: a frameless window that exactly covers the monitor. On Windows this often lets the driver skip the desktop compositor's copy.
- Check vsync. Cleave doesn't set a swap interval today (SDL and driver default), so make it explicit and measure both.

### Phase 4: ImGui row cost (only if the ImGui build time grows with height)

- Cache fitted text per row, keyed on text, width and UI scale.
- Skip building rows that are scrolled out of view in the navigator, inspector and help columns.

## Verification

- Unit tests for Phase 2 as above: `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py -k timeline`.
- On Windows, run the frame timer before and after each phase at 1920x1080 and maximised 5120x1440, and record the numbers in this plan.
- Target: the maximised window within about 1-2 fps of the 1920x1080 window on the same project.
