# Live tuning UI performance review

Review of frame-rate impact when the tuning panel is open, especially expanding a single layer (~5 fps observed).

## Per-frame pipeline (while UI is visible)

Every display frame in [cleave/viz/app.py](cleave/viz/app.py) `VisualizerApp.run()`:

1. `build_view_state()` builds a fresh [TuningViewState](cleave/viz/tuning_view_state.py) and calls `RowLayout.build()` in `__post_init__`
2. [TuningOverlay.draw()](cleave/viz/tuning_panel_draw.py) allocates surfaces and renders every visible row
3. [overlay_surface.fill((0,0,0,0))](cleave/viz/overlay_draw.py) clears the full 1280x720 overlay buffer
4. [upload_overlay_texture()](cleave/gl_compositor.py) does `pygame.image.tostring` + `glTexSubImage2D` for the panel

There is no panel cache for the tuning UI. The render credits overlay uses [RenderOverlayPanelCache](cleave/viz/frame_finish.py) via `ensure_render_overlay_panel()`; the tuning panel has no equivalent.

## What changes when you expand one layer

Collapsed: one `TRACK_HEADER` per layer.

Expanded (default: preset switching and effects still collapsed): about 10 rows for that layer:

- Header (visibility icon + multi-part label + text fitting)
- Preset dir / preset (Material Icons + path fitting)
- Preset switching header (collapsed)
- Stem, beat, blend, opacity (labeled rows)
- Effects header (collapsed)
- Delete row

One expand adds roughly 9 drawable rows. With four layers that is ~12 to ~21 visible rows (~75% more draw work). If preset switching is also expanded, add ~8 more rows (~17 total for that layer).

## Biggest causes (ranked)

### 1. Full uncached redraw every frame

[TuningOverlay.draw()](cleave/viz/tuning_panel_draw.py) recreates all row surfaces and a new panel `pygame.Surface` every visible frame. No dirty tracking, no retention between frames.

### 2. Per-row CPU cost is high

Typical row work per frame:

- `font.render()` (often 2-4 times for composite rows)
- New `pygame.Surface(..., SRCALPHA)` per row (and sometimes per icon)
- [fit_text_to_width()](cleave/viz/text_fit.py) / `fit_path_label_to_width()` with binary search and repeated `font.size()` calls

Track headers are especially heavy: `render_visibility_icon`, `_fit_track_header_stem` (multiple `font.size` calls), `_render_track_header_label` (3-4 renders + surfaces).

### 3. All visible rows are built even when scrolled off-screen

In scroll mode, the first loop in `draw()` still builds surfaces for all `visible_indices`. The scroll loop only skips blitting off-screen rows:

```python
if y + line_h <= scroll_top or y >= scroll_bottom:
    continue
```

Expanding one layer can push the panel into scroll mode (~21 rows at 720p). You pay for all rows but only blit the viewport.

### 4. GL texture upload every frame

[upload_overlay_texture()](cleave/gl_compositor.py) copies the full panel to CPU memory via `pygame.image.tostring`, then uploads with `glTexSubImage2D`. A taller panel means more pixels per frame. Size changes trigger `glTexImage2D` reallocation (delete + create), which is worse than subimage updates.

At default `ui_width=110`, content width is ~528px. A ~21-row panel is on the order of 500x500+ pixels (~1 MB RGBA) copied and uploaded per frame.

### 5. `blit_tint` allocates per focused row

[blit_tint()](cleave/viz/ui_tint.py) creates a temporary SRCALPHA surface for focus and move-mode row backgrounds, called from `_blit_row` every frame.

### 6. View state and layout rebuilt every frame

`TuningViewState.__post_init__` always calls `RowLayout.build(self)`. [TuningViewStateBuilder.build()](cleave/viz/tuning_view_state.py) copies all `TrackBlock` dicts and, with timeline enabled, calls `effective_layer_enabled()` per layer. Layout work grows when sections expand.

### 7. Full-viewport overlay clear

[OverlayDrawer.draw_tuning()](cleave/viz/overlay_draw.py) clears the entire 1280x720 overlay surface even though only a small panel region is uploaded.

### 8. FPS feedback loop (secondary)

When `display_fps` is set, [app.py](cleave/viz/app.py) passes it to `layer.pm.set_fps()`. UI cost lowers measured fps, which lowers libprojectM target fps, which can make visuals feel worse beyond the overlay work itself.

## Suggestions (by impact vs effort)

### Quick wins

1. **Skip overlay work when fully hidden** — Early-return in `_tick_frame_live_overlay` when `overlay.visibility <= 0.01` (still call `update()`, skip `build_view_state` + draw + upload).

2. **Viewport-only row rendering** — In `draw()`, only build `row_surfaces` for header rows plus scroll-visible rows. Best single change when scroll is active.

3. **Replace `blit_tint` with `pygame.draw.rect`** — Focus backgrounds do not need a temporary SRCALPHA surface.

4. **Dedicated small overlay surface** — Size to panel bounds instead of full viewport; drop the 1280x720 fill.

5. **Cache fitted text** — Key `(row_kind, slot, value_hash, max_width)` so `fit_text_to_width` is not rerun every frame for static labels (preset paths, layer names).

### Medium effort (best long-term ROI)

6. **Panel cache with dirty rows** (mirror `RenderOverlayPanelCache`) — Retain one panel surface between frames; track dirty row indices (focus change, value change, expand/collapse); redraw only dirty rows; full rebuild on expand/collapse/width change. Align invalidation with computed signatures per [architecture principles](.cursor/rules/architecture-principles.mdc).

7. **Row surface cache** — Cache per-row rendered surfaces keyed by display content + color state. Invalidate on mutation or focus change (focus only affects one row).

8. **Defer `RowLayout.build()`** — Rebuild layout only when `expanded` flags, layer count, or conditional predicates change, not when only transport position or fps updates.

9. **Split static vs dynamic rows** — Transport time and fps change every frame; most layer rows do not. Draw static rows from cache; redraw one or two dynamic rows.

### Larger / architectural

10. **Incremental GPU upload** — PBOs or dirty-rect uploads if panel size is stable; avoid full-panel `tostring` when only focus highlight moved.

11. **Decouple projectM fps from overlay fps** — Use a smoothed or capped pm fps so UI spikes do not throttle Milkdrop.

12. **Lazy sub-sections** — Default `preset_switching_expanded=False` already helps. Consider collapsing more sub-trees by default or expand-on-focus to keep row count low.

## How to validate

Profile one frame with UI visible, collapsed vs one layer expanded. Wrap `TuningOverlay.draw` or `_tick_frame_live_overlay` with `cProfile`.

Expect top time in:

- `font.render` / `font.size`
- `pygame.Surface` creation
- `pygame.image.tostring`
- `fit_text_to_width`

A micro-benchmark counting `visible_indices` and `font.render` calls per frame should correlate with the fps delta.

## Bottom line

The ~5 fps hit is less about the expand toggle itself and more about the panel going from ~12 to ~21 fully rasterized, uncached rows per frame, plus a larger GL upload. Highest-leverage fixes: viewport-only rendering, a panel/row cache, and avoiding per-frame full texture readback. Follow the render overlay cache pattern in [frame_finish.py](cleave/viz/frame_finish.py).
