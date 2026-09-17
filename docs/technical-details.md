# Technical Details

In-depth details on the rendering engine and signal-driven effects system.

## Compositing

* The editor supports up to eight libprojectM layers at tiered resolutions
* Live preview composites at the editor window size (default **1920x1080**; Settings > Editor Window) and upscales via user-config `editor.upscale` at display frame rate
* Offline render output size and frame rate are Project > Render (default **1920x1080** at **60fps**; stored in `project.yaml`)
* Each layer's libprojectM instance receives PCM from its assigned stem; stereo stems are fed as stereo, mono as mono.
* Milkdrop draws on black, so cleave treats black as transparent and uses pixel brightness as blend weight (`black-key` default).

## Effects

Signal-driven compositor modifiers on top of each layer. Tune depths (0-100%).

| Stem | Effects |
| --- | --- |
| Drums | pulse, flash, grit |
| Bass | pulse (sub_bass, mid_bass), flash, grit |
| Vocals | pulse, hue (pitch), flash, grit |
| Other | pulse, flash, grit |

## Render Overlay

TODO: Document

## Post-processing

TODO: Document

## Timeline Presets - Song Markers

Timeline presets make it easy to generate a complete layered visualisation of a song. For best results, curate presets into Roles and use song markers to anchor the generation.

There are multiple song marker types:

* `-` standard song marker, no special behaviour.
* `crescendo` - where the visual intensity should build, before crashing off to low intensity.
* `diminuendo` - where the visual intensity should reduce, before returning to normal intensity.
* `begin` - where a crescendo or diminuendo ramp should begin.
* `sustain` - where a crescendo or diminuendo should hit maximum / minimum intensity.

```
CRESCENDO:   thin >>>  FULL ---- FULL ---- > solo
             begin   sustain         crescendo

DIMINUENDO:  FULL >>>  thin ---- thin ---- > restore
             begin   sustain         diminuendo
```
