# GPU post-processing (moderngl)

Layer bloom, grit, and highlight rolloff run in [cleave/gl_post_process.py](../cleave/gl_post_process.py) via **moderngl** on the same OpenGL context as pygame and the fixed-function compositor in [cleave/gl_compositor.py](../cleave/gl_compositor.py).

Highlight rolloff supports two apply modes under `render.post_fx.highlight_rolloff.mode`:

- `composite` (default): after all layers are stacked in [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)
- `per_layer`: on each active layer before compositing in [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py)

Per-layer mode keeps a frozen rolloff source texture per layer slot in the compositor so paused live tuning can re-apply rolloff without stacking. The shoulder curve is `render.post_fx.highlight_rolloff.curve` (`rolloff`, `smoothstep`, `aces_fit`).

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
  tests/cleave/test_highlight_rolloff_gpu_probe.py \
  tests/cleave/test_highlight_rolloff_gl_integration.py -v
```

Use `-s` on the probe file to print CPU vs GPU timing.

## Related code

| Piece | Location |
| --- | --- |
| Composite highlight rolloff | [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py) |
| Per-layer highlight rolloff | [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) |
| Rolloff source textures (paused tuning) | [cleave/gl_compositor.py](../cleave/gl_compositor.py) |
| Per-layer bloom / grit | [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) |
| CPU reference math (tests) | [cleave/viz/post_fx.py](../cleave/viz/post_fx.py) |
