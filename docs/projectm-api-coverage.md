# libprojectM API coverage in Cleave

Audit of exported libprojectM 4.x symbols vs [cleave/projectm.py](../cleave/projectm.py) and [cleave/projectm_playlist.py](../cleave/projectm_playlist.py). Status values: **bound** (ctypes argtypes/restype), **used** (called from Cleave), **ignored** (deliberately unused), **future** (candidate for later work).

Related: [legacy-plans/presets-scan-plan.md](legacy-plans/presets-scan-plan.md) (experimental / low confidence), [todos.md](todos.md) (projectM robustness item).

## Core library (`libprojectM-4`)

| Symbol | Status | Notes |
| --- | --- | --- |
| `projectm_create` | bound, used | Required; `ProjectM.__init__` |
| `projectm_create_with_opengl_load_proc` | ignored | Cleave uses default resolver after pygame GL context |
| `projectm_destroy` | bound, used | `ProjectM.destroy` |
| `projectm_load_preset_file` | bound, used | Manual browse and timer restart |
| `projectm_load_preset_data` | future | In-memory presets for scan or network sources |
| `projectm_reset_textures` | future | After texture path changes without recreate |
| `projectm_set_window_size` | bound, used | Layer FBO resize |
| `projectm_get_window_size` | future | Diagnostics |
| `projectm_set_texture_search_paths` | bound, used | Config `paths.texture_paths` |
| `projectm_pcm_add_float` | bound, used | Stem PCM feed |
| `projectm_pcm_add_int16` | ignored | Cleave normalizes to float32 |
| `projectm_pcm_add_uint8` | ignored | Cleave normalizes to float32 |
| `projectm_pcm_get_max_samples` | bound, used | Chunk sizing |
| `projectm_opengl_render_frame` | ignored | Cleave renders to layer FBOs |
| `projectm_opengl_render_frame_fbo` | bound, used | Per-layer render |
| `projectm_opengl_burn_texture` | ignored | No burn pass in Cleave |
| `projectm_set_beat_sensitivity` | bound, used | Per-layer and global |
| `projectm_get_beat_sensitivity` | bound, ignored | Cleave caches sensitivity locally |
| `projectm_set_fps` | bound, used | Live/offline frame rate |
| `projectm_get_fps` | future | Diagnostics |
| `projectm_set_frame_time` | bound, used | Monotonic render clock (`ProjectMFrameClock`); not song playhead |
| `projectm_get_last_frame_time` | future | Diagnostics |
| `projectm_set_hard_cut_enabled` | bound, used | Preset switching |
| `projectm_get_hard_cut_enabled` | future | Read-back for panel |
| `projectm_set_soft_cut_duration` | bound, used | Preset switching |
| `projectm_get_soft_cut_duration` | future | Read-back |
| `projectm_set_preset_duration` | bound, used | Preset switching |
| `projectm_get_preset_duration` | future | Read-back |
| `projectm_set_hard_cut_duration` | bound, used | Preset switching |
| `projectm_get_hard_cut_duration` | future | Read-back |
| `projectm_set_hard_cut_sensitivity` | bound, used | Preset switching |
| `projectm_get_hard_cut_sensitivity` | future | Read-back |
| `projectm_set_easter_egg` | bound, used | Preset switching |
| `projectm_get_easter_egg` | future | Read-back |
| `projectm_set_preset_start_clean` | bound, used | Preset switching |
| `projectm_get_preset_start_clean` | future | Read-back |
| `projectm_set_preset_locked` | bound, used | Manual browse / mode none |
| `projectm_get_preset_locked` | bound, ignored | Not surfaced in UI |
| `projectm_set_mesh_size` | future | Tie to `render_mode` ([todos.md](todos.md)) |
| `projectm_get_mesh_size` | future | Diagnostics |
| `projectm_set_aspect_correction` | ignored | Cleave controls aspect via compositor |
| `projectm_get_aspect_correction` | ignored | |
| `projectm_set_texel_offset` | ignored | |
| `projectm_get_texel_offset` | ignored | |
| `projectm_set_preset_switch_requested_event_callback` | future | Custom switch policy without playlist |
| `projectm_set_preset_switch_failed_event_callback` | bound, used | Enqueues `PresetLoadFailure`; drained per frame |
| `projectm_set_texture_load_event_callback` | bound, ignored | Non-filesystem textures; bind ready for future |
| `projectm_set_log_callback` | bound, used | Always registered; Warning+ queued for panel toasts |
| `projectm_set_log_level` | bound, used | WARN by default; DEBUG when `CLEAVE_PROJECTM_LOG=1` |
| `projectm_get_version_components` | bound, used | `ProjectM.version_info()` |
| `projectm_get_version_string` | bound, used | `ProjectM.version_info()` |
| `projectm_get_vcs_version_string` | bound, used | `ProjectM.version_info()` |
| `projectm_free_string` | bound, used | Version string cleanup |
| `projectm_alloc_string` | ignored | Internal helper |
| `projectm_touch` / `projectm_touch_drag` / `projectm_touch_destroy*` | ignored | No touch input in Cleave |
| `projectm_sprite_*` | ignored | No user sprites |
| `projectm_write_debug_image_on_next_frame` | future | Offline scan / debug captures |

## Playlist library (`libprojectM-4-playlist`)

| Symbol | Status | Notes |
| --- | --- | --- |
| `projectm_playlist_create` | bound, used | Auto rotation |
| `projectm_playlist_destroy` | bound, used | Layer teardown |
| `projectm_playlist_connect` | bound, used | Attach to `ProjectM` |
| `projectm_playlist_add_path` | bound, used | Directory rotation (`recurse=False`) |
| `projectm_playlist_add_preset` | bound, used | Fallback when `add_presets` missing |
| `projectm_playlist_add_presets` | bound, used | User-defined rotation |
| `projectm_playlist_set_shuffle` | bound, used | Per-layer `preset_switching_shuffle` session field |
| `projectm_playlist_size` | bound, used | Position sync |
| `projectm_playlist_get_position` | bound, ignored | Position set only |
| `projectm_playlist_set_position` | bound, used | Browse sync |
| `projectm_playlist_item` | bound, used | Preset path lookup |
| `projectm_playlist_free_string` | bound, used | `item()` cleanup |
| `projectm_playlist_play_next` | bound, ignored | Available; native rotation uses internal loop |
| `projectm_playlist_play_previous` / `play_last` | future | Manual transport controls |
| `projectm_playlist_get_retry_count` | bound, used | Wrapper + tests |
| `projectm_playlist_set_retry_count` | bound, used | `DEFAULT_RETRY_COUNT` on connect |
| `projectm_playlist_set_preset_switched_event_callback` | bound, used | Browse sync via `on_preset_loaded` |
| `projectm_playlist_set_preset_switch_failed_event_callback` | bound, used | Exhausted retries -> panel notification |
| `projectm_playlist_set_preset_load_event_callback` | ignored | **Not installed**; native load/retry/removal |
| `projectm_playlist_clear` / `remove_*` / `insert_*` | future | Dynamic playlist editing |
| `projectm_playlist_items` / `free_string_array` | future | Bulk listing |
| `projectm_playlist_get_shuffle` / `set_shuffle` | bound, used | set only |
| `projectm_playlist_sort` | bound, used | After directory `add_path`; filename ascending to match Cleave browse |
| `projectm_playlist_set_filter` / `apply_filter` / `get_filter` | ignored | No playlist filters in Cleave |

## Live failure handling

- Per-instance `projectm_set_preset_switch_failed_event_callback` enqueues individual load failures.
- Connected playlist `projectm_playlist_set_preset_switch_failed_event_callback` enqueues **exhausted** failures (`exhausted=True`).
- [cleave/projectm_health.py](../cleave/projectm_health.py) drains queues each frame before layer render; rate-limited skip notifications and rotation-stall message via panel notification sink.
- Warning+ libprojectM log lines are queued in [cleave/projectm.py](../cleave/projectm.py) and drained to panel toasts (`projectM: ...`) once per unique message per session.

## Environment

| Variable | Effect |
| --- | --- |
| `CLEAVE_PROJECTM_LOG=1` | libprojectM log level DEBUG; mirror all callback messages to stderr (Warning+ still toast when live) |
| `PROJECTM_LIB` | Override core library path |
| `PROJECTM_PLAYLIST_LIB` | Override playlist library path |
