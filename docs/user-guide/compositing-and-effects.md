# Compositing, effects, and overlays

How Cleave stacks Milkdrop layers, applies stem-driven effects, and adds render cards and post-processing.

## Compositing

- Up to eight libprojectM layers, at tiered resolutions.
- Live preview composites at the editor window size (default 1920x1080; Settings > Editor Window) and upscales via `editor.upscale` at display frame rate.
- Offline render size and frame rate are Project > Render (default 1920x1080 at 60fps; stored in `project.yaml`).
- Each layer's libprojectM instance receives PCM from its assigned stem; stereo stems are fed as stereo, mono as mono.
- Milkdrop draws on black, so Cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default).

## Effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%).

| Stem | Effects |
| --- | --- |
| Drums | pulse, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |

## Render overlay

Opening and closing cards drawn on the final frame (live preview and offline render). Each card has its own enabled flag. Tune them under Render > Overlays.

- **Opening card** appears at a chosen time (default 10s) and stays for a display duration.
- **Closing card** disappears at a chosen time (default 0s from the end).
- Title and body text, fonts, colours, margin, padding, and border are editable.
- Position: top-left, top-right, centre, bottom-left, bottom-right.
- Animation: fade, slide, slide-fade, cascade, wipe, cascade-wipe, with a slide direction.

Default title is `Cleave Final Render`. Use the cards for credits, musician names, year, or similar.

## Post-processing

GPU passes after the layer stack (Render > Post FX). A parent `enabled` flag gates every child. Fade in and fade out times apply to the whole post-FX block.

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
