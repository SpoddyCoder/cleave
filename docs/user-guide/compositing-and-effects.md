# Compositing, effects, and overlays

How Cleave stacks Milkdrop layers, applies stem-driven effects, and adds render cards and post-processing.

## Compositing

- Up to eight libprojectM layers, at tiered resolutions.
- Live preview takes its shape from Project > Resolution width and height and fits into the visualiser area of the window, letterboxed to the render shape. It renders only as many pixels as that area shows, up to the project resolution, so a 4K project in a small window does not cost a 4K render. The size follows the window and columns (drag the window edges, maximise it, or use Settings > Fullscreen (F11)). It runs at display frame rate.
- Preview quality: output renders every layer at the project resolution; full-quality (the default) renders every layer at the size shown; balanced, performance, and ultra-performance step lower layers down from that size. Overlay cards, bloom, and chromatic aberration keep their size relative to the frame. Milkdrop presets and film grain can look slightly different below the project resolution, so use output to check a look before rendering.
- Offline render size is Project > Resolution and frame rate is Project > Render (default 1920x1080 at 60fps; stored in `project.yaml` under `resolution:` and `render:`).
- Each layer's libprojectM instance receives PCM from its assigned stem; stereo stems are fed as stereo, mono as mono.
- Milkdrop draws on black, so Cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default).
- Each layer's blend mode and opacity live under a Compositing submenu. While Pattern Mask is enabled, those rows are greyed out and ignored: blend is identity (`black-key`) and the layer's opacity is treated as 100%. Effect pulse, timeline level, and limiter gain still apply.

## Effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%).

| Stem | Effects |
| --- | --- |
| Drums | pulse, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |

## Render overlay

Opening and closing cards drawn on the final frame (live preview and offline render). Each card has its own enabled flag. Tune them under Overlay in the navigator.

- **Opening card** appears at a chosen time (default 10s) and stays for a display duration.
- **Closing card** disappears at a chosen time (default 0s from the end).
- Title and body text, fonts, colours, margin, padding, and border are editable.
- Position: top-left, top-right, centre, bottom-left, bottom-right.
- Animation: fade, slide, slide-fade, cascade, wipe, cascade-wipe, with a slide direction.

Default title is `Cleave Final Render`. Use the cards for credits, musician names, year, or similar.

## Post-processing

GPU passes after the layer stack (Post-FX in the navigator). A parent `enabled` flag gates every child. The fade section fades the picture in from the song start (start and end in seconds) and out counted back from the song end (start and end in seconds), using a curve (linear, smoothstep, ease out cubic, or ease out expo).

**Highlight rolloff** compresses bright peaks. Apply per layer, on the composite (default), or off. Curves: rolloff (Reinhard-style), smoothstep, aces_fit. Threshold, ceiling, strength, softness, and desaturation are percentages.

**Chroma boost** increases colour. Apply per layer, on the composite, or off (default). Variants: saturation (uniform) or vibrance (boosts muted colours more). Amount is a percentage.

HDR compositing (`project.yaml` `compositor.hdr`, default on) is separate from these user post-FX knobs.

## Timeline presets and song markers

Timeline presets generate a complete layered visualisation of a song. For best results, curate presets into Roles and use song markers to anchor the generation.

Marker types:

- `-` standard song marker, no special behaviour.
- `crescendo` - visual intensity builds, then crashes to low intensity.
- `diminuendo` - visual intensity reduces, then returns to normal.
- `begin` - where a crescendo or diminuendo ramp should begin.
- `sustain` - where a crescendo or diminuendo should hit maximum / minimum intensity.

```
CRESCENDO:   thin >>>  FULL ---- FULL ---- > solo
             begin   sustain         crescendo

DIMINUENDO:  FULL >>>  thin ---- thin ---- > restore
             begin   sustain         diminuendo
```
