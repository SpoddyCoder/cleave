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

Goal: stop multi-layer whiteout at the source and reduce the need for aggressive
per-layer highlight rolloff (which is what currently drains vibrancy). Composite
the whole stack in floating point without per-step clamping, then apply one
global highlight curve at the end. This preserves each layer's true energy and
chroma through the stack, so a gentle global curve replaces heavy per-layer
compression.

Why per-layer rolloff is needed today: black-key blend is
`out = src + dst * (1 - src)`. In `GL_RGBA8` targets each intermediate result is
clamped to `[0,1]`, so after three or four bright layers the top of the range is
already `(1,1,1)` with no chroma left. Composite-mode rolloff then tone-maps
pixels that are already white and cannot recover color. Float accumulation keeps
the true sum so a single curve at present time can roll off gracefully.

Implementation notes:

- Change layer FBO and content FBO allocation from `GL_RGBA8` to a float
internal format (`GL_RGBA16F`) in
[cleave/gl_compositor.py](../cleave/gl_compositor.py) (`_create_rgba_texture`,
`_allocate_content_fbo`, `_allocate_layer_framebuffer`, and the rolloff source
slot in `_ensure_rolloff_source`). Use `GL_RGBA16F` internal format with
`GL_RGBA`, `GL_FLOAT` (or `GL_HALF_FLOAT`) pixel type. Confirm
`glCheckFramebufferStatus` still returns `GL_FRAMEBUFFER_COMPLETE`; float
color-renderable formats are required by the target GL version.
- libprojectM renders into the layer FBOs. Verify it writes correctly into a
float target and that values are not pre-clamped on the projectM side
([cleave/projectm.py](../cleave/projectm.py)).
- moderngl post-FX in [cleave/gl_post_process.py](../cleave/gl_post_process.py)
wraps these textures with `external_texture(..., "u1")` and internal
ping-pong textures via `ctx.texture(key, 4)`. Switch the external dtype to
`"f2"` (half) or `"f4"` (float) to match the new FBO format, and allocate the
internal buffers as float (`ctx.texture(key, 4, dtype="f2")`). Mismatched
dtype silently samples wrong or clamps.
- Apply exactly one global tone/soft-knee curve toward 1 on the composited
content before present. Reuse the existing composite highlight rolloff pass in
[cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)
(`apply_highlight_rolloff` on `content_texture_id`); with HDR input it now has
real headroom to work with. Per-layer rolloff should become optional and
light, not the primary defense.
- `present_content` blits the content FBO to the default 8-bit framebuffer, which
clamps for display. That is fine for the screen, but make sure the tone curve
runs before present so the mapping to `[0,1]` is graceful rather than a hard
clip.
- Offline render: `read_rgba_frame` in
[cleave/gl_compositor.py](../cleave/gl_compositor.py) reads
`GL_UNSIGNED_BYTE`. Since present already tone-maps into the 8-bit default
framebuffer, reading the default framebuffer as bytes still works; verify the
render path presents (tone-maps) before readback. If any readback happens from
a float FBO directly, add explicit tonemap plus 8-bit conversion.
- Consider a config toggle under `render` (for example
`render.hdr_compositing`) so the float path can be compared against the
current 8-bit path. Follow descriptor-driven config in
[cleave/config_schema.py](../cleave/config_schema.py).
- Tests: extend the GPU probe and integration tests in
[tests/cleave/test_highlight_rolloff_gpu_probe.py](../tests/cleave/test_highlight_rolloff_gpu_probe.py)
and
[tests/cleave/test_highlight_rolloff_gl_integration.py](../tests/cleave/test_highlight_rolloff_gl_integration.py)
to assert that stacking several bright layers in float retains chroma
(channels differ) where the 8-bit path would read `(1,1,1)`. Verify with pixel
readback, not mocks.
- Watch performance and VRAM: half-float doubles texture memory versus 8-bit.
`GL_RGBA16F` is the sensible middle ground over full `GL_RGBA32F`.



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