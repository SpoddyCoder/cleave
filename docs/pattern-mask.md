# Pattern mask (stem territories)

High-level proposal. Aspirational; not scheduled.

Related: [roadmap.md](roadmap.md) (Pattern mask; Geometric transition wipes), [cleave/gl_compositor.py](../cleave/gl_compositor.py), [cleave/blend_modes.py](../cleave/blend_modes.py).

---

## Intent

Give each visible layer a **spatial territory** on screen: drums in one region, vocals in another, mix as underlay or center disc, and so on. Pattern type and density shape the map; stem-driven layers supply the content.

This is not a MilkDrop3 `.milk2` clone. MD3 is a strong two-preset mashup. Cleave's difference is a typical stack of four stems plus optional full mix (up to eight layers). The feature should scale with that stack, not collapse to dual blend.

Complements existing compositing: black-key / add (and other [blend modes](../cleave/blend_modes.py)) stay **how** a layer writes; the pattern mask is **where** it may write.

---

## Mental model

- Inputs: the N currently visible layers (session order, or an explicit role mapping).
- A mask field `w_i(x, y)` per layer. In hard mode one layer wins per pixel; in soft mode weights form a soft partition (ideally summing to about 1).
- Composite still happens in the OpenGL compositor. Layer opacity, timeline level, and blend mode apply inside each layer's contribution; the mask gates or weights that contribution spatially.

Layer count is not a mask parameter. It comes from the session. Geometry knobs (density) control how the map is subdivided, then regions are assigned to layers. Region count equals visible layer count; density controls the geometry within that constraint (strip width, feathering).

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
  density             # geometry (e.g. strip count, checker tiles), not layer count
  mode: hard | soft
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

Hard mode gives clean "territories." Soft mode gives MD3-like plasma blends without locking to two sources.

---

## Product stance

- Do not aim for `.milk2` import or MD3 pattern parity.
- Do aim for **stem cartography**: spatial arrangement of stem-driven layers.
- Dual blend (N=2) is a degenerate case of the same system, not the headline.

---

## Conductor integration

The stem conductor ([cleave/timeline_presets/conductor.py](../cleave/timeline_presets/conductor.py)) gains a boolean toggle: `timeline.preset.pattern_mask` (like the existing `timeline.preset.conductor`). When on, generative Apply sets `render.pattern_mask.enabled: true` with a sensible default type (strips). The conductor does not pick pattern type or density; the user tunes those in the panel if desired.

v1: static for the song. The conductor turns pattern mask on globally; pattern params stay fixed across phrases. Per-phrase pattern variation (e.g. strips in a verse, radial in a chorus) is appealing but adds significant complexity; defer until the static version is validated.

---

## Build phases

### Phase 1: shader composite and strips

Prove the architecture. One pattern, hard mode only.

1. Add a moderngl shader composite path alongside the existing fixed-function compositor. Unmasked layers continue through fixed-function; masked layers use the shader path with a 1D mask texture.
2. Strips pattern generator: vertical bands, one per visible layer. Density controls strip count (minimum = layer count). Region count equals visible layer count.
3. Hard mode only (one layer wins per pixel).
4. Panel: `RENDER > PATTERN MASK` with `enabled`, `type: strips`, `density`, `invert`. Seed not needed yet (strips are deterministic).
5. YAML schema: `render.pattern_mask` section with `enabled`, `type`, `density`, `invert`.
6. Conductor toggle: `timeline.preset.pattern_mask` boolean; Apply sets `enabled: true`, `type: strips`.

### Phase 2: pattern library and soft mode

Expand the pattern set and add weighted compositing.

1. Radial pattern (wedges / rings; mix-in-center option).
2. Checker / tiled pattern (cycle layers through tiles).
3. Soft mode: mask weights form a soft partition. Weights apply as opacity modulation before the existing per-layer blend mode (not a separate color lerp), so interaction with black-key / add / multiply stays predictable.
4. Plasma / soft field pattern with persisted seed and respin.
5. Panel: `mode: hard | soft`, `seed`, respin action.

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
- **Soft mode blend interaction:** weights modulate opacity before the layer's existing blend mode. No new compositing algebra.
