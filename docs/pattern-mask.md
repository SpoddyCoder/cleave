# Pattern mask (stem territories)

High-level proposal. Aspirational; not scheduled.

Related: [roadmap.md](roadmap.md) (Pattern mask; Geometric transition wipes), [pattern-mask-transition-fragility.md](pattern-mask-transition-fragility.md), [cleave/gl_compositor.py](../cleave/gl_compositor.py), [cleave/blend_modes.py](../cleave/blend_modes.py).

---

## Intent

Give each visible layer a **spatial territory** on screen: drums in one region, vocals in another, mix as underlay or center disc, and so on. Pattern type and density shape the map; stem-driven layers supply the content.

This is not a MilkDrop3 `.milk2` clone. MD3 is a strong two-preset mashup. Cleave's difference is a typical stack of four stems plus optional full mix (up to eight layers). The feature should scale with that stack, not collapse to dual blend.

Complements existing compositing: black-key / add (and other [blend modes](../cleave/blend_modes.py)) stay **how** a layer writes; the pattern mask is **where** it may write.

---

## Mental model

- Inputs: the N currently visible layers (session order, or an explicit role mapping).
- A mask field `w_i(x, y)` per layer. At feather 0% one layer wins per pixel; at 100% weights form a soft partition (ideally summing to about 1). In-between values widen the blend zone.
- Composite still happens in the OpenGL compositor. Layer opacity, timeline level, and blend mode apply inside each layer's contribution; the mask gates or weights that contribution spatially.

Layer count is not a mask parameter. It comes from the session. Geometry knobs (density) control how the map is subdivided, then regions are assigned to layers. Region count equals visible layer count; density is a multiplier of segments per layer (1.0x = one segment per active layer).

---

## Prerequisite: shader composite path

The current compositor ([cleave/gl_compositor.py](../cleave/gl_compositor.py)) uses fixed-function GL (`glBegin(GL_QUADS)`, `glBlendFunc`). Per-pixel mask weights cannot be expressed with fixed-function blending. Pattern masking requires a shader-based composite pass that samples both the mask texture and the layer texture per pixel.

This is a partial compositor rewrite and the single biggest prerequisite. Unmasked layers can continue through the existing fixed-function path; masked layers need the shader path. The shader path should land and stabilize before any pattern generator work begins.

---

## Why not POST FX

[Render post-FX](../cleave/viz/post_fx.py) is single-buffer polish on an already-composited frame (bloom, grit, rolloff, chroma, fade). Pattern masking needs multiple layer textures at composite time. It belongs beside the layer stack: a RENDER sibling (e.g. `PATTERN MASK`) or compositor setting, not a POST FX child.

Shared mask shaders should later feed [geometric transition wipes](roadmap.md) (A-to-B preset change on one layer). Same library, different use; do not let that future reuse influence the v1 shader design.

---

## Controls

```
RENDER > PATTERN MASK
  enabled
  type: off | strips | radial | checker | plasma
  density             # multiplier: 1.0x = 1 segment/layer, 10.0x = 10/layer
  feather               # 0-100%; 0% hard territories, 100% maximum overlap
  layer order         # default: visible stack order; optional mix special-case
  invert
  seed                # persisted in YAML; respin action in panel
```

Panel placement: RENDER sibling alongside POST FX and OVERLAYS.

Seed is persisted (`render.pattern_mask.seed`) so offline render is deterministic. A respin action regenerates it.

Optional later: explicit stem-role mapping (which region family the mix owns), timeline automation of type, audio-reactive region weights from stem energy.

---

## Patterns

| Pattern | Fit for 4-5 layers |
| --- | --- |
| Strips (vertical / horizontal) | One stem per band; readable; easy density |
| Radial / rings | Mix in center (or outer frame), stems in wedges or rings |
| Checker / tiled | Cycle visible layers through tiles; density = tile count |
| Plasma / soft field | Continuous soft assignment; seedable |

Feather 0% gives clean territories. Feather 100% gives MD3-like plasma blends without locking to two sources.

---

## Product stance

- Do not aim for `.milk2` import or MD3 pattern parity.
- Do aim for **stem cartography**: spatial arrangement of stem-driven layers.
- Dual blend (N=2) is a degenerate case of the same system, not the headline.

---

## Conductor integration

The timeline preset ([cleave/timeline_presets/mode.py](../cleave/timeline_presets/mode.py)) stages `timeline.preset.mode` (`layers` or `pattern_mask`).

When `pattern_mask`, generative Apply uses [cleave/timeline_presets/pattern_mask_arrange.py](../cleave/timeline_presets/pattern_mask_arrange.py) instead of the character builders, and sets `render.pattern_mask.enabled: true`, `type: strips`, `feather_pct: 0`, and `transition: 1.0`. Density, invert, and seed stay user-tuned in the panel. Every interior song marker starts a section and forces a slot-set change at that time (add, remove, or simultaneous swap; recast does not count). Begin and crescendo collapse to one layer; the section before a crescendo stays at two or more. Sustain, standard, and diminuendo still change the set; diminuendo keeps a low-count bias that may land on one. One-layer states are allowed infrequently elsewhere. The layers-mode crescendo/accent post-passes are skipped.

Strips and radial wipe by interpolating 1D cuts so territories slide, at any feather. Arriving bands grow from a cut and departing bands shrink; feather scales tent width with each interval. Hard checker and plasma dissolve for the morph only; static frames stay hard. Soft checker and plasma stay a dissolve. Apply enables the mask and passes that 1.0s `transition` into `compose_pattern_mask_timeline` as `transition_duration` before compose runs. Add-then-remove overlap is kept only when `t_remove - t_add` is at least one wipe plus one beat; otherwise the section swaps in one step. Isolated add-only and remove-only timing is unchanged. See [pattern-mask-transition-fragility.md](pattern-mask-transition-fragility.md).

When `layers`, Apply keeps the character builders and post-passes; pattern mask is left as the user set it.

---

## Build phases

### Phase 1: shader composite and strips

Prove the architecture. One pattern, hard territories only.

1. Add a moderngl shader composite path alongside the existing fixed-function compositor. Unmasked layers continue through fixed-function; masked layers use the shader path with a 1D mask texture.
2. Strips pattern generator: vertical bands, one per visible layer. Density controls strip count (minimum = layer count). Region count equals visible layer count.
3. Hard territories only (one layer wins per pixel).
4. Panel: `RENDER > PATTERN MASK` with `enabled`, `type: strips`, `density`, `invert`. Seed not needed yet (strips are deterministic).
5. YAML schema: `render.pattern_mask` section with `enabled`, `type`, `density`, `invert`.
6. Timeline preset mode: `timeline.preset.mode` (`layers` | `pattern_mask`); Apply with `pattern_mask` uses the pattern-mask arranger and sets `enabled: true`, `type: strips`, `feather_pct: 0`, `transition: 1.0`.

### Phase 2: pattern library and feather

Expand the pattern set and add weighted compositing.

1. Radial pattern (wedges / rings; mix-in-center option).
2. Checker / tiled pattern (cycle layers through tiles).
3. Feather: mask weights form a soft partition. Weights apply as opacity modulation before the existing per-layer blend mode (not a separate color lerp), so interaction with black-key / add / multiply stays predictable. 0% is hard territories; 100% is maximum overlap.
4. Plasma / soft field pattern with persisted seed and respin.
5. Panel: `feather` (0-100%), `seed`, respin action.

### Phase 3: dynamic masks and transition wipes

Make patterns song-aware and reuse the mask library for preset transitions.

1. Per-phrase pattern variation via conductor (pattern type and density as cue properties).
2. Audio-reactive region weights from per-stem energy envelopes.
3. Explicit stem-role mapping (which region family the mix owns).
4. Shared mask shaders feed geometric transition wipes (A-to-B preset change on one layer).

---

## Resolved decisions

- **Region count = visible layer count.** Decoupling them (repeat, omit, merge when they differ) is phase 3 scope at earliest.
- **Seed is persisted in YAML.** Offline render determinism requires it; random-per-session is not acceptable.
- **Panel placement:** RENDER sibling, not a POST FX child or layer-tree subsection.
- **Feather blend interaction:** weights modulate opacity before the layer's existing blend mode. No new compositing algebra.
