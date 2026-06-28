# Graph Report - cleave  (2026-06-28)

## Corpus Check
- 173 files · ~123,942 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3319 nodes · 11269 edges · 110 communities (105 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 489 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `69adf0c9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]
- [[_COMMUNITY_Community 109|Community 109]]

## God Nodes (most connected - your core abstractions)
1. `RowDescriptor` - 286 edges
2. `TuningControls` - 236 edges
3. `TuningViewState` - 187 edges
4. `_make_controls()` - 183 edges
5. `_keydown()` - 175 edges
6. `TuningSession` - 158 edges
7. `TimelineCue` - 128 edges
8. `_desc()` - 97 edges
9. `RowKind` - 96 edges
10. `TuningOverlay` - 96 edges

## Surprising Connections (you probably didn't know these)
- `test_clamp_effect_pct()` --calls--> `clamp_effect_pct()`  [INFERRED]
  tests/cleave/test_config.py → cleave/effects/constants.py
- `StubMixPlayer` --uses--> `PathsConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py
- `StubMixPlayer` --uses--> `LayerConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py
- `test_visualizer_display_dimensions()` --calls--> `VisualizerConfig`  [EXTRACTED]
  tests/cleave/test_config.py → cleave/config.py
- `StubMixPlayer` --uses--> `VisualizerConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py

## Import Cycles
- 3-file cycle: `cleave/viz/controls.py -> cleave/viz/row_fields.py -> cleave/viz/row_sections.py -> cleave/viz/controls.py`
- 3-file cycle: `cleave/viz/controls.py -> cleave/viz/wiring.py -> cleave/viz/timeline_controls.py -> cleave/viz/controls.py`

## Communities (110 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (130): hard_cut_enabled_display(), preset_start_clean_display(), ui_fade_display(), Event, Return True when a modal dialog consumed the event., Handle a key down event for the main tuning tree., Keyboard focus machine for the live tuning tree overlay., TuningControls (+122 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (89): timeline_viewport_reserve_px(), panel_content_max_width(), Top-left x, y, width, height of the last drawn panel, if any., Return the VALUE-role color for a row (before label/value split rendering)., Content width budget for a row; scrollable rows reserve the scrollbar column., Tree-style live tuning panel; holds visible after input, then fades out., _row_bg_color(), _row_has_tree_focus() (+81 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (22): _ActiveRepeat, add_current_preset_key_pressed(), delete_key_pressed(), KeyRepeatController, mod_shift(), Event, Hold-to-repeat controller for pygame tuning and navigation keys., True for forward-delete keys (keysym or scancode; not Backspace). (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (77): dump_yaml(), ensure_project_viz_config(), load_config(), _parse_layers(), project_viz_config_path(), Any, Path, Return the default per-project visualizer config path. (+69 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (63): _confirm_modal_yes(), _header_row(), _make_controls_with_manager(), _make_playlist(), _preset_row(), Unit-style tests for live tuning controls (no Milkdrop window)., _row(), _sub_rows_for_stem() (+55 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (58): effect_help_description(), effect_help_title(), description_section(), DescriptionSection, HelpSection, _keyboard_section(), layer_section(), _preset_dir_section() (+50 more)

### Community 6 - "Community 6"
Cohesion: 0.17
Nodes (16): dir_has_presets(), directory_display(), list_navigable_dirs(), milk_files_in_dir(), navigable_parent(), _path_at_or_below(), PresetPlaylist, Path (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.15
Nodes (26): data_dir(), project_dir(), project_slug(), projects_dir(), Path, Return Cleave data root (``CLEAVE_DATA`` or the repo / package root)., Return the directory that holds per-track project folders., Return the project directory for *slug* under :func:`projects_dir`. (+18 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (50): CleaveConfig, LayerConfig, PathsConfig, Return layers in compositor draw order (bottom-to-top)., _load_original_dict(), next_unnamed_path(), _path_to_yaml_str(), persisted_session_signature() (+42 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (99): RenderPostFxConfig, as_mapping(), _build_render_overlay_background(), _build_render_overlay_border(), _build_render_overlay_config(), _build_render_overlay_text_block(), clamp_beat_sensitivity(), clamp_easter_egg() (+91 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (57): RenderOverlayBackgroundConfig, RenderOverlayBorderConfig, RenderOverlayConfig, RenderOverlayTextBlockConfig, _background_pixel_alpha(), _blit_text(), _body_font(), build_live_overlay_config() (+49 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (19): current_sec(), init_playback(), PlaybackState, Playback timing and seek helpers for the visualizer., seek(), toggle_pause(), Event, Stop an in-progress timeline take without closing the panel. (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (6): Clear to background and stack *layers* bottom-to-top., Multiply content-target RGB by *alpha* (render fade in/out)., Blit content FBO to the default framebuffer at display size., Read RGBA pixels from the default framebuffer for ffmpeg rawvideo., Draw *texture_id* onto the content FBO with SRCALPHA blending., test_lerp_tint_rgb_scales_hue_mix()

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (41): _nan_to_null(), ndarray, Path, Orchestrate per-stem feature extraction and write signals.json., run_analyse(), _stem_duration_sec(), BassSignals, extract_bass() (+33 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (49): TimelineCue, build_record_punch_cues(), build_timeline_view_state(), effective_layer_enabled(), FocusCursor, Cues to punch on record stop: baseline, toggles, and committed restore at stop., _slot_has_t0_cue(), timeline_committed_visible() (+41 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (54): _mutate_timeline_arm(), _mutate_timeline_preview_pause(), _mutate_timeline_recording_start(), _make_timeline_controls(), Unit tests for timeline panel keyboard controls., test_backward_seek_during_record_fills_and_expands_punch_start(), test_ctrl_enter_noop_while_recording(), test_ctrl_seek_when_not_recording() (+46 more)

### Community 16 - "Community 16"
Cohesion: 0.08
Nodes (53): _track_header_layer_prefix(), Row indices drawn in the panel (sub-rows hidden when collapsed)., row_draw_visible(), _sub_row_expanded(), append_expand_section_rows(), append_render_section_rows(), _append_section_nodes(), _append_track_effect_rows() (+45 more)

### Community 17 - "Community 17"
Cohesion: 0.23
Nodes (27): Bottom-anchored timeline panel drawn over the composited frame., TimelineOverlay, _abbrev_bg_pixel(), _draw(), Surface, test_armed_not_recording_abbrev_always_red(), test_armed_recording_abbrev_flashes_with_rec(), test_armed_recording_monitor_eye_flashes_when_focused() (+19 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (48): _archive_top_level_dir(), backup_project(), confirm_overwrite(), _is_archive_file_path(), Path, Backup and restore Cleave project directories as gzip tar archives., Extract a project archive into :func:`~cleave.paths.projects_dir`., Resolve a backup destination to the output archive path. (+40 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (51): _value_step_section(), build_layout_frame(), Row layout and visibility/navigability for the live tuning overlay., Count of scrollable content rows (all rows except pinned header rows)., Row indices reachable via Up/Down (sub-rows skipped when collapsed)., Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers., resolve_navigable_descriptor(), row_navigable() (+43 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (23): allow_overwrite_for_path(), config_path_display(), Path, Active config path for the config header row (truncation happens at draw time)., Hide overwrite only for the repo-root template cleave-viz.yaml., _choose_save_as_new(), _mutate_dirty(), Path (+15 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (18): panel_content_max_width_px(), Shared colors and layout constants for Milkdrop live tuning UI panels.  Typograp, Scaled bottom timeline strip height in pixels., Map persisted ui_width (20-200) to scaled panel content max width in pixels., scale_px(), timeline_panel_height_px(), timeline_ui_metrics(), TimelineUiMetrics (+10 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (51): load_mix_pcm(), load_wav_pcm_44k(), ndarray, Path, Shared PCM loading for stems and mix playback., Load a wav as float32 PCM at 44.1 kHz in native channel layout., Load mix audio as interleaved stereo float32 at 44.1 kHz., _resample_stereo_interleaved() (+43 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): 1.1 Replace the `LAYER_SLOTS` constant, 1.2 Relax `parse_layers_section`, 1.3 Relax `parse_layer_z_order_section`, 1.4 Update `persist_layers`, 1.5 Update `parse_timeline_section`, 1.6 `CleaveConfig` — un-freeze and use `list`, 2.1 `GlCompositor.remove_layer_fbo(name: str)`, 2.2 `LayerFramePipeline.build_single` (+40 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (43): ArgumentParser, build_parser(), cmd_backup(), cmd_play(), cmd_render(), cmd_restore(), cmd_separate(), _exit_error() (+35 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (33): FocusCursor, Focus-driven live tuning input for the Milkdrop visualizer overlay., FocusContext, Shared focus and view-state access for tuning sub-controllers., build_focus_ring(), cursor_main_descriptor(), cursor_timeline_row(), cursor_timeline_submenu_focused() (+25 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (31): _gl_bool_vector(), _gl_int(), GlPostProcess, _PingPongBuffers, _prepare_fixed_function_gl(), GPU post-processing (bloom) via moderngl sharing the active pygame GL context., Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)., Separable bloom pass on an existing layer FBO texture. (+23 more)

### Community 27 - "Community 27"
Cohesion: 0.15
Nodes (42): _CleaveHelpFormatter, RenderConfig, _default_output_path(), _is_partial_segment(), Ensure *project_dir* is ready for offline render; return resolved path., RenderSegment, _resolve_segment(), validate_render_project() (+34 more)

### Community 28 - "Community 28"
Cohesion: 0.11
Nodes (31): apply_field_horizontal(), _full_line_branch_depth(), full_line_prefix(), labeled_row_prefix(), Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth., row_dynamic_labeled_display_text(), row_dynamic_labeled_prefix(), row_field_def() (+23 more)

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (30): load_signals(), Path, resolve_signals_path(), test_pulse_envelope_state_tracks_playback(), test_sample_normalized_interpolates(), Path, Tests for cleave.signals., test_load_signals_minimal_fixture() (+22 more)

### Community 30 - "Community 30"
Cohesion: 0.07
Nodes (82): format_fps_display(), Wall-clock frame rate measurement for the live visualizer., _bar_width(), _icon_height(), material_font(), Font, Surface, Material Icons rendering for the live tuning overlay. (+74 more)

### Community 31 - "Community 31"
Cohesion: 0.21
Nodes (12): _beat_sensitivity(), Path, Unit tests for LayerFramePipeline add/remove helpers., _session(), _stem_layer(), test_apply_preview_resolutions_resizes_when_size_changes(), test_apply_preview_resolutions_skips_when_unchanged(), test_build_preview_resolutions_false_skips_scaling() (+4 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (6): _get_lib(), ProjectM, c_void_p, ndarray, Path, Context-manager-friendly wrapper around a libprojectM instance.

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (32): LiveVisualizerRuntime, Fully initialized live visualizer runtime., dispatch_keydown(), dispatch_keyup(), dispatch_should_notify_overlay(), _handle_global_keydown(), key_handler_for_runtime(), Event (+24 more)

### Community 34 - "Community 34"
Cohesion: 0.12
Nodes (29): arm_abbrev_flash_active(), arm_abbrev_flash_visible(), armed_abbrev_bg_visible(), bar_tick_times_for_row(), _clip_segments(), cue_times_for_stem(), playhead_x(), prune_expired_arm_flashes() (+21 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (37): active_auto_preset_path(), apply_preset_switching(), _apply_projectm_timing(), _auto_preset_loaded_callback(), Path, PresetSwitchingMode, PresetSwitchingScope, Apply per-layer preset switching mode to live ProjectM instances. (+29 more)

### Community 36 - "Community 36"
Cohesion: 0.20
Nodes (26): project_stems_complete(), Path, Separate and/or analyse a Cleave project from an audio file or project slug., Return True when every stem wav from :func:`stem_paths` exists., Return True when ``signals.json`` exists in *project_dir*., Resolve *path_or_slug* to ``(project_dir, audio_path)``.      * Audio file: slug, resolve_separate_target(), run_separate() (+18 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (35): `cleave/analyse.py` and `cleave/extract.py`, `cleave/config.py`, `cleave/config_schema.py`, `cleave/effects/registry.py`, `cleave/effects/runtime.py`, `cleave/extract.py`, `cleave/preset_playlist.py`, `cleave/stem_pcm.py` (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.21
Nodes (16): fade_alpha(), Shared easing helpers for visual fades and transitions., Return combined fade multiplier in [0, 1] using smoothstep easing., smoothstep(), live_frame_fade_alpha(), Live render post-FX fade for the visualizer., Tests for cleave.easing., test_fade_alpha_combined() (+8 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (42): _choose_overwrite(), _config_header_row(), _desc(), test_config_header_greyed_while_solo_active(), test_ctrl_quick_nav_blocked_during_move_mode(), test_ctrl_quick_nav_cycles_headers_and_transport(), test_ctrl_quick_nav_from_config_header_row(), test_ctrl_quick_nav_from_sub_row_jumps_forward() (+34 more)

### Community 40 - "Community 40"
Cohesion: 0.21
Nodes (28): VisualizerApp, _key_handler_for_session(), _minimal_runtime(), Surface, Tests for VisualizerApp frame tick ordering., Mirror VisualizerApp.run KEYDOWN/KEYUP routing., _run_seed(), test_esc_hide_clears_submenu_focus_preserves_panel_open() (+20 more)

### Community 41 - "Community 41"
Cohesion: 0.06
Nodes (31): Architecture alignment, Config (sketch), Decisions, Dependencies, Feature scope, How libprojectM preset switching works, Implementation notes, none (+23 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (22): copy_mono_pcm_chunk_as_stereo(), copy_stereo_pcm_chunk(), _default_output_device(), MixPlayer, ndarray, StemSource, SDL audio playback for preloaded mix PCM., Fill interleaved stereo *out* from frame *read_index* in *pcm*.      Returns ``( (+14 more)

### Community 43 - "Community 43"
Cohesion: 0.14
Nodes (20): _format_sample_line(), OverlayFrameSample, OverlayProfiler, Per-frame overlay draw profiling for the live tuning UI.  Enable at runtime with, CaptureFixture, MonkeyPatch, Tests for live overlay draw profiling., test_counter_increments() (+12 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (30): Architecture refactor plan, Background: what is wrong today, Definition of done for the whole refactor, Guiding rules, Phase 1: Correctness and cleanup (low risk, complete), Phase 2: Structural decomposition (medium to high risk, complete), Phase 3 (continued), Phase 3: Unify duplicated systems (medium to high risk, complete) (+22 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (30): `append_dynamic_children`, `collapse_on_disable`, Collapsible sections refactor, Conditional rows, `ConditionalRowsDef`, Controls dispatch, Current state summary, Draw (+22 more)

### Community 46 - "Community 46"
Cohesion: 0.20
Nodes (5): _get_lib(), ProjectMPlaylist, c_void_p, Path, Context-manager-friendly wrapper around a libprojectM playlist instance.

### Community 47 - "Community 47"
Cohesion: 0.22
Nodes (16): draw(), _draw_message(), _draw_options(), draw_rect(), _measure_options(), _measure_panel(), _option_text(), Font (+8 more)

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (11): cycle_render_overlay_font(), Render overlay row mutations for live tuning., Mutations for render overlay rows., RenderOverlayControls, Tests for render overlay system font discovery., test_cycle_render_overlay_font_backward(), test_cycle_render_overlay_font_empty_list_keeps_current(), test_cycle_render_overlay_font_forward() (+3 more)

### Community 49 - "Community 49"
Cohesion: 0.15
Nodes (14): Compositor blend mode names (no OpenGL / pygame dependency)., LiveLayerBindings, Live layer sync handlers for tuning controls., Tests for compositor blend mode registry and config parsing., test_cycle_blend_recovers_from_unknown_mode(), test_cycle_blend_steps_backward(), test_cycle_blend_wraps_forward(), test_parse_blend_mode_accepts_all_modes() (+6 more)

### Community 50 - "Community 50"
Cohesion: 0.20
Nodes (22): _apply_hue(), hue_mix_pct(), hue_rgb(), HueState, is_voiced_pitch(), lerp_hue(), pitch_to_hue(), Per-layer hue tint from vocal pitch (vocals only). (+14 more)

### Community 51 - "Community 51"
Cohesion: 0.16
Nodes (35): playlist_at_dir(), preset_filename_display(), Build a playlist from a .milk file or a directory of presets., Current preset filename with position, or empty-state label., Scan one preset playlist per configured layer., Build a playlist for presets directly in ``dir``., scan_all_layers(), scan_preset_playlist() (+27 more)

### Community 52 - "Community 52"
Cohesion: 0.18
Nodes (15): Fixed eye slot width (glyph plus horizontal pad for solo background)., visibility_icon_slot_width(), layer_num_prefix(), Font, Surface, Width of the row label prefix (num, abbrev, monitor eye slot)., rec_flash_visible(), row_prefix_width() (+7 more)

### Community 53 - "Community 53"
Cohesion: 0.29
Nodes (6): Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, UI Performance Results

### Community 54 - "Community 54"
Cohesion: 0.19
Nodes (27): load_manifest(), manifest_path(), mix_path(), ProjectManifest, Path, Project manifest (project.yaml) for Cleave projects., Update ``project.yaml`` *slug* and optional ``restored-from`` provenance., resolve_mix_path() (+19 more)

### Community 55 - "Community 55"
Cohesion: 0.17
Nodes (12): ModalHost, Event, Return True when the event is consumed (including while blocking)., Modal prompt host; consumes keys while active., _keydown(), Event, Unit tests for live tuning modal host., test_unsaved_quit_consumes_keys_while_active() (+4 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (24): _cue_modifies_armed_stem(), _merge_cues_at_same_t(), punch_replace(), StemSource, Timeline cue evaluation and editing for per-slot layer visibility., should_accept_toggle(), stem_abbreviation(), visible_state_at() (+16 more)

### Community 57 - "Community 57"
Cohesion: 0.19
Nodes (18): flash_alpha(), flash_threshold(), update_burst(), _layer_runtime(), Tests for flash burst triggers, decay, and EffectRuntime integration., _signals_with_stem_key(), test_effect_runtime_all_stems_expose_flash_modifier(), test_effect_runtime_flash_driver_triggers() (+10 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (28): handler_for(), Any, EffectRuntime, Owns per-row envelope state; tick updates signals then exposes modifiers., Advance envelope state from signals (call once per frame)., Fully initialized offline render runtime., GL-initialized state shared by live and offline render paths., RenderVisualizerRuntime (+20 more)

### Community 59 - "Community 59"
Cohesion: 0.25
Nodes (3): PanelNotificationHost, Pinned header notification timing for the live tuning panel., Single-slot notification state with monotonic expiry.

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (6): ConfigSaveController, Path, Dirty tracking, save dialogs, and deferred quit., Return True once when quit was deferred (e.g. Don't save from unsaved dialog)., Handle a quit request. Return True when the app should exit now., FocusCursor

### Community 61 - "Community 61"
Cohesion: 0.15
Nodes (21): preset_browse_floor(), Lowest directory this layer may ascend to when browsing presets., add_layer_to_session(), _beat_sensitivity(), default_render_overlay_runtime(), default_render_post_fx_runtime(), Live tuning session state and config bootstrap., remove_layer_from_session() (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (11): Map layer opacity to glColor4f for the active layer blend mode.          GL_MODU, Tests for layer opacity mapping in the GL compositor., Runtime fallback blend is black-key; opacity must scale RGB., Flash draws a solid quad with add blend; strength must be glColor alpha., test_flash_rgba_puts_strength_in_alpha_for_add_blend(), test_layer_gl_color_add_keeps_hue_in_rgb_and_opacity_in_alpha(), test_layer_gl_color_bakes_opacity_into_rgb(), test_layer_gl_color_full_opacity_preserves_tint() (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.27
Nodes (18): preview_layer_size(), preview_sizes_for_session(), VisualizerRenderMode, Live preview layer resolution from visualizer render mode and z-order., _requested_scale(), _cfg(), _layer_cfg(), Tests for live preview layer resolution from render mode and z-order. (+10 more)

### Community 64 - "Community 64"
Cohesion: 0.23
Nodes (14): bloom_strength(), flare_triggered(), update_burst(), update_smoothed(), Tests for flare burst triggers, decay, and EffectRuntime integration., _signals_with_stem_key(), test_bloom_strength_scales_with_depth_and_burst(), test_flare_burst_state_decays_toward_zero() (+6 more)

### Community 65 - "Community 65"
Cohesion: 0.14
Nodes (16): Path, Path, Helpers for per-layer user-defined preset lists., Format a user preset row label, numbering duplicate paths in the list., Return destination path and whether the source file must be copied., resolve_user_preset_dest(), _same_preset_file(), _unique_copy_dest() (+8 more)

### Community 66 - "Community 66"
Cohesion: 0.33
Nodes (14): _controls_with_playlist(), _make_sibling_dir_tree(), _preset_dir_row(), Return (preset_root, sibling_dirs) each with at least one .milk file., test_backspace_at_preset_root_is_noop(), test_ctrl_left_at_preset_root_is_noop(), test_directory_ctrl_arrows_descend_and_ascend(), test_directory_ctrl_arrows_do_not_repeat_parent_climb() (+6 more)

### Community 67 - "Community 67"
Cohesion: 0.16
Nodes (27): clamp_effect_pct(), Shared clamps and per-driver pulse envelope constants., _apply_flare(), FlareBurstState, Per-layer bloom flare: onset delta and threshold burst (drums only)., _update_flare(), _apply_flash(), FlashBurstState (+19 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): `cleave`, `cleave` a track, Cleave effects, CLI, Compositing, Download Some Milkdrop Presets, Layer visibility timeline, Post-processing fade (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.20
Nodes (14): Signal-driven compositor effects for the Milkdrop visualizer., all_stem_sources(), _def(), effect_roster(), effect_row_count(), StemSource, Per-stem effect roster: fixed effect and driver rows for the live tuning UI., validate_effect_entry() (+6 more)

### Community 70 - "Community 70"
Cohesion: 0.27
Nodes (7): draw_loading_screen(), _loading_font_get(), Font, Centered loading message during visualizer boot., Tests for visualizer boot loading screen., test_draw_loading_screen_uploads_overlay_and_flips(), Mock GlCompositor helpers for unit tests (no OpenGL).

### Community 71 - "Community 71"
Cohesion: 0.19
Nodes (16): Map a sub-row to its section header using the composition tree., section_header_from_section_tree(), Tests for expandable section composition in row_sections., test_layout_includes_conditional_rows_when_predicates_pass(), test_layout_omits_conditional_rows_when_predicate_fails(), test_section_header_from_tree_preset_switching_submenu(), test_sub_row_expand_visible_nested_sections(), test_track_layout_collapsed_effects() (+8 more)

### Community 72 - "Community 72"
Cohesion: 0.07
Nodes (53): _expand_layer_1(), _expand_render_overlay(), _mutate_effects_expanded(), _mutate_focus_navigation(), _mutate_help_visible(), _mutate_layer_z_order(), _mutate_move_mode_without_confirm(), _mutate_preset_path() (+45 more)

### Community 73 - "Community 73"
Cohesion: 0.23
Nodes (17): fit_counter_label_to_width(), fit_path_label_to_width(), fit_text_to_width(), Font, Text fitting helpers for overlay labels., Shorten text with a trailing ellipsis until it fits max_px., Shorten a path for overlay width; keep the tail (subdir + filename)., Shorten a path or filename to max_px; preserve a trailing ``(N/TOTAL)`` counter. (+9 more)

### Community 74 - "Community 74"
Cohesion: 0.08
Nodes (46): _expand_path(), find_config_path(), _parse_paths(), Load Cleave YAML configuration for Milkdrop preset and compositor settings., Offline render output frame rate from config., Offline render output resolution from config., Locate config: CLI override, project cleave-viz.yaml, global, then repo template, render_fps() (+38 more)

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (18): 1. Full uncached redraw every frame, 2. Per-row CPU cost is high, 3. All visible rows are built even when scrolled off-screen, 4. GL texture upload every frame, 5. `blit_tint` allocates per focused row, 6. View state and layout rebuilt every frame, 7. Full-viewport overlay clear, 8. FPS feedback loop (secondary) (+10 more)

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (19): Anchor, ensure_row_surface(), panel_signature(), PanelSignature, Font, Surface, Retained surfaces and signatures for the live tuning panel., row_render_key() (+11 more)

### Community 77 - "Community 77"
Cohesion: 0.39
Nodes (8): _mock_lib(), Tests for cleave.projectm PCM feeding., test_feed_pcm_chunks_above_max_samples(), test_feed_pcm_scales_by_beat_sensitivity(), test_feed_pcm_skips_empty(), test_feed_pcm_stereo_chunks_on_even_boundaries(), test_flush_pcm_uses_last_channel_layout(), test_set_beat_sensitivity_clamps_and_stores()

### Community 78 - "Community 78"
Cohesion: 0.26
Nodes (10): ndarray, Resample native-rate analysis frames to a uniform 100 Hz grid., Linearly interpolate *values* onto a uniform 100 Hz time grid.      Grid covers, resample_to_100hz(), Tests for cleave.resample., test_resample_boundary_excludes_endpoint(), test_resample_empty_duration_returns_empty_array(), test_resample_linear_interpolation_at_known_points() (+2 more)

### Community 79 - "Community 79"
Cohesion: 0.23
Nodes (15): layer_visible_at(), _anchor_visibility_for_slot(), armed_recording_defaults(), armed_recording_visible(), committed_visible_outside_punch(), Timeline visibility algebra and per-frame layer enablement., Visibility for a record-pass slot during an active take., Committed visibility at *record_stop* ignoring armed-slot cues inside the punch. (+7 more)

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Architecture improvements, Phase 1 - Cache `build_row_layout` per frame, Phase 2 - Decouple FPS from transport color; route fps through the view builder, Phase 3 - Use `RowDescriptor` as the focus cursor, Phase 4 - Unified focus model for the timeline bridge, Phase 5 - Split overlay into layout/nav and draw modules

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (51): _row_text(), view_state_structure_signature(), _expand_settings(), _expand_settings_ui(), _focus_index(), _make_controls(), test_build_view_state_passes_fps(), test_cycle_stem_to_full_mix() (+43 more)

### Community 85 - "Community 85"
Cohesion: 0.18
Nodes (6): GlCompositor, Stack tiered layer FBO textures into a content FBO, then present to display., Initialize GL state after a pygame OPENGL context exists., Resize an existing layer FBO, preserving compositor state fields., Destroy the named FBO and remove it from the compositor stack., Draw *texture_id* onto the display framebuffer with SRCALPHA blending.

### Community 86 - "Community 86"
Cohesion: 0.24
Nodes (11): effective_opacity(), update_envelope(), test_grit_envelope_uses_pulse_decay_gain(), Tests for pulse effect sampling, opacity, and runtime wiring., test_effective_opacity_at_full_tracks_signal(), test_effective_opacity_at_zero_is_static(), test_effective_opacity_lerp_half(), test_pulse_decay_gain_constants() (+3 more)

### Community 87 - "Community 87"
Cohesion: 0.20
Nodes (9): Goals and budget, Independent review: findings beyond the first review, Live tuning UI performance plan, Phase 1: Measurement harness and hidden-panel guardrails, Phase 2: Compute layout and view state once per frame, Phase 3: Panel signature, row cache, and retained panel surface, Phase 4: Stable-size GPU upload, Phase 5: Decouple projectM fps from UI-loaded display fps (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.22
Nodes (4): LayerFbo, BlendMode, Configure GL blend for stacking layer FBOs onto the output framebuffer., Off-screen RGBA framebuffer for one compositor layer.

### Community 89 - "Community 89"
Cohesion: 0.43
Nodes (7): StemSource, stem_control_label(), stem_overlay_header(), Tests for stem source display helpers., test_display_helpers_cover_all_stem_sources(), test_stem_control_label(), test_stem_overlay_header()

### Community 90 - "Community 90"
Cohesion: 0.26
Nodes (13): aberration_px(), _apply_grit(), grit_strength(), _layer_runtime(), Tests for grit envelope, scaling, and EffectRuntime integration., _signals_with_stem_key(), test_aberration_px_scales_with_envelope_and_depth(), test_effect_runtime_grit_all_stems() (+5 more)

### Community 91 - "Community 91"
Cohesion: 0.36
Nodes (8): ModalViewState, _font(), Tests for centered modal overlay drawing., test_message_options_vertical_spacing(), test_modal_focused_option_has_highlight_background(), test_modal_options_centered_when_message_is_wider(), test_modal_panel_is_centered(), test_modal_scrim_covers_viewport()

### Community 92 - "Community 92"
Cohesion: 0.20
Nodes (15): _help_compose_kwargs(), OverlayDrawer, Surface, GL upload path for live tuning and timeline overlays., Upload pygame overlay surfaces to the display framebuffer., _union_rect(), _mock_tuning_compose(), _overlay_surface_mock() (+7 more)

### Community 93 - "Community 93"
Cohesion: 0.36
Nodes (3): _gl_name(), Surface, Upload a pygame SRCALPHA surface as a GL texture (Y-flipped for GL).

### Community 94 - "Community 94"
Cohesion: 0.22
Nodes (6): FrameRateMeter, Track achieved FPS from full main-loop iterations., Tests for live visualizer frame rate measurement., test_format_fps_display(), test_frame_rate_meter_first_frame(), test_frame_rate_meter_smoothing()

### Community 95 - "Community 95"
Cohesion: 0.36
Nodes (10): _mock_lib(), Path, Tests for cleave.projectm_playlist ctypes bindings., test_connect_installs_instant_load_callback(), test_create_connect_add_path_set_shuffle_destroy(), test_destroy_clears_preset_load_callback(), test_destroy_disconnects_before_free(), test_item_roundtrip_with_real_library() (+2 more)

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (3): Render post-FX row mutations for live tuning., Mutations for render post-FX rows., RenderPostFxControls

### Community 97 - "Community 97"
Cohesion: 0.24
Nodes (10): _live_overlay_ui_active(), FocusCursor, Show the bottom timeline strip while the main panel is visible or a row is focus, _tick_frame_live_overlay(), _timeline_strip_fade(), _timeline_strip_visible(), _tuning_view_state_needed(), test_live_overlay_ui_active_gating() (+2 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (28): OpenGL FBO layer stack and black-key compositing., Shared frame tick for live and render. Returns updated was_paused., tick_frame_core(), apply_effect_modifiers(), _apply_layer_bloom(), _apply_layer_grit(), Per-frame GL pipeline for stem layers., _render_layer_fbo() (+20 more)

### Community 99 - "Community 99"
Cohesion: 0.25
Nodes (8): _init_compositor_and_post(), init_gl_resources_cheap(), init_gl_resources_heavy(), _make_compositor(), Surface, Pre-GL runtime state produced by build_runtime_base., VisualizerSeed, _heavy_init_side_effect()

### Community 102 - "Community 102"
Cohesion: 0.50
Nodes (3): Save and quit orchestration for live tuning., ModalKind, Centered confirm modal host for live tuning UI.

### Community 103 - "Community 103"
Cohesion: 0.28
Nodes (8): _bind_functions(), _library_candidates(), _pkg_config_candidates(), ProjectMLibraryError, CDLL, ctypes wrapper for libprojectM., libprojectM shared library not found or failed to load., OSError

### Community 104 - "Community 104"
Cohesion: 0.28
Nodes (8): _bind_functions(), _library_candidates(), _pkg_config_candidates(), ProjectMPlaylistLibraryError, CDLL, ctypes wrapper for libprojectM playlist library., libprojectM playlist shared library not found or failed to load., test_bind_functions_requires_symbols()

### Community 105 - "Community 105"
Cohesion: 0.22
Nodes (9): TimelineViewState, _bar_visible_at(), Return the bar's visibility value for a slot at time t., After a backward seek during recording, the bar shows the fill state., Backward seek past record_start: bar still shows fill for skipped range., No backward seek: bar shows record_buffer only up to playhead., test_bar_shows_fill_for_backward_seek_with_expanded_punch_start(), test_bar_shows_fill_for_backward_skipped_range() (+1 more)

### Community 106 - "Community 106"
Cohesion: 0.38
Nodes (3): _list_to_array(), ndarray, _validate_signals_data()

### Community 107 - "Community 107"
Cohesion: 0.38
Nodes (6): layer_configs(), layer_runtimes(), Path, Shared config helpers for unit tests., repo_root_template_path(), slot_for_stem()

## Knowledge Gaps
- **187 isolated node(s):** `Requirements`, `Setup`, `Download Some Milkdrop Presets`, ``cleave` a track`, `Project Directory` (+182 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TuningControls` connect `Community 0` to `Community 2`, `Community 4`, `Community 8`, `Community 9`, `Community 11`, `Community 15`, `Community 16`, `Community 19`, `Community 20`, `Community 25`, `Community 28`, `Community 30`, `Community 33`, `Community 39`, `Community 40`, `Community 48`, `Community 49`, `Community 55`, `Community 58`, `Community 59`, `Community 60`, `Community 65`, `Community 66`, `Community 67`, `Community 72`, `Community 74`, `Community 84`, `Community 96`, `Community 98`, `Community 99`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `TuningSession` connect `Community 58` to `Community 0`, `Community 1`, `Community 4`, `Community 6`, `Community 8`, `Community 9`, `Community 11`, `Community 14`, `Community 15`, `Community 16`, `Community 25`, `Community 27`, `Community 31`, `Community 33`, `Community 35`, `Community 40`, `Community 48`, `Community 49`, `Community 50`, `Community 56`, `Community 57`, `Community 60`, `Community 61`, `Community 63`, `Community 64`, `Community 66`, `Community 67`, `Community 74`, `Community 79`, `Community 84`, `Community 86`, `Community 90`, `Community 96`, `Community 97`, `Community 98`, `Community 99`, `Community 102`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `TuningOverlay` connect `Community 1` to `Community 0`, `Community 33`, `Community 99`, `Community 4`, `Community 40`, `Community 72`, `Community 74`, `Community 76`, `Community 16`, `Community 19`, `Community 58`, `Community 92`, `Community 30`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 24 inferred relationships involving `RowDescriptor` (e.g. with `TuningControls` and `MainFocus`) actually correct?**
  _`RowDescriptor` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TuningControls` (e.g. with `LiveVisualizerRuntime` and `RenderVisualizerRuntime`) actually correct?**
  _`TuningControls` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `TuningViewState` (e.g. with `TuningControls` and `FocusContext`) actually correct?**
  _`TuningViewState` has 28 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cleave: stem-driven music visualizer.`, `Orchestrate per-stem feature extraction and write signals.json.`, `Backup and restore Cleave project directories as gzip tar archives.` to the rest of the system?**
  _548 weakly-connected nodes found - possible documentation gaps or missing edges._