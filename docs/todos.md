# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Bug Fixes

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

