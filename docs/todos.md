# Todos

Must-do items for Cleave. Everything else is iterative tuning in-session or listed in [roadmap.md](roadmap.md).

## Features

### Add help to the visualizer UI
Bottom right of main tuning UI shoiuld have `h - help`
Pressing h toggles the help UI in the top right of the screen, same visual treatments as our other two UI's.
The help UI is read only and shows context sensitive help for the currently highlighted item

Examples...

When on the transport row...

```
Transport Controls
------------------
left/right - skip back/forward 10 seconds
CTRL + left/right - skip back/forward 30 second
Enter - play/pause

Navigation Controls
-------------------
up/down - move up/down
CTRL + up/down - move up/down section
ESC - hide UI
CTRL + q - quit
```

This example is not exhaustive, there may be other controls to show for this row, but the idea is to show the most relevant controls first and then any secondary controls that may be available while in the menu location / mode that they presently are in.

The example is also not explictly stating layout / visual treatements or exact content - it is illustrative of the idea. The Agent should make it look nice, readable and consistent with the overall UI style we have adopted.

Descriptions should be very short and concise.


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

