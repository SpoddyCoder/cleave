# Live tuning UI performance plan

Phased plan to cut the CPU cost of the live tuning overlay so it stops stealing
budget from the visualizers. Companion to the review in
[docs/ui-performance-improvements.md](docs/ui-performance-improvements.md).
Follows [.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc):
computed signatures over mark-dirty flags, typed injection, model/controller/view
separation, and one cache pattern mirrored from
[cleave/viz/frame_finish.py](cleave/viz/frame_finish.py).

## Independent review: findings beyond the first review

The first review is broadly correct. The independent pass through the draw loop
adds three corrections and one reframing that change where the effort should go.

1. The steady-state cost is the hidden panel, not the expanded one. In
   [cleave/viz/app.py](cleave/viz/app.py) `_tick_frame_live_overlay`,
   `build_view_state()` runs every frame before any visibility check, and
   [cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py) `draw_tuning` always
   clears the full 1280x720 surface. Only `TuningOverlay.draw` early-returns at
   `visibility <= 0.01`. So after the panel fades out (the common case during
   playback) every frame still pays a full view-state build (including
   `RowLayout.build`, per-layer dict copies, and `effective_layer_enabled` when
   the timeline is on) plus a full-surface fill. This is the single biggest
   always-on tax and the cheapest to remove.

2. The GL upload is already panel-sized, not full-frame. The previous review
   item 4 overstates it: [cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py)
   uploads a `subsurface` of the panel rect, so `pygame.image.tostring` and
   `glTexSubImage2D` only touch the panel region. The real GL cost is texture
   reallocation: [cleave/gl_compositor.py](cleave/gl_compositor.py)
   `upload_overlay_texture` calls `glTexImage2D` (delete plus create) whenever the
   panel height changes, which is every expand, collapse, and scroll step.

3. Layout and focus resolution are recomputed O(rows) several times per frame.
   `visible_indices`, `navigable_indices`, and the `focus_index` property (which
   calls `resolve_navigable` then `navigable_descriptors` then a linear
   `find_descriptor`) in [cleave/viz/row_layout.py](cleave/viz/row_layout.py) each
   walk the full row list, and they run multiple times per frame across draw and
   focus handling. `RowLayout.build` itself reruns every frame inside
   `TuningViewState.__post_init__`.

4. The first surface-build loop in `TuningOverlay.draw` is unconditional. It
   renders every visible row (text fit, `font.render`, new surfaces) before the
   scroll loop decides what to blit, so scrolled-off rows are fully rasterized and
   thrown away. This is the dominant per-frame CPU cost once the panel is open.

5. The preset directory row rescans the filesystem every frame, per layer. In
   [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py)
   `TuningViewStateBuilder.build` computes `preset_dir_label` via
   `directory_display` for each layer. To produce the `(N/M)` sibling-position
   suffix, [cleave/preset_playlist.py](cleave/preset_playlist.py)
   `directory_display` calls `list_navigable_dirs`, which runs `iterdir()` on the
   parent preset directory and then a recursive `rglob("*.milk")` (`dir_has_presets`)
   on every sibling subdirectory, plus several `.resolve()` syscalls. The preset
   libraries are very large, so this is real, potentially stalling filesystem I/O
   on every frame for every layer, and because of finding 1 it runs even while the
   panel is faded out. The file/preset-name row (`preset_filename_display`) is
   pure and not a concern. The directory label only changes on preset navigation
   (`next`, `prev`, `enter_child`, `go_parent`, `step_sibling`).

Net: the work splits cleanly into "stop doing work while hidden" (cheap, large),
"compute layout once, including the preset directory I/O" (architectural cleanup),
and "cache rendered rows and the panel surface" (the structural win), plus the
upload and projectM-fps tails.

## Goals and budget

- Hidden panel: near-zero overlay cost (no view-state build, no fill, no draw,
  no preset filesystem scan).
- No per-frame filesystem I/O: the preset directory label is memoized and only
  recomputed on preset navigation.
- Open panel, no interaction: no per-row rasterization or upload when nothing
  visibly changed; only live rows (transport time, fps) refresh.
- Open panel, interacting: redraw only the rows that changed plus viewport rows.
- Reasonable effort: five phases, each independently shippable and measurable.
  Stop early if a phase already meets the target.

## Phase 1: Measurement harness and hidden-panel guardrails

Goal: make every later phase verifiable, and bank the two largest no-risk wins.

- Add a typed overlay profiler (for example `OverlayProfiler` in a new
  `cleave/viz/overlay_profiler.py`), injected into the live runtime, not a global.
  Capture per-frame: view-state build, panel draw, surface-build count and
  `font.render` count, upload, and present. Toggle with a key or `CLEAVE_*` env
  var; emit a compact line to stdout and optionally a debug row in the panel.
- Skip overlay work when hidden. In `_tick_frame_live_overlay`, run
  `overlay.update(overlay_dt)` first, then early-return before `build_view_state`
  and `draw_tuning` when `overlay.visibility <= 0.01` and no modal or timeline
  strip needs drawing. Keep `finish_content_frame` (it draws the visuals).
- Drop the full-surface clear. Give the tuning panel a dedicated scratch surface
  sized to panel bounds (or fill only the panel rect), removing the 1280x720
  `fill((0,0,0,0))` in `draw_tuning`.

Files: [cleave/viz/app.py](cleave/viz/app.py),
[cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py), new profiler module.

Validation: harness shows hidden-frame overlay cost at or near zero; collapsed
and one-layer-expanded baselines recorded for later phases.

Risk: low. Behavior unchanged while visible; hidden path simply does less.

## Phase 2: Compute layout and view state once per frame

Goal: remove redundant O(rows) recomputation so caching has a clean foundation.

- Memoize `visible_indices`, `navigable_indices`, and `focus_index` for a built
  `RowLayout` so each is computed at most once per frame; replace the linear
  `find_descriptor` and repeated `resolve_navigable` calls with the memoized
  result.
- Split `TuningViewStateBuilder.build` into a structural part (row structure,
  expand flags, layer set, conditional predicates) that is reused across frames
  and a cheap dynamic part (transport position, fps, focus) refreshed every frame.
  Rebuild the structural `RowLayout` only when a structure-affecting input
  changes, detected by a computed structure signature, not a dirty flag, per the
  architecture rule. Keep model, controller, and view separated: the builder owns
  the model, `TuningOverlay` stays the view.
- Eliminate the per-frame preset directory filesystem scan (finding 5). The
  preset libraries are very large, so this is the highest-value single fix here.
  Cache the `directory_display` label (and its `list_navigable_dirs` sibling
  listing) against the playlist and recompute only when the layer navigates
  presets, rather than walking the filesystem to recompute a `(N/M)` counter every
  frame. Hang the cached label or listing on `PresetPlaylist` and invalidate it in
  the navigation mutators (`next`, `prev`, `step_by`, `step_sibling`,
  `enter_child`, `go_parent`, `_apply`) in
  [cleave/preset_playlist.py](cleave/preset_playlist.py), so the view-state build
  reads a memoized string. This lands inside the structural-versus-dynamic split
  above and removes the I/O even while the panel is faded out.

Files: [cleave/viz/row_layout.py](cleave/viz/row_layout.py),
[cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py),
[cleave/preset_playlist.py](cleave/preset_playlist.py).

Validation: harness shows view-state build time and per-frame layout passes drop;
output identical (snapshot the row list and focus index in unit tests).

Risk: medium. Touches focus resolution; cover with existing focus-nav and
view-state tests plus a structure-signature test.

## Phase 3: Panel signature, row cache, and retained panel surface

Goal: the structural win. Stop rasterizing unchanged rows and recompositing the
panel every frame.

- Add `TuningPanelCache` mirroring
  [RenderOverlayPanelCache](cleave/viz/frame_finish.py): hold rendered per-row
  surfaces keyed by a computed row signature
  `(kind, slot, display_text, color_state, max_width, line_h)`, plus a fitted-text
  memo keyed the same way so `fit_text_to_width` and friends do not rerun for
  static labels (preset paths, layer names).
- Build a row surface only when it is viewport-visible and the cache misses.
  Fold text fitting into the same miss path so off-screen rows cost nothing.
- Retain one composited panel surface between frames; recomposite only when the
  panel signature changes (structure, any row content, focus, visibility bucket,
  or width). Live rows (transport time, fps) are one or two rows and refresh each
  frame; one-frame latency on them is acceptable, so they do not force a full
  recomposite.
- Replace the per-focus-row `blit_tint` temp surface with a direct
  `pygame.draw.rect` fill on the panel.

Files: [cleave/viz/tuning_panel_draw.py](cleave/viz/tuning_panel_draw.py),
[cleave/viz/text_fit.py](cleave/viz/text_fit.py),
[cleave/viz/ui_tint.py](cleave/viz/ui_tint.py), cache in
[cleave/viz/frame_finish.py](cleave/viz/frame_finish.py) or a sibling
`cleave/viz/tuning_panel_cache.py`.

Validation: harness shows surface-build and `font.render` counts near zero on
idle-open and equal to changed-row count on interaction; pixel-compare a few
panel states against the pre-cache output.

Risk: medium-high. Cache invalidation is the hard part; drive it from computed
signatures and add tests asserting a known mutation invalidates exactly the
expected rows.

## Phase 4: Stable-size GPU upload

Goal: remove texture reallocation churn and skip uploads when nothing changed.

- Allocate the overlay texture to a max panel size and update sub-regions with
  `glTexSubImage2D`, so expand, collapse, and scroll no longer trigger
  `glTexImage2D` delete-plus-create in
  [cleave/gl_compositor.py](cleave/gl_compositor.py).
- Skip `tostring` and upload entirely when the Phase 3 panel signature and panel
  position are unchanged; redraw the existing texture instead. Consider a PBO only
  if the harness still shows upload as a hotspot after the skip.

Files: [cleave/gl_compositor.py](cleave/gl_compositor.py),
[cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py).

Validation: harness shows zero uploads on idle-open frames and no reallocation on
expand or scroll.

Risk: medium. GL state and Y-flip correctness; verify visually and keep the
existing upload as the fallback path for the modal full-surface case.

## Phase 5: Decouple projectM fps from UI-loaded display fps

Goal: stop the feedback loop where UI cost lowers measured fps, which lowers the
libprojectM target, which degrades the visuals beyond the overlay work itself.

- Replace the direct `layer.pm.set_fps(round(display_fps))` feed in
  [cleave/viz/app.py](cleave/viz/app.py) with a smoothed or clamped target that
  does not collapse on transient UI spikes (for example an EMA with a floor, or a
  target derived from the configured render mode rather than the instantaneous
  UI-loaded measurement).

Files: [cleave/viz/app.py](cleave/viz/app.py),
[cleave/viz/frame_rate.py](cleave/viz/frame_rate.py).

Validation: opening and scrolling the panel no longer drops the projectM target
fps; visuals hold steady while interacting.

Risk: low-medium. Tuning the smoothing; validate against the harness with the
panel open versus closed.

## Sequencing and exit criteria

Phases are ordered by leverage per unit risk. Phase 1 is mandatory (it gates the
rest). Phases 2 and 3 are the core architectural work and deliver most of the
gain. Phases 4 and 5 are tails: do them if the harness still shows upload cost or
fps throttling after Phase 3. Re-measure after each phase against the Phase 1
baselines and stop when the open-panel overlay cost is a small fraction of a
visualizer frame.
