# Visual editor compositing path issues

Status: the encode-canvas and snapshot issues below are fixed. Offline render uses an output-sized content FBO (`present_content` is 1:1). Panel render writes the snapshot under the project directory, and `cleave render` loads it with that project as `project_root`. Live play is still an editor-window preview; a 9:16 job is not letterboxed in a 16:9 window.

Review of two bugs when exporting video from the live editor:

1. Opening and closing cards stretch at output aspects other than 16:9. Live play and CLI `cleave render` do not.
2. Milkdrop presets in that export do not match live play or CLI render (those two match).

There is not a second compositing engine. Panel render spawns the same `cleave render` pipeline the CLI uses. The shared path is invoked with a split canvas (editor-sized content FBO, output-sized layer FBOs) and, from the editor, a temp YAML whose parse context is not the project.

Related: [architecture principles](../.cursor/rules/architecture-principles.mdc) (shared `frame_finish` / `LayerFramePipeline.composite`), [architecture-review.md](architecture-review.md).

---

## Verdict

The compositor, overlay draw, and post-FX used by live play and offline render are the same modules:

- Layer stack: [cleave/viz/layer_pipeline.py](../cleave/viz/layer_pipeline.py) `LayerFramePipeline.composite`
- Finish (HDR shoulder, limiter, post-FX, overlay cards, present): [cleave/viz/frame_finish.py](../cleave/viz/frame_finish.py)
- Overlay upload: [cleave/viz/render_overlay.py](../cleave/viz/render_overlay.py)
- GPU blit: [cleave/gl_compositor.py](../cleave/gl_compositor.py)

Render from the editor is [cleave/viz/project_render_job.py](../cleave/viz/project_render_job.py) writing a session snapshot, then `subprocess` of `cleave render --config <temp.yaml> --width ... --height ...`. That is the CLI entry, not a parallel GL path.

The bugs come from **which rectangle is treated as "the frame"** in that shared path, plus **which directory `load_config` treats as the project** when the config file is a tempfile.

Do not add another compositor to "fix" editor export. Size one content canvas consistently, and load the snapshot as if it still lived in the project.

---

## Three surfaces, two runtimes

| Surface | Runtime | Config | Content FBO | Layer / projectM size | Display / ffmpeg |
| --- | --- | --- | --- | --- | --- |
| Live editor | `init_gl_resources_heavy` | Project `cleave-viz.yaml` + `project.yaml` | `cfg.editor` (user window, typically 16:9) | Preview scale of editor size (same aspect) | Window = editor aspect (upscale) |
| CLI `cleave render` | `init_gl_resources_render` | Project `cleave-viz.yaml` + `project.yaml` | `cfg.editor` | `render_output_size(cfg)` from `project.yaml` (or `--width` / `--height`) | Output pixels |
| Panel Render Project | Same render runtime via child process | **Temp snapshot** + `--width` / `--height` from the live session | `cfg.editor` from **user config** (snapshot has no `editor:` section) | Argv output size | Argv output size |

Live and default CLI both run projectM at 16:9 when the editor window and `project.yaml` `render.width` / `render.height` share that aspect. Cards are laid out in the content FBO and presented 1:1 (or same-aspect upscale). They match.

Panel render always passes the live Project / Render width and height. Changing that panel to 9:16 (or 1:1, 4:3, ...) is enough to hit both bugs without saving `project.yaml`. CLI without those flags still encodes 16:9 and still matches the editor.

CLI with the same `--width` / `--height` uses the same `render()` function and **would stretch cards the same way**. The editor is not a unique blit path; it is the easy way to request a non-16:9 output while the content canvas stays 16:9.

---

## Split canvas

Offline setup in [cleave/viz/app.py](../cleave/viz/app.py):

- `build_runtime_base` sets `seed.width` / `seed.height` from `cfg.editor` (user window), never from render output.
- `init_gl_resources_render` builds `GlCompositor(seed.width, seed.height, display_width=output_width, display_height=output_height)`.
- `LayerFramePipeline.build(..., preview_resolutions=False)` sizes each layer with `render_layer_size` in [cleave/viz/layer_preview_resolution.py](../cleave/viz/layer_preview_resolution.py), which returns `render_output_size(cfg)` unless `--viz-quality`.

So for a 1080x1920 panel export with a 1920x1080 editor window:

```
projectM / layer FBO     1080 x 1920   (output aspect)
        |  draw_layer stretches the quad to the content FBO
content FBO              1920 x 1080   (editor aspect)
        |  overlay cards laid out in content pixels
        |  present_content stretches the quad to the display FBO
display / ffmpeg         1080 x 1920   (output aspect)
```

Both GPU blits are full-bleed stretches, not letterbox:

- [cleave/gl_compositor.py](../cleave/gl_compositor.py) `draw_layer`: textured quad `content_width` x `content_height`
- `present_content`: textured quad `display_width` x `display_height`
- `read_rgba_frame` reads the **display** framebuffer (the stretched result)

Live never does this. Content, layers (preview-scaled copies of the same aspect), and window stay one aspect. `present_content` at `upscale != 1` is a same-aspect scale.

This split is also why tests such as `test_render_ffmpeg_uses_explicit_render_resolution` in [tests/cleave/viz/test_render.py](../tests/cleave/viz/test_render.py) can composite at 4x4 content and encode 1920x1080: ffmpeg size is display size, not content size. Same-aspect scale is intended; cross-aspect stretch is not called out.

---

## Symptom 1: stretched opening / closing cards

Cards are rasterized at intrinsic font/padding size, then placed in **content** pixels by `panel_position` and `composite_render_overlay_with_alpha` ([cleave/viz/render_overlay.py](../cleave/viz/render_overlay.py)). `finish_content_frame` passes `core.seed.width` / `core.seed.height` (editor), not output size.

On a 16:9 content canvas the card is a rectangle with the right shape. `present_content` then stretches that whole canvas onto a 9:16 (or other) display. Text and panel chrome squash or stretch with it.

Live play draws the same cards onto the same editor-sized content FBO and presents at the same aspect, so they look correct.

CLI at default 1920x1080: content 16:9, display 16:9, no stretch.

The card path is not a second overlay compositor. It is the shared overlay path on the wrong canvas, then a stretch blit that live never applies across aspects.

Pattern mask is evaluated at `compositor.content_width` / `content_height` (editor) while layer textures are output-sized. Masked exports at a mismatched aspect have the same split, even if cards are disabled.

---

## Symptom 2: presets that do not match live or CLI

Two separate mechanisms, often stacked.

### 2a. projectM runs at a different aspect

Milkdrop presets are authored against mesh / window size. Live uses `cfg.editor` (16:9). Default CLI uses `project.yaml` render size (also 16:9 in the usual project). Panel render sets layer FBOs to the **output** size, so projectM actually runs 9:16 (or whatever was requested).

`draw_layer` then stretches that portrait (or square) texture onto the 16:9 content FBO; `present_content` stretches back to output. For the layer stack those two stretches roughly cancel, so the video shows a **true output-aspect** projectM frame. That is not what the 16:9 editor showed. It reads as "a different preset" even when the `.milk` path is identical.

CLI at 16:9 matches the editor because projectM's window aspect matches. CLI at the same non-16:9 size as the panel would also look unlike the live window (same layer sizing), and would also stretch cards (same content FBO).

### 2b. Temp snapshot is parsed as if `/tmp` were the project

Panel confirm calls `write_render_snapshot` ([cleave/viz/project_render_job.py](../cleave/viz/project_render_job.py)): `tempfile.mkstemp(prefix="cleave-render-", suffix=".yaml")`, then `write_session_snapshot`. Persist uses the **original** `cfg.config_path.parent` (the project) for relative user-preset paths. The child then does:

```
cfg = load_config(config_path, resource_dir())
```

in [cleave/viz/render.py](../cleave/viz/render.py).

`load_config` treats `config_path.parent` as `cfg_dir` and looks for `project.yaml` next to the YAML (and under the `project_root` argument, which is `resource_dir()`, not the song directory). For a tempfile that means:

| Lookup | CLI (`<project>/cleave-viz.yaml`) | Panel (temp snapshot) |
| --- | --- | --- |
| `cfg_dir` for `preset_switching_list` | Project directory | `/tmp` (or `%TEMP%`) |
| `project.yaml` (beat, HDR, default render size) | Found | **Not found** (defaults) |
| `paths:` | From project YAML, or user defaults | Copied from original only if that YAML had a `paths` block |
| `editor:` | User config (window size) | User config (same); snapshot never writes `editor` |

`preset_switching_list` entries persist as paths relative to the project (`presets/foo.milk` under the project tree, see [cleave/viz/user_presets.py](../cleave/viz/user_presets.py)). Reload with `cfg_dir=/tmp` resolves them to `/tmp/presets/foo.milk`. Those files are missing. Switching-on layers then lock to the browse-pack current (or feed projectM a dead list) instead of the list the editor is playing.

The browse `preset:` field is relative to `preset_root`, so pack presets can still round-trip. Divergence is worst when the look comes from a project-local switching list, and whenever `project.yaml` milkdrop beat or compositor HDR is not the schema default.

This is a **second config context**, not a second compositor: the child is not loading the project document the editor and CLI share.

---

## Why this feels like "a different compositing path"

The product rule is one frame path. Live and offline both call `finish_content_frame` and `LayerFramePipeline.composite`. That is still true.

What is not shared is the **meaning of the content FBO**:

- Live: content FBO **is** the picture (editor canvas).
- Offline: content FBO is an **intermediate** at editor size; output size exists twice (layer FBOs and display), and the two are glued together with stretch quads.

Panel render then adds a third document (temp YAML) so the child is not even reading the same files as `cleave render <project>`.

Width, height, and fps for export live on `project.yaml` / `session.project.render`. Overlay layout and projectM mesh follow `cfg.editor` and the content FBO. Those two size domains were left disconnected on purpose for live preview vs export resolution; they were never meant to differ in **aspect**.

---

## Direction (do not implement a second path)

1. **One content canvas per runtime.** Live: editor window. Offline: output width x height. `present_content` for encode should be 1:1 with that canvas (or a same-aspect scale). `draw_layer` should stretch only preview-scaled layers that keep the canvas aspect, which is the case the masked-compositor tests already describe.

2. **Size projectM to that canvas** (or a same-aspect preview scale). Overlay `panel_position` already uses the width/height it is given; pass the content size. Cards then match live when live is showing the output aspect, and match the file when it is not.

3. **Load the snapshot as a project file.** Either write it under the project directory, or pass the real project dir into `load_config` so `cfg_dir` and `project.yaml` resolve as they do for CLI. User-preset relatives must not be interpreted against `/tmp`.

4. **WYSIWYG for non-16:9.** Until the live content FBO can follow `session.project.render` aspect (letterboxed in the window), the editor cannot show what a 9:16 encode will do to projectM. Fixing only the encode canvas still leaves live as a 16:9 preview of a 9:16 job; that is a preview limitation, not a reason to keep stretching cards.

The compositing engine stays the one in `LayerFramePipeline` / `frame_finish` / `GlCompositor`. The fix is to stop calling it with two conflicting rectangles and a tempfile for a project.
