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

- [cleave/viz/controls.py](cleave/viz/controls.py) `TuningControls` is still large
  (~800 lines) but Phase 2 split save/quit, render setters, and view state into
  collaborators; it now focuses on focus and input dispatch.
- Config dirty tracking: fixed in Phase 1 via snapshot signature compare in
  [cleave/config_snapshot.py](cleave/config_snapshot.py).
- [cleave/viz/app.py](cleave/viz/app.py) `VisualizerRuntime` bag: fixed in Phase 2.
  `VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`, and
  `RenderVisualizerRuntime` enforce readiness by type; entry via
  `build_runtime_base` in [cleave/viz/app.py](cleave/viz/app.py).
- [cleave/viz/layer.py](cleave/viz/layer.py): fixed in Phase 2. `StemLayer` only;
  frame pipeline, visibility, and overlay drawing live in
  [cleave/viz/layer_pipeline.py](cleave/viz/layer_pipeline.py),
  [cleave/viz/layer_visibility.py](cleave/viz/layer_visibility.py), and
  [cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py).
  [cleave/viz/app.py](cleave/viz/app.py) imports public names only.
- Config schema unified in Phase 3: parse, defaults, and persisted payload in
  [cleave/config_schema.py](cleave/config_schema.py); snapshots in
  [cleave/config_snapshot.py](cleave/config_snapshot.py).
- Effects runtime dispatches through [cleave/effects/handlers.py](cleave/effects/handlers.py)
  (Phase 3); registry in [cleave/effects/registry.py](cleave/effects/registry.py).

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

## Phase 2: Structural decomposition (medium to high risk, complete)

Goal: break up the two largest structures so adding a feature touches fewer places
and readiness is enforced by types rather than asserts. Do Phase 1 first.

**Status:** Complete. User smoke-tested. Task 2.1: session model in
[cleave/viz/session.py](cleave/viz/session.py); save/quit in
[cleave/viz/config_save.py](cleave/viz/config_save.py); render overlay and post-FX
setters in [cleave/viz/render_overlay_controls.py](cleave/viz/render_overlay_controls.py)
and [cleave/viz/render_post_fx_controls.py](cleave/viz/render_post_fx_controls.py);
view state in [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py).
Task 2.2: `VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`,
`RenderVisualizerRuntime`, `build_live_runtime`, `build_render_runtime`,
`tick_frame_core` in [cleave/viz/app.py](cleave/viz/app.py). Task 2.3:
`LayerFramePipeline` in [cleave/viz/layer_pipeline.py](cleave/viz/layer_pipeline.py),
visibility in [cleave/viz/layer_visibility.py](cleave/viz/layer_visibility.py),
`OverlayDrawer` in [cleave/viz/overlay_draw.py](cleave/viz/overlay_draw.py);
[cleave/viz/layer.py](cleave/viz/layer.py) is `StemLayer` only.

### Task 2.1: Split `TuningControls` (done)

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

### Task 2.2: Replace the `VisualizerRuntime` bag (done)

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

### Task 2.3: Turn `layer.py` helpers into classes (done)

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

Phase 2 exit criteria: met. `TuningControls`, runtime types, and `layer.py` no
longer concentrate unrelated responsibilities; unit suite green; live visualizer
smoke tested by a human.

---

## Review of phases 1 and 2

Reviewed after both phases landed (800 unit tests green). The work is in line with
the intent and is having the intended effect.

What went well:

- `TuningControls` dropped from ~1325 to ~792 lines and now delegates to
  `ConfigSaveController` ([cleave/viz/config_save.py](cleave/viz/config_save.py)),
  `RenderOverlayControls`, `RenderPostFxControls`, and `TuningViewStateBuilder`
  ([cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py)).
- `layer.py` is now `StemLayer` only; the pipeline, visibility, and overlay drawing
  are focused modules with public classes.
- The runtime is typed end to end (`VisualizerSeed`, `VisualizerCore`,
  `LiveVisualizerRuntime`, `RenderVisualizerRuntime`); the old asserts became
  explicit type errors at the seam.
- Dirty tracking is now a computed signature over `persisted_session_payload`
  ([cleave/config_snapshot.py](cleave/config_snapshot.py)), reused by both the
  snapshot writer and the dirty check. Setters no longer call `mark_config_dirty()`,
  so the bug class that motivated this work is structurally gone. This anticipates
  part of Task 3.1.

New rough edges introduced (fold the fixes into Phase 3, see Task 3.0):

- Lambda-bag dependency injection. Sub-controllers receive a `focus_ctx` dict of
  closures, including `"set_focus_index": lambda index: setattr(self, ...)`. This is
  stringly typed and will spread as Phase 3 extracts more controllers.
- Default values for the render overlay runtime are duplicated inside
  [cleave/viz/session.py](cleave/viz/session.py) (`default_render_overlay_runtime()`
  and the `else` branch of `render_overlay_runtime_from_cfg()`).
- `VisualizerSeed` and `VisualizerCore` repeat ~18 fields, bridged by a
  `_core_fields_from_seed` dict spread; `build_live_runtime` and
  `build_render_runtime` are currently identical no-op wrappers around
  `build_runtime_base`.
- Dead code: `build_tuning_view_state` free function in
  [cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py) has no callers.

Not a problem (checked): `_snapshot_render_overlay` is built on top of
`_persisted_render_payload`, so the dirty signature and the written YAML share one
base and cannot silently diverge.

---

## Phase 3: Unify duplicated systems (medium to high risk, complete)

**Status:** Complete. Single config schema in [cleave/config_schema.py](cleave/config_schema.py);
registry-driven effects in [cleave/effects/handlers.py](cleave/effects/handlers.py);
shared frame finish in [cleave/viz/frame_finish.py](cleave/viz/frame_finish.py).
Typed `FocusContext` replaces closure-bag DI; `VisualizerCore` composes
`VisualizerSeed` via `runtime.seed.*`.

### Task 3.0: Clean up rough edges from Phase 2 (low risk, do first)

Small fixes that pay down the new smells before the larger Phase 3 work builds on
them.

- Replace the `focus_ctx` lambda bag with a small typed context. Define a
  `FocusContext` (a `Protocol` or a frozen dataclass holding `get`/`set` focus,
  `build_view_state`, and `is_paused`) and pass that one object to
  `RenderOverlayControls`, `RenderPostFxControls`, and any controller Phase 3 adds.
  No `setattr` by string.
- Collapse the duplicated render overlay defaults in
  [cleave/viz/session.py](cleave/viz/session.py): have
  `render_overlay_runtime_from_cfg()` fall back to `default_render_overlay_runtime()`
  instead of repeating the default field list. This also feeds Task 3.1.
- Remove the unused `build_tuning_view_state` free function.
- Reduce `VisualizerSeed` / `VisualizerCore` duplication: prefer composition (core
  holds a seed, or seed is the base) over the `_core_fields_from_seed` dict spread.
  Keep `build_live_runtime` / `build_render_runtime` only if they will diverge in
  Task 3.3; otherwise call `build_runtime_base` directly.

Acceptance: no closure-bag DI remains; render overlay defaults exist once; no dead
helper; unit suite passes.

## Phase 3 (continued)

### Task 3.1: Single config schema for load, save, and defaults

Today load lives in [cleave/config.py](cleave/config.py) (`_parse_*`), save in
[cleave/config_snapshot.py](cleave/config_snapshot.py), and defaults are duplicated
across those files and [cleave/viz/session.py](cleave/viz/session.py) (the
`default_*_runtime` functions and the `*_from_cfg` fallbacks).

Phase 1 already established `persisted_session_payload` as the single description of
which fields are persisted, shared by the snapshot writer and the dirty signature.
Build on that: extend the same single source to cover parse and defaults, rather than
introducing a third mechanism.

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
`.modifiers()` repeat near identical loops per effect (`pulse`, `flash`,
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

## Phase 4: Capture the principles as rules (low risk, complete)

Goal: turn the patterns established in Phases 1 to 3 into durable, agent facing
guidance so future work preserves the architecture instead of eroding it. This phase
edits Cursor rules and skills, not application code.

**Status:** Complete. [.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc)
captures conventions; existing rules cross-checked for post-refactor paths.

Use the create-rule skill for format and placement
([.cursor/rules](.cursor/rules)). Keep entries short and link to the canonical
example in code, following
[.cursor/rules/documentation-style.mdc](.cursor/rules/documentation-style.mdc).

### Task 4.1: Add an architecture principles rule

Create [.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc)
(always applied, or scoped to `cleave/viz/**` and `cleave/**`). Capture the
conventions this refactor established, each with a one line rationale and a pointer
to the reference implementation:

- Single source of truth for persisted config. New persisted fields go through
  `persisted_session_payload` in [cleave/config_snapshot.py](cleave/config_snapshot.py)
  so load, save, and dirty tracking stay aligned. Do not add a parallel serializer.
- Dirty tracking is computed, not marked. Never reintroduce manual
  `mark_config_dirty()` calls; mutate session state and let the signature compare
  detect changes.
- Keep controllers thin and split by feature. `TuningControls` coordinates focus and
  input and delegates mutations to focused sub controllers
  ([cleave/viz/config_save.py](cleave/viz/config_save.py),
  [cleave/viz/render_overlay_controls.py](cleave/viz/render_overlay_controls.py)).
  Do not let one class accumulate unrelated responsibilities again.
- Model, controller, and view are separate. Session dataclasses live in
  [cleave/viz/session.py](cleave/viz/session.py); the view model is built by
  `TuningViewStateBuilder`; the overlay only draws. Keep that boundary.
- Enforce readiness with types, not asserts. Prefer typed runtimes
  (`VisualizerSeed`, `VisualizerCore`, `LiveVisualizerRuntime`) over optional fields
  guarded by `assert ... is not None`.
- Inject dependencies as typed objects, not closure bags. Pass a small typed context
  (Protocol or dataclass), never a dict of lambdas or `setattr` by string.
- No cross module underscore imports. If another module needs a helper, make it
  public on a class or module API.
- Keep defaults in one place per setting.

### Task 4.2: Remind agents to weigh architecture on larger features

Add a short section to the same rule (or to a project workflow rule, or
[AGENTS.md](AGENTS.md) if the project adopts one) stating: when a change is more than
a small localized edit (a new feature, a new config or effect type, a new overlay
section, or anything touching several modules), the agent should first consider the
architecture, and refactor or introduce an abstraction when it keeps the change
cohesive, rather than bolting onto an existing class. Point at this document and at
the architecture principles rule. Note the existing project rules it complements:
[.cursor/rules/project-context.mdc](.cursor/rules/project-context.mdc) and
[.cursor/rules/no-backward-compatibility.mdc](.cursor/rules/no-backward-compatibility.mdc).

### Task 4.3: Cross check existing rules

Reread the rules under [.cursor/rules](.cursor/rules) (for example
[.cursor/rules/live-tuning-ui.mdc](.cursor/rules/live-tuning-ui.mdc)) and update any
file or symbol references that moved during Phases 1 to 3 (for example session
dataclasses now in [cleave/viz/session.py](cleave/viz/session.py), not
`controls.py`). Stale rule references mislead future agents.

Acceptance: a new architecture principles rule exists and is discoverable; the larger
feature reminder is in place; existing rules point at current file locations.

---

## Phase 5: Finish to standard (low to medium risk)

Goal: close the gap between the landed work and the Definition of done, and remove the
few patterns that now contradict
[.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc).
A post-refactor review found the intent largely met (dirty tracking, decomposition,
shared frame finish, registry effects, rules) but flagged residual smells. This phase
pays them down. Tasks are ordered low risk first; verify each with the unit suite.

**Progress so far:** Task 5.1 complete (802 tests green). Tasks 5.2, 5.3, 5.4 not
started.

### Task 5.1: Remove principle violations (low risk, do first) (done)

Done. Renames landed and all call sites plus tests updated:

- `init_gl_resources_render` / `init_gl_resources_heavy` / `init_gl_resources_cheap` are
  public in [cleave/viz/app.py](cleave/viz/app.py); [cleave/viz/render.py](cleave/viz/render.py)
  and [tests/cleave/viz/test_render.py](tests/cleave/viz/test_render.py),
  [tests/cleave/viz/test_app.py](tests/cleave/viz/test_app.py) use the public names.
- `clip_rect_to_surface` is public in [cleave/viz/overlay.py](cleave/viz/overlay.py);
  callers in [cleave/viz/help_overlay.py](cleave/viz/help_overlay.py) and
  [cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py) updated.
- `parse_blend_mode` is public in [cleave/config_schema.py](cleave/config_schema.py);
  [tests/cleave/test_blend_modes.py](tests/cleave/test_blend_modes.py) imports it from
  there.
- `close_timeline_panel` is a public method on `TuningControls`
  ([cleave/viz/controls.py](cleave/viz/controls.py)); [cleave/viz/wiring.py](cleave/viz/wiring.py)
  and [tests/cleave/viz/test_controls.py](tests/cleave/viz/test_controls.py) updated.
- Removed the `_parse_*` alias shim from [cleave/config.py](cleave/config.py); tests now
  import `parse_visualizer_section`, `parse_render_section`, `parse_timeline_section`,
  `parse_hex_colour` from [cleave/config_schema.py](cleave/config_schema.py). Note
  `_parse_layers` remains a real private helper in [cleave/config.py](cleave/config.py)
  (still imported by tests; out of scope here).
- [cleave/viz/config_save.py](cleave/viz/config_save.py) imports
  `persisted_session_payload` from [cleave/config_schema.py](cleave/config_schema.py)
  (its home), not via the snapshot re-export. Dead duplicate `_expand_path` removed from
  [cleave/config_schema.py](cleave/config_schema.py) (kept the one in
  [cleave/config.py](cleave/config.py)).

Original task scope (for reference):

- Make cross-module helpers public and update call sites:
  - `_init_gl_resources_render`, `_init_gl_resources_heavy`, `_init_gl_resources_cheap`
    in [cleave/viz/app.py](cleave/viz/app.py) (used by [cleave/viz/render.py](cleave/viz/render.py)).
  - `_clip_rect_to_surface` in [cleave/viz/overlay.py](cleave/viz/overlay.py) (used by
    [cleave/viz/help_overlay.py](cleave/viz/help_overlay.py) and
    [cleave/viz/timeline_overlay.py](cleave/viz/timeline_overlay.py)).
  - `_parse_blend_mode` in [cleave/config_schema.py](cleave/config_schema.py) (used by
    [cleave/config.py](cleave/config.py)).
  - `_close_timeline_panel` reached via `tuning_controls._close_timeline_panel()` in
    [cleave/viz/wiring.py](cleave/viz/wiring.py); expose a public method.
- Delete the backward-compat alias shim in [cleave/config.py](cleave/config.py)
  (`_parse_hex_colour`, `_parse_visualizer`, `_parse_render`, `_parse_timeline`,
  `_parse_layer_z_order`) and update the tests that import them to the public names.
- Import `persisted_session_payload` from [cleave/config_schema.py](cleave/config_schema.py)
  (its home) in [cleave/viz/config_save.py](cleave/viz/config_save.py), not via the
  [cleave/config_snapshot.py](cleave/config_snapshot.py) re-export. Dedupe the duplicated
  `_expand_path` so it exists once.

Acceptance: no cross-module underscore imports remain; no `_parse_*` aliases; suite green.

### Task 5.2: Complete the single config schema

`visualizer` and `render.post_fx` are descriptor driven, but `render.overlay`, `layers`,
and `timeline` still have a hand-written parse path separate from their persist path,
the divergence risk this refactor set out to remove.

- Add a nested section schema on top of `FieldDescriptor` (for example a
  `SectionDescriptor` with nested fields and kebab and British-spelling key support) and
  migrate `render.overlay` (title and body blocks, background, border) so parse,
  serialize, and default derive from one descriptor set.
- Preserve the Task 3.1 constraints: merge unknown keys in `paths` and `render` with the
  original file; keep `colour` and `font-colour` keys; keep the content trailing-newline
  behavior.
- For `layers` and `timeline`: either migrate them or make a deliberate carve-out
  documented in
  [.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc)
  (nested cue and layer sections use bespoke parse and persist; defaults stay single
  sourced from constants in [cleave/config_schema.py](cleave/config_schema.py)).

Note on reach: session-mirrored fields also touch the runtime dataclass in
[cleave/viz/session.py](cleave/viz/session.py), the view model in
[cleave/viz/tuning_view_state.py](cleave/viz/tuning_view_state.py), a setter, and a UI
row. The schema work removes the parse-versus-persist duplication; collapsing the live
mirror to one place is a larger follow-on and is out of scope here.

Acceptance: adding an overlay cfg field edits one descriptor entry (plus the session
mirror and UI row); the round-trip test still proves load, mutate, save, reload
stability; defaults exist once; suite green.

### Task 5.3: Replace the TuningControls callback bag

[cleave/viz/controls.py](cleave/viz/controls.py) `TuningControls` still takes roughly ten
`on_*` callables wired as closures in [cleave/viz/wiring.py](cleave/viz/wiring.py), the
closure-bag DI shape the principles warn against.

- Define a typed bindings dataclass (for example `LiveLayerBindings` holding the
  preset, blend, opacity, enabled, solo, beat, seek, and timeline-enabled handlers),
  build it in [cleave/viz/wiring.py](cleave/viz/wiring.py), and pass that one object to
  `TuningControls`.

Acceptance: `TuningControls.__init__` takes typed context objects, not a bag of optional
callbacks; suite green.

### Task 5.4: Type the effect handler interface

[cleave/effects/handlers.py](cleave/effects/handlers.py) `EffectHandler` uses
`state: object` and `mod: object` with runtime `assert isinstance` in each effect module.

- Make `EffectHandler` and its `update` and `apply` generic (or a `Protocol` over
  `LayerModifiers` and a per-effect state type) so the asserts are unnecessary.

Acceptance: no `assert isinstance(state, ...)` in effect modules; effect typing is
static; suite green.

Phase 5 exit criteria: no cross-module underscore imports, no compat aliases, no
closure-bag DI; `render.overlay` parse, serialize, and default derive from one schema
(layers and timeline migrated or documented); effect handlers typed; suite green.

---

## Sequencing and effort

| Phase | Theme | Risk | Rough effort | Status |
| --- | --- | --- | --- | --- |
| 1 | Correctness and cleanup | Low | Low | Complete |
| 2 | Structural decomposition | Medium to high | Medium to high | Complete |
| 3 | Unify duplicated systems | Medium to high | Medium to high | Complete |
| 4 | Capture principles as rules | Low | Low | Complete |
| 5 | Finish to standard | Low to medium | Medium | In progress (5.1 done; 5.2-5.4 pending) |

Phases 1 through 4 are complete; Phase 5 finishes the residual smells. Principles live in
[.cursor/rules/architecture-principles.mdc](.cursor/rules/architecture-principles.mdc).

## Definition of done for the whole refactor

- A new feature that adds a tunable config key touches roughly one schema location,
  one setter or sub controller, and the UI row, instead of 6 to 8 files.
- Dirty tracking cannot be silently bypassed by a new setter.
- No god object, no partially initialized runtime guarded by asserts, no cross module
  underscore imports, no closure-bag dependency injection.
- Live and offline render share their frame finishing logic.
- The architecture principles are written down as a Cursor rule so future features
  preserve them.
- The unit suite passes and the live visualizer is smoke tested by a human after the
  GL touching phases.
