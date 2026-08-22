# Pattern mask (stem territories)

Spatial territories for the multi-layer stack: where each stem-driven layer may own the frame, complementary to black-key / add.

**Status:** Done. Shader composite, four patterns, feather, conductor `pattern_mask` mode, and slot-set transition wipes are shipped. Follow-ups moved to [roadmap.md](../roadmap.md).

Related: [pattern-mask-transition-fragility.md](pattern-mask-transition-fragility.md), [roadmap.md](../roadmap.md), [cleave/gl_masked_compositor.py](../../cleave/gl_masked_compositor.py), [cleave/pattern_mask.py](../../cleave/pattern_mask.py), [cleave/blend_modes.py](../../cleave/blend_modes.py).

---

## Intent

Give each visible layer a **spatial territory** on screen: drums in one region, vocals in another, mix as underlay or center disc, and so on. Pattern type and density shape the map; stem-driven layers supply the content.

This is not a MilkDrop3 `.milk2` clone. MD3 is a strong two-preset mashup. Cleave's difference is a typical stack of four stems plus optional full mix (up to eight layers). The feature scales with that stack, not as dual blend.

Complements existing compositing: black-key / add (and other [blend modes](../../cleave/blend_modes.py)) stay **how** a layer writes; the pattern mask is **where** it may write.

---

## Mental model

- Inputs: the N currently visible layers (session order).
- A mask field `w_i(x, y)` per layer. At feather 0% one layer wins per pixel; at 100% weights form a soft partition (ideally summing to about 1). In-between values widen the blend zone.
- Composite happens in the OpenGL compositor. Layer opacity, timeline level, and blend mode apply inside each layer's contribution; the mask gates or weights that contribution spatially.

Layer count is not a mask parameter. It comes from the session. Geometry knobs (density) control how the map is subdivided, then regions are assigned to layers. Region count equals visible layer count; density is a multiplier of segments per layer (1.0x = one segment per active layer).

---

## Shipped architecture

- Shader composite path in [cleave/gl_masked_compositor.py](../../cleave/gl_masked_compositor.py) alongside the fixed-function compositor in [cleave/gl_compositor.py](../../cleave/gl_compositor.py). Unmasked layers use fixed-function; masked layers use the shader path.
- Pattern generators and upload helpers in [cleave/pattern_mask.py](../../cleave/pattern_mask.py).
- Panel: `RENDER > PATTERN MASK` sibling to POST FX and OVERLAYS ([cleave/viz/render_pattern_mask_controls.py](../../cleave/viz/render_pattern_mask_controls.py)).
- YAML: `render.pattern_mask` in [cleave/config_schema.py](../../cleave/config_schema.py).
- Frame path: [cleave/viz/layer_pipeline.py](../../cleave/viz/layer_pipeline.py).

Pattern masking belongs beside the layer stack, not under [render post-FX](../../cleave/viz/post_fx.py) (single-buffer polish on an already-composited frame).

---

## Shipped controls

```
RENDER > PATTERN MASK
  enabled
  type: strips | radial | checker | plasma
  density             # multiplier: 1.0x = 1 segment/layer, 10.0x = 10/layer
  feather             # 0-100%; 0% hard territories, 100% maximum overlap
  transition          # seconds; slot-set morph duration
  invert
  seed                # persisted in YAML; respin action in panel
```

`enabled: false` replaces a separate `type: off`. Seed is persisted (`render.pattern_mask.seed`) so offline render is deterministic.

---

## Patterns (done)

| Pattern | Fit for 4-5 layers |
| --- | --- |
| Strips (vertical / horizontal) | One stem per band; readable; easy density |
| Radial / rings | Stems in wedges or rings |
| Checker / tiled | Cycle visible layers through tiles; density = tile count |
| Plasma / soft field | Continuous soft assignment; seedable |

Feather 0% gives clean territories. Feather 100% gives MD3-like plasma blends without locking to two sources.

---

## Product stance

- Do not aim for `.milk2` import or MD3 pattern parity.
- Do aim for **stem cartography**: spatial arrangement of stem-driven layers.
- Dual blend (N=2) is a degenerate case of the same system, not the headline.

---

## Conductor integration (done)

The timeline preset ([cleave/timeline_presets/mode.py](../../cleave/timeline_presets/mode.py)) stages `timeline.preset.mode` (`layers` or `pattern_mask`).

When `pattern_mask`, generative Apply uses [cleave/timeline_presets/pattern_mask_arrange.py](../../cleave/timeline_presets/pattern_mask_arrange.py) instead of the character builders, and sets `render.pattern_mask.enabled: true`, `type: strips`, `feather_pct: 0`, and `transition: 1.0`. Density, invert, and seed stay user-tuned in the panel. Every interior song marker starts a section and forces a slot-set change at that time (add, remove, or simultaneous swap; recast does not count). Begin and crescendo collapse to one layer; the section before a crescendo stays at two or more. Sustain, standard, and diminuendo still change the set; diminuendo keeps a low-count bias that may land on one. One-layer states are allowed infrequently elsewhere. The layers-mode crescendo/accent post-passes are skipped.

Strips and radial wipe by interpolating 1D cuts so territories slide, at any feather. Arriving bands grow from a cut and departing bands shrink; feather scales tent width with each interval. Hard checker and plasma dissolve for the morph only; static frames stay hard. Soft checker and plasma stay a dissolve. Apply enables the mask and passes `transition` into `compose_pattern_mask_timeline` as `transition_duration` before compose runs. Add-then-remove overlap is kept only when `t_remove - t_add` is at least one wipe plus one beat; otherwise the section swaps in one step. Isolated add-only and remove-only timing is unchanged. See [pattern-mask-transition-fragility.md](pattern-mask-transition-fragility.md).

When `layers`, Apply keeps the character builders and post-passes; pattern mask is left as the user set it.

---

## Build phases

### Phase 1: shader composite and strips (done)

1. Moderngl shader composite path alongside fixed-function compositor.
2. Strips pattern generator: vertical bands, one per visible layer; density controls strip count (minimum = layer count).
3. Hard territories (one layer wins per pixel).
4. Panel: `RENDER > PATTERN MASK` with `enabled`, `type: strips`, `density`, `invert`.
5. YAML schema: `render.pattern_mask` with `enabled`, `type`, `density`, `invert`.
6. Timeline preset mode `pattern_mask`; Apply uses the pattern-mask arranger and sets `enabled: true`, `type: strips`, `feather_pct: 0`, `transition: 1.0`.

### Phase 2: pattern library and feather (done)

1. Radial pattern (wedges / rings).
2. Checker / tiled pattern (cycle layers through tiles).
3. Feather: mask weights form a soft partition; weights modulate opacity before the existing per-layer blend mode.
4. Plasma / soft field pattern with persisted seed and respin.
5. Panel: `feather` (0-100%), `seed`, respin action, `transition`.

### Phase 3: dynamic masks and preset wipes

Moved to [roadmap.md](../roadmap.md) (pattern mask follow-ups and geometric transition wipes).

---

## Resolved decisions

- **Region count = visible layer count.** Decoupling them (repeat, omit, merge when they differ) is follow-up scope.
- **Seed is persisted in YAML.** Offline render determinism requires it; random-per-session is not acceptable.
- **Panel placement:** RENDER sibling, not a POST FX child or layer-tree subsection.
- **Feather blend interaction:** weights modulate opacity before the layer's existing blend mode. No new compositing algebra.
