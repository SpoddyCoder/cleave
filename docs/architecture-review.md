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
- Panel field manifest (`RowFieldDef`, `present_style`, `fit_strategy`, `visibility_icon`) in [cleave/viz/row_fields.py](../cleave/viz/row_fields.py); draw through [row_present_renderers.py](../cleave/viz/row_present_renderers.py); mutations through [layer_mutations.py](../cleave/viz/layer_mutations.py)
- `RowDescriptor` carries `slot` (per-track) and `card` (per overlay card); overlay rows share one `RowKind` set instanced by card key
- Focus as `FocusCursor` in [cleave/viz/focus_nav.py](../cleave/viz/focus_nav.py); `RowLayout` built once per structure signature
- User editor prefs in [cleave/user_config.py](../cleave/user_config.py); project editor size/beat stay on viz YAML
- Panel caches ([cleave/viz/tuning_panel_cache.py](../cleave/viz/tuning_panel_cache.py), [cleave/viz/timeline_panel_cache.py](../cleave/viz/timeline_panel_cache.py)) and overlay upload in [cleave/viz/overlay_upload.py](../cleave/viz/overlay_upload.py)

What remains is complexity debt in a few hotspots: the `config_schema` monolith, effects coupled to `TuningSession`, and parallel UI registries that still require coordinated edits per new row.

Approximate sizes of the largest modules:

| Module | Lines |
| --- | --- |
| [config_schema.py](../cleave/config_schema.py) | 2,829 |
| [row_fields.py](../cleave/viz/row_fields.py) | 2,721 |
| [row_semantics.py](../cleave/viz/row_semantics.py) | 1,605 |
| [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) | 2,022 |
| [timeline_overlay.py](../cleave/viz/timeline_overlay.py) | 1,766 |
| [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) | 1,505 |
| [controls.py](../cleave/viz/controls.py) | 1,461 |
| [row_present_renderers.py](../cleave/viz/row_present_renderers.py) | 1,068 |
| [row_sections.py](../cleave/viz/row_sections.py) | 1,337 |
| [pattern_mask.py](../cleave/pattern_mask.py) | 1,343 |
| [gl_compositor.py](../cleave/gl_compositor.py) | 1,075 |
| [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) | 982 |

---

## Resolved since last review

These items are no longer the right targets.

**Snapshot writes bypassed descriptors.** `write_session_snapshot` now takes the full payload from `persisted_session_payload`. The leftover `_snapshot_render` deep-merge only preserves original YAML key order and strips legacy overlay keys. New render fields belong on the descriptor tables, not a second serializer.

**Per-layer width/height vs preview quality.** Live preview and `--viz-quality` both use [layer_preview_resolution.py](../cleave/viz/layer_preview_resolution.py). Default offline render stays full `render.width` x `render.height` per layer.

**Uncached full-panel redraw.** Structure signatures, `TuningPanelCache`, and incremental compose are in place (see [ui-performance-improvements.md](completed/ui-performance-improvements.md)). Remaining draw cost is incremental compose and cache invalidation, not the old every-frame rebuild.

**Layer live authority.** `TuningSession` is the only live store for creative layer state (opacity, blend, stem, beat, enabled, locked, effects, preset switching, z-order). `CleaveConfig.layers` is YAML bootstrap for `session_from_cfg` and `scan_all_layers`. GPU objects are copies pushed from session. Persist (`persist_layers`, `persist_layer_z_order`) reads session only. Overlay card title/body text and colours stay on cfg because they are never live-edited. Editor prefs and `project.yaml` song markers remain separate documents. Detail: [Appendix: P0 work](#appendix-p0-work).

**Layer composite contract.** Both GPU compositors implement [layer_composite.py](../cleave/layer_composite.py) `LayerCompositor` against one `LayerCompositeRequest`. Blend, opacity-in-alpha, and HDR format live in [layer_blend.py](../cleave/layer_blend.py) and [gl_color_format.py](../cleave/gl_color_format.py). [layer_pipeline.py](../cleave/viz/layer_pipeline.py) `LayerFramePipeline.composite` is the layer choke point (mask on/off only selects the implementation). Wipes are an explicit `MaskTransition`. Hard composite (feather 0%) still ignores per-layer blend, hue, and flash by design; the soft path applies them. [frame_finish.py](../cleave/viz/frame_finish.py) remains the post-composite choke point. Detail: [Appendix: P0 work](#appendix-p0-work).

**Panel present-style draw and public mutation API.** All tuning-panel rows draw through `RowPresentStyle` renderers in [row_present_renderers.py](../cleave/viz/row_present_renderers.py). [row_fields.py](../cleave/viz/row_fields.py) carries `fit_strategy`, `visibility_icon`, and `shows_enter_icon` on `RowFieldDef`; [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) has no `RowKind` branches. Mutations go through public `LayerMutations` in [layer_mutations.py](../cleave/viz/layer_mutations.py) and public sub-controllers on `TuningControls` (`settings`, `render_overlays`, `render_post_fx`, and the rest). [test_tuning_panel_draw.py](../tests/cleave/viz/test_tuning_panel_draw.py) covers one row per present style plus a source-scan guard. Detail: [Appendix: P1 work](#appendix-p1-work).

**Card-parameterized overlay kinds.** Opening and closing cards share 16 card-neutral `RowKind` values instanced by `RowDescriptor.card` (same pattern as `slot`). `RowFieldDef` callbacks take the descriptor and resolve the card through `controls.render_overlays.card(...)`. Asymmetric appear/disappear times are one `RENDER_OVERLAY_CARD_TIME` kind whose label comes from the card key.

**TrackBlock as a thin projection.** [tuning_view_state.py](../cleave/viz/tuning_view_state.py) `TrackBlock` holds a `LayerRuntime` reference plus derived labels and visibility (`preset_dir_label`, `preset_label`, `preset_list_labels`, `preset_empty`, `visible`, `active_preset_list_index`). `RenderOverlayCardBlock` holds a `RenderOverlayCardRuntime` reference. Formatters and draw read `block.runtime.*`. Overlay card title/body text and colours stay on cfg. Session and view dataclass defaults import constants from [config_schema.py](../cleave/config_schema.py).

---

## 1. Flaws to address (long-term brittleness)

These will lead to silent bugs, divergent behavior, or escalating change cost if left unaddressed.

### Four copies of the same settings

Adding a persisted knob still touches YAML descriptors, config dataclasses, session runtimes, and a panel row (`RowKind` + `RowFieldDef` + section tree + structure signature). View blocks are thin projections over session (`TrackBlock.runtime`, `RenderOverlayCardBlock.runtime`) plus derived labels; overlay opening/closing duplication is gone (one kind set plus `RowDescriptor.card`).

**Recommended direction:** keep view blocks as projections; stop adding parallel default literals outside `config_schema`.

### Domain layering: effects (and the frame path) depend on viz

[cleave/effects/runtime.py](../cleave/effects/runtime.py) still imports `TuningSession`. Core effect logic is coupled to the editor session model. The same type now threads through [layer_pipeline.py](../cleave/viz/layer_pipeline.py), [post_fx.py](../cleave/viz/post_fx.py), [visual_limiter.py](../cleave/viz/visual_limiter.py), and [frame_finish.py](../cleave/viz/frame_finish.py). Adding effects or a headless composite from CLI/tests without the viz stack stays harder than it should be.

[timeline_presets/](../cleave/timeline_presets/) does *not* import viz (good). Apply still lives in [timeline_preset_controls.py](../cleave/viz/timeline_preset_controls.py) and reaches into pattern-mask session fields.

**Recommended direction:** extract a small neutral type (for example `LayerEffectState`) in a non-viz module that session and effects both use. Frame-path helpers should take the slices they need (post-FX runtime, pattern-mask runtime), not the whole `TuningSession`, unless they are genuinely UI.

---

## 2. Weaknesses worth addressing (maintainability)

These will make the codebase easier to work in but are lower risk than the flaws above.

### `config_schema.py` monolith (~2,829 lines)

The module holds defaults, parse, dump, persist, display helpers, and section descriptors for editor, layers, render (overlays, post-FX, pattern mask), and timeline. It is the right abstraction, but at this size it is hard to review and easy to break cross-section. Function-local imports back to [config.py](../cleave/config.py) and [user_config.py](../cleave/user_config.py) still exist to avoid cycles.

Layers and timeline remain bespoke parse/persist (called out in the architecture principles). That is reasonable for nested lanes and per-slot layers; it does mean new timeline cue fields have no descriptor checklist.

**Pragmatic split:** `config_schema/editor.py`, `layers.py`, `render.py`, `timeline.py` with a thin re-export, or keep one package but extract section descriptor tables. Do not add a second persist function.

### Four parallel UI registries, still growing

| Module | Role | ~Lines |
| --- | --- | --- |
| [row_semantics.py](../cleave/viz/row_semantics.py) | `RowKind` (~100 values), affordances, help, lock rules | 1,605 |
| [row_fields.py](../cleave/viz/row_fields.py) | Labels, formatters, mutations | 2,721 |
| [row_sections.py](../cleave/viz/row_sections.py) | Tree composition, conditionals | 1,337 |
| [tuning_view_state.py](../cleave/viz/tuning_view_state.py) | Session to `TrackBlock` / render blocks | 967 |

Adding a panel row still touches three to four files plus structure-signature tests. Overlay cards no longer double the kind count.

**Pragmatic wins:** co-locate semantics and field def per row (or generate from one table).

### `controls.py` and `wiring.py` remain integration hubs

Feature controllers exist ([settings_controls.py](../cleave/viz/settings_controls.py), [render_overlay_controls.py](../cleave/viz/render_overlay_controls.py), [render_post_fx_controls.py](../cleave/viz/render_post_fx_controls.py), [render_pattern_mask_controls.py](../cleave/viz/render_pattern_mask_controls.py), [preset_curation_controls.py](../cleave/viz/preset_curation_controls.py), timeline snap/cut/preset/phase). [TuningControls](../cleave/viz/controls.py) is ~1,461 lines: preset browsing, user-preset file I/O, layer add/delete, move mode, solo, and song markers. Layer knob mutations live on `LayerMutations`, not underscore methods.

[wiring.py](../cleave/viz/wiring.py) (~582 lines) is still a factory of inline closures (`LiveLayerBindings`, `RenderPostFxBindings`). Typed dataclasses of callables are better than a lambda dict, but they are still a bag of side effects rather than a layer service.

**Pragmatic wins:** move preset-browser and user-preset flows into dedicated controllers; shrink `make_tuning_controls` to wiring only.

### `timeline_overlay.py` is still a second UI stack (~1,766 lines)

GL upload and dirty rects moved to [overlay_upload.py](../cleave/viz/overlay_upload.py) and [overlay_draw.py](../cleave/viz/overlay_draw.py). The strip still reimplements panel drawing, caching, and input-adjacent view construction, and imports `clip_rect_to_bounds` / `render_visibility_icon` from [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py). Help ([help_overlay.py](../cleave/viz/help_overlay.py)) and modals ([modal_overlay.py](../cleave/viz/modal_overlay.py)) are further stacks but smaller.

**Pragmatic wins:** extract shared overlay primitives (icon render, clip, upload cache interface) into a small module both panels use. Do not fold the timeline strip into `RowLayout` (it is a panel anchor by design).

### Generative timeline is a second domain (~4,300 lines)

[timeline_presets/](../cleave/timeline_presets/) is well isolated from viz. [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) alone is ~982 lines of overlap emit, recast, and wipe constraints that must match compositor behavior. Drift between compose and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py) is a product bug, not just a tidy issue.

Keep the package boundary. The compose/compositor contract (duration, overlap, recast vs slot-set change, hard-path blend exemption) lives next to the code in [pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) and [gl_masked_compositor.py](../cleave/gl_masked_compositor.py).

### Test coverage on panel draw

[test_controls.py](../tests/cleave/viz/test_controls.py) and [test_row_fields.py](../tests/cleave/viz/test_row_fields.py) cover input. [test_tuning_panel_draw.py](../tests/cleave/viz/test_tuning_panel_draw.py) covers present-style text/fit and asserts no `RowKind` branches remain in the draw module. Cache, overlay, and editor-mode tests import some draw helpers. Masked compositing has [test_masked_compositor_gl_integration.py](../tests/cleave/test_masked_compositor_gl_integration.py), [test_compositor_parity.py](../tests/cleave/test_compositor_parity.py) (soft full-coverage vs unmasked), and pattern-mask unit tests.

---

## 3. Suggested priority

| Priority | Item | Why |
| --- | --- | --- |
| **P2** | Decouple effects (and frame helpers) from `TuningSession` | Unblocks reuse and cleaner module boundaries |
| **P2** | Split `config_schema` by domain | Low risk, improves reviewability |
| **P3** | Shared overlay primitives for timeline and tuning panel | Pays off when timeline chrome grows |

---

## 4. Bottom line

The architecture principles still match what the code is aiming for. Layer creative state lives on session after bootstrap. Both layer compositors share one request contract, blend/opacity/HDR helpers, and an explicit wipe command. The tuning panel is descriptor-driven end to end: overlay cards are one kind set plus a card key, `TrackBlock` is a thin projection over `LayerRuntime`, and draw has no per-`RowKind` branches. Remaining tax is YAML/config/session for new persisted knobs and coordinated edits across the four UI registries.

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

## Appendix: P1 work

The P1 items from this review. Invariants also live in [architecture principles](../.cursor/rules/architecture-principles.mdc).

### Phase 1: public mutation API

[row_fields.py](../cleave/viz/row_fields.py) no longer calls private `TuningControls` members. Sub-controllers are public on [controls.py](../cleave/viz/controls.py). Layer knob mutations live on [layer_mutations.py](../cleave/viz/layer_mutations.py) `LayerMutations`, owned by `TuningControls`.

| Path | Change |
| --- | --- |
| [layer_mutations.py](../cleave/viz/layer_mutations.py) | `LayerMutations` facade: set/cycle/step layer and preset knobs, enter/parent directory, solo enter/exit |
| [controls.py](../cleave/viz/controls.py) | Public `render_post_fx`, `render_pattern_mask`, `render_overlays`, `settings`, `timeline_phase`, `editor_mode`; owns `layer_mutations` |
| [row_fields.py](../cleave/viz/row_fields.py) | All `apply_horizontal` / format callbacks use public APIs only |

[test_row_fields.py](../tests/cleave/viz/test_row_fields.py) asserts no `RowFieldDef` callback touches a private controls attribute.

### Phase 2: present-style draw completion

Draw dispatches on `RowPresentStyle` only. `RowFieldDef` carries `fit_strategy`, `visibility_icon`, and `shows_enter_icon`. New styles: `TRACK_HEADER`, `NOTIFICATION`, `SPACER`.

| Path | Change |
| --- | --- |
| [row_present_renderers.py](../cleave/viz/row_present_renderers.py) | Per-style paint, fit, and color keyed by `RowPresentStyle` |
| [row_fields.py](../cleave/viz/row_fields.py) | Descriptor slots for fit, visibility icon, enter icon |
| [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) | Lookup plus shared surface setup; no `RowKind` comparisons |

[test_tuning_panel_draw.py](../tests/cleave/viz/test_tuning_panel_draw.py) covers one row per present style and source-scans for `RowKind` branches.

### Phase 3: card-parameterized overlay kinds

32 opening/closing `RowKind` pairs collapsed to 16 card-neutral kinds. `RowDescriptor.card` (`opening_card` / `closing_card`) instances overlay rows the same way `slot` instances track rows.

| Path | Change |
| --- | --- |
| [row_semantics.py](../cleave/viz/row_semantics.py) | Card-neutral overlay kinds; `RowDescriptor.card` field |
| [row_layout.py](../cleave/viz/row_layout.py) | `find` routes on `card` |
| [row_sections.py](../cleave/viz/row_sections.py) | `_build_render_overlay_card_section` called per card key |
| [row_fields.py](../cleave/viz/row_fields.py) | Callbacks take descriptor; resolve card via `controls.render_overlays.card(...)` |

### Phase 4: thin view projections

`TrackBlock` holds `runtime: LayerRuntime` plus derived labels and visibility. `RenderOverlayCardBlock` holds `runtime: RenderOverlayCardRuntime`. Formatters and draw read `block.runtime.*`. Layer defaults (`DEFAULT_LAYER_ENABLED`, `DEFAULT_LAYER_OPACITY`, `DEFAULT_LAYER_LOCKED`) live in [config_schema.py](../cleave/config_schema.py) and are imported by session and config types.

[test_layer_authority.py](../tests/cleave/viz/test_layer_authority.py) and view-state tests assert session mutations flow through projections without block-side writes.
