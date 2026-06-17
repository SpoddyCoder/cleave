# Architecture refactor plan

A three phase plan to pay down architectural debt in the visualizer and CLI after
a period of fast feature layering. The goal is to put Cleave in good shape for
adding more features without growing brittleness.

Each phase below is scoped enough for another agent to write a low level plan and
implement it. Phases are ordered by risk and dependency: Phase 1 is low risk and
unblocks the rest, Phase 2 restructures the largest objects, Phase 3 unifies the
remaining duplicated systems.

## Guiding rules

- No backward compatibility. Rename and remove superseded code in the same change
  (see [.cursor/rules/no-backward-compatibility.mdc](.cursor/rules/no-backward-compatibility.mdc)).
- Behavior preserving. These phases are refactors. The live visualizer, offline
  render, and config save/load must behave identically before and after, except
  where a task explicitly fixes a bug.
- Verify each task with the unit suite:
  `/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py`.
- Do not launch the live visualizer for routine verification; it needs display and
  OpenGL. Use unit tests, and ask a human for a manual smoke test when GL behavior
  changes.
- Keep one logical change per commit so phases stay reviewable.

## Background: what is wrong today

- [cleave/viz/controls.py](cleave/viz/controls.py) `TuningControls` is a god object
  (~1100 lines) owning input, focus navigation, ~30 mutation setters, save and quit
  orchestration, modal dialogs, and view state projection.
- Config dirty tracking: fixed in Phase 1 via snapshot signature compare in
  [cleave/config_snapshot.py](cleave/config_snapshot.py).
- [cleave/viz/app.py](cleave/viz/app.py) `VisualizerRuntime` is a 32 field bag with
  most fields `Optional` and filled across several init phases, guarded by
  `assert ... is not None` rather than types.
- [cleave/viz/layer.py](cleave/viz/layer.py) mixes four concerns and exposes 12
  leading underscore functions that [cleave/viz/app.py](cleave/viz/app.py) imports
  directly, a sign of a missing class.
- Config schema is hand maintained twice: load in [cleave/config.py](cleave/config.py)
  and save in [cleave/config_snapshot.py](cleave/config_snapshot.py), with defaults
  triplicated across those files and [cleave/viz/controls.py](cleave/viz/controls.py).
- The effects runtime in [cleave/effects/runtime.py](cleave/effects/runtime.py)
  repeats near identical per effect blocks instead of dispatching through the
  registry.

---

## Phase 1: Correctness and cleanup (low risk, complete)

Goal: fix the latent save bugs, make dirty tracking impossible to forget, and
delete dead code. This phase changes behavior only where it fixes a real bug, and
gives later phases a clean base.

**Status:** Complete. Dirty tracking uses `persisted_session_signature()` (Option A).
`warmup_sec` round-trips on snapshot. Tests: [tests/cleave/viz/test_config_dirty.py](tests/cleave/viz/test_config_dirty.py),
`test_session_snapshot_full_round_trip` in [tests/cleave/test_config_snapshot.py](tests/cleave/test_config_snapshot.py).

### Task 1.1: Remove dead and vestigial code (done)

Confirm each item has no live caller (search the whole repo and tests), then remove
it and any now unused imports.

- `_init_gl_resources` in [cleave/viz/app.py](cleave/viz/app.py): defined, never
  called (`run()` calls the cheap and heavy steps separately).
- `on_z_order_change=lambda _order: None` no op hook in
  [cleave/viz/wiring.py](cleave/viz/wiring.py); z order is already applied live via
  `session.layer_z_order` in the compositor. Remove the parameter and its plumbing
  through `TuningControls` if nothing else uses it.
- `write_layer_presets()` in [cleave/preset_playlist.py](cleave/preset_playlist.py):
  no callers.
- `RENDER_TIMELINE_SUB_ROW_KINDS` in
  [cleave/viz/row_semantics.py](cleave/viz/row_semantics.py): built from a
  `parent_group` no row uses; its only consumer
  (`_refocus_render_timeline_header_if_sub_row`) never triggers. Remove both.
- `timeline_cues_for_eval`: confirm it is referenced only by tests. If so, either
  inline it into the test or keep it but document it as test only.

Acceptance: unit suite passes; no references remain; nothing imported but unused.

### Task 1.2: Audit and fix per setter dirty tracking (done)

Short term fix before the systemic fix in 1.3.

- Audit every mutation setter in [cleave/viz/controls.py](cleave/viz/controls.py)
  that writes a persisted session field and confirm it calls `mark_config_dirty()`.
  Known miss: `_set_render_overlay_display_time` (writes
  `session.render_overlay.display_time` without marking dirty).
- Cross check against [cleave/config_snapshot.py](cleave/config_snapshot.py): every
  field written by the snapshot must have a setter that marks dirty. Fields that are
  session only and never persisted (solo flags, expand flags, timeline
  `panel_open`, recording and override state) must not mark dirty.

Acceptance: add a unit test that, for each persisted field, mutating it sets
`config_dirty` true, and mutating a known session only field does not.

### Task 1.3: Centralize dirty tracking so it cannot be forgotten (done)

Replace manual `mark_config_dirty()` calls with a single mechanism.

Recommended approach (the implementing agent should evaluate both and pick one in
the low level plan):

- Option A, snapshot compare: compute a stable signature (for example a normalized
  dict or hash) of the persisted subset of `TuningSession` at load and after each
  save. `config_dirty` becomes a computed comparison against the last saved
  signature. This removes all manual marking and is robust to new fields, as long
  as new persisted fields are included in the signature (ideally derived from the
  same source as the snapshot writer, which Phase 3 unifies).
- Option B, mutation choke point: route persisted mutations through a small wrapper
  on the session (or a `dirty` observer) that sets the flag, so individual setters
  cannot bypass it.

Acceptance: deleting an arbitrary `mark_config_dirty()` call no longer hides a save;
the dirty asterisk and the unsaved quit dialog behave as before; unit tests cover a
representative edit then quit flow.

### Task 1.4: Close known load and save gaps (done)

- `warmup_sec` is loaded in [cleave/config.py](cleave/config.py) but not written by
  `write_session_snapshot()`. Decide whether it is user tunable; if yes, write it;
  if no, document that it is template only and not round tripped.
- Reconcile default mismatches noted in the review (for example
  `DEFAULT_RENDER_POST_FX_FADE_IN` in [cleave/config.py](cleave/config.py) versus
  the template value in [cleave-viz.yaml](cleave-viz.yaml)). Pick one source of
  truth (the constant), and make the template match or be generated.

Acceptance: a load then save round trip preserves all user tunable fields; a test
asserts round trip stability for a fully populated config.

Phase 1 exit criteria: unit suite green, no dead code from the list above, dirty
tracking centralized, and a documented config round trip test in place.

---

## Phase 2: Structural decomposition (medium to high risk)

Goal: break up the two largest structures so adding a feature touches fewer places
and readiness is enforced by types rather than asserts. Do Phase 1 first.

### Task 2.1: Split `TuningControls`

[cleave/viz/controls.py](cleave/viz/controls.py) `TuningControls` should shrink to a
focus and input coordinator. Extract cohesive responsibilities into collaborators
that it owns and delegates to. Suggested seams (the agent should validate against
the code before finalizing):

- Save and quit controller: `try_quit`, `_prompt_save`, `_trigger_save_new`,
  `_quit_save`, `_quit_discard`, `_finish_quit_after_save`, `_prompt_overwrite`, the
  three modal dialog instances, and dirty state. This is the unit that the recent
  quit confirm work touched; isolating it is the main win.
- Per feature setter groups: render overlay setters, render post fx setters, and
  timeline enable and panel lifecycle each move to their own small object or module,
  keeping the `_apply_horizontal` dispatch in `TuningControls` but delegating the
  body.
- View state projection: `build_view_state` and its helpers can become a separate
  builder that reads session plus the controls UI state.

Constraints:

- Keep the public surface that [cleave/viz/app.py](cleave/viz/app.py) and
  [cleave/viz/input_dispatch.py](cleave/viz/input_dispatch.py) call stable, or update
  all call sites in the same change.
- The session data classes (`TuningSession`, `LayerRuntime`, `TimelineRuntime`,
  `RenderOverlayRuntime`, `RenderPostFxRuntime`) currently live in
  [cleave/viz/controls.py](cleave/viz/controls.py). Move them to a dedicated module
  (for example `cleave/viz/session.py`) so model and controller are separated.

Acceptance: `TuningControls` is materially smaller; each extracted object has a
single responsibility; unit suite passes; the keyboard dispatch behavior described
in [.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc) is unchanged.

### Task 2.2: Replace the `VisualizerRuntime` bag

[cleave/viz/app.py](cleave/viz/app.py) `VisualizerRuntime` has 32 fields filled
across `build_runtime_full`, `_init_gl_resources_cheap`, `_init_gl_resources_heavy`,
and `_init_gl_resources_render`, then guarded by asserts.

Recommended approach: split into a small always present core and the phase or mode
specific groups, or use a staged builder that returns a fully initialized object per
mode.

- `build_live()` returns an object where live only fields (controls, mix player,
  playback, overlays) are non optional.
- `build_render()` returns an object for the offline path where those fields are
  absent by type, not by `None`.
- Remove the `assert rt.x is not None` guards in `tick_frame` once types guarantee
  presence. `tick_frame(draw_overlay=...)` may split into a shared core plus a live
  only finisher (see Task 3.3).

Acceptance: no `Optional` field that is always set in practice remains optional; the
asserts in `tick_frame` are gone or justified; live and render paths both construct
through the new entry points; unit suite passes.

### Task 2.3: Turn `layer.py` helpers into classes

[cleave/viz/layer.py](cleave/viz/layer.py) exposes 12 leading underscore functions
that [cleave/viz/app.py](cleave/viz/app.py) imports. Group them into classes and make
the public API explicit (no cross module underscore imports).

Suggested grouping (validate before finalizing):

- Frame pipeline: `_build_layers`, `_render_layer_fbo`, `_apply_layer_bloom`,
  `_apply_layer_grit`, `_composite_ordered`, `_flush_all_pcm`, `_warmup_layers`,
  `_destroy_layers`.
- Timeline visibility: the visibility algebra (`apply_layer_visibility`,
  `effective_layer_enabled`, and the timeline view state builder).
- Config bootstrap: `_session_from_cfg` and the `_render_*_runtime_from_cfg`
  helpers. Consider moving these next to the session module from Task 2.1 or the
  config layer, since they are config to session mapping, not GL.
- Overlay GL upload: `_draw_tuning_overlay`, `_draw_timeline_overlay`.

Keep `StemLayer` a thin data class.

Acceptance: [cleave/viz/app.py](cleave/viz/app.py) imports only public names; each
new class has a clear responsibility; unit suite passes.

Phase 2 exit criteria: `TuningControls`, `VisualizerRuntime`, and `layer.py` no
longer concentrate unrelated responsibilities; no behavior change; suite green.

---

## Phase 3: Unify duplicated systems (medium to high risk)

Goal: remove the parallel maintenance burdens so a new config key, effect, or render
tweak changes one place instead of many. Builds on Phases 1 and 2.

### Task 3.1: Single config schema for load, save, and defaults

Today load lives in [cleave/config.py](cleave/config.py) (`_parse_*`), save in
[cleave/config_snapshot.py](cleave/config_snapshot.py), and defaults are triplicated
across those files and [cleave/viz/controls.py](cleave/viz/controls.py).

Define one source of truth that drives parse, serialize, and default. Options for
the agent to weigh: per field descriptors with name, default, parse, and dump; or a
typed (de)serializer over the existing frozen dataclasses. Requirements:

- Preserve the snapshot behavior of merging unknown keys in `paths` and `render`
  with the original file.
- Preserve British spelling keys (`colour`, `font-colour`) and the kebab versus
  snake conventions already in the YAML, or migrate them deliberately as a clean
  break and update the template.
- After unification, the Phase 1.3 dirty signature should derive from this schema so
  new persisted fields are covered automatically.

Acceptance: adding a new persisted field requires editing one schema location plus
its UI; a round trip test (load, mutate, save, reload) proves stability; defaults
exist in exactly one place.

### Task 3.2: Registry driven effect dispatch

[cleave/effects/runtime.py](cleave/effects/runtime.py) `EffectRuntime.update()` and
`.modifiers()` repeat near identical loops per effect (`pulse`, `flash`, `flare`,
`hue`, `grit`). Drive them from [cleave/effects/registry.py](cleave/effects/registry.py)
so adding an effect means adding a registry entry plus one effect module, not editing
dispatch blocks.

- Give each effect module a uniform interface (for example an envelope or apply
  callable) that the runtime can call generically.
- Keep the registry as the single roster of valid `(stem, effect, driver)` tuples.

Acceptance: the per effect branches in the runtime collapse to a generic loop; a new
effect can be added without touching `runtime.py` dispatch logic; existing visual
output is unchanged (verify with any effect unit tests; ask for a manual smoke test
if needed).

### Task 3.3: Unify the live and offline finish frame paths

Live `tick_frame` (`draw_overlay=True`) and the loop in
[cleave/viz/render.py](cleave/viz/render.py) diverge on fade, render overlay, and
present. They also differ on defaults: when `cfg.render` is absent, live falls back
to a default overlay config while offline renders no overlay.

- Extract a shared finisher that applies post fx fade, composites the render overlay,
  and presents, parameterized by whether the tuning UI is drawn and whether session
  overrides apply (live) or frozen config applies (offline).
- Decide and document the intended behavior when `cfg.render` is absent so live and
  offline agree, or are intentionally different for a stated reason.

Acceptance: the fade and overlay logic exists once; live and offline call it with
explicit parameters; a test or documented manual check confirms a short render still
matches the live look.

Phase 3 exit criteria: config, effects, and the render finish path each have a single
implementation; adding a config key, an effect, or a render tweak touches one place;
suite green.

---

## Sequencing and effort

| Phase | Theme | Risk | Rough effort | Status |
| --- | --- | --- | --- | --- |
| 1 | Correctness and cleanup | Low | Low | Complete |
| 2 | Structural decomposition | Medium to high | Medium to high | |
| 3 | Unify duplicated systems | Medium to high | Medium to high | |

Do the phases in order. Phase 1 is complete and safe to ship on its own.
Phase 2 depends on Phase 1 (centralized dirty tracking and the session module move).
Phase 3 depends on Phase 2 (the session module and split runtime simplify the schema
and render unification work).

## Definition of done for the whole refactor

- A new feature that adds a tunable config key touches roughly one schema location,
  one setter or sub controller, and the UI row, instead of 6 to 8 files.
- Dirty tracking cannot be silently bypassed by a new setter.
- No god object, no partially initialized runtime guarded by asserts, no cross module
  underscore imports.
- Live and offline render share their frame finishing logic.
- The unit suite passes and the live visualizer is smoke tested by a human after the
  GL touching phases.
