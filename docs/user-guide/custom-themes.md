# Custom Themes

Cleave ships with four themes: three dark ones (Ultraviolet, the default, plus Chocolate and Mint) and the light Daylight. You can add your own as small YAML files in the `themes` folder (see [Where your files live](README.md#where-your-files-live)); **Settings > UI > Open themes folder** takes you there.

## Making a theme

A custom theme inherits everything from a built-in base and overrides only the colours you list, so a useful theme can be a handful of lines. Name the file after the theme, for example `midnight.yaml`:

```yaml
name: Midnight
base: ultraviolet
label: "#a0b0ff"
hover: [128, 84, 255]
button_bg: "#202040"
```

- **name** is the label shown in the Theme setting. If omitted, the file name is used.
- **base** is the built-in theme to inherit from: `ultraviolet`, `chocolate`, or `mint` for a dark theme, or `daylight` for a light one. If omitted, it defaults to Ultraviolet.
- Every other key sets one colour, either as a quoted hex string (`"#rrggbb"`) or as an `[r, g, b]` list with values from 0 to 255.
- A few keys take numbers rather than colours:
  - Keys ending in `_alpha` take 0 to 255, except the row bands, which take a pair of values from 0 to 1.
  - `button_sheen` and `button_shade` take 0 to 1.
  - `icon_lit_hover_lift` and `icon_lit_hover_edge_lift` take -1 to 1: positive values lighten a lit icon under the pointer, negative values darken it.
- `timeline_track_colors` is a list of up to eight colours, one per timeline row.

## Text on panels and text on fills

Most text is drawn directly on the panel, so `value`, `label`, `muted`, and the other text colours need enough contrast against `background`. Text on a solid fill takes a separate colour, which is what lets a light theme use dark text on its panels and light text on a saturated button:

| Colour name | Text on |
| --- | --- |
| `on_hover`, `on_hover_muted` | A button under the pointer, an open list, and the lit row of a menu (`on_hover_muted` is the shortcut on that row) |
| `on_primary` | The chosen option of a row of options, and a dialog's confirm button |
| `on_danger` | The confirm button of a dialog that deletes or replaces something |
| `on_accent` | Headings on the blue-to-violet title bar |
| `on_lit_icon` | Navigator and timeline icons that are switched on (on, solo, record) |

`modal_scrim` and `modal_scrim_alpha` set the colour and opacity of the overlay that dims the window behind a dialog. Light themes usually look best with a dark scrim at lower opacity than Ultraviolet's.

## Using your theme

Select your theme in **Settings > UI > Theme**. While iterating, use **Settings > UI > Reload themes** to apply edits without restarting. Errors such as a misspelt key or an unquoted hex value are reported in a message at startup and on reload, and the affected colour falls back to the base theme's.

## Colour names

Every key a theme can set, grouped by where it appears:

| Area | Colour names |
| --- | --- |
| Window and panels | `background`, `background_alpha`, `modal_scrim`, `modal_scrim_alpha`, `transport_rule`, `panel_edge`, `panel_focus_edge`, `navigator_tree_line`, `inspector_divider` |
| Text | `label`, `value`, `disabled`, `off_control_text`, `off_control_muted`, `muted`, `highlight`, `error_notification`, `notification_on_fill` |
| Text on fills | `on_hover`, `on_hover_muted`, `on_primary`, `on_danger`, `on_accent`, `on_lit_icon` |
| Icons and modes | `preset_icon`, `preset_file_icon`, `move_mode`, `lock_icon`, `locked`, `locked_muted`, `solo_bg`, `override_bg`, `nav_on_bg`, `nav_lock_bg`, `nav_lock_glyph`, `notice_bg`, `on_notice`, `config_dirty`, `armed_bg`, `override_glyph`, `override_glyph_off`, `rec_bg` |
| Buttons | `button_bg`, `button_border`, `button_hover_bg`, `button_hover_border`, `button_active_bg`, `button_primary_bg`, `button_primary_border`, `button_primary_hover_bg`, `button_primary_hover_border`, `button_primary_active_bg`, `button_off_bg`, `button_off_border`, `button_off_chosen_bg`, `button_off_chosen_border`, `button_danger_bg`, `button_danger_border`, `button_danger_hover_bg`, `button_danger_hover_border`, `button_danger_active_bg`, `button_sheen`, `button_shade`, `button_glow_alpha` |
| Menus, dialogs, and progress bars | `surface_bg`, `surface_edge`, `surface_text`, `accent_from`, `accent_to` |
| Rows | `hover`, `hover_bg_alpha`, `row_select_tint`, `row_selected_alpha`, `row_selected_bar`, `row_focused_alpha`, `row_focused_bar`, `row_focus_edge` |
| Icon hover | `icon_hover_fg`, `icon_hover_bg`, `icon_hover_bg_alpha`, `icon_hover_edge`, `icon_lit_hover_lift`, `icon_lit_hover_edge_lift` |
| Timeline strip | `timeline_track_colors`, `timeline_off_segment`, `bar_grid`, `song_bound`, `playhead`, `playhead_flash`, `song_marker`, `song_marker_selected`, `timeline_scroll_rail`, `timeline_scroll_thumb` |
| Calibration | `calibration_flash` |
| Scrollbars | `scrollbar_track`, `scrollbar_thumb`, `scrollbar_thumb_hover` |

## Starter theme

This file sets every key to Ultraviolet's value, so it renders identically until you change something. Copy it into a new file in the `themes` folder, rename it, and edit the colours you want; any line you leave unchanged can be deleted. For a light theme, set `base` to `daylight` and delete the lines you haven't changed, so they inherit from Daylight instead.

```yaml
name: My Theme
base: ultraviolet

# Window and panels
background: "#000000"
background_alpha: 255
modal_scrim: "#000000"
modal_scrim_alpha: 140
transport_rule: "#343a4a"
panel_edge: "#343a4a"
panel_focus_edge: "#386ccd"
navigator_tree_line: "#48526c"
inspector_divider: "#2c3240"

# Text
label: "#a5c6fa"
value: "#ffffff"
disabled: "#7c8294"
off_control_text: "#aab1c4"
off_control_muted: "#7c8294"
muted: "#8c97b0"
highlight: "#ffeb82"
error_notification: "#ff8c8c"
notification_on_fill: "#000000"

# Text on fills
on_hover: "#ffffff"
on_hover_muted: "#cdd4e4"
on_primary: "#ffffff"
on_danger: "#ffffff"
on_accent: "#ffffff"
on_lit_icon: "#ffffff"

# Icons and modes
preset_icon: "#ffc35a"
preset_file_icon: "#fffaeb"
move_mode: "#3c78ff"
lock_icon: "#eb5a5a"
locked: "#eb9696"
locked_muted: "#aa6e6e"
solo_bg: "#c82828"
override_bg: "#ffc83c"
nav_on_bg: "#288c4b"
nav_lock_bg: "#e18c28"
nav_lock_glyph: "#000000"
notice_bg: "#f5aa14"
on_notice: "#000000"
config_dirty: "#ffff00"
armed_bg: "#c82828"
override_glyph: "#000000"
override_glyph_off: "#7c8294"
rec_bg: "#dc0000"

# Buttons
button_bg: "#303642"
button_border: "#555f73"
button_hover_bg: "#543ea8"
button_hover_border: "#aa8cff"
button_active_bg: "#342470"
button_primary_bg: "#2d5596"
button_primary_border: "#5374a9"
button_primary_hover_bg: "#3a78d7"
button_primary_hover_border: "#96cdff"
button_primary_active_bg: "#204078"
button_off_bg: "#1e212a"
button_off_border: "#3e4454"
button_off_chosen_bg: "#28344e"
button_off_chosen_border: "#4f596e"
button_danger_bg: "#c82828"
button_danger_border: "#d24f4f"
button_danger_hover_bg: "#ee3a34"
button_danger_hover_border: "#ffaf9b"
button_danger_active_bg: "#961a1a"
button_sheen: 0.14
button_shade: 0.22
button_glow_alpha: 0.32

# Menus, dialogs, and progress bars
surface_bg: "#141222"
surface_edge: "#7058d2"
surface_text: "#cdd4e4"
accent_from: "#3a78d7"
accent_to: "#8054ff"

# Rows
hover: "#8054ff"
hover_bg_alpha: 40
row_select_tint: "#3a78d7"
row_selected_alpha: [0.3, 0.06]
row_selected_bar: "#3a78d7"
row_focused_alpha: [0.5, 0.14]
row_focused_bar: "#7cb8ff"
row_focus_edge: "#2e5eac"

# Icon hover
icon_hover_fg: "#ffeb82"
icon_hover_bg: "#8054ff"
icon_hover_bg_alpha: 120
icon_hover_edge: "#7a5cdc"
icon_lit_hover_lift: 0.25
icon_lit_hover_edge_lift: 0.45

# Timeline strip
timeline_track_colors:
  - "#7fd1ff"
  - "#b7a6ff"
  - "#ffd27f"
  - "#9cf0b0"
  - "#f6a6c8"
  - "#ffa38f"
  - "#d4ee8a"
  - "#80e8d8"
timeline_off_segment: "#282828"
bar_grid: "#465f82"
song_bound: "#3a4254"
playhead: "#5a3282"
playhead_flash: "#dcaaff"
song_marker: "#dc2828"
song_marker_selected: "#ffaa28"
timeline_scroll_rail: "#3a4254"
timeline_scroll_thumb: "#8c97b0"

# Calibration
calibration_flash: "#ffffff"

# Scrollbars
scrollbar_track: "#1a1d26"
scrollbar_thumb: "#58627e"
scrollbar_thumb_hover: "#aa8cff"
```

---

Back to the [Cleave User Guide](README.md).
