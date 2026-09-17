# Architecture review

Start implementation from [.cursor/rules/project-context.mdc](../../.cursor/rules/project-context.mdc). Read this review only when adding a cross-module abstraction.

Living note of current invariants. P0 through P4 are shipped; the write-ups live in [plans-completed/architecture-review-p0-p4.md](plans-completed/architecture-review-p0-p4.md). Remaining section 2 items are domain isolation kept on purpose, not a next P.

Related: [architecture-principles.mdc](../../.cursor/rules/architecture-principles.mdc), [todos.md](todos.md), [plans-completed/architecture-refactor.md](plans-completed/architecture-refactor.md), [plans-completed/architecture-improvements.md](plans-completed/architecture-improvements.md).

---

## Current architecture

- Typed runtimes (`VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`, `RenderVisualizerRuntime`) in [cleave/viz/app.py](../../cleave/viz/app.py)
- Descriptor-driven parse, dump, and persist in [cleave/config_schema/](../../cleave/config_schema/) (`editor`, `layers`, `render`, `timeline`, `persist`); [__init__.py](../../cleave/config_schema/__init__.py) has no re-exports
- Computed dirty tracking via `persisted_session_signature` in [cleave/config_snapshot.py](../../cleave/config_snapshot.py); snapshot writes go through `persisted_session_payload` in [persist.py](../../cleave/config_schema/persist.py)
- Registry-based effect dispatch in [cleave/effects/handlers.py](../../cleave/effects/handlers.py)
- Shared live/offline frame finish in [cleave/viz/frame_finish.py](../../cleave/viz/frame_finish.py)
- Panel row registry (`RowSpec`, `present_style`, `fit_strategy`, `visibility_icon`) in [row_spec.py](../../cleave/viz/row_spec.py) and [row_specs/](../../cleave/viz/row_specs/); kinds in [row_kinds.py](../../cleave/viz/row_kinds.py); draw through [row_present_renderers.py](../../cleave/viz/row_present_renderers.py); mutations through [layer_mutations.py](../../cleave/viz/layer_mutations.py)
- `RowDescriptor` carries `slot` (per-track) and `card` (per overlay card); overlay rows share one `RowKind` set instanced by card key
- Focus as `FocusCursor` in [cleave/viz/focus_nav.py](../../cleave/viz/focus_nav.py); `RowLayout` built once per structure signature
- User editor prefs (including window size) in [cleave/user_config.py](../../cleave/user_config.py); project Milkdrop beat lives in `project.yaml`
- Panel caches ([cleave/viz/tuning_panel_cache.py](../../cleave/viz/tuning_panel_cache.py), [cleave/viz/timeline_panel_cache.py](../../cleave/viz/timeline_panel_cache.py)) and overlay upload in [cleave/viz/overlay_upload.py](../../cleave/viz/overlay_upload.py)
- Shared overlay primitives in [cleave/viz/overlay_primitives.py](../../cleave/viz/overlay_primitives.py)
- Feature controllers on `TuningControls` (`preset_list`, `song_markers`, `layer_lifecycle`, plus settings / overlays / post-FX / pattern mask / curation); live GPU bindings from [live_layer_binding_factory.py](../../cleave/viz/live_layer_binding_factory.py)

`TuningSession` is the only live store for creative layer state after `session_from_cfg`. YAML bootstrap dataclasses and live session runtimes stay separate by design. Adding a persisted knob still needs a config_schema field, a session runtime field, a `RowSpec`, and a section-tree placement; those four touchpoints are the checklist, not parallel serializers or default literals.

Approximate sizes of the largest modules:

| Module | Lines |
| --- | --- |
| [gl_masked_compositor.py](../../cleave/gl_masked_compositor.py) | 2,023 |
| [timeline_overlay.py](../../cleave/viz/timeline_overlay.py) | 1,743 |
| [tuning_panel_draw.py](../../cleave/viz/tuning_panel_draw.py) | 1,458 |
| [pattern_mask.py](../../cleave/pattern_mask.py) | 1,343 |
| [row_sections.py](../../cleave/viz/row_sections.py) | 1,337 |
| [timeline.py](../../cleave/viz/row_specs/timeline.py) | 1,099 |
| [controls.py](../../cleave/viz/controls.py) | 1,096 |
| [gl_compositor.py](../../cleave/gl_compositor.py) | 1,075 |
| [row_present_renderers.py](../../cleave/viz/row_present_renderers.py) | 1,066 |
| [pattern_mask_arrange.py](../../cleave/timeline_presets/pattern_mask_arrange.py) | 982 |

---

## Remaining notes (domain isolation)

These are lower risk than the shipped P0-P4 flaws. Keep the boundaries.

### `timeline_overlay.py` is still a second UI stack (~1,743 lines)

Clip, font, panel chrome, `ComposedPanel`, and `visibility_bucket` live in [overlay_primitives.py](../../cleave/viz/overlay_primitives.py). Timeline, help, and modal do not import [tuning_panel_draw.py](../../cleave/viz/tuning_panel_draw.py). `render_visibility_icon` is imported from [row_present_renderers.py](../../cleave/viz/row_present_renderers.py). GL upload and dirty rects live in [overlay_upload.py](../../cleave/viz/overlay_upload.py) and [overlay_draw.py](../../cleave/viz/overlay_draw.py).

The strip still owns its own compose, cache, and live-patch domain (bars, cues, glyphs). Help ([help_overlay.py](../../cleave/viz/help_overlay.py)) and modals ([modal_overlay.py](../../cleave/viz/modal_overlay.py)) are further stacks but smaller.

Do not fold the timeline strip into `RowLayout` (it is a panel anchor by design).

### Generative timeline is a second domain (~4,300 lines)

[timeline_presets/](../../cleave/timeline_presets/) is well isolated from viz. [pattern_mask_arrange.py](../../cleave/timeline_presets/pattern_mask_arrange.py) alone is ~982 lines of overlap emit, recast, and wipe constraints that must match compositor behavior. Drift between compose and [gl_masked_compositor.py](../../cleave/gl_masked_compositor.py) is a product bug, not just a tidy issue.

Keep the package boundary. The compose/compositor contract (duration, overlap, recast vs slot-set change, hard-path blend exemption) lives next to the code in [pattern_mask_arrange.py](../../cleave/timeline_presets/pattern_mask_arrange.py) and [gl_masked_compositor.py](../../cleave/gl_masked_compositor.py).

### Test coverage on panel draw

[test_controls.py](../../tests/cleave/viz/test_controls.py) and [test_row_spec.py](../../tests/cleave/viz/test_row_spec.py) cover input and the `RowSpec` registry (totality over `RowKind`, public-API callbacks). [test_tuning_panel_draw.py](../../tests/cleave/viz/test_tuning_panel_draw.py) covers present-style text/fit and asserts no `RowKind` branches remain in the draw module. Cache, overlay, and editor-mode tests import some draw helpers. Masked compositing has [test_masked_compositor_gl_integration.py](../../tests/cleave/test_masked_compositor_gl_integration.py), [test_compositor_parity.py](../../tests/cleave/test_compositor_parity.py) (soft full-coverage vs unmasked), and pattern-mask unit tests.

`LiveLayerBindings` / `RenderPostFxBindings` remain typed dataclasses of callables assembled by [live_layer_binding_factory.py](../../cleave/viz/live_layer_binding_factory.py), not a layer service.

---

## Bottom line

The architecture principles match the code. Layer creative state lives on session after bootstrap. Effects consume `LayerEffectState` and do not import viz. Config schema is a package of section modules with one persist payload; session and view defaults import those constants. Both layer compositors share one request contract, blend/opacity/HDR helpers, and an explicit wipe command. The tuning panel is descriptor-driven end to end: overlay cards are one kind set plus a card key, `TrackBlock` is a thin projection over `LayerRuntime`, draw has no per-`RowKind` branches, and each kind has one `RowSpec`. Overlay clip, font, chrome, `ComposedPanel`, and `visibility_bucket` live in [overlay_primitives.py](../../cleave/viz/overlay_primitives.py). `TuningControls` is a focus/input hub over feature controllers; `make_tuning_controls` wires a binding factory.
