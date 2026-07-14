# Todos

Must-do items for Cleave. Everything else is iterative enhancements or listed in [roadmap.md](roadmap.md).

---

## Bug Fixes

Outstanding bugs and issues.

---

## Architecture

### Preset Curation Mode
New 1st row select control inside Editor Settings:

editor-mode: visualizer | preset curation

visualizer mode is what we have now - full fat editing.

preset-curator...

1) If the user has unsaved changes:
a) modal to ask if they want to save their changes before going into preset curation mode: YES, DISCARD CHANGES, CANCEL
b) options should do what they imply

2) Reduces the UI to only the reequired preset curation tools...

a) Hides ALL top level (section) rows, EXCEPT:
i) header: editor settings, transport controls
ii) layers: layer 1

b) The layer 1 section has ALL child rows hidden, EXCEPT...
i) Preset directory, preset file name, driving stem, beat sensitivity

3) Removes keyboard shortcuts no longer relevant to preset curation:

a) Disable ALL Navigation / Global keyboard shortcuts, EXCEPT...
i) Up/Down
ii) Ctrl + Up/Down
iii) ESC
iv) Ctrl + q

4) When the user changes the editr mode back to visualizer, the UI is restored.
a) Load the previously active visualizer yaml
b) Restore the UI to the full fat editing mode

5) The editor-mode should be a session only state, not saved to either the project yaml or the visualizer yaml.
a) When the visualizer is first launched it should be in visualizer mode.





### projectM

- Tie projectM mesh size to `render_mode` (internal warp mesh resolution, separate from Cleave layer FBO downscaling in [cleave/viz/layer_preview_resolution.py](cleave/viz/layer_preview_resolution.py)).

- Review beat sensitivity scaling: [cleave/projectm.py](cleave/projectm.py) `feed_pcm` pre-scales samples by beat sensitivity, which couples that knob to hard-cut detection; native projectM keeps beat sensitivity and hard cut sensitivity independent.

- **Robustness and API coverage:** Done. See [projectm-api-coverage.md](projectm-api-coverage.md). Native playlist load path (no custom `preset_load` callback), switch-failed draining, optional debug logging.
