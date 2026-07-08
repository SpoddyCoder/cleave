# Architecture review

Pragmatic assessment of the Cleave codebase from a Python software architecture perspective. Focus is on high-value refactors, not perfection.

Related: [architecture principles](../.cursor/rules/architecture-principles.mdc), [todos.md](todos.md).

---

## Context

The codebase has been through a deliberate refactor. The current direction is sound:

- Typed runtimes (`VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`, `RenderVisualizerRuntime`) in [cleave/viz/app.py](../cleave/viz/app.py)
- Descriptor-driven config parse, dump, and persist in [cleave/config_schema.py](../cleave/config_schema.py)
- Computed dirty tracking via `persisted_session_signature` in [cleave/config_snapshot.py](../cleave/config_snapshot.py)
- Registry-based effect dispatch in [cleave/effects/handlers.py](../cleave/effects/handlers.py)
- Shared live/offline frame finish in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)
- Panel field manifest (`RowFieldDef`) in [cleave/viz/row_fields.py](../cleave/viz/row_fields.py)

What remains is complexity debt in a few hotspots that will keep costing effort on every new panel row, effect, or render setting.

---

## 1. Flaws to address (long-term brittleness)

These will lead to silent bugs, divergent behavior, or escalating change cost if left unaddressed.

### Dual authority: `CleaveConfig` vs `TuningSession`

Live edits mutate `session.layers`, `session.render_overlay`, and related runtime objects. `cfg` is only partially updated during play (for example `editor.render_mode` via `replace`, layer add/remove in [cleave/viz/wiring.py](../cleave/viz/wiring.py)). Most layer fields (opacity, stem, preset switching, effects) live only in session until save, when [persist_layers](../cleave/config_schema.py) merges session back into YAML.

This works today because persistence is careful, but it is a convention, not enforced by types. Any new code that reads `cfg.layers[slot].opacity` instead of `session.layers[slot].opacity_pct` will silently use stale data. The `FieldSource` (`cfg` / `session` / `both`) model in field descriptors helps at save time but does not protect runtime readers.

**Recommended direction:** make session the single live authority; treat `cfg` as bootstrap plus immutable structural fields (paths), or sync both on every mutation.

### Layer resolution model (simplified)

Done: offline render uses full `render.width` x `render.height` per layer by default; live preview and `--viz-quality` offline renders scale layers via `editor.preview_quality` only. Per-layer width/height removed from config.

Three concepts used to interact:

1. Per-layer `width` / `height` in config (removed)
2. `editor.preview_quality` preview downscaling ([cleave/viz/layer_preview_resolution.py](../cleave/viz/layer_preview_resolution.py))
3. Offline render output size ([cleave/viz/render.py](../cleave/viz/render.py))

**Remaining risk:** live/offline divergence if preview quality changes are not reflected in offline `--viz-quality` path; default offline path is full resolution per layer.

### Snapshot write has a parallel persist path

`persisted_session_payload` is the intended single source for persisted state, but [config_snapshot._snapshot_render_overlay](../cleave/config_snapshot.py) hand-merges render overlay and post-fx into the original YAML dict, partially bypassing the descriptor dump path. Two persist strategies means new render fields can be added to descriptors but forgotten in the snapshot merger, or vice versa.

**Recommended direction:** route snapshot writes entirely through descriptor dump, preserving only `paths` and cosmetic YAML ordering from the original file.

### Domain layering inversion: effects depend on viz

[cleave/effects/runtime.py](../cleave/effects/runtime.py) imports `TuningSession` from [cleave/viz/session.py](../cleave/viz/session.py). Core effect logic is coupled to the editor session model. Adding effects from CLI, batch tools, or tests without the full viz stack gets harder; the dependency arrow points the wrong way.

**Recommended direction:** extract a small neutral type (for example `LayerEffectState`) in a non-viz module that both session and effects use.

### Panel manifest migration is incomplete on the draw side

Input is largely descriptor-driven (`ROW_FIELDS`, [row_sections](../cleave/viz/row_sections.py), `apply_field_horizontal`). Drawing is not: [tuning_panel_draw.py](../cleave/viz/tuning_panel_draw.py) (~2,100 lines) still branches on `RowKind` for icons, transport, visibility eyes, disabled states, and special row chrome. New rows require coordinated edits across `row_semantics`, `row_fields`, `row_sections`, `view_state_structure_signature`, and draw special cases.

The architecture rules say not to add per-`RowKind` branches in draw or controls; residual branches are the main leak point.

---

## 2. Weaknesses worth addressing (maintainability)

These will make the codebase easier to work in but are lower risk than the flaws above.

### `config_schema.py` monolith (~1,900 lines)

The module holds defaults, parse, dump, persist, display helpers, and section descriptors for editor, layers, render, and timeline. It is the right abstraction, but at this size it is hard to review, easy to break cross-section, and uses lazy imports back to [cleave/config.py](../cleave/config.py) to avoid cycles.

**Pragmatic split:** `config_schema/editor.py`, `layers.py`, `render.py`, `timeline.py` with a thin re-export, or keep one module but extract section descriptor tables.

### Four parallel UI registries

| Module | Role | ~Lines |
| --- | --- | --- |
| [row_semantics.py](../cleave/viz/row_semantics.py) | `RowKind` enum, affordances, help, lock rules | 840 |
| [row_fields.py](../cleave/viz/row_fields.py) | Labels, formatters, mutations | 1,400 |
| [row_sections.py](../cleave/viz/row_sections.py) | Tree composition, conditionals | 850 |
| [tuning_view_state.py](../cleave/viz/tuning_view_state.py) | Session to `TrackBlock` projection | 575 |

Adding a panel row touches three to four files plus structure-signature tests. `TrackBlock` largely mirrors `LayerRuntime` field-for-field.

**Pragmatic wins:** co-locate semantics and field def per row (or generate from one table); reduce `TrackBlock` to thin views over session where possible.

### `controls.py` and `wiring.py` remain integration hubs

[TuningControls](../cleave/viz/controls.py) (~950 lines) still owns preset browsing, user-preset file I/O, layer add/delete, move mode, solo, and dozens of `_set_*` callbacks that `row_fields` delegates to. [wiring.py](../cleave/viz/wiring.py) (~490 lines) is a factory wiring many subsystems with inline closures.

The split into `settings_controls`, `render_overlay_controls`, and similar modules helped, but coordinator classes are still where new features land by default.

**Pragmatic wins:** move preset-browser and user-preset flows into dedicated controllers; shrink `make_tuning_controls` to wiring only, not business logic.

### `timeline_overlay.py` is a second UI stack (~1,100 lines)

[timeline_overlay.py](../cleave/viz/timeline_overlay.py) reimplements panel drawing, caching, upload planning, and input semantics parallel to the main tuning panel, with cross-imports from `tuning_panel_draw` for shared glyphs. Timeline features will continue to diverge from main-panel patterns.

**Pragmatic wins:** extract shared overlay primitives (icon render, clip, upload cache interface) into a small module both panels use.

### GL pipeline concentration

[gl_compositor.py](../cleave/gl_compositor.py) (~1,080 lines) and [gl_post_process.py](../cleave/gl_post_process.py) (~800 lines) hold most GPU logic. Unit tests exist but are integration-heavy; Python-side orchestration in [layer_pipeline.py](../cleave/viz/layer_pipeline.py) and [post_fx.py](../cleave/viz/post_fx.py) bridges GL, session, and effects.

Not urgent unless adding many new GPU effects, but refactors there are high-risk without keeping [frame_finish](../cleave/viz/frame_finish.py) as the single composition choke point (which the codebase already does well).

### Test gaps on the largest draw file

[test_controls.py](../tests/cleave/viz/test_controls.py) and [test_row_fields.py](../tests/cleave/viz/test_row_fields.py) cover input well. There is no `test_tuning_panel_draw.py`; draw regressions are caught only indirectly via overlay and cache tests. Given draw special-casing, this is a gap.

---

## 3. Suggested priority

| Priority | Item | Why |
| --- | --- | --- |
| **P0** | Session as single live authority (or strict sync) | Prevents silent stale-config bugs as features grow |
| **P1** | Unify snapshot persist through descriptors | Stops render/overlay field drift on save |
| **P1** | Finish draw-side descriptor migration (or extract `PresentStyle` renderers) | Cuts multi-file tax per new row |
| **P2** | Decouple effects from `viz.session` | Unblocks reuse and cleaner module boundaries |
| **P2** | Split `config_schema` by domain | Low risk, improves reviewability |
| **P3** | Shared overlay primitives for timeline and tuning panel | Pays off when timeline grows |
| **P3** | Direct draw tests for `tuning_panel_draw` | Cheap insurance on the largest untested draw module |

---

## 4. Bottom line

The architecture principles in the cursor rules match what the code is aiming for. The highest-risk debt is not messy code but **multiple sources of truth** (cfg/session, dual persist paths) and **incomplete descriptor coverage on the draw path**. Fixing those two areas gives the best return before polishing module sizes or GL structure.
