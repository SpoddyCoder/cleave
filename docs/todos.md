# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

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