# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

## Features

### Dirty Config Flag and Save Protection

When the user makes a change to the config, a dirty flag is set.
If the user saves the config, the dirty flag is cleared.

If the user treis to quit the app when the dirty flag is set, the user is prompted to save the config before quitting.

UI should indicate when config is dirty by adding and asterisk at the end of the active config filepath.

---

## Bug Fixes

### Disarming track mid-record does unexpected things
Disarming a track before you stop recording, stops the recording but also make the timeline go solid.
When the track is subsequently stopped with space bar... all the recorded elements correctly pop-in on the timeline.

## Architecture

