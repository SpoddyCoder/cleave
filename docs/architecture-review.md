# Architecture review

Pragmatic assessment of the Cleave codebase from a Python software architecture perspective. Focus is on high-value refactors, not perfection. Reviewed against the current tree (August 2026).

Related: [architecture principles](../.cursor/rules/architecture-principles.mdc), [todos.md](todos.md), completed [architecture refactor](completed/architecture-refactor.md) and [architecture improvements](completed/architecture-improvements.md).

---

## Context

The earlier refactor direction is still sound and has been extended:

- Typed runtimes (`VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`, `RenderVisualizerRuntime`) in [cleave/viz/app.py](../cleave/viz/app.py)
- Descriptor-driven parse, dump, and persist in [cleave/config_schema.py](../cleave/config_schema.py)
- Computed dirty tracking via `persisted_session_signature` in [cleave/config_snapshot.py](../cleave/config_snapshot.py); snapshot writes go through `persisted_session_payload`
- Registry-based effect dispatch in [cleave/effects/handlers.py](../cleave/effects/handlers.py)
- Shared live/offline frame finish in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)
- Panel field manifest (`RowFieldDef`, `present_style`) in [cleave/viz/row_fields.py](../cleave/viz/row_fields.py)
- Focus as `FocusCursor` in [cleave/viz/focus_nav.py](../cleave/viz/focus_nav.py); `RowLayout` built once per structure signature
- User editor prefs in [cleave/user_config.py](../cleave/user_config.py); project editor size/beat stay on viz YAML
- Panel caches ([cleave/viz/tuning_panel_cache.py](../cleave/viz/tuning_panel_cache.py), [cleave/viz/timeline_panel_cache.py](../cleave/viz/timeline_panel_cache.py)) and overlay upload in [cleave/viz/overlay_upload.py](../cleave/viz/overlay_upload.py)

What remains is complexity debt in a few hotspots. Several of those modules have grown since the last review, and new features (pattern mask, generative timeline, visual limiter, HDR) added a second GPU composite path and more type copies of the same settings.

Approximate sizes of the largest modules:

| Module | Lines |
| --- | --- |
| [config_schema.py](../cleave/config_schema.py) | 2,920 |
| [row_fields.py](../cleave/viz/row_fields.py) | 2,721 |
| [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) | 2,494 |
| [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) | 1,988 |
| [timeline_overlay.py](../cleave/viz/timeline_overlay.py) | 1,766 |
| [row_semantics.py](../cleave/viz/row_semantics.py) | 1,744 |
| [controls.py](../cleave/viz/controls.py) | 1,699 |
| [row_sections.py](../cleave/viz/row_sections.py) | 1,391 |
| [pattern_mask.py](../cleave/pattern_mask.py) | 1,343 |
| [tuning_view_state.py](../cleave/viz/tuning_view_state.py) | 1,113 |
| [gl_compositor.py](../cleave/gl_compositor.py) | 1,114 |
| [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) | 967 |

---

## Resolved since last review

These items are no longer the right targets.

**Snapshot writes bypassed descriptors.** `write_session_snapshot` now takes the full payload from `persisted_session_payload`. The leftover `_snapshot_render` deep-merge only preserves original YAML key order and strips legacy overlay keys. New render fields belong on the descriptor tables, not a second serializer.

**Per-layer width/height vs preview quality.** Live preview and `--viz-quality` both use [layer_preview_resolution.py](../cleave/viz/layer_preview_resolution.py). Default offline render stays full `render.width` x `render.height` per layer.

**Uncached full-panel redraw.** Structure signatures, `TuningPanelCache`, and incremental compose are in place (see [ui-performance-improvements.md](completed/ui-performance-improvements.md)). Remaining draw cost is special-case chrome, not the old every-frame rebuild.

**Layer live authority.** `TuningSession` is the only live store for creative layer state (opacity, blend, stem, beat, enabled, locked, effects, preset switching, z-order). `CleaveConfig.layers` is YAML bootstrap for `session_from_cfg` and `scan_all_layers`. GPU objects are copies pushed from session. Persist (`persist_layers`, `persist_layer_z_order`) reads session only. Overlay card title/body text and colours stay on cfg because they are never live-edited. Editor prefs and `project.yaml` song markers remain separate documents.

**Layer composite contract.** Both GPU compositors implement [layer_composite.py](../cleave/layer_composite.py) `LayerCompositor` against one `LayerCompositeRequest`. Blend, opacity-in-alpha, and HDR format live in [layer_blend.py](../cleave/layer_blend.py) and [gl_color_format.py](../cleave/gl_color_format.py). [layer_pipeline.py](../cleave/viz/layer_pipeline.py) `LayerFramePipeline.composite` is the layer choke point (mask on/off only selects the implementation). Wipes are an explicit `MaskTransition`. Hard composite (feather 0%) still ignores per-layer blend, hue, and flash by design; the soft path applies them. [frame_finish.py](../cleave/viz/frame_finish.py) remains the post-composite choke point.

---

## 1. Flaws to address (long-term brittleness)

These will lead to silent bugs, divergent behavior, or escalating change cost if left unaddressed.

### Four copies of the same settings

Adding a persisted knob still touches:

| Layer | Example |
| --- | --- |
| YAML descriptors / parse | [config_schema.py](../cleave/config_schema.py) |
| Config dataclasses | [config.py](../cleave/config.py) (`CleaveConfig`, `LayerConfig`, overlay/post-FX types) |
| Session runtimes | [session.py](../cleave/viz/session.py) (`LayerRuntime`, `RenderPostFxRuntime`, ...) |
| View blocks | [tuning_view_state.py](../cleave/viz/tuning_view_state.py) (`TrackBlock`, `RenderOverlayCardBlock`, ...) |
| Panel row | `RowKind` + `RowFieldDef` + section tree + structure signature |

`TrackBlock` still mirrors `LayerRuntime` field-for-field. Overlay opening and closing cards duplicate ~30 `RowKind` values that differ only by card name. Defaults are intended to live once in `config_schema`, but session and view dataclasses restate many of them.

**Recommended direction:** generate view blocks as thin projections (or read session through formatters); parameterize opening/closing overlay rows as one kind plus a card key; stop adding parallel default literals outside `config_schema`.

### Panel manifest migration is incomplete on the draw side

Input is largely descriptor-driven (`ROW_FIELDS`, [row_sections.py](../cleave/viz/row_sections.py), `apply_field_horizontal`). Drawing has `RowPresentStyle` dispatch for labeled value, action parameter, expand subheader, path icon, and similar, but [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) (~2,494 lines) still branches on `RowKind` for track headers, render eyes, transport, notifications, config dirty, and preset icons. New rows still require coordinated edits across `row_semantics`, `row_fields`, `row_sections`, `view_state_structure_signature`, and draw special cases.

[row_fields.py](../cleave/viz/row_fields.py) mutates through `controls._settings`, `controls._set_opacity`, and other underscore methods, which violates the public-API rule in the architecture principles.

The architecture rules say not to add per-`RowKind` label or mutation branches in draw or controls; residual branches and private callbacks are the leak.

### Domain layering: effects (and the frame path) depend on viz

[cleave/effects/runtime.py](../cleave/effects/runtime.py) still imports `TuningSession`. Core effect logic is coupled to the editor session model. The same type now threads through [layer_pipeline.py](../cleave/viz/layer_pipeline.py), [post_fx.py](../cleave/viz/post_fx.py), [visual_limiter.py](../cleave/viz/visual_limiter.py), and [frame_finish.py](../cleave/viz/frame_finish.py). Adding effects or a headless composite from CLI/tests without the viz stack stays harder than it should be.

[timeline_presets/](../cleave/timeline_presets/) does *not* import viz (good). Apply still lives in [timeline_preset_controls.py](../cleave/viz/timeline_preset_controls.py) and reaches into pattern-mask session fields.

**Recommended direction:** extract a small neutral type (for example `LayerEffectState`) in a non-viz module that session and effects both use. Frame-path helpers should take the slices they need (post-FX runtime, pattern-mask runtime), not the whole `TuningSession`, unless they are genuinely UI.

---

## 2. Weaknesses worth addressing (maintainability)

These will make the codebase easier to work in but are lower risk than the flaws above.

### `config_schema.py` monolith (~2,920 lines)

The module holds defaults, parse, dump, persist, display helpers, and section descriptors for editor, layers, render (overlays, post-FX, pattern mask), and timeline. It is the right abstraction, but at this size it is hard to review and easy to break cross-section. Function-local imports back to [config.py](../cleave/config.py) and [user_config.py](../cleave/user_config.py) still exist to avoid cycles.

Layers and timeline remain bespoke parse/persist (called out in the architecture principles). That is reasonable for nested lanes and per-slot layers; it does mean new timeline cue fields have no descriptor checklist.

**Pragmatic split:** `config_schema/editor.py`, `layers.py`, `render.py`, `timeline.py` with a thin re-export, or keep one package but extract section descriptor tables. Do not add a second persist function.

### Four parallel UI registries, still growing

| Module | Role | ~Lines |
| --- | --- | --- |
| [row_semantics.py](../cleave/viz/row_semantics.py) | `RowKind` (~100 values), affordances, help, lock rules | 1,744 |
| [row_fields.py](../cleave/viz/row_fields.py) | Labels, formatters, mutations | 2,721 |
| [row_sections.py](../cleave/viz/row_sections.py) | Tree composition, conditionals | 1,391 |
| [tuning_view_state.py](../cleave/viz/tuning_view_state.py) | Session to `TrackBlock` / render blocks | 1,113 |

Adding a panel row touches three to four files plus structure-signature tests. Opening/closing overlay duplication multiplies that tax.

**Pragmatic wins:** co-locate semantics and field def per row (or generate from one table); card-parameterized overlay kinds; reduce `TrackBlock` to thin views over session.

### `controls.py` and `wiring.py` remain integration hubs

Feature controllers exist ([settings_controls.py](../cleave/viz/settings_controls.py), [render_overlay_controls.py](../cleave/viz/render_overlay_controls.py), [render_post_fx_controls.py](../cleave/viz/render_post_fx_controls.py), [render_pattern_mask_controls.py](../cleave/viz/render_pattern_mask_controls.py), [preset_curation_controls.py](../cleave/viz/preset_curation_controls.py), timeline snap/cut/preset/phase). [TuningControls](../cleave/viz/controls.py) still grew to ~1,699 lines: preset browsing, user-preset file I/O, layer add/delete, move mode, solo, song markers, and dozens of `_set_*` / `_cycle_*` methods that `row_fields` calls.

[wiring.py](../cleave/viz/wiring.py) (~582 lines) is still a factory of inline closures (`LiveLayerBindings`, `RenderPostFxBindings`). Typed dataclasses of callables are better than a lambda dict, but they are still a bag of side effects rather than a layer service.

**Pragmatic wins:** move preset-browser and user-preset flows into dedicated controllers; expose a public mutation API that `row_fields` can call without underscores; shrink `make_tuning_controls` to wiring only.

### `timeline_overlay.py` is still a second UI stack (~1,766 lines)

GL upload and dirty rects moved to [overlay_upload.py](../cleave/viz/overlay_upload.py) and [overlay_draw.py](../cleave/viz/overlay_draw.py). The strip still reimplements panel drawing, caching, and input-adjacent view construction, and imports `clip_rect_to_bounds` / `render_visibility_icon` from [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py). Help ([help_overlay.py](../cleave/viz/help_overlay.py)) and modals ([modal_overlay.py](../cleave/viz/modal_overlay.py)) are further stacks but smaller.

**Pragmatic wins:** extract shared overlay primitives (icon render, clip, upload cache interface) into a small module both panels use. Do not fold the timeline strip into `RowLayout` (it is a panel anchor by design).

### Generative timeline is a second domain (~4,300 lines)

[timeline_presets/](../cleave/timeline_presets/) is well isolated from viz. [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) alone is ~967 lines of overlap emit, recast, and wipe constraints that must match compositor behavior. Drift between compose and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) is a product bug, not just a tidy issue.

Keep the package boundary. The compose/compositor contract (duration, overlap, recast vs slot-set change, hard-path blend exemption) lives next to the code in [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py).

### Test gaps on draw chrome

[test_controls.py](../tests/cleave/viz/test_controls.py) and [test_row_fields.py](../tests/cleave/viz/test_row_fields.py) cover input. Cache, overlay, and editor-mode tests import some draw helpers. There is still no `test_tuning_panel_draw.py`. Masked compositing has [test_masked_compositor_gl_integration.py](../tests/cleave/test_masked_compositor_gl_integration.py), [test_compositor_parity.py](../tests/cleave/test_compositor_parity.py) (soft full-coverage vs unmasked), and pattern-mask unit tests.

---

## 3. Suggested priority

| Priority | Item | Why |
| --- | --- | --- |
| **P1** | Finish draw-side descriptor migration (or extract `PresentStyle` renderers); public mutation API for `row_fields` | Cuts multi-file tax per new row; stops underscore coupling |
| **P1** | Collapse four setting copies (especially overlay card kinds and `TrackBlock`) | Same tax as draw migration, on the data side |
| **P2** | Decouple effects (and frame helpers) from `TuningSession` | Unblocks reuse and cleaner module boundaries |
| **P2** | Split `config_schema` by domain | Low risk, improves reviewability |
| **P3** | Shared overlay primitives for timeline and tuning panel | Pays off when timeline chrome grows |
| **P3** | Direct draw tests | Cheap insurance on the largest untested draw module |

---

## 4. Bottom line

The architecture principles still match what the code is aiming for. Layer creative state lives on session after bootstrap. Both layer compositors share one request contract, blend/opacity/HDR helpers, and an explicit wipe command. Incomplete descriptor coverage on the draw path remains the main tax on every new panel row.
