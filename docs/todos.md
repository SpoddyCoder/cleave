# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Features

### Render section
New flags for render, both are in seconds...
```bash
./cleave.py render ~/music/mysong.wav --start 10 --end 20
```
Output filename is appended with `_{start}-{end}s.mp4`, eg: `sights-and-sounds-26_10-20s.mp4`

---

## Bug Fixes

### Audio starts before visualizer / render is fully booted
The visualizer app is not fully initialised when auidio starts - confusing UX.
Similar happens when rendering - audio starts before the projectM visualisers.

The correct UX is to wait and show a loading bar / spinner while the app is initialising.
Once everything is ready, the app and audio should start together.

Similarly on render - render no frames until the app is fully initiliased and the projectM instances are confirmed working.

### Disarming track mid-record does unexpected things
Disarming a track before you stop recording, stops the recording but also make the timeline go solid.
When the track is subsequently stopped with space bar... all the recorded elements correctly pop-in on the timeline.

### Pressing ESC or t when recording hides the timeline
This is by design atm, but ESC semantically means get me out of this. 
And it does not get the user out of recording - it just make it harder for them to stop the recording.

Suggest solutions...
1) ESC while recording should stop the recording. 2nd press ESC hides the timeline UI.
2) pressing t while recording does nothing (doesnt hide timeline).

---

## Architecture

### Unify compositor upscale path
Upscale > 1 forks the pipeline: `_uses_content_fbo` renders to an offscreen FBO then `present_content()` blits; upscale 1.0 renders direct to the default framebuffer and `present_content()` is a no-op. Boot uses a separate GL path (`LoadingScreen` + `blit_fullscreen_texture` to the display FB only). Target: one compositing path (always content FBO or a unified abstraction), one present handoff, boot and playback sharing the same GL lifecycle; upscale is only the final blit scale factor.
