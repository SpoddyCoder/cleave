# Pattern mask transition fragility

**Currently suspected, not confirmed.** Capture for a second-pass analysis. Do not treat this as a fix plan.

Related: [pattern-mask.md](pattern-mask.md), [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py), [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py).

---

## Symptom

With timeline preset mode `pattern_mask`, visual transitions look broken after generative Apply. Layers mode was not touched and is believed fine.

Suspected triggers in the pattern-mask arranger: recast cues (mid-section off-then-on on held slots) and shorter sections (biased 1-2 bars, `SECTION_SEC_MIN = 2.0`). Apply also sets `render.pattern_mask.transition` to 1.0s with feather 0%.

## Suspected problem

The pattern mask pipeline has three layers that do not share a contract about transition timing.

1. The arranger in [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) emits timestamped slot-set changes. It knows beat periods. It has no knowledge of compositor `transition_duration`.
2. Layer visibility evaluates timeline lane level each frame and sets `fbo.enabled` in [cleave/viz/layer_visibility.py](../cleave/viz/layer_visibility.py). That converts cues into per-frame booleans.
3. `GlMaskedCompositor` in [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py) discovers slot-set changes **reactively** by comparing `active_slots != self._last_active_slots` in `_ensure_mask_textures`. On a diff it starts a new spatial transition. If one is already in progress, it snapshots the mid-blend as the new "old" via `_blended_transition_weights` and restarts.

### Recast

A held slot is turned off at mid-section then on again about two beats later (`t_on = mid + 2 * beat_period`). With feather 0% and transition 1.0s:

- At off: compositor starts a 1.0s wipe toward the slot-absent mask.
- At on (about 0.5-1.0s later): compositor interrupts, restarts toward slot-present again.
- `keep_disabled_visible` copies the departing layer FBO during the wipe. If the app loop stops rendering disabled layers, that FBO can be stale.
- Two changes inside one transition window means the compositor never settles to a static mask.

### Shorter sections

Sections biased to 1-2 bars with `SECTION_SEC_MIN = 2.0` can pack add/remove overlap states closer together than 1.0s. That may independently interrupt transitions even without recast.

## Architectural root (suspected)

- No transition-awareness in the arranger: it does not receive `transition_duration` and cannot enforce min gaps.
- Reactive compositor with no rate limit, debounce, or settle time.
- No integration test of the temporal pipeline. Arranger tests check slot-sets ([tests/cleave/test_pattern_mask_arrange.py](../tests/cleave/test_pattern_mask_arrange.py)); compositor tests check GPU ([tests/cleave/test_masked_compositor_gl_integration.py](../tests/cleave/test_masked_compositor_gl_integration.py)). Nobody simulates a sequence of rapid `active_slots` changes over time.
- `keep_disabled_visible` assumes infrequent transitions.

## Possible directions

For the second pass to evaluate, not implement:

- **Option A:** pass `transition_duration` into the arranger and enforce min gaps; only recast when the section is long enough.
- **Option B:** declarative `TransitionEvent` objects so the compositor does not diff `active_slots` each frame; recast could be a different kind (preset swap without spatial wipe).

Confirm which of these (or something else) actually causes the visual breakage, and whether the compositor abstractions themselves need a refactor vs a tighter arranger contract.

## Key code

- Recast emit: [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) (around the `_pick_recasts` / `t_on = mid + 2 * beat_period` block).
- Reactive transition start: `_ensure_mask_textures` in [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py) (`slots_changed` plus `_blended_transition_weights` restart).
- Per-frame `active_slots` from `fbo.enabled`: `LayerPipeline.composite` in [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py).
- Apply enabling the mask: `_enable_pattern_mask` in [cleave/viz/timeline_preset_controls.py](../cleave/viz/timeline_preset_controls.py) (`transition = 1.0`).
- Mid-wipe FBO copy: `_copy_layers_into_array(..., keep_disabled_visible=transitioning)`.

## Second pass

Answer these before changing code:

1. Does the in-progress restart (`_blended_transition_weights` as the new old mask) cause the visual bug, or is it a red herring?
2. Does recast dominate, or do shorter-section overlap states suffice on their own?
3. Is FBO staleness under `keep_disabled_visible` involved (disabled layers not redrawn, copied as last frame)?
4. Is a compositor refactor warranted (Option B), or is a tighter arranger contract enough (Option A)?
