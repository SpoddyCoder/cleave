# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

---

## Compositing and post-FX

Both items target the same root cause: the layer stack composites in 8-bit
(`GL_RGBA8`) and clamps to `[0,1]` at every blend step, so with several busy
black-key layers the highlights collapse to flat white before any tone curve
runs. See [gl-post-process.md](gl-post-process.md) and the black-key blend in
[cleave/gl_compositor.py](../cleave/gl_compositor.py) (`_apply_layer_blend_mode`,
`GL_ONE, GL_ONE_MINUS_SRC_COLOR`).

### HDR compositing with a single tone curve toward white

Done — see [gl-post-process.md](gl-post-process.md#hdr-compositing).


### Post-FX vibrance / saturation boost pass

Goal: a complementary post-FX control that pushes chroma back up after highlight
compression. This is cosmetic and cannot recover color already lost to clamped
compositing (that is what the HDR item fixes), but it restores perceived
vibrancy on hue that survived. Useful on its own and alongside HDR compositing.

Implementation notes:

- Add a new fragment shader and pass in
[cleave/gl_post_process.py](../cleave/gl_post_process.py) next to
`_HIGHLIGHT_ROLLOFF_FRAG` / `apply_highlight_rolloff`, following the
copy-then-draw and `_save_gl_state` / `_restore_gl_state` conventions in
[gl-post-process.md](gl-post-process.md). A saturation boost increases chroma
around Rec.709 luma: `out = mix(vec3(luma), rgb, 1 + amount)` where `amount`
is `> 0` to boost. A "vibrance" variant weights the boost lower for
already-saturated pixels to avoid clipping bright primaries.
- Add a CPU reference implementation in
[cleave/viz/post_fx.py](../cleave/viz/post_fx.py) mirroring the shader math
(as `apply_highlight_rolloff_rgb` does) so it is unit-testable without GL.
- Wire it as a child of Render: POST FX. Add fields to the post-FX descriptor in
[cleave/config_schema.py](../cleave/config_schema.py), session state on
`RenderPostFxRuntime` / `RenderPostFxBlock` in
[cleave/viz/session.py](../cleave/viz/session.py), a panel row via `RowFieldDef`
in [cleave/viz/row_fields.py](../cleave/viz/row_fields.py), and the section in
[cleave/viz/row_sections.py](../cleave/viz/row_sections.py). Follow the
panel-field manifest rules in
[.cursor/rules/live-tuning-ui.mdc](../.cursor/rules/live-tuning-ui.mdc).
- Gate the pass on the parent Render: POST FX `enabled` flag the same way
highlight rolloff does (`highlight_rolloff_active` in
[cleave/viz/post_fx.py](../cleave/viz/post_fx.py)); UI dimming is not enough,
the frame path must skip it when the section is disabled. Decide apply order:
running saturation after highlight rolloff is the natural default.
- If it gates row presence (for example an expandable subsection), add the
gating field to `view_state_structure_signature()` in
[cleave/viz/tuning_view_state.py](../cleave/viz/tuning_view_state.py) and a
`test_structure_signature_invalidates_on_*` test.
- Tests: add CPU math tests in
[tests/cleave/viz/test_post_fx.py](../tests/cleave/viz/test_post_fx.py) plus a
disabled-section test in
[tests/cleave/viz/test_frame_finish.py](../tests/cleave/viz/test_frame_finish.py)
asserting the pass is skipped when the parent is off. Add a GPU integration or
probe test confirming pixels actually change.



## Architecture



### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).
- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.



### Review Child Menus

Done — see [collapsable-sections-refactor.md](collapsable-sections-refactor.md).