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

**Layer live authority.** `TuningSession` is the only live store for creative layer state (opacity, blend, stem, beat, enabled, locked, effects, preset switching, z-order). `CleaveConfig.layers` is YAML bootstrap for `session_from_cfg` and `scan_all_layers`. GPU objects are copies pushed from session. Persist (`persist_layers`, `persist_layer_z_order`) reads session only. Overlay card title/body text and colours stay on cfg because they are never live-edited. Editor prefs and `project.yaml` song markers remain separate documents. Detail: [Appendix: P0 work](#appendix-p0-work).

**Layer composite contract.** Both GPU compositors implement [layer_composite.py](../cleave/layer_composite.py) `LayerCompositor` against one `LayerCompositeRequest`. Blend, opacity-in-alpha, and HDR format live in [layer_blend.py](../cleave/layer_blend.py) and [gl_color_format.py](../cleave/gl_color_format.py). [layer_pipeline.py](../cleave/viz/layer_pipeline.py) `LayerFramePipeline.composite` is the layer choke point (mask on/off only selects the implementation). Wipes are an explicit `MaskTransition`. Hard composite (feather 0%) still ignores per-layer blend, hue, and flash by design; the soft path applies them. [frame_finish.py](../cleave/viz/frame_finish.py) remains the post-composite choke point. Detail: [Appendix: P0 work](#appendix-p0-work).

**Panel present-style draw and public mutation API.** Labeled/value rows draw through `RowPresentStyle` renderers in [row_present_renderers.py](../cleave/viz/row_present_renderers.py). [row_fields.py](../cleave/viz/row_fields.py) mutates via public `LayerMutations` and public sub-controllers (`settings`, `render_overlays`, `render_post_fx`, and the rest). [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) still has `RowKind` chrome for track headers, render eyes, transport, notifications, config dirty, and preset icons.

**Card-parameterized overlay kinds.** Opening and closing cards share 16 card-neutral `RowKind` values instanced by `RowDescriptor.card` (same pattern as `slot`). `RowFieldDef` callbacks take the descriptor and resolve the card through `controls.render_overlays.card(...)`. Asymmetric appear/disappear times are one `RENDER_OVERLAY_CARD_TIME` kind whose label comes from the card key.

**TrackBlock as a thin projection.** [tuning_view_state.py](../cleave/viz/tuning_view_state.py) `TrackBlock` holds a `LayerRuntime` reference plus derived labels and visibility (`preset_dir_label`, `preset_label`, `preset_list_labels`, `preset_empty`, `visible`, `active_preset_list_index`). `RenderOverlayCardBlock` holds a `RenderOverlayCardRuntime` reference. Formatters and draw read `block.runtime.*`. Overlay card title/body text and colours stay on cfg. Session and view dataclass defaults import constants from [config_schema.py](../cleave/config_schema.py).

---

## 1. Flaws to address (long-term brittleness)

These will lead to silent bugs, divergent behavior, or escalating change cost if left unaddressed.

### Four copies of the same settings

Adding a persisted knob still touches YAML descriptors, config dataclasses, session runtimes, and a panel row (`RowKind` + `RowFieldDef` + section tree + structure signature). View blocks are thin projections over session (`TrackBlock.runtime`, `RenderOverlayCardBlock.runtime`) plus derived labels; do not add mirrored creative fields on the block.

**Recommended direction:** keep view blocks as projections; stop adding parallel default literals outside `config_schema`.

### Residual draw chrome still branches on RowKind

Input is descriptor-driven (`ROW_FIELDS`, [row_sections.py](../cleave/viz/row_sections.py), `apply_field_horizontal`). Labeled/value drawing goes through `RowPresentStyle` in [row_present_renderers.py](../cleave/viz/row_present_renderers.py). [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) still branches on `RowKind` for track headers, render eyes, transport, notifications, config dirty, and preset icons. New chrome of that kind still needs a draw special case.

The architecture rules say not to add per-`RowKind` label or mutation branches in draw or controls; leftover header/icon chrome is the remaining leak.

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

Adding a panel row touches three to four files plus structure-signature tests.

**Pragmatic wins:** co-locate semantics and field def per row (or generate from one table).

### `controls.py` and `wiring.py` remain integration hubs

Feature controllers exist ([settings_controls.py](../cleave/viz/settings_controls.py), [render_overlay_controls.py](../cleave/viz/render_overlay_controls.py), [render_post_fx_controls.py](../cleave/viz/render_post_fx_controls.py), [render_pattern_mask_controls.py](../cleave/viz/render_pattern_mask_controls.py), [preset_curation_controls.py](../cleave/viz/preset_curation_controls.py), timeline snap/cut/preset/phase). [TuningControls](../cleave/viz/controls.py) still grew to ~1,699 lines: preset browsing, user-preset file I/O, layer add/delete, move mode, solo, and song markers.

[wiring.py](../cleave/viz/wiring.py) (~582 lines) is still a factory of inline closures (`LiveLayerBindings`, `RenderPostFxBindings`). Typed dataclasses of callables are better than a lambda dict, but they are still a bag of side effects rather than a layer service.

**Pragmatic wins:** move preset-browser and user-preset flows into dedicated controllers; shrink `make_tuning_controls` to wiring only.

### `timeline_overlay.py` is still a second UI stack (~1,766 lines)

GL upload and dirty rects moved to [overlay_upload.py](../cleave/viz/overlay_upload.py) and [overlay_draw.py](../cleave/viz/overlay_draw.py). The strip still reimplements panel drawing, caching, and input-adjacent view construction, and imports `clip_rect_to_bounds` / `render_visibility_icon` from [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py). Help ([help_overlay.py](../cleave/viz/help_overlay.py)) and modals ([modal_overlay.py](../cleave/viz/modal_overlay.py)) are further stacks but smaller.

**Pragmatic wins:** extract shared overlay primitives (icon render, clip, upload cache interface) into a small module both panels use. Do not fold the timeline strip into `RowLayout` (it is a panel anchor by design).

### Generative timeline is a second domain (~4,300 lines)

[timeline_presets/](../cleave/timeline_presets/) is well isolated from viz. [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) alone is ~967 lines of overlap emit, recast, and wipe constraints that must match compositor behavior. Drift between compose and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) is a product bug, not just a tidy issue.

Keep the package boundary. The compose/compositor contract (duration, overlap, recast vs slot-set change, hard-path blend exemption) lives next to the code in [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py).

### Test gaps on draw chrome

[test_controls.py](../tests/cleave/viz/test_controls.py) and [test_row_fields.py](../tests/cleave/viz/test_row_fields.py) cover input. [test_tuning_panel_draw.py](../tests/cleave/viz/test_tuning_panel_draw.py) covers present-style text/fit guards. Cache, overlay, and editor-mode tests import some draw helpers. Masked compositing has [test_masked_compositor_gl_integration.py](../tests/cleave/test_masked_compositor_gl_integration.py), [test_compositor_parity.py](../tests/cleave/test_compositor_parity.py) (soft full-coverage vs unmasked), and pattern-mask unit tests.

---

## 3. Suggested priority

| Priority | Item | Why |
| --- | --- | --- |
| **P2** | Decouple effects (and frame helpers) from `TuningSession` | Unblocks reuse and cleaner module boundaries |
| **P2** | Split `config_schema` by domain | Low risk, improves reviewability |
| **P3** | Shared overlay primitives for timeline and tuning panel | Pays off when timeline chrome grows |
| **P3** | Direct draw tests for remaining header/icon chrome | Cheap insurance on the largest draw module |

---

## 4. Bottom line

The architecture principles still match what the code is aiming for. Layer creative state lives on session after bootstrap. Both layer compositors share one request contract, blend/opacity/HDR helpers, and an explicit wipe command. Overlay cards are one kind set plus a card key. `TrackBlock` is a thin projection over `LayerRuntime`. Remaining tax is YAML/config/session plus residual header/icon chrome in draw.

---

## Appendix: P0 work

The two P0 items from this review. Invariants also live in [architecture principles](../.cursor/rules/architecture-principles.mdc).

### Phase 1: session as live layer authority

`TuningSession` is the only live store for creative layer state after `session_from_cfg`. `CleaveConfig.layers` is YAML bootstrap for that builder and for [preset_playlist.py](../cleave/preset_playlist.py) `scan_all_layers` (playlists exist before session). Editor prefs, paths, sizes, and overlay card title/body text and colours stay on cfg because they are never live-edited. `project.yaml` song markers remain a separate document.

| Path | Change |
| --- | --- |
| [layer_pipeline.py](../cleave/viz/layer_pipeline.py) | `build` / `build_single` take `LayerRuntime` and `session.layer_z_order`. GPU opacity, blend, enabled, beat, and preset switching seed from session. |
| [session.py](../cleave/viz/session.py) | `new_layer_runtime` builds an add-layer runtime. No `LayerConfig` on the live add path. |
| [wiring.py](../cleave/viz/wiring.py) | `LayerManager` add/remove mutates session, playlists, and GPU only. |
| [config_schema.py](../cleave/config_schema.py) | `persist_layers` and `persist_layer_z_order` read session only. |
| [layer_preview_resolution.py](../cleave/viz/layer_preview_resolution.py) | `offline_layer_sizes` takes an explicit z-order. |
| [app.py](../cleave/viz/app.py), [render.py](../cleave/viz/render.py), [editor_mode_controls.py](../cleave/viz/editor_mode_controls.py) | Missing-preset checks use session playlists. |

[test_layer_authority.py](../tests/cleave/viz/test_layer_authority.py) poisons `cfg.layers` after live edits and asserts persist, GPU seed, and add-then-save still follow session.

### Phase 2: shared layer-composite contract

Both GPU compositors implement [layer_composite.py](../cleave/layer_composite.py) `LayerCompositor` against one `LayerCompositeRequest` (`target_fbo_id`, layers in session z-order with first = topmost, `color_format`, optional `mask`, `active_slots`, `song_time_sec`, optional `MaskTransition`). [layer_pipeline.py](../cleave/viz/layer_pipeline.py) `LayerFramePipeline.composite` builds that request and only branches to pick the implementation. [frame_finish.py](../cleave/viz/frame_finish.py) stays the post-composite choke point.

| Path | Change |
| --- | --- |
| [layer_blend.py](../cleave/layer_blend.py) | Public `apply_layer_blend_mode` and `opacity_in_alpha` (add uses opacity in alpha; other modes bake opacity into RGB). |
| [gl_color_format.py](../cleave/gl_color_format.py) | Shared RGBA16F probe; both compositors fail the same way when HDR is unsupported. |
| [pattern_mask_transition.py](../cleave/pattern_mask_transition.py) | `PatternMaskTransitionTracker` holds the previous active set. Pipeline `peek`s a `MaskTransition` (`hard_layout` / `weight_field` / `clear`) and `commit`s. Compositors do not infer wipes from slot diffs. `live_slots` uses the same pending command plus in-flight morph territory. |
| [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) | Soft path applies hue and flash. Hard path (feather 0%) ignores blend, hue, and flash by design. |
| [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) | Compose/compositor contract (duration, overlap, recast vs slot-set change, hard-path exemption) lives next to the emit code. |

[test_layer_composite.py](../tests/cleave/test_layer_composite.py) asserts both classes satisfy the protocol. [test_compositor_parity.py](../tests/cleave/test_compositor_parity.py) compares soft full-coverage mask-on vs unmasked output across blend modes and colour formats.
