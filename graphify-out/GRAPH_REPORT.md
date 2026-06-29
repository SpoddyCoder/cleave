# Graph Report - cleave  (2026-06-29)

## Corpus Check
- 182 files · ~139,233 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3659 nodes · 12512 edges · 98 communities (97 shown, 1 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 607 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `50073215`
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
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 94|Community 94]]
- [[_COMMUNITY_Community 95|Community 95]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 107|Community 107]]

## God Nodes (most connected - your core abstractions)
1. `RowDescriptor` - 322 edges
2. `TuningControls` - 251 edges
3. `TuningViewState` - 200 edges
4. `_make_controls()` - 184 edges
5. `_keydown()` - 182 edges
6. `TuningSession` - 159 edges
7. `TimelineCue` - 134 edges
8. `TuningOverlay` - 113 edges
9. `RowKind` - 102 edges
10. `GlCompositor` - 98 edges

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

## Communities (98 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (108): hard_cut_enabled_display(), preset_start_clean_display(), preset_switching_display(), PresetSwitchingMode, _apply_expand_subheader(), _apply_render_overlay_body_font(), _apply_render_overlay_body_font_size(), _apply_render_overlay_border_width() (+100 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (21): init_gl_resources_heavy(), Surface, Shared frame tick for live and render. Returns updated was_paused., tick_frame_core(), apply_effect_modifiers(), _apply_layer_bloom(), _apply_layer_grit(), _beat_sensitivity() (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (22): _ActiveRepeat, add_current_preset_key_pressed(), delete_key_pressed(), KeyRepeatController, mod_shift(), Event, Hold-to-repeat controller for pygame tuning and navigation keys., True for forward-delete keys (keysym or scancode; not Backspace). (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (88): dump_yaml(), ensure_project_viz_config(), _expand_path(), find_config_path(), load_config(), _parse_layers(), _parse_paths(), project_viz_config_path() (+80 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (56): OverlayTextureSlot, OpenGL FBO layer stack and black-key compositing., _coordinator_upload(), _help_compose_kwargs(), _note_upload(), _present_overlay(), Surface, GL upload path for live tuning and timeline overlays. (+48 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (52): effect_help_description(), effect_help_title(), description_section(), HelpSection, _keyboard_section(), layer_section(), _preset_dir_section(), _preset_section() (+44 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (52): Event, FocusCursor, Path, Return True when a modal dialog consumed the event., Handle a key down event for the main tuning tree., Keyboard focus machine for the live tuning tree overlay., TuningControls, _expand_render_overlay() (+44 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (62): timeline_viewport_reserve_px(), panel_content_max_width(), Top-left x, y, width, height of the last drawn panel, if any., Content width budget for a row; scrollable rows reserve the scrollbar column., Tree-style live tuning panel; holds visible after input, then fades out., TuningOverlay, TrackBlock, _cached_compose_panel() (+54 more)

### Community 8 - "Community 8"
Cohesion: 0.14
Nodes (48): CleaveConfig, LayerConfig, PathsConfig, Return layers in compositor draw order (bottom-to-top)., next_unnamed_path(), _path_to_yaml_str(), Path, Write a full reproducible YAML snapshot without modifying the launch config. (+40 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (102): HighlightRolloffConfig, Load Cleave YAML configuration for Milkdrop preset and compositor settings., Offline render output frame rate from config., Offline render output resolution from config., render_fps(), render_output_size(), RenderConfig, RenderPostFxConfig (+94 more)

### Community 10 - "Community 10"
Cohesion: 0.05
Nodes (100): RenderOverlayBackgroundConfig, RenderOverlayBorderConfig, RenderOverlayConfig, RenderOverlayTextBlockConfig, fade_alpha(), Shared easing helpers for visual fades and transitions., Return combined fade multiplier in [0, 1] using smoothstep easing., smoothstep() (+92 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (15): init_playback(), PlaybackState, Playback timing and seek helpers for the visualizer., seek(), toggle_pause(), Keyboard input for the timeline panel overlay., Tests for cleave.viz.playback., test_current_sec_clamps_to_duration() (+7 more)

### Community 12 - "Community 12"
Cohesion: 0.19
Nodes (18): bloom_strength(), flare_triggered(), update_burst(), update_smoothed(), _layer_runtime(), Tests for flare burst triggers, decay, and EffectRuntime integration., _signals_with_stem_key(), test_bloom_strength_scales_with_depth_and_burst() (+10 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (56): _nan_to_null(), ndarray, Path, Orchestrate per-stem feature extraction and write signals.json., run_analyse(), _stem_duration_sec(), BassSignals, extract_bass() (+48 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (55): TimelineCue, _anchor_visibility_for_slot(), armed_recording_defaults(), build_record_punch_cues(), build_timeline_view_state(), committed_visible_outside_punch(), effective_layer_enabled(), FocusCursor (+47 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (55): armed_recording_visible(), Visibility for a record-pass slot during an active take., _mutate_timeline_arm(), _mutate_timeline_preview_pause(), _mutate_timeline_recording_start(), _make_timeline_controls(), Unit tests for timeline panel keyboard controls., test_backward_seek_during_record_fills_and_expands_punch_start() (+47 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (52): append_expand_section_rows(), append_render_section_rows(), _append_section_nodes(), append_track_section_rows(), apply_panel_anchor_toggle(), _assign_expand_indent_depth(), _assign_indent_depth(), _build_row_tree_indent_depth() (+44 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (57): cue_times_for_stem(), prune_expired_arm_flashes(), Cue times that change visibility for *slot* within ``[0, duration_sec]``., Bottom-anchored timeline panel drawn over the composited frame., Last draw bar metrics: ``(bar_left, bar_width, eye_slot_w)`` in panel coordinate, Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates., TimelineOverlay, unique_cue_times() (+49 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (48): _archive_top_level_dir(), backup_project(), confirm_overwrite(), _is_archive_file_path(), Path, Backup and restore Cleave project directories as gzip tar archives., Extract a project archive into :func:`~cleave.paths.projects_dir`., Resolve a backup destination to the output archive path. (+40 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (18): aberration_px(), _apply_grit(), grit_strength(), handler_for(), Any, EffectRuntime, Owns per-row envelope state; tick updates signals then exposes modifiers., Advance envelope state from signals (call once per frame). (+10 more)

### Community 20 - "Community 20"
Cohesion: 0.14
Nodes (29): data_dir(), default_project_config(), project_dir(), project_slug(), projects_dir(), Path, Filesystem layout for Cleave data and projects., Return Cleave data root (``CLEAVE_DATA`` or the repo / package root). (+21 more)

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (15): panel_content_max_width_px(), Shared colors and layout constants for Milkdrop live tuning UI panels.  Typograp, Map persisted ui_width (20-200) to scaled panel content max width in pixels., scale_px(), TimelineUiMetrics, tuning_ui_metrics(), TuningUiMetrics, Tests for UI scale helpers in cleave.viz.theme. (+7 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (37): load_mix_pcm(), load_wav_pcm_44k(), ndarray, Path, Shared PCM loading for stems and mix playback., Load a wav as float32 PCM at 44.1 kHz in native channel layout., Load mix audio as interleaved stereo float32 at 44.1 kHz., _resample_stereo_interleaved() (+29 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): 1.1 Replace the `LAYER_SLOTS` constant, 1.2 Relax `parse_layers_section`, 1.3 Relax `parse_layer_z_order_section`, 1.4 Update `persist_layers`, 1.5 Update `parse_timeline_section`, 1.6 `CleaveConfig` — un-freeze and use `list`, 2.1 `GlCompositor.remove_layer_fbo(name: str)`, 2.2 `LayerFramePipeline.build_single` (+40 more)

### Community 24 - "Community 24"
Cohesion: 0.14
Nodes (45): ArgumentParser, build_parser(), _CleaveHelpFormatter, cmd_backup(), cmd_play(), cmd_render(), cmd_restore(), cmd_separate() (+37 more)

### Community 25 - "Community 25"
Cohesion: 0.07
Nodes (56): Return the VALUE-role color for a row (before label/value split rendering)., _row_text(), _row_value_color(), _confirm_modal_yes(), _expand_settings(), _expand_settings_ui(), _focus_index(), _header_row() (+48 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (36): _gl_bool_vector(), _gl_int(), GlPostProcess, _PingPongBuffers, _prepare_fixed_function_gl(), Program, VertexArray, GPU post-processing (bloom, grit, highlight rolloff) via moderngl sharing the ac (+28 more)

### Community 27 - "Community 27"
Cohesion: 0.15
Nodes (41): _default_output_path(), _is_partial_segment(), Path, Ensure *project_dir* is ready for offline render; return resolved path., _resolve_render_config_path(), _resolve_segment(), validate_render_project(), _attach_render_post_fx_session() (+33 more)

### Community 28 - "Community 28"
Cohesion: 0.07
Nodes (53): Buffer, _ensure_moderngl_draw_state(), Leave fixed-function GL state compatible with moderngl fullscreen draws., Context, _compile_raw_program(), _gl_int(), _make_mgl_quad_vao(), _make_pygl_tex_fbo() (+45 more)

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (35): _list_to_array(), load_signals(), ndarray, Path, Load and sample per-stem signals from signals.json., resolve_signals_path(), Signals, _validate_signals_data() (+27 more)

### Community 30 - "Community 30"
Cohesion: 0.17
Nodes (32): _tuning_view_state_needed(), VisualizerApp, _heavy_init_side_effect(), _key_handler_for_session(), _minimal_runtime(), Surface, Tests for VisualizerApp frame tick ordering., Mirror VisualizerApp.run KEYDOWN/KEYUP routing. (+24 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (17): ModalHost, ModalKind, ModalOption, ModalRequest, Event, Centered confirm modal host for live tuning UI., Return True when the event is consumed (including while blocking)., Modal prompt host; consumes keys while active. (+9 more)

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (13): _bind_functions(), _get_lib(), _library_candidates(), _pkg_config_candidates(), ProjectM, ProjectMLibraryError, c_void_p, CDLL (+5 more)

### Community 33 - "Community 33"
Cohesion: 0.13
Nodes (33): LiveVisualizerRuntime, Fully initialized live visualizer runtime., dispatch_keydown(), dispatch_keyup(), dispatch_should_notify_overlay(), _handle_global_keydown(), key_handler_for_runtime(), Event (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (37): view_state_structure_signature(), _make_controls(), _mutate_dirty(), Event, test_build_view_state_passes_fps(), test_default_focus_stays_on_transport(), test_held_key_repeat_keeps_overlay_visible(), test_key_repeat_armed_while_navigation_key_held() (+29 more)

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (34): active_auto_preset_path(), apply_preset_switching(), _apply_projectm_timing(), _auto_preset_loaded_callback(), Path, PresetSwitchingMode, PresetSwitchingScope, Apply per-layer preset switching mode to live ProjectM instances. (+26 more)

### Community 36 - "Community 36"
Cohesion: 0.16
Nodes (32): Return the stem wav directory inside a Cleave project., stems_dir(), project_stems_complete(), Path, Run Demucs stem separation and write stem wavs into a Cleave project., Separate and/or analyse a Cleave project from an audio file or project slug., Return True when every stem wav from :func:`stem_paths` exists., Return True when ``signals.json`` exists in *project_dir*. (+24 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (35): `cleave/analyse.py` and `cleave/extract.py`, `cleave/config.py`, `cleave/config_schema.py`, `cleave/effects/registry.py`, `cleave/effects/runtime.py`, `cleave/extract.py`, `cleave/preset_playlist.py`, `cleave/stem_pcm.py` (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.11
Nodes (26): _format_sample_line(), OverlayFrameSample, OverlayProfiler, Per-frame overlay draw profiling for the live tuning UI.  Enable at runtime with, _upload_stats_suffix(), CaptureFixture, MonkeyPatch, Tests for live overlay draw profiling. (+18 more)

### Community 39 - "Community 39"
Cohesion: 0.12
Nodes (24): _bar_width(), _icon_height(), material_font(), Font, Surface, Material Icons rendering for the live tuning overlay., render_transport_icons(), row_icon_prefix_width() (+16 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (43): Fixed eye slot width (glyph plus horizontal pad for solo background)., visibility_icon_slot_width(), Scaled bottom timeline strip height in pixels., timeline_panel_height_px(), timeline_ui_metrics(), arm_abbrev_flash_active(), arm_abbrev_flash_visible(), armed_abbrev_bg_visible() (+35 more)

### Community 41 - "Community 41"
Cohesion: 0.06
Nodes (31): Architecture alignment, Config (sketch), Decisions, Dependencies, Feature scope, How libprojectM preset switching works, Implementation notes, none (+23 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (22): copy_mono_pcm_chunk_as_stereo(), copy_stereo_pcm_chunk(), _default_output_device(), MixPlayer, ndarray, StemSource, SDL audio playback for preloaded mix PCM., Fill interleaved stereo *out* from frame *read_index* in *pcm*.      Returns ``( (+14 more)

### Community 43 - "Community 43"
Cohesion: 0.20
Nodes (15): effective_opacity(), update_envelope(), test_grit_envelope_uses_pulse_decay_gain(), _layer_runtime(), Tests for pulse effect sampling, opacity, and runtime wiring., test_effect_runtime_all_stems_pulse_modulate(), test_effect_runtime_bass_multi_pulse_stacking(), test_effect_runtime_pulse_driver_modulates_opacity() (+7 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (30): Architecture refactor plan, Background: what is wrong today, Definition of done for the whole refactor, Guiding rules, Phase 1: Correctness and cleanup (low risk, complete), Phase 2: Structural decomposition (medium to high risk, complete), Phase 3 (continued), Phase 3: Unify duplicated systems (medium to high risk, complete) (+22 more)

### Community 45 - "Community 45"
Cohesion: 0.06
Nodes (30): `append_dynamic_children`, `collapse_on_disable`, Collapsible sections refactor, Conditional rows, `ConditionalRowsDef`, Controls dispatch, Current state summary, Draw (+22 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (13): _bind_functions(), _get_lib(), _library_candidates(), _pkg_config_candidates(), ProjectMPlaylist, ProjectMPlaylistLibraryError, c_void_p, CDLL (+5 more)

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (6): ConfigSaveController, Path, Dirty tracking, save dialogs, and deferred quit., Return True once when quit was deferred (e.g. Don't save from unsaved dialog)., Handle a quit request. Return True when the app should exit now., FocusCursor

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (17): cycle_render_overlay_font(), _has_latin_glyphs(), System font discovery for render overlay tuning., True when *name* provides distinct Latin glyphs (not tofu placeholders)., Sorted Latin-capable pygame/SDL font names on this machine., Font name with ``(position/total)`` when *name* is in the Latin font list., render_overlay_font_display(), render_overlay_system_fonts() (+9 more)

### Community 49 - "Community 49"
Cohesion: 0.16
Nodes (21): _apply_flash(), flash_alpha(), flash_threshold(), FlashBurstState, update_burst(), _update_flash(), _layer_runtime(), Tests for flash burst triggers, decay, and EffectRuntime integration. (+13 more)

### Community 50 - "Community 50"
Cohesion: 0.17
Nodes (25): _apply_hue(), hue_mix_pct(), hue_rgb(), HueState, is_voiced_pitch(), lerp_hue(), pitch_to_hue(), Per-layer hue tint from vocal pitch (vocals only). (+17 more)

### Community 51 - "Community 51"
Cohesion: 0.09
Nodes (50): dir_has_presets(), directory_display(), list_navigable_dirs(), milk_files_in_dir(), navigable_parent(), _path_at_or_below(), playlist_at_dir(), PresetPlaylist (+42 more)

### Community 52 - "Community 52"
Cohesion: 0.20
Nodes (5): current_sec(), Event, Stop an in-progress timeline take without closing the panel., Keyboard focus for the bottom timeline strip when the panel is open., TimelineControls

### Community 53 - "Community 53"
Cohesion: 0.14
Nodes (25): clamp_effect_pct(), Shared clamps and per-driver pulse envelope constants., _apply_flare(), FlareBurstState, Per-layer bloom flare: onset delta and threshold burst (drums only)., _update_flare(), Per-layer flash overlay: threshold burst from normalized stem signals., GritState (+17 more)

### Community 54 - "Community 54"
Cohesion: 0.24
Nodes (23): load_manifest(), manifest_path(), mix_path(), ProjectManifest, Path, Project manifest (project.yaml) for Cleave projects., Update ``project.yaml`` *slug* and optional ``restored-from`` provenance., resolve_mix_path() (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.20
Nodes (15): Map a sub-row to its section header using the composition tree., section_header_from_section_tree(), Tests for expandable section composition in row_sections., test_layout_includes_conditional_rows_when_predicates_pass(), test_layout_omits_conditional_rows_when_predicate_fails(), test_section_header_from_tree_preset_switching_submenu(), test_track_layout_collapsed_effects(), test_track_layout_collapsed_layer() (+7 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (26): _cue_modifies_armed_stem(), layer_visible_at(), _merge_cues_at_same_t(), punch_replace(), StemSource, Timeline cue evaluation and editing for per-slot layer visibility., should_accept_toggle(), stem_abbreviation() (+18 more)

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (35): Compositor blend mode names (no OpenGL / pygame dependency)., clamp_easter_egg(), parse_blend_mode(), BlendMode, Focus-driven live tuning input for the Milkdrop visualizer overlay., LiveLayerBindings, Live layer sync handlers for tuning controls., Render overlay row mutations for live tuning. (+27 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (38): DescriptionSection, ComposedHelpPanel, HelpOverlay, Font, HelpContent, Surface, Context-sensitive help panel for the Cleave visualizer., Read-only help panel anchored top-right; visibility from session state. (+30 more)

### Community 59 - "Community 59"
Cohesion: 0.11
Nodes (18): 1. Full uncached redraw every frame, 2. Per-row CPU cost is high, 3. All visible rows are built even when scrolled off-screen, 4. GL texture upload every frame, 5. `blit_tint` allocates per focused row, 6. View state and layout rebuilt every frame, 7. Full-viewport overlay clear, 8. FPS feedback loop (secondary) (+10 more)

### Community 60 - "Community 60"
Cohesion: 0.10
Nodes (44): preset_filename_display(), Current preset filename with position, or empty-state label., FocusContext, Shared focus and view-state access for tuning sub-controllers., build_focus_ring(), cursor_main_descriptor(), cursor_timeline_row(), cursor_timeline_submenu_focused() (+36 more)

### Community 61 - "Community 61"
Cohesion: 0.12
Nodes (25): Count of scrollable content rows (all rows except pinned header rows)., _derived_blocked_by_layer_lock(), _derived_navigable_when_layer_locked(), expandable_row_kinds(), layer_lock_blocks_mutation(), Row interaction semantics for the live tuning overlay., True when Delete should prompt to remove the focused track block's layer., row_behavior() (+17 more)

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (26): _overlay_subimage_y(), Map top-left *dest_y* to glTexSubImage2D's bottom-origin row., Map layer opacity to glColor4f for the active layer blend mode.          GL_MODU, _make_overlay_compositor(), _make_surface(), Surface, Tests for layer opacity mapping in the GL compositor., Runtime fallback blend is black-key; opacity must scale RGB. (+18 more)

### Community 63 - "Community 63"
Cohesion: 0.27
Nodes (18): preview_layer_size(), preview_sizes_for_session(), VisualizerRenderMode, Live preview layer resolution from visualizer render mode and z-order., _requested_scale(), _cfg(), _layer_cfg(), Tests for live preview layer resolution from render mode and z-order. (+10 more)

### Community 64 - "Community 64"
Cohesion: 0.09
Nodes (60): format_fps_display(), render_glyph(), OverlayDrawCounters, format_mmss(), expand_subheader_prefix(), format_composite_header_expand_value(), format_expand_subheader_value(), labeled_row_prefix() (+52 more)

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (15): Path, Helpers for per-layer user-defined preset lists., Format a user preset row label, numbering duplicate paths in the list., Return destination path and whether the source file must be copied., resolve_user_preset_dest(), _same_preset_file(), _unique_copy_dest(), user_preset_item_display_name() (+7 more)

### Community 66 - "Community 66"
Cohesion: 0.24
Nodes (17): _controls_with_playlist(), _make_sibling_dir_tree(), _preset_dir_row(), _preset_row(), Return (preset_root, sibling_dirs) each with at least one .milk file., test_backspace_at_preset_root_is_noop(), test_ctrl_left_at_preset_root_is_noop(), test_directory_ctrl_arrows_descend_and_ascend() (+9 more)

### Community 67 - "Community 67"
Cohesion: 0.36
Nodes (10): _mock_lib(), Path, Tests for cleave.projectm_playlist ctypes bindings., test_connect_installs_instant_load_callback(), test_create_connect_add_path_set_shuffle_destroy(), test_destroy_clears_preset_load_callback(), test_destroy_disconnects_before_free(), test_item_roundtrip_with_real_library() (+2 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): `cleave`, `cleave` a track, Cleave effects, CLI, Compositing, Download Some Milkdrop Presets, Layer visibility timeline, Post-processing fade (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.25
Nodes (11): all_stem_sources(), effect_roster(), effect_row_count(), StemSource, validate_effect_entry(), Tests for the per-stem cleave effects registry., test_all_stem_sources_have_rosters(), test_effect_roster_per_stem() (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.06
Nodes (63): _expand_layer_1(), _mutate_effects_expanded(), _mutate_move_mode_without_confirm(), _mutate_preset_path(), _mutate_preset_switching(), _mutate_solo_slot(), _mutate_stem_beat_sensitivity(), _mutate_stem_blend_mode() (+55 more)

### Community 71 - "Community 71"
Cohesion: 0.36
Nodes (6): draw_loading_screen(), _loading_font_get(), Font, Centered loading message during visualizer boot., Tests for visualizer boot loading screen., test_draw_loading_screen_uploads_overlay_and_flips()

### Community 72 - "Community 72"
Cohesion: 0.20
Nodes (9): Goals and budget, Independent review: findings beyond the first review, Live tuning UI performance plan, Phase 1: Measurement harness and hidden-panel guardrails, Phase 2: Compute layout and view state once per frame, Phase 3: Panel signature, row cache, and retained panel surface, Phase 4: Stable-size GPU upload, Phase 5: Decouple projectM fps from UI-loaded display fps (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.23
Nodes (17): fit_counter_label_to_width(), fit_path_label_to_width(), fit_text_to_width(), Font, Text fitting helpers for overlay labels., Shorten text with a trailing ellipsis until it fits max_px., Shorten a path for overlay width; keep the tail (subdir + filename)., Shorten a path or filename to max_px; preserve a trailing ``(N/TOTAL)`` counter. (+9 more)

### Community 74 - "Community 74"
Cohesion: 0.08
Nodes (31): clamp_ui_fade(), clamp_ui_width(), default_highlight_rolloff_runtime_values(), default_render_overlay_runtime_values(), default_render_post_fx_runtime_values(), preset_browse_floor(), Lowest directory this layer may ascend to when browsing presets., _beat_sensitivity() (+23 more)

### Community 75 - "Community 75"
Cohesion: 0.29
Nodes (5): ndarray, StemSource, Preloaded float32 PCM for *stem* (mono 1D or interleaved stereo)., Channel count for *stem* (1 mono, 2 interleaved stereo)., Return per-channel *n_samples* of float32 PCM from *t_sec*, zero-padded past end

### Community 76 - "Community 76"
Cohesion: 0.08
Nodes (48): load_stem_pcm(), Path, Preloaded per-stem PCM at 44.1 kHz for libprojectM audio feed., PCM samples to feed libprojectM per visual frame at *fps*., PCM samples for one live visual frame from elapsed wall time., Load five audio sources from *project_dir* into memory., samples_for_dt(), samples_per_frame() (+40 more)

### Community 77 - "Community 77"
Cohesion: 0.39
Nodes (8): _mock_lib(), Tests for cleave.projectm PCM feeding., test_feed_pcm_chunks_above_max_samples(), test_feed_pcm_scales_by_beat_sensitivity(), test_feed_pcm_skips_empty(), test_feed_pcm_stereo_chunks_on_even_boundaries(), test_flush_pcm_uses_last_channel_layout(), test_set_beat_sensitivity_clamps_and_stores()

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (29): new_layer_config(), next_layer_slot(), _load_original_dict(), persisted_session_signature(), Any, Write reproducible Cleave YAML snapshots from a live tuning session., Stable compare key for persisted session state., _snapshot_render_overlay() (+21 more)

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (28): ModalViewState, draw(), _draw_message(), _draw_options(), draw_rect(), _measure_options(), _measure_panel(), _option_text() (+20 more)

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Architecture improvements, Phase 1 - Cache `build_row_layout` per frame, Phase 2 - Decouple FPS from transport color; route fps through the view builder, Phase 3 - Use `RowDescriptor` as the focus cursor, Phase 4 - Unified focus model for the timeline bridge, Phase 5 - Split overlay into layout/nav and draw modules

### Community 84 - "Community 84"
Cohesion: 0.09
Nodes (38): ui_fade_display(), apply_field_horizontal(), composite_header_prefix_part(), composite_header_suffix_part(), format_row_value(), _full_line_branch_depth(), full_line_prefix(), row_composite_header_display_text() (+30 more)

### Community 85 - "Community 85"
Cohesion: 0.08
Nodes (42): Anchor, ensure_row_surface(), live_upload_signature(), panel_signature(), PanelSignature, Font, Surface, Retained surfaces and signatures for the live tuning panel. (+34 more)

### Community 86 - "Community 86"
Cohesion: 0.25
Nodes (8): bar_segments_for_row(), Visibility segments for one timeline row, including live record preview., Return ``(start_t, end_t, visible)`` segments for *slot* over ``[0, duration_sec, visibility_segments(), test_recorded_timeline_bar_unchanged_after_disable_layer_toggle_reenable(), test_visibility_segments_default_only(), test_visibility_segments_from_cues(), test_visibility_segments_other_stem_unchanged_across_unrelated_cue()

### Community 88 - "Community 88"
Cohesion: 0.08
Nodes (28): build_layout_frame(), Row layout and visibility/navigability for the live tuning overlay., Row indices drawn in the panel (sub-rows hidden when collapsed)., Row indices reachable via Up/Down (sub-rows skipped when collapsed)., Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers., resolve_navigable_descriptor(), row_draw_visible(), row_navigable() (+20 more)

### Community 90 - "Community 90"
Cohesion: 0.08
Nodes (26): _mutate_layer_z_order(), _desc(), test_ctrl_quick_nav_blocked_during_move_mode(), test_ctrl_quick_nav_cycles_headers_and_transport(), test_ctrl_quick_nav_from_sub_row_jumps_forward(), test_effect_pulse_clamps(), test_focus_navigation_wraps(), test_move_mode_backspace_cancels_without_applying() (+18 more)

### Community 91 - "Community 91"
Cohesion: 0.29
Nodes (6): Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, UI Performance Results

### Community 94 - "Community 94"
Cohesion: 0.13
Nodes (14): FrameRateMeter, ProjectMFpsGovernor, Track achieved FPS from full main-loop iterations., Smooth projectM target FPS independently of UI-loaded display measurement., _mock_layers(), Tests for live visualizer frame rate measurement., test_format_fps_display(), test_frame_rate_meter_first_frame() (+6 more)

### Community 95 - "Community 95"
Cohesion: 0.46
Nodes (7): _fill_content_white(), gl_context(), OpenGL integration: highlight rolloff must change content FBO pixels., _read_content_pixel(), test_highlight_rolloff_darkens_blown_out_white(), test_highlight_rolloff_strength_zero_is_noop(), test_highlight_rolloff_toggle_off_vs_on()

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (7): clamp_highlight_rolloff_desaturation_pct(), clamp_highlight_rolloff_softness_pct(), clamp_highlight_rolloff_strength_pct(), clamp_highlight_rolloff_threshold_pct(), Render post-FX row mutations for live tuning., Mutations for render post-FX rows., RenderPostFxControls

### Community 101 - "Community 101"
Cohesion: 0.25
Nodes (3): PanelNotificationHost, Pinned header notification timing for the live tuning panel., Single-slot notification state with monotonic expiry.

### Community 102 - "Community 102"
Cohesion: 0.10
Nodes (30): allow_overwrite_for_path(), config_path_display(), Path, Active config path for the config header row (truncation happens at draw time)., Hide overwrite only for the repo-root template cleave-viz.yaml., test_display_time_mutation_clears_dirty_after_save(), _choose_overwrite(), _choose_save_as_new() (+22 more)

### Community 104 - "Community 104"
Cohesion: 0.32
Nodes (3): LayerFbo, Off-screen RGBA framebuffer for one compositor layer., Stable GL overlay texture bucket (one texture per slot).

### Community 105 - "Community 105"
Cohesion: 0.06
Nodes (27): _gl_name(), GlCompositor, _overlay_surface_rgba(), _OverlaySlotState, BlendMode, Surface, RGBA pixel bytes with Y flipped for OpenGL upload., Stack tiered layer FBO textures into a content FBO, then present to display. (+19 more)

### Community 107 - "Community 107"
Cohesion: 0.43
Nodes (7): _overlay_font(), Font, test_config_header_truncates_long_paths(), test_fit_row_text_config_and_preset_share_panel_width(), test_preset_row_truncates_long_filenames(), baseline_tuning_ui_metrics(), Unscaled tuning metrics for layout tests that assume 14px spacing.

## Knowledge Gaps
- **187 isolated node(s):** `Requirements`, `Setup`, `Download Some Milkdrop Presets`, ``cleave` a track`, `Project Directory` (+182 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TuningControls` connect `Community 6` to `Community 0`, `Community 1`, `Community 2`, `Community 8`, `Community 11`, `Community 15`, `Community 16`, `Community 25`, `Community 30`, `Community 31`, `Community 33`, `Community 34`, `Community 47`, `Community 48`, `Community 53`, `Community 57`, `Community 60`, `Community 66`, `Community 70`, `Community 74`, `Community 76`, `Community 78`, `Community 84`, `Community 90`, `Community 98`, `Community 101`, `Community 102`?**
  _High betweenness centrality (0.083) - this node is a cross-community bridge._
- **Why does `TuningSession` connect `Community 78` to `Community 0`, `Community 1`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 10`, `Community 11`, `Community 12`, `Community 14`, `Community 15`, `Community 19`, `Community 25`, `Community 27`, `Community 30`, `Community 33`, `Community 34`, `Community 35`, `Community 43`, `Community 47`, `Community 48`, `Community 49`, `Community 50`, `Community 51`, `Community 52`, `Community 53`, `Community 57`, `Community 60`, `Community 63`, `Community 66`, `Community 74`, `Community 76`, `Community 98`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Why does `GlCompositor` connect `Community 105` to `Community 1`, `Community 33`, `Community 4`, `Community 71`, `Community 10`, `Community 76`, `Community 78`, `Community 30`, `Community 28`, `Community 62`, `Community 95`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 29 inferred relationships involving `RowDescriptor` (e.g. with `TuningControls` and `MainFocus`) actually correct?**
  _`RowDescriptor` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TuningControls` (e.g. with `LiveVisualizerRuntime` and `RenderVisualizerRuntime`) actually correct?**
  _`TuningControls` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuningViewState` (e.g. with `TuningControls` and `FocusContext`) actually correct?**
  _`TuningViewState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cleave: stem-driven music visualizer.`, `Orchestrate per-stem feature extraction and write signals.json.`, `Backup and restore Cleave project directories as gzip tar archives.` to the rest of the system?**
  _607 weakly-connected nodes found - possible documentation gaps or missing edges._