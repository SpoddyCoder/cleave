# GPU post-processing (moderngl)

Layer bloom, grit, and highlight rolloff run in [cleave/gl_post_process.py](../cleave/gl_post_process.py) via **moderngl** on the same OpenGL context as pygame and the fixed-function compositor in [cleave/gl_compositor.py](../cleave/gl_compositor.py).

Highlight rolloff supports three apply modes under `render.post_fx.highlight_rolloff.mode`:

- `off`: disabled
- `per_layer`: on each active layer before compositing in [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py)
- `composite` (default): after all layers are stacked in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)

Both apply paths gate on `highlight_rolloff_active()` in [cleave/viz/post_fx.py](../cleave/viz/post_fx.py), which requires `render.post_fx.enabled`, `mode != "off"`, and (for composite) not `render_post_fx_solo`. The parent **Render: POST FX** eye toggle must disable highlight rolloff the same way it disables fade (`live_frame_fade_alpha`). UI dimming of sub-rows is not enough; runtime helpers must check `pp.enabled`.

Per-layer mode keeps a frozen rolloff source texture per layer slot in the compositor so paused live tuning can re-apply rolloff without stacking. The shoulder curve is `render.post_fx.highlight_rolloff.curve` (`rolloff`, `smoothstep`, `aces_fit`).

## HDR compositing

When `render.hdr_compositing` is true (default in [cleave-viz.yaml](../cleave-viz.yaml)), the compositor allocates layer FBOs, the content FBO, and per-layer rolloff source slots as `GL_RGBA16F` instead of `GL_RGBA8`. Format selection lives in [cleave/gl_color_format.py](../cleave/gl_color_format.py) (`resolve_compositor_format`, `probe_rgba16f_framebuffer`). Overlay textures stay `GL_RGBA8`.

`GlPostProcess` must match compositor FBO formats: `external_texture` uses `moderngl_external_dtype` (`u1` for `GL_RGBA8`, `f2` for `GL_RGBA16F`); internal ping-pong buffers use `moderngl_internal_dtype` (`f1` for 8-bit, `f2` for half-float). Do not use `u1` for 8-bit internal buffers; moderngl `ctx.texture()` defaults to normalized `f1` and `u1` internal buffers break copy/grit/bloom on layer textures. Mismatched external dtype silently samples wrong values or clamps early. Bloom, grit, and composite highlight rolloff skip output clamp when the post-process instance is wired for `RGBA16F` (`hdr` uniform in [cleave/gl_post_process.py](../cleave/gl_post_process.py)).

Black-key stacking (`GL_ONE`, `GL_ONE_MINUS_SRC_COLOR`) clamps each intermediate result in 8-bit targets, which washes stacked bright layers to flat white before any tone curve. Float accumulation keeps true energy and chroma through the stack.

Frame finish order in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py) (`finish_content_frame`):

1. Composite highlight rolloff on the content FBO (when `mode` is `composite` and post-FX is active)
2. Frame fade (`apply_frame_fade`)
3. Render overlay composite
4. Present to the default 8-bit framebuffer (`present_content`)

`present_content` blits the content texture to the display framebuffer, which clamps for screen output. Composite rolloff runs before present so tone mapping is graceful rather than a hard clip.

Offline render in [cleave/viz/render.py](../cleave/viz/render.py) calls `finish_content_frame` then `read_rgba_frame`, which reads `GL_UNSIGNED_BYTE` from the default framebuffer after present. No float readback is required on the render path.

Toggle `render.hdr_compositing: false` to compare against the legacy 8-bit compositor path. Descriptor and defaults are in [cleave/config_schema.py](../cleave/config_schema.py).

## Incident: silent all-black shader output (2026)

Highlight rolloff was first wired with a moderngl fragment shader, but toggling controls had **no visible effect**. A CPU readback path (glReadPixels, numpy, glTexSubImage2D) worked but cost roughly half the frame rate at 720p.

Probe tests in [tests/cleave/test_highlight_rolloff_gpu_probe.py](../tests/cleave/test_highlight_rolloff_gpu_probe.py) showed that **every** moderngl fullscreen draw wrote black pixels, including bloom and grit.

### Root cause

The shared quad VBO was created from an ASCII byte string:

```python
# Wrong: 75 bytes interpreted as float32 -> degenerate vertex positions (~1e-10)
self._ctx.buffer(b"-1.0 -1.0  0.0 0.0  1.0 -1.0  1.0 0.0 ...")
```

Moderngl treats buffer contents as raw bytes. The string bytes are not float32 values. The fullscreen triangle strip collapsed to the origin, was clipped, and fragments never ran. **No GL error was reported.**

### Fix

Upload explicit binary float32 vertex data (position + UV, `2f 2f` layout):

```python
self._ctx.buffer(
    np.array(
        [-1.0, -1.0, 0.0, 0.0, 1.0, -1.0, 1.0, 0.0, -1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        dtype=np.float32,
    ).tobytes()
)
```

After this fix, the GPU highlight rolloff path matched the CPU math and was ~15x faster than readback at 1280x720 in probe timing.

## Incident: per-layer rolloff wrote to the wrong texture (2026)

Per-layer highlight rolloff had no visible effect while composite mode worked. The cause was `_dest_fbo_for(src, texture_id, ...)`: it attached the sampled `src` texture as the render target and used `texture_id` only as a cache key. For in-place passes (bloom, grit, composite rolloff) `src` and `texture_id` are the same texture, so it worked by accident. The per-layer path is the first pass whose sample source differs from its write destination (`copy_texture` and `apply_highlight_rolloff(..., source_texture_id=...)`), so every draw wrote back onto the source and left the layer texture untouched.

Fix: `_dest_fbo_for(texture_id, ...)` now attaches the external texture for `texture_id` (the destination), so source and destination are decoupled. When they coincide the behavior is identical to before.

## Checklist for new render post-FX children

When adding a subsection under **Render: POST FX** (new YAML fields, panel rows, or GPU passes):

1. **Respect `render.post_fx.enabled`.** Reuse `highlight_rolloff_active()` or an equivalent helper that checks `pp.enabled` and `render_post_fx_solo` where applicable. Do not gate only on a child `mode` or strength field.
2. **Test with `enabled=False`.** Add or extend tests in [tests/cleave/viz/test_post_fx.py](../tests/cleave/viz/test_post_fx.py), [tests/cleave/viz/test_frame_finish.py](../tests/cleave/viz/test_frame_finish.py), and/or [tests/cleave/viz/test_layer_pipeline.py](../tests/cleave/viz/test_layer_pipeline.py) asserting the effect is skipped when the parent section is disabled.

## Checklist for new GPU passes

When adding or changing code in `GlPostProcess`:

1. **Vertex buffers** must be binary (`numpy.float32.tobytes()`, `struct.pack`, or moderngl `buffer` from typed arrays). Never pass human-readable float strings as `bytes`.
2. **Call `_ensure_moderngl_draw_state()`** before fullscreen draws (via `_draw_quad`). Fixed-function compositing may leave blend, scissor, depth test, or color mask incompatible with shader output.
3. **In-place texture writes** use copy-then-draw: sample the source into an internal FBO (`_copy_prog`), then draw the effect into `_dest_fbo_for` wrapping the external texture. Do not sample a texture while it is the active draw attachment.
4. **Save and restore GL state** around each pass (`_save_gl_state` / `_restore_gl_state`), then `_prepare_fixed_function_gl()` before returning to the compositor.
5. **Verify with pixel readback**, not only mocks. Add or extend tests in `test_highlight_rolloff_gpu_probe.py` or `test_highlight_rolloff_gl_integration.py`. A pass that runs without error can still produce unchanged pixels.

## Verification commands

```bash
/home/fernpa/anaconda3/envs/cleave/bin/python -m pytest \
  tests/cleave/test_gl_color_format.py \
  tests/cleave/test_hdr_compositing_gl_integration.py \
  tests/cleave/test_highlight_rolloff_gpu_probe.py \
  tests/cleave/test_highlight_rolloff_gl_integration.py -v
```

Use `-s` on the probe file to print CPU vs GPU timing.

## Related code

| Piece | Location |
| --- | --- |
| HDR compositing format | [cleave/gl_color_format.py](../cleave/gl_color_format.py) |
| Compositor float FBOs | [cleave/gl_compositor.py](../cleave/gl_compositor.py) |
| `render.hdr_compositing` config | [cleave/config_schema.py](../cleave/config_schema.py) |
| Composite highlight rolloff | [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py) |
| Per-layer highlight rolloff | [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) |
| Rolloff source textures (paused tuning) | [cleave/gl_compositor.py](../cleave/gl_compositor.py) |
| Per-layer bloom / grit | [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) |
| CPU reference math (tests) | [cleave/viz/post_fx.py](../cleave/viz/post_fx.py) |
