# Pattern mask transition fragility

Resolution of the Apply hard-path wipe. Related: [pattern-mask.md](pattern-mask.md), [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py), [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py), [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py).

---

## Symptom

With timeline preset mode `pattern_mask`, generative Apply sets `render.pattern_mask.enabled`, `type: strips`, `feather_pct: 0`, and `transition: 1.0`. A one-hot mix then `argmax` froze disputed pixels until `t = 0.5`, then flipped them together. Departing stems were last-FBO stills. Add-then-remove at 120 BPM was often only 1.0s, so the overlap set never held.

## Contract

Hard strips and radial (feather 0%): store old and target [HardLayout1D](../cleave/pattern_mask.py) layouts, lerp cuts each frame, rasterize at content resolution, upload the R8 mask, and draw the hard composite shader. Territories slide. Mid-transition retarget snapshots the current lerped layout as the new old.

Hard checker and plasma (feather 0%): no 1D cuts. During the morph only, the soft transition shader dissolves; static frames stay hard.

Soft (`feather` above 0%): dissolve via the existing weight-field path.

[GlMaskedCompositor.live_slots](../cleave/gl_masked_compositor.py) is called before the layer render loop. A slot stays live while it is active or still has morph width (hard 1D interval) or weight-field mass (checker/plasma/soft). [LayerFramePipeline.render_frame](../cleave/viz/layer_pipeline.py) feeds PCM and renders those slots even when timeline `enabled` is false. `keep_disabled_visible` is a last-frame fallback.

[compose_pattern_mask_timeline](../cleave/timeline_presets/pattern_mask_arrange.py) takes `transition_duration`. Apply enables the mask (`transition = 1.0`) first, then passes that duration in. For add-then-remove, `t_remove - t_add` must be at least `transition_duration` plus one beat; if the section cannot fit that, the existing simultaneous-swap fallback runs. Isolated add-only and remove-only gaps are unchanged. Pattern-mask compose may emit `SlotCue.recast` on a continuing slot; that is a preset switch, not a mask wipe or slot-set change.

The compositor still starts a wipe from an `active_slots` diff in `_ensure_mask_textures`. There is no `TransitionEvent` type.

## Remaining polish

Weight-field transitions (soft, and checker/plasma hard morphs) still generate at 1/4 content resolution (`_TRANSITION_GEN_DIVISOR`). After settle, the static full-res mask can sharpen edges. Whether that gen should follow preview quality is an architecture note in [todos.md](todos.md); this file does not track that work.

## Key code

- Apply: `_enable_pattern_mask` then `compose_pattern_mask_timeline(..., transition_duration=...)` in [cleave/viz/timeline_preset_controls.py](../cleave/viz/timeline_preset_controls.py).
- Overlap emit: `_overlap_states` in [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py).
- Recast emit: mid-section `SlotCue.recast` upsert in [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py).
- Hard 1D wipe: `hard_layout_1d` / `lerp_hard_layout_1d` / `rasterize_hard_layout_1d` in [cleave/pattern_mask.py](../cleave/pattern_mask.py); compositor stores layouts and uploads R8 each frame.
- Live departing layers: `live_slots` on [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py); render/PCM in [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py).
- Reactive start / retarget: `_ensure_mask_textures` in [cleave/gl_masked_compositor.py](../cleave/gl_masked_compositor.py).
