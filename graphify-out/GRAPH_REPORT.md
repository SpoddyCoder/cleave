# Graph Report - cleave  (2026-06-28)

## Corpus Check
- 165 files · ~114,974 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3148 nodes · 10562 edges · 84 communities (82 shown, 2 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 435 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `94db291a`
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

## God Nodes (most connected - your core abstractions)
1. `RowDescriptor` - 271 edges
2. `TuningControls` - 236 edges
3. `_keydown()` - 175 edges
4. `_make_controls()` - 175 edges
5. `TuningViewState` - 158 edges
6. `TuningSession` - 156 edges
7. `TimelineCue` - 128 edges
8. `_desc()` - 97 edges
9. `RowKind` - 85 edges
10. `CleaveConfig` - 83 edges

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

## Communities (84 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (97): hard_cut_enabled_display(), preset_start_clean_display(), ui_fade_display(), _has_latin_glyphs(), System font discovery for render overlay tuning., True when *name* provides distinct Latin glyphs (not tofu placeholders)., Sorted Latin-capable pygame/SDL font names on this machine., Font name with ``(position/total)`` when *name* is in the Latin font list. (+89 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (86): format_fps_display(), Wall-clock frame rate measurement for the live visualizer., timeline_viewport_reserve_px(), panel_content_max_width(), panel_fps_layout(), PanelScrollMetrics, Return the VALUE-role color for a row (before label/value split rendering)., Top-right FPS readout in the header region; shifts left for the scrollbar. (+78 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (65): Compositor blend mode names (no OpenGL / pygame dependency)., OpenGL FBO layer stack and black-key compositing., PresetPlaylist, Shared frame tick for live and render. Returns updated was_paused., tick_frame_core(), apply_effect_modifiers(), _apply_layer_bloom(), _apply_layer_grit() (+57 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (89): dump_yaml(), ensure_project_viz_config(), _expand_path(), find_config_path(), load_config(), _parse_layers(), _parse_paths(), project_viz_config_path() (+81 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (34): Event, Path, Return True when a modal dialog consumed the event., Handle a key down event for the main tuning tree., Keyboard focus machine for the live tuning tree overlay., TuningControls, _expand_render_overlay(), _expand_render_post_fx() (+26 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (79): effect_help_description(), effect_help_title(), description_section(), DescriptionSection, HelpSection, _keyboard_section(), layer_section(), _preset_dir_section() (+71 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (72): _bar_width(), _icon_height(), material_font(), Font, Surface, Material Icons rendering for the live tuning overlay., render_glyph(), render_transport_icons() (+64 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (70): _row_text(), _expand_settings(), _expand_settings_ui(), _focus_index(), _header_row(), _make_controls(), _mutate_dirty(), Unit-style tests for live tuning controls (no Milkdrop window). (+62 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (63): CleaveConfig, LayerConfig, PathsConfig, Return layers in compositor draw order (bottom-to-top)., _load_original_dict(), next_unnamed_path(), _path_to_yaml_str(), persisted_session_signature() (+55 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (66): RenderPostFxConfig, _build_render_overlay_background(), _build_render_overlay_border(), _build_render_overlay_config(), _build_render_overlay_text_block(), clamp_upscale(), default_render_overlay_config(), default_render_overlay_runtime_values() (+58 more)

### Community 10 - "Community 10"
Cohesion: 0.09
Nodes (63): RenderOverlayBackgroundConfig, RenderOverlayBorderConfig, RenderOverlayConfig, RenderOverlayTextBlockConfig, _composite_render_overlay(), ensure_render_overlay_panel(), Surface, Shared content-frame finish for live play and offline render.  After layer compo (+55 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (29): Focus-driven live tuning input for the Milkdrop visualizer overlay., add_current_preset_key_pressed(), mod_ctrl(), mod_shift(), Hold-to-repeat controller for pygame tuning and navigation keys., True for + keys that add the current preset in user-defined mode., snapshot_monitor_from_output(), current_sec() (+21 more)

### Community 12 - "Community 12"
Cohesion: 0.06
Nodes (20): _gl_name(), GlCompositor, LayerFbo, BlendMode, Surface, Stack tiered layer FBO textures into a content FBO, then present to display., Initialize GL state after a pygame OPENGL context exists., Configure GL blend for stacking layer FBOs onto the output framebuffer. (+12 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (54): _nan_to_null(), ndarray, Path, Orchestrate per-stem feature extraction and write signals.json., run_analyse(), _stem_duration_sec(), BassSignals, extract_bass() (+46 more)

### Community 14 - "Community 14"
Cohesion: 0.11
Nodes (56): TimelineCue, _anchor_visibility_for_slot(), armed_recording_defaults(), armed_recording_visible(), build_record_punch_cues(), build_timeline_view_state(), committed_visible_outside_punch(), effective_layer_enabled() (+48 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (57): _mutate_timeline_arm(), _mutate_timeline_preview_pause(), _mutate_timeline_recording_start(), _make_timeline_controls(), Unit tests for timeline panel keyboard controls., test_backward_seek_during_record_fills_and_expands_punch_start(), test_ctrl_enter_noop_while_recording(), test_ctrl_seek_when_not_recording() (+49 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (53): _append_section_nodes(), _append_track_effect_rows(), _append_user_preset_rows(), _assign_expand_indent_depth(), _assign_indent_depth(), _build_row_tree_indent_depth(), _build_section_header_parent_map(), _collect_expand_sections() (+45 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (49): bar_tick_times_for_row(), cue_times_for_stem(), prune_expired_arm_flashes(), Cue times that change visibility for *slot* within ``[0, duration_sec]``., Cue tick times for one timeline row., Bottom-anchored timeline panel drawn over the composited frame., Last draw bar metrics: ``(bar_left, bar_width, eye_slot_w)`` in panel coordinate, Last draw layout: ``(row_index, x, y, w, h, stem)`` in panel coordinates. (+41 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (52): _archive_top_level_dir(), backup_project(), confirm_overwrite(), _is_archive_file_path(), Path, Backup and restore Cleave project directories as gzip tar archives., Extract a project archive into :func:`~cleave.paths.projects_dir`., Resolve a backup destination to the output archive path. (+44 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (32): Row layout and visibility/navigability for the live tuning overlay., Row indices drawn in the panel (sub-rows hidden when collapsed)., Row indices reachable via Up/Down (sub-rows skipped when collapsed)., Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers., row_draw_visible(), row_navigable(), RowLayout, _sub_row_expanded() (+24 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (53): _mutate_layer_z_order(), _desc(), _keydown(), Event, test_beat_sensitivity_clamps(), test_ctrl_enter_toggles_lock(), test_ctrl_quick_nav_blocked_during_move_mode(), test_ctrl_quick_nav_cycles_headers_and_transport() (+45 more)

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (43): Anchor, ModalViewState, draw(), _draw_message(), _draw_options(), draw_rect(), _measure_options(), _measure_panel() (+35 more)

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (45): load_mix_pcm(), load_wav_pcm_44k(), ndarray, Path, Shared PCM loading for stems and mix playback., Load a wav as float32 PCM at 44.1 kHz in native channel layout., Load mix audio as interleaved stereo float32 at 44.1 kHz., _resample_stereo_interleaved() (+37 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): 1.1 Replace the `LAYER_SLOTS` constant, 1.2 Relax `parse_layers_section`, 1.3 Relax `parse_layer_z_order_section`, 1.4 Update `persist_layers`, 1.5 Update `parse_timeline_section`, 1.6 `CleaveConfig` — un-freeze and use `list`, 2.1 `GlCompositor.remove_layer_fbo(name: str)`, 2.2 `LayerFramePipeline.build_single` (+40 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (43): ArgumentParser, CaptureFixture, build_parser(), cmd_backup(), cmd_play(), cmd_render(), cmd_restore(), cmd_separate() (+35 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (27): FocusCursor, FocusContext, Shared focus and view-state access for tuning sub-controllers., build_focus_ring(), cursor_main_descriptor(), cursor_timeline_row(), cursor_timeline_submenu_focused(), MainFocus (+19 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (28): _gl_bool_vector(), _gl_int(), _PingPongBuffers, _prepare_fixed_function_gl(), GPU post-processing (bloom) via moderngl sharing the active pygame GL context., Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)., Bloom *texture_id* in-place; returns the (unchanged) texture id., Film grain + chromatic aberration in-place; returns texture id. (+20 more)

### Community 27 - "Community 27"
Cohesion: 0.14
Nodes (43): Return the repository root directory., repo_root(), Ensure *project_dir* is ready for offline render; return resolved path., _resolve_segment(), validate_render_project(), default_render_overlay_runtime(), default_render_post_fx_runtime(), render_post_fx_runtime_from_cfg() (+35 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (35): GlPostProcess, Separable bloom pass on an existing layer FBO texture., Attach to the current pygame OpenGL context., StemPcmBank, _init_compositor_and_post(), init_gl_resources_cheap(), init_gl_resources_heavy(), init_gl_resources_render() (+27 more)

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (35): _list_to_array(), load_signals(), ndarray, Path, Load and sample per-stem signals from signals.json., resolve_signals_path(), Signals, _validate_signals_data() (+27 more)

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (39): apply_field_horizontal(), composite_header_prefix_part(), composite_header_suffix_part(), expand_subheader_prefix(), _full_line_branch_depth(), full_line_prefix(), labeled_row_prefix(), Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth. (+31 more)

### Community 31 - "Community 31"
Cohesion: 0.14
Nodes (25): clamp_effect_pct(), Shared clamps and per-driver pulse envelope constants., _apply_flare(), FlareBurstState, Per-layer bloom flare: onset delta and threshold burst (drums only)., _update_flare(), Per-layer flash overlay: threshold burst from normalized stem signals., GritState (+17 more)

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (14): _bind_functions(), _get_lib(), _library_candidates(), _pkg_config_candidates(), ProjectM, ProjectMLibraryError, c_void_p, CDLL (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (35): VisualizerApp, TimelineFocus, draw_loading_screen(), _loading_font_get(), Font, Centered loading message during visualizer boot., _heavy_init_side_effect(), _key_handler_for_session() (+27 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (35): Fixed eye slot width (glyph plus horizontal pad for solo background)., visibility_icon_slot_width(), arm_abbrev_flash_active(), arm_abbrev_flash_visible(), armed_abbrev_bg_visible(), bar_segments_for_row(), _clip_segments(), layer_num_prefix() (+27 more)

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (34): active_auto_preset_path(), apply_preset_switching(), _apply_projectm_timing(), _auto_preset_loaded_callback(), Path, PresetSwitchingMode, PresetSwitchingScope, Apply per-layer preset switching mode to live ProjectM instances. (+26 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (34): Return the stem wav directory inside a Cleave project., Map stem names to wav paths under a Cleave project., stem_paths(), stems_dir(), project_stems_complete(), Path, Run Demucs stem separation and write stem wavs into a Cleave project., Separate and/or analyse a Cleave project from an audio file or project slug. (+26 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (35): `cleave/analyse.py` and `cleave/extract.py`, `cleave/config.py`, `cleave/config_schema.py`, `cleave/effects/registry.py`, `cleave/effects/runtime.py`, `cleave/extract.py`, `cleave/preset_playlist.py`, `cleave/stem_pcm.py` (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (35): _expand_layer_1(), _mutate_effects_expanded(), _mutate_focus_navigation(), _mutate_move_mode_without_confirm(), _mutate_preset_path(), _mutate_preset_switching(), _mutate_render_overlay_display_time(), _mutate_solo_slot() (+27 more)

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (32): LiveVisualizerRuntime, Fully initialized live visualizer runtime., dispatch_keydown(), dispatch_keyup(), dispatch_should_notify_overlay(), _handle_global_keydown(), key_handler_for_runtime(), Event (+24 more)

### Community 40 - "Community 40"
Cohesion: 0.11
Nodes (31): clamp_beat_sensitivity(), clamp_easter_egg(), new_layer_config(), parse_blend_mode(), _parse_effects(), parse_layers_section(), _parse_stem(), persist_layers() (+23 more)

### Community 41 - "Community 41"
Cohesion: 0.06
Nodes (31): Architecture alignment, Config (sketch), Decisions, Dependencies, Feature scope, How libprojectM preset switching works, Implementation notes, none (+23 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (22): copy_mono_pcm_chunk_as_stereo(), copy_stereo_pcm_chunk(), _default_output_device(), MixPlayer, ndarray, StemSource, SDL audio playback for preloaded mix PCM., Fill interleaved stereo *out* from frame *read_index* in *pcm*.      Returns ``( (+14 more)

### Community 43 - "Community 43"
Cohesion: 0.14
Nodes (14): HelpOverlay, Font, HelpContent, Surface, Read-only help panel anchored top-right; visibility from session state., Surface, GL upload path for live tuning and timeline overlays., _union_rect() (+6 more)

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
Cohesion: 0.13
Nodes (17): Save and quit orchestration for live tuning., ModalHost, ModalKind, ModalOption, ModalRequest, Event, Centered confirm modal host for live tuning UI., Return True when the event is consumed (including while blocking). (+9 more)

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (10): cycle_render_overlay_font(), Mutations for render overlay rows., RenderOverlayControls, Tests for render overlay system font discovery., test_cycle_render_overlay_font_backward(), test_cycle_render_overlay_font_empty_list_keeps_current(), test_cycle_render_overlay_font_forward(), test_cycle_render_overlay_font_unknown_starts_at_first() (+2 more)

### Community 49 - "Community 49"
Cohesion: 0.13
Nodes (24): _CleaveHelpFormatter, Offline render output frame rate from config., render_fps(), build_runtime_base(), Path, load_stem_signals(), Path, Visualizer bootstrap: config resolution, paths, and preset loading. (+16 more)

### Community 50 - "Community 50"
Cohesion: 0.17
Nodes (25): _apply_hue(), hue_mix_pct(), hue_rgb(), HueState, is_voiced_pitch(), lerp_hue(), pitch_to_hue(), Per-layer hue tint from vocal pitch (vocals only). (+17 more)

### Community 51 - "Community 51"
Cohesion: 0.17
Nodes (27): preset_browse_floor(), preset_filename_display(), Build a playlist from a .milk file or a directory of presets., Current preset filename with position, or empty-state label., Scan one preset playlist per configured layer., Lowest directory this layer may ascend to when browsing presets., scan_all_layers(), scan_preset_playlist() (+19 more)

### Community 52 - "Community 52"
Cohesion: 0.11
Nodes (28): allow_overwrite_for_path(), config_path_display(), Path, Active config path for the config header row (truncation happens at draw time)., Hide overwrite only for the repo-root template cleave-viz.yaml., _choose_overwrite(), _choose_save_as_new(), _config_header_row() (+20 more)

### Community 53 - "Community 53"
Cohesion: 0.17
Nodes (25): data_dir(), default_project_config(), project_slug(), Path, Filesystem layout for Cleave data and projects., Return Cleave data root (``CLEAVE_DATA`` or the repo / package root)., Raise :class:`ValueError` when *slug* is not a safe project identifier., Resolve a project slug or path to an existing project directory.      * Slug: `` (+17 more)

### Community 54 - "Community 54"
Cohesion: 0.24
Nodes (23): load_manifest(), manifest_path(), mix_path(), ProjectManifest, Path, Project manifest (project.yaml) for Cleave projects., Update ``project.yaml`` *slug* and optional ``restored-from`` provenance., resolve_mix_path() (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (15): dir_has_presets(), directory_display(), list_navigable_dirs(), milk_files_in_dir(), navigable_parent(), _path_at_or_below(), Path, Scan Milkdrop preset anchors into playlists and sync config selections. (+7 more)

### Community 56 - "Community 56"
Cohesion: 0.16
Nodes (23): _cue_modifies_armed_stem(), layer_visible_at(), _merge_cues_at_same_t(), punch_replace(), StemSource, Timeline cue evaluation and editing for per-slot layer visibility., should_accept_toggle(), stem_abbreviation() (+15 more)

### Community 57 - "Community 57"
Cohesion: 0.16
Nodes (21): _apply_flash(), flash_alpha(), flash_threshold(), FlashBurstState, update_burst(), _update_flash(), _layer_runtime(), Tests for flash burst triggers, decay, and EffectRuntime integration. (+13 more)

### Community 58 - "Community 58"
Cohesion: 0.17
Nodes (18): aberration_px(), _apply_grit(), grit_strength(), handler_for(), Any, EffectRuntime, Owns per-row envelope state; tick updates signals then exposes modifiers., Advance envelope state from signals (call once per frame). (+10 more)

### Community 59 - "Community 59"
Cohesion: 0.14
Nodes (17): _ActiveRepeat, delete_key_pressed(), KeyRepeatController, Event, True for forward-delete keys (keysym or scancode; not Backspace)., Arms on KEYDOWN, disarms on KEYUP; tick() fires repeat callbacks while held., _arm(), Tests for cleave.viz.key_repeat. (+9 more)

### Community 60 - "Community 60"
Cohesion: 0.13
Nodes (5): ConfigSaveController, Path, Dirty tracking, save dialogs, and deferred quit., Return True once when quit was deferred (e.g. Don't save from unsaved dialog)., Handle a quit request. Return True when the app should exit now.

### Community 61 - "Community 61"
Cohesion: 0.21
Nodes (16): fade_alpha(), Shared easing helpers for visual fades and transitions., Return combined fade multiplier in [0, 1] using smoothstep easing., smoothstep(), live_frame_fade_alpha(), Live render post-FX fade for the visualizer., Tests for cleave.easing., test_fade_alpha_combined() (+8 more)

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (12): Map layer opacity to glColor4f for the active layer blend mode.          GL_MODU, Tests for layer opacity mapping in the GL compositor., Runtime fallback blend is black-key; opacity must scale RGB., Flash draws a solid quad with add blend; strength must be glColor alpha., test_flash_rgba_puts_strength_in_alpha_for_add_blend(), test_layer_gl_color_add_keeps_hue_in_rgb_and_opacity_in_alpha(), test_layer_gl_color_bakes_opacity_into_rgb(), test_layer_gl_color_full_opacity_preserves_tint() (+4 more)

### Community 63 - "Community 63"
Cohesion: 0.27
Nodes (18): preview_layer_size(), preview_sizes_for_session(), VisualizerRenderMode, Live preview layer resolution from visualizer render mode and z-order., _requested_scale(), _cfg(), _layer_cfg(), Tests for live preview layer resolution from render mode and z-order. (+10 more)

### Community 64 - "Community 64"
Cohesion: 0.19
Nodes (18): bloom_strength(), flare_triggered(), update_burst(), update_smoothed(), _layer_runtime(), Tests for flare burst triggers, decay, and EffectRuntime integration., _signals_with_stem_key(), test_bloom_strength_scales_with_depth_and_burst() (+10 more)

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (15): Path, Helpers for per-layer user-defined preset lists., Format a user preset row label, numbering duplicate paths in the list., Return destination path and whether the source file must be copied., resolve_user_preset_dest(), _same_preset_file(), _unique_copy_dest(), user_preset_item_display_name() (+7 more)

### Community 66 - "Community 66"
Cohesion: 0.24
Nodes (17): _controls_with_playlist(), _make_sibling_dir_tree(), _preset_dir_row(), _preset_row(), Return (preset_root, sibling_dirs) each with at least one .milk file., test_backspace_at_preset_root_is_noop(), test_ctrl_left_at_preset_root_is_noop(), test_directory_ctrl_arrows_descend_and_ascend() (+9 more)

### Community 67 - "Community 67"
Cohesion: 0.20
Nodes (15): effective_opacity(), update_envelope(), test_grit_envelope_uses_pulse_decay_gain(), _layer_runtime(), Tests for pulse effect sampling, opacity, and runtime wiring., test_effect_runtime_all_stems_pulse_modulate(), test_effect_runtime_bass_multi_pulse_stacking(), test_effect_runtime_pulse_driver_modulates_opacity() (+7 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): `cleave`, `cleave` a track, Cleave effects, CLI, Compositing, Download Some Milkdrop Presets, Layer visibility timeline, Post-processing fade (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.25
Nodes (11): all_stem_sources(), effect_roster(), effect_row_count(), StemSource, validate_effect_entry(), Tests for the per-stem cleave effects registry., test_all_stem_sources_have_rosters(), test_effect_roster_per_stem() (+3 more)

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (5): clamp_ui_fade(), clamp_ui_width(), Settings row mutations for live tuning., Mutations for settings rows., SettingsControls

### Community 71 - "Community 71"
Cohesion: 0.36
Nodes (10): _mock_lib(), Path, Tests for cleave.projectm_playlist ctypes bindings., test_connect_installs_instant_load_callback(), test_create_connect_add_path_set_shuffle_destroy(), test_destroy_clears_preset_load_callback(), test_destroy_disconnects_before_free(), test_item_roundtrip_with_real_library() (+2 more)

### Community 72 - "Community 72"
Cohesion: 0.23
Nodes (10): Tests for compositor blend mode registry and config parsing., test_cycle_blend_recovers_from_unknown_mode(), test_cycle_blend_steps_backward(), test_cycle_blend_wraps_forward(), test_parse_blend_mode_accepts_all_modes(), test_parse_blend_mode_rejects_unknown(), test_header_toggle_blocked_when_timeline_enabled(), make_controls() (+2 more)

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (11): _confirm_modal_yes(), _make_controls_with_manager(), _make_playlist(), test_add_layer_confirm_calls_manager(), test_add_layer_row_omitted_at_max(), test_cycle_render_mode_calls_apply_preview_resolutions(), test_delete_layer_at_min_shows_toast(), test_delete_layer_clamps_timeline_focus_row() (+3 more)

### Community 74 - "Community 74"
Cohesion: 0.27
Nodes (10): visibility_icon_prefix_width(), _overlay_font(), Font, test_config_header_truncates_long_paths(), test_fit_row_text_config_and_preset_share_panel_width(), test_preset_row_truncates_long_filenames(), test_track_header_icons_render(), test_track_header_prefix_width_matches_visibility_icon() (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.20
Nodes (10): test_ctrl_preset_steps_by_ten_wrapping(), test_easter_egg_steps_with_standard_and_large_increments(), test_hard_cut_enabled_cycles_and_hides_child_rows(), test_header_toggles_enabled(), test_preset_switching_row_cycles_none_and_projectm(), test_projectm_mode_blocks_preset_browse(), test_render_timeline_enabled_change_callback(), test_shift_right_enters_solo() (+2 more)

### Community 77 - "Community 77"
Cohesion: 0.39
Nodes (8): _mock_lib(), Tests for cleave.projectm PCM feeding., test_feed_pcm_chunks_above_max_samples(), test_feed_pcm_scales_by_beat_sensitivity(), test_feed_pcm_skips_empty(), test_feed_pcm_stereo_chunks_on_even_boundaries(), test_flush_pcm_uses_last_channel_layout(), test_set_beat_sensitivity_clamps_and_stores()

### Community 78 - "Community 78"
Cohesion: 0.29
Nodes (5): ndarray, StemSource, Preloaded float32 PCM for *stem* (mono 1D or interleaved stereo)., Channel count for *stem* (1 mono, 2 interleaved stereo)., Return per-channel *n_samples* of float32 PCM from *t_sec*, zero-padded past end

### Community 79 - "Community 79"
Cohesion: 0.25
Nodes (3): PanelNotificationHost, Pinned header notification timing for the live tuning panel., Single-slot notification state with monotonic expiry.

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Architecture improvements, Phase 1 - Cache `build_row_layout` per frame, Phase 2 - Decouple FPS from transport color; route fps through the view builder, Phase 3 - Use `RowDescriptor` as the focus cursor, Phase 4 - Unified focus model for the timeline bridge, Phase 5 - Split overlay into layout/nav and draw modules

## Knowledge Gaps
- **159 isolated node(s):** `Requirements`, `Setup`, `Download Some Milkdrop Presets`, ``cleave` a track`, `Project Directory` (+154 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TuningSession` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 7`, `Community 8`, `Community 10`, `Community 11`, `Community 14`, `Community 15`, `Community 25`, `Community 27`, `Community 28`, `Community 31`, `Community 33`, `Community 35`, `Community 39`, `Community 40`, `Community 47`, `Community 48`, `Community 50`, `Community 57`, `Community 58`, `Community 60`, `Community 63`, `Community 64`, `Community 66`, `Community 67`, `Community 70`, `Community 72`, `Community 73`, `Community 76`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `TuningControls` connect `Community 4` to `Community 0`, `Community 2`, `Community 6`, `Community 7`, `Community 8`, `Community 11`, `Community 15`, `Community 16`, `Community 20`, `Community 25`, `Community 28`, `Community 30`, `Community 31`, `Community 33`, `Community 38`, `Community 39`, `Community 40`, `Community 47`, `Community 48`, `Community 52`, `Community 59`, `Community 60`, `Community 66`, `Community 70`, `Community 72`, `Community 73`, `Community 76`, `Community 79`?**
  _High betweenness centrality (0.081) - this node is a cross-community bridge._
- **Why does `GlCompositor` connect `Community 12` to `Community 33`, `Community 2`, `Community 39`, `Community 10`, `Community 43`, `Community 28`, `Community 62`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `RowDescriptor` (e.g. with `TuningControls` and `MainFocus`) actually correct?**
  _`RowDescriptor` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TuningControls` (e.g. with `LiveVisualizerRuntime` and `RenderVisualizerRuntime`) actually correct?**
  _`TuningControls` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `TuningViewState` (e.g. with `TuningControls` and `FocusContext`) actually correct?**
  _`TuningViewState` has 21 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cleave: stem-driven music visualizer.`, `Orchestrate per-stem feature extraction and write signals.json.`, `Backup and restore Cleave project directories as gzip tar archives.` to the rest of the system?**
  _514 weakly-connected nodes found - possible documentation gaps or missing edges._