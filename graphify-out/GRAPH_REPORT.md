# Graph Report - cleave  (2026-06-29)

## Corpus Check
- 179 files · ~131,924 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3510 nodes · 12096 edges · 97 communities (94 shown, 3 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 590 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e8e10bc4`
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
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
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
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 105|Community 105]]

## God Nodes (most connected - your core abstractions)
1. `RowDescriptor` - 301 edges
2. `TuningControls` - 236 edges
3. `TuningViewState` - 193 edges
4. `_make_controls()` - 183 edges
5. `_keydown()` - 175 edges
6. `TuningSession` - 158 edges
7. `TimelineCue` - 132 edges
8. `TuningOverlay` - 113 edges
9. `RowKind` - 101 edges
10. `_desc()` - 97 edges

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

## Communities (97 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (124): hard_cut_enabled_display(), preset_start_clean_display(), ui_fade_display(), _apply_expand_subheader(), apply_field_horizontal(), _apply_render_overlay_body_font(), _apply_render_overlay_body_font_size(), _apply_render_overlay_border_width() (+116 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (51): timeline_viewport_reserve_px(), panel_content_max_width(), panel_fps_layout(), Top-left x, y, width, height of the last drawn panel, if any., Top-right FPS readout in the header region; shifts left for the scrollbar., Content width budget for a row; scrollable rows reserve the scrollbar column., Tree-style live tuning panel; holds visible after input, then fades out., TuningOverlay (+43 more)

### Community 2 - "Community 2"
Cohesion: 0.14
Nodes (17): _ActiveRepeat, delete_key_pressed(), KeyRepeatController, Event, True for forward-delete keys (keysym or scancode; not Backspace)., Arms on KEYDOWN, disarms on KEYUP; tick() fires repeat callbacks while held., _arm(), Tests for cleave.viz.key_repeat. (+9 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (100): dump_yaml(), ensure_project_viz_config(), _expand_path(), find_config_path(), load_config(), _parse_layers(), _parse_paths(), project_viz_config_path() (+92 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (50): _desc(), _expand_settings(), _header_row(), _keydown(), Event, test_beat_sensitivity_clamps(), test_ctrl_q_not_handled_by_main_controls(), test_ctrl_quick_nav_blocked_during_move_mode() (+42 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (52): effect_help_description(), effect_help_title(), description_section(), HelpSection, _keyboard_section(), layer_section(), _preset_dir_section(), _preset_section() (+44 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (35): Event, FocusCursor, Path, Return True when a modal dialog consumed the event., Handle a key down event for the main tuning tree., Keyboard focus machine for the live tuning tree overlay., TuningControls, _expand_render_overlay() (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.14
Nodes (29): data_dir(), default_project_config(), project_dir(), project_slug(), projects_dir(), Path, Filesystem layout for Cleave data and projects., Return Cleave data root (``CLEAVE_DATA`` or the repo / package root). (+21 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (56): LayerConfig, PathsConfig, Return layers in compositor draw order (bottom-to-top)., _load_original_dict(), next_unnamed_path(), _path_to_yaml_str(), persisted_session_signature(), Any (+48 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (95): RenderPostFxConfig, _build_render_overlay_background(), _build_render_overlay_border(), _build_render_overlay_config(), _build_render_overlay_text_block(), clamp_beat_sensitivity(), clamp_easter_egg(), clamp_upscale() (+87 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (58): RenderOverlayBackgroundConfig, RenderOverlayBorderConfig, RenderOverlayConfig, RenderOverlayTextBlockConfig, _background_pixel_alpha(), _blit_text(), _body_font(), build_live_overlay_config() (+50 more)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (16): current_sec(), seek(), toggle_pause(), Event, Stop an in-progress timeline take without closing the panel., Keyboard focus for the bottom timeline strip when the panel is open., TimelineControls, Tests for cleave.viz.playback. (+8 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (78): clamp_effect_pct(), Shared clamps and per-driver pulse envelope constants., _apply_flare(), bloom_strength(), flare_triggered(), FlareBurstState, Per-layer bloom flare: onset delta and threshold burst (drums only)., update_burst() (+70 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (37): _nan_to_null(), ndarray, Path, Orchestrate per-stem feature extraction and write signals.json., run_analyse(), _stem_duration_sec(), BassSignals, extract_bass() (+29 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (63): TimelineCue, _anchor_visibility_for_slot(), armed_recording_defaults(), armed_recording_visible(), build_record_punch_cues(), build_timeline_view_state(), committed_visible_outside_punch(), effective_layer_enabled() (+55 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (57): _mutate_timeline_arm(), _mutate_timeline_preview_pause(), _mutate_timeline_recording_start(), _make_timeline_controls(), Unit tests for timeline panel keyboard controls., test_backward_seek_during_record_fills_and_expands_punch_start(), test_ctrl_enter_noop_while_recording(), test_ctrl_seek_when_not_recording() (+49 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (54): append_expand_section_rows(), append_render_section_rows(), _append_section_nodes(), _append_track_effect_rows(), append_track_section_rows(), _append_user_preset_rows(), _assign_expand_indent_depth(), _assign_indent_depth() (+46 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (46): prune_expired_arm_flashes(), Bottom-anchored timeline panel drawn over the composited frame., Last draw bar metrics: ``(bar_left, bar_width, eye_slot_w)`` in panel coordinate, Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates., TimelineOverlay, unique_cue_times(), _abbrev_bg_pixel(), _bar_visible_at() (+38 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (48): _archive_top_level_dir(), backup_project(), confirm_overwrite(), _is_archive_file_path(), Path, Backup and restore Cleave project directories as gzip tar archives., Extract a project archive into :func:`~cleave.paths.projects_dir`., Resolve a backup destination to the output archive path. (+40 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (31): build_layout_frame(), Row layout and visibility/navigability for the live tuning overlay., Count of scrollable content rows (all rows except pinned header rows)., Row indices drawn in the panel (sub-rows hidden when collapsed)., Row indices reachable via Up/Down (sub-rows skipped when collapsed)., Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers., resolve_navigable_descriptor(), row_draw_visible() (+23 more)

### Community 20 - "Community 20"
Cohesion: 0.24
Nodes (16): DescriptionSection, compute_help_panel_size(), _entry_gap(), _entry_width(), _help_flag_variants(), help_panel_max_dimensions(), _line_width(), _max_key_width() (+8 more)

### Community 21 - "Community 21"
Cohesion: 0.17
Nodes (19): panel_content_max_width_px(), Shared colors and layout constants for Milkdrop live tuning UI panels.  Typograp, Scaled bottom timeline strip height in pixels., Map persisted ui_width (20-200) to scaled panel content max width in pixels., scale_px(), timeline_panel_height_px(), timeline_ui_metrics(), TimelineUiMetrics (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (37): load_mix_pcm(), load_wav_pcm_44k(), ndarray, Path, Shared PCM loading for stems and mix playback., Load a wav as float32 PCM at 44.1 kHz in native channel layout., Load mix audio as interleaved stereo float32 at 44.1 kHz., _resample_stereo_interleaved() (+29 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): 1.1 Replace the `LAYER_SLOTS` constant, 1.2 Relax `parse_layers_section`, 1.3 Relax `parse_layer_z_order_section`, 1.4 Update `persist_layers`, 1.5 Update `parse_timeline_section`, 1.6 `CleaveConfig` — un-freeze and use `list`, 2.1 `GlCompositor.remove_layer_fbo(name: str)`, 2.2 `LayerFramePipeline.build_single` (+40 more)

### Community 24 - "Community 24"
Cohesion: 0.14
Nodes (44): ArgumentParser, build_parser(), _CleaveHelpFormatter, cmd_backup(), cmd_play(), cmd_render(), cmd_restore(), cmd_separate() (+36 more)

### Community 25 - "Community 25"
Cohesion: 0.17
Nodes (23): FocusContext, Shared focus and view-state access for tuning sub-controllers., build_focus_ring(), cursor_main_descriptor(), cursor_timeline_row(), cursor_timeline_submenu_focused(), MainFocus, move_focus() (+15 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (27): _gl_bool_vector(), _gl_int(), _PingPongBuffers, _prepare_fixed_function_gl(), Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)., Bloom *texture_id* in-place; returns the (unchanged) texture id., Film grain + chromatic aberration in-place; returns texture id., _restore_gl_state() (+19 more)

### Community 27 - "Community 27"
Cohesion: 0.17
Nodes (39): RenderConfig, Ensure *project_dir* is ready for offline render; return resolved path., _resolve_segment(), validate_render_project(), default_render_overlay_runtime(), _attach_render_post_fx_session(), _attach_session_from_cfg(), _mock_render_runtime() (+31 more)

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (41): flash_alpha(), flash_threshold(), update_burst(), EffectRuntime, Owns per-row envelope state; tick updates signals then exposes modifiers., Advance envelope state from signals (call once per frame)., Render overlay row mutations for live tuning., Render post-FX row mutations for live tuning. (+33 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (24): _list_to_array(), load_signals(), ndarray, Path, Load and sample per-stem signals from signals.json., resolve_signals_path(), _validate_signals_data(), load_stem_signals() (+16 more)

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (47): _bar_width(), _icon_height(), material_font(), Font, Surface, Material Icons rendering for the live tuning overlay., Fixed eye slot width (glyph plus horizontal pad for solo background)., render_transport_icons() (+39 more)

### Community 31 - "Community 31"
Cohesion: 0.08
Nodes (43): arm_abbrev_flash_active(), arm_abbrev_flash_visible(), armed_abbrev_bg_visible(), layer_num_prefix(), playhead_x(), Font, Surface, Bottom timeline strip overlay for per-stem layer visibility cues. (+35 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (8): _get_lib(), _library_candidates(), _pkg_config_candidates(), ProjectM, c_void_p, ndarray, Path, Context-manager-friendly wrapper around a libprojectM instance.

### Community 33 - "Community 33"
Cohesion: 0.17
Nodes (25): dispatch_keydown(), dispatch_should_notify_overlay(), key_handler_for_runtime(), Event, FocusCursor, Mirror VisualizerApp.run overlay fade-in on input., True when the key should route to timeline controls (submenu focused)., Pick the context handler for a key (tests and dispatch). (+17 more)

### Community 34 - "Community 34"
Cohesion: 0.27
Nodes (10): view_state_structure_signature(), Tests for TuningViewStateBuilder structure signature and cache., test_builder_skips_layout_rebuild_when_structure_unchanged(), test_minimal_view_state_still_builds_layout(), test_reused_structure_produces_identical_row_list_and_focus(), test_structure_signature_invalidates_on_expand(), test_structure_signature_invalidates_on_layer_z_order(), test_structure_signature_invalidates_on_notification() (+2 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (55): milk_files_in_dir(), Non-recursive ``*.milk`` files directly in ``dir``., ctypes wrapper for libprojectM., apply_effect_modifiers(), Stem layer data class., StemLayer, apply_layer_visibility(), active_auto_preset_path() (+47 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (34): Return the stem wav directory inside a Cleave project., Map stem names to wav paths under a Cleave project., stem_paths(), stems_dir(), project_stems_complete(), Path, Run Demucs stem separation and write stem wavs into a Cleave project., Separate and/or analyse a Cleave project from an audio file or project slug. (+26 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (35): `cleave/analyse.py` and `cleave/extract.py`, `cleave/config.py`, `cleave/config_schema.py`, `cleave/effects/registry.py`, `cleave/effects/runtime.py`, `cleave/extract.py`, `cleave/preset_playlist.py`, `cleave/stem_pcm.py` (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (57): OverlayTextureSlot, OpenGL FBO layer stack and black-key compositing., ComposedHelpPanel, Context-sensitive help panel for the Cleave visualizer., _coordinator_upload(), _help_compose_kwargs(), _note_upload(), OverlayDrawer (+49 more)

### Community 39 - "Community 39"
Cohesion: 0.18
Nodes (20): format_fps_display(), render_glyph(), OverlayDrawCounters, clip_rect_to_bounds(), clip_rect_to_surface(), _compose_surface(), panel_help_hint_layout(), PanelScrollMetrics (+12 more)

### Community 40 - "Community 40"
Cohesion: 0.13
Nodes (35): _live_overlay_ui_active(), _tuning_view_state_needed(), _key_handler_for_session(), _keyup_handler_for_session(), _minimal_runtime(), Surface, Tests for VisualizerApp frame tick ordering., Mirror VisualizerApp.run KEYDOWN/KEYUP routing. (+27 more)

### Community 41 - "Community 41"
Cohesion: 0.06
Nodes (31): Architecture alignment, Config (sketch), Decisions, Dependencies, Feature scope, How libprojectM preset switching works, Implementation notes, none (+23 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (22): copy_mono_pcm_chunk_as_stereo(), copy_stereo_pcm_chunk(), _default_output_device(), MixPlayer, ndarray, StemSource, SDL audio playback for preloaded mix PCM., Fill interleaved stereo *out* from frame *read_index* in *pcm*.      Returns ``( (+14 more)

### Community 43 - "Community 43"
Cohesion: 0.12
Nodes (25): _format_sample_line(), OverlayFrameSample, OverlayProfiler, _upload_stats_suffix(), CaptureFixture, MonkeyPatch, Tests for live overlay draw profiling., _sample() (+17 more)

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
Cohesion: 0.09
Nodes (40): Anchor, format_mmss(), RowPresentStyle, ensure_row_surface(), live_upload_signature(), panel_signature(), PanelSignature, Font (+32 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (17): cycle_render_overlay_font(), _has_latin_glyphs(), System font discovery for render overlay tuning., True when *name* provides distinct Latin glyphs (not tofu placeholders)., Sorted Latin-capable pygame/SDL font names on this machine., Font name with ``(position/total)`` when *name* is in the Latin font list., render_overlay_font_display(), render_overlay_system_fonts() (+9 more)

### Community 49 - "Community 49"
Cohesion: 0.23
Nodes (10): Tests for compositor blend mode registry and config parsing., test_cycle_blend_recovers_from_unknown_mode(), test_cycle_blend_steps_backward(), test_cycle_blend_wraps_forward(), test_parse_blend_mode_accepts_all_modes(), test_parse_blend_mode_rejects_unknown(), test_header_toggle_blocked_when_timeline_enabled(), make_controls() (+2 more)

### Community 50 - "Community 50"
Cohesion: 0.20
Nodes (22): _apply_hue(), hue_mix_pct(), hue_rgb(), HueState, is_voiced_pitch(), lerp_hue(), pitch_to_hue(), Per-layer hue tint from vocal pitch (vocals only). (+14 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (42): dir_has_presets(), directory_display(), list_navigable_dirs(), navigable_parent(), _path_at_or_below(), playlist_at_dir(), Path, True when any ``.milk`` preset exists anywhere under ``path``. (+34 more)

### Community 52 - "Community 52"
Cohesion: 0.12
Nodes (24): _expand_layer_1(), _mutate_effects_expanded(), _mutate_focus_navigation(), _mutate_layer_z_order(), _mutate_move_mode_without_confirm(), _mutate_preset_path(), _mutate_preset_switching(), _mutate_render_overlay_display_time() (+16 more)

### Community 53 - "Community 53"
Cohesion: 0.29
Nodes (6): Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, UI Performance Results

### Community 54 - "Community 54"
Cohesion: 0.24
Nodes (23): load_manifest(), manifest_path(), mix_path(), ProjectManifest, Path, Project manifest (project.yaml) for Cleave projects., Update ``project.yaml`` *slug* and optional ``restored-from`` provenance., resolve_mix_path() (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.29
Nodes (5): ndarray, StemSource, Preloaded float32 PCM for *stem* (mono 1D or interleaved stereo)., Channel count for *stem* (1 mono, 2 interleaved stereo)., Return per-channel *n_samples* of float32 PCM from *t_sec*, zero-padded past end

### Community 56 - "Community 56"
Cohesion: 0.16
Nodes (23): _cue_modifies_armed_stem(), layer_visible_at(), _merge_cues_at_same_t(), punch_replace(), StemSource, Timeline cue evaluation and editing for per-slot layer visibility., should_accept_toggle(), stem_abbreviation() (+15 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (43): CleaveConfig, preset_browse_floor(), PresetPlaylist, Scan Milkdrop preset anchors into playlists and sync config selections., Scan one preset playlist per configured layer., Lowest directory this layer may ascend to when browsing presets., scan_all_layers(), build_runtime_base() (+35 more)

### Community 58 - "Community 58"
Cohesion: 0.39
Nodes (8): Return the VALUE-role color for a row (before label/value split rendering)., _row_bg_color(), _row_has_tree_focus(), _row_highlight_color(), _row_value_color(), _track_disabled(), test_row_value_color_dim_for_focused_empty_preset(), test_main_tree_rows_not_highlighted_when_timeline_submenu_focused()

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (6): minimal_project(), minimal_signals_json_path(), Path, _pygame_session(), Shared pytest fixtures for Cleave tests., Initialize pygame once for control and overlay tests.

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (65): preset_filename_display(), Current preset filename with position, or empty-state label., ConfigSaveController, Path, Dirty tracking, save dialogs, and deferred quit., Return True once when quit was deferred (e.g. Don't save from unsaved dialog)., Handle a quit request. Return True when the app should exit now., PlaybackState (+57 more)

### Community 61 - "Community 61"
Cohesion: 0.09
Nodes (37): Compositor blend mode names (no OpenGL / pygame dependency)., Focus-driven live tuning input for the Milkdrop visualizer overlay., _handle_global_keydown(), Layered keyboard dispatch for the live tuning overlay., Global shortcuts. True = handled, False = quit, None = pass through., add_current_preset_key_pressed(), mod_ctrl(), mod_shift() (+29 more)

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (25): _overlay_subimage_y(), Map top-left *dest_y* to glTexSubImage2D's bottom-origin row., Map layer opacity to glColor4f for the active layer blend mode.          GL_MODU, _make_overlay_compositor(), _make_surface(), Surface, Tests for layer opacity mapping in the GL compositor., Runtime fallback blend is black-key; opacity must scale RGB. (+17 more)

### Community 63 - "Community 63"
Cohesion: 0.31
Nodes (17): preview_layer_size(), preview_sizes_for_session(), VisualizerRenderMode, _requested_scale(), _cfg(), _layer_cfg(), Tests for live preview layer resolution from render mode and z-order., _session() (+9 more)

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (15): Path, Helpers for per-layer user-defined preset lists., Format a user preset row label, numbering duplicate paths in the list., Return destination path and whether the source file must be copied., resolve_user_preset_dest(), _same_preset_file(), _unique_copy_dest(), user_preset_item_display_name() (+7 more)

### Community 66 - "Community 66"
Cohesion: 0.24
Nodes (17): _controls_with_playlist(), _make_sibling_dir_tree(), _preset_dir_row(), _preset_row(), Return (preset_root, sibling_dirs) each with at least one .milk file., test_backspace_at_preset_root_is_noop(), test_ctrl_left_at_preset_root_is_noop(), test_directory_ctrl_arrows_descend_and_ascend() (+9 more)

### Community 67 - "Community 67"
Cohesion: 0.40
Nodes (6): render_visibility_icon(), track_header_prefix_width(), test_solo_visibility_icon_same_width_as_normal(), test_track_header_prefix_width_matches_visibility_icon(), test_solo_visibility_icon_disabled_stem_uses_value_not_disabled(), test_solo_visibility_icon_uses_red_background()

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): `cleave`, `cleave` a track, Cleave effects, CLI, Compositing, Download Some Milkdrop Presets, Layer visibility timeline, Post-processing fade (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.24
Nodes (10): all_stem_sources(), effect_row_count(), StemSource, validate_effect_entry(), Tests for the per-stem cleave effects registry., test_all_stem_sources_have_rosters(), test_effect_roster_per_stem(), test_full_mix_roster_uses_full_mix_signal_stem() (+2 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (20): HelpOverlay, Font, HelpContent, Surface, Read-only help panel anchored top-right; visibility from session state., help_content_signature(), help_upload_signature(), HelpContentSignature (+12 more)

### Community 71 - "Community 71"
Cohesion: 0.21
Nodes (16): fade_alpha(), Shared easing helpers for visual fades and transitions., Return combined fade multiplier in [0, 1] using smoothstep easing., smoothstep(), live_frame_fade_alpha(), Live render post-FX fade for the visualizer., Tests for cleave.easing., test_fade_alpha_combined() (+8 more)

### Community 73 - "Community 73"
Cohesion: 0.23
Nodes (17): fit_counter_label_to_width(), fit_path_label_to_width(), fit_text_to_width(), Font, Text fitting helpers for overlay labels., Shorten text with a trailing ellipsis until it fits max_px., Shorten a path for overlay width; keep the tail (subdir + filename)., Shorten a path or filename to max_px; preserve a trailing ``(N/TOTAL)`` counter. (+9 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (7): clamp_ui_fade(), clamp_ui_width(), PanelNotificationHost, Pinned header notification timing for the live tuning panel., Single-slot notification state with monotonic expiry., Mutations for settings rows., SettingsControls

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (18): 1. Full uncached redraw every frame, 2. Per-row CPU cost is high, 3. All visible rows are built even when scrolled off-screen, 4. GL texture upload every frame, 5. `blit_tint` allocates per focused row, 6. View state and layout rebuilt every frame, 7. Full-viewport overlay clear, 8. FPS feedback loop (secondary) (+10 more)

### Community 77 - "Community 77"
Cohesion: 0.39
Nodes (8): _mock_lib(), Tests for cleave.projectm PCM feeding., test_feed_pcm_chunks_above_max_samples(), test_feed_pcm_scales_by_beat_sensitivity(), test_feed_pcm_skips_empty(), test_feed_pcm_stereo_chunks_on_even_boundaries(), test_flush_pcm_uses_last_channel_layout(), test_set_beat_sensitivity_clamps_and_stores()

### Community 78 - "Community 78"
Cohesion: 0.28
Nodes (8): _bind_functions(), _library_candidates(), _pkg_config_candidates(), ProjectMPlaylistLibraryError, CDLL, ctypes wrapper for libprojectM playlist library., libprojectM playlist shared library not found or failed to load., test_bind_functions_requires_symbols()

### Community 79 - "Community 79"
Cohesion: 0.06
Nodes (46): Save and quit orchestration for live tuning., ModalHost, ModalKind, ModalOption, ModalRequest, ModalViewState, draw(), _draw_message() (+38 more)

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Architecture improvements, Phase 1 - Cache `build_row_layout` per frame, Phase 2 - Decouple FPS from transport color; route fps through the view builder, Phase 3 - Use `RowDescriptor` as the focus cursor, Phase 4 - Unified focus model for the timeline bridge, Phase 5 - Split overlay into layout/nav and draw modules

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (52): _make_controls(), _row(), test_build_view_state_passes_fps(), test_ctrl_enter_toggles_lock(), test_ctrl_quick_nav_does_not_affect_normal_up_down(), test_default_focus_stays_on_transport(), test_disable_auto_collapses_sub_rows(), test_disabled_track_can_expand_sub_rows() (+44 more)

### Community 85 - "Community 85"
Cohesion: 0.18
Nodes (9): _overlay_surface_rgba(), _OverlaySlotState, Surface, RGBA pixel bytes with Y flipped for OpenGL upload., Read RGBA pixels from the default framebuffer for ffmpeg rawvideo., Current GL texture size for *slot* (0, 0) when not allocated yet., Allocate or grow a slot texture; capacity never shrinks until destroy()., Upload a pygame surface region into a stable slot texture. (+1 more)

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (4): Clear to background and stack *layers* bottom-to-top., Multiply content-target RGB by *alpha* (render fade in/out)., Draw *texture_id* onto the content FBO with SRCALPHA blending., test_lerp_tint_rgb_scales_hue_mix()

### Community 87 - "Community 87"
Cohesion: 0.20
Nodes (9): Goals and budget, Independent review: findings beyond the first review, Live tuning UI performance plan, Phase 1: Measurement harness and hidden-panel guardrails, Phase 2: Compute layout and view state once per frame, Phase 3: Panel signature, row cache, and retained panel surface, Phase 4: Stable-size GPU upload, Phase 5: Decouple projectM fps from UI-loaded display fps (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.20
Nodes (5): LayerFbo, BlendMode, Off-screen RGBA framebuffer for one compositor layer., Configure GL blend for stacking layer FBOs onto the output framebuffer., Stable GL overlay texture bucket (one texture per slot).

### Community 89 - "Community 89"
Cohesion: 0.26
Nodes (10): ndarray, Resample native-rate analysis frames to a uniform 100 Hz grid., Linearly interpolate *values* onto a uniform 100 Hz time grid.      Grid covers, resample_to_100hz(), Tests for cleave.resample., test_resample_boundary_excludes_endpoint(), test_resample_empty_duration_returns_empty_array(), test_resample_linear_interpolation_at_known_points() (+2 more)

### Community 90 - "Community 90"
Cohesion: 0.07
Nodes (51): _row_text(), _confirm_modal_yes(), _expand_settings_ui(), _focus_index(), _make_controls_with_manager(), _make_playlist(), _mutate_dirty(), Unit-style tests for live tuning controls (no Milkdrop window). (+43 more)

### Community 91 - "Community 91"
Cohesion: 0.43
Nodes (7): StemSource, stem_control_label(), stem_overlay_header(), Tests for stem source display helpers., test_display_helpers_cover_all_stem_sources(), test_stem_control_label(), test_stem_overlay_header()

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (8): bar_segments_for_row(), _clip_segments(), Visibility segments for one timeline row, including live record preview., Return ``(start_t, end_t, visible)`` segments for *slot* over ``[0, duration_sec, visibility_segments(), test_visibility_segments_default_only(), test_visibility_segments_from_cues(), test_visibility_segments_other_stem_unchanged_across_unrelated_cue()

### Community 94 - "Community 94"
Cohesion: 0.04
Nodes (85): Offline render output frame rate from config., render_fps(), GlPostProcess, GPU post-processing (bloom) via moderngl sharing the active pygame GL context., Separable bloom pass on an existing layer FBO texture., Attach to the current pygame OpenGL context., load_stem_pcm(), Path (+77 more)

### Community 95 - "Community 95"
Cohesion: 0.36
Nodes (10): _mock_lib(), Path, Tests for cleave.projectm_playlist ctypes bindings., test_connect_installs_instant_load_callback(), test_create_connect_add_path_set_shuffle_destroy(), test_destroy_clears_preset_load_callback(), test_destroy_disconnects_before_free(), test_item_roundtrip_with_real_library() (+2 more)

### Community 102 - "Community 102"
Cohesion: 0.08
Nodes (38): allow_overwrite_for_path(), config_path_display(), Path, Active config path for the config header row (truncation happens at draw time)., Hide overwrite only for the repo-root template cleave-viz.yaml., _choose_overwrite(), _choose_save_as_new(), _config_header_row() (+30 more)

### Community 103 - "Community 103"
Cohesion: 0.40
Nodes (5): _bind_functions(), ProjectMLibraryError, CDLL, libprojectM shared library not found or failed to load., OSError

### Community 105 - "Community 105"
Cohesion: 0.12
Nodes (9): _gl_name(), GlCompositor, Stack tiered layer FBO textures into a content FBO, then present to display., Initialize GL state after a pygame OPENGL context exists., Resize an existing layer FBO, preserving compositor state fields., Destroy the named FBO and remove it from the compositor stack., Blit content FBO to the default framebuffer at display size., Return overlay texture realloc count since last consume and reset. (+1 more)

## Knowledge Gaps
- **187 isolated node(s):** `Requirements`, `Setup`, `Download Some Milkdrop Presets`, ``cleave` a track`, `Project Directory` (+182 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TuningSession` connect `Community 28` to `Community 0`, `Community 6`, `Community 8`, `Community 9`, `Community 11`, `Community 12`, `Community 14`, `Community 15`, `Community 27`, `Community 33`, `Community 34`, `Community 35`, `Community 40`, `Community 48`, `Community 49`, `Community 50`, `Community 57`, `Community 60`, `Community 61`, `Community 63`, `Community 66`, `Community 74`, `Community 79`, `Community 84`, `Community 90`, `Community 94`, `Community 98`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Why does `GlCompositor` connect `Community 105` to `Community 35`, `Community 38`, `Community 10`, `Community 85`, `Community 86`, `Community 88`, `Community 94`, `Community 93`, `Community 62`, `Community 57`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **Why does `TuningControls` connect `Community 6` to `Community 0`, `Community 2`, `Community 4`, `Community 9`, `Community 11`, `Community 15`, `Community 16`, `Community 25`, `Community 28`, `Community 33`, `Community 35`, `Community 47`, `Community 48`, `Community 49`, `Community 52`, `Community 57`, `Community 60`, `Community 61`, `Community 66`, `Community 74`, `Community 79`, `Community 84`, `Community 90`, `Community 94`, `Community 98`, `Community 102`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Are the 28 inferred relationships involving `RowDescriptor` (e.g. with `TuningControls` and `MainFocus`) actually correct?**
  _`RowDescriptor` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TuningControls` (e.g. with `LiveVisualizerRuntime` and `RenderVisualizerRuntime`) actually correct?**
  _`TuningControls` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `TuningViewState` (e.g. with `TuningControls` and `FocusContext`) actually correct?**
  _`TuningViewState` has 29 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cleave: stem-driven music visualizer.`, `Orchestrate per-stem feature extraction and write signals.json.`, `Backup and restore Cleave project directories as gzip tar archives.` to the rest of the system?**
  _575 weakly-connected nodes found - possible documentation gaps or missing edges._