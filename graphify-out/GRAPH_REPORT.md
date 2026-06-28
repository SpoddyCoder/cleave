# Graph Report - cleave  (2026-06-28)

## Corpus Check
- 169 files · ~119,256 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3224 nodes · 10780 edges · 103 communities (98 shown, 5 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 445 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `969f71ac`
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

## God Nodes (most connected - your core abstractions)
1. `RowDescriptor` - 273 edges
2. `TuningControls` - 236 edges
3. `_keydown()` - 175 edges
4. `_make_controls()` - 175 edges
5. `TuningViewState` - 160 edges
6. `TuningSession` - 156 edges
7. `TimelineCue` - 128 edges
8. `_desc()` - 97 edges
9. `RowKind` - 85 edges
10. `CleaveConfig` - 83 edges

## Surprising Connections (you probably didn't know these)
- `StubMixPlayer` --uses--> `PathsConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py
- `StubMixPlayer` --uses--> `LayerConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py
- `test_visualizer_display_dimensions()` --calls--> `VisualizerConfig`  [EXTRACTED]
  tests/cleave/test_config.py → cleave/config.py
- `StubMixPlayer` --uses--> `VisualizerConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py
- `StubMixPlayer` --uses--> `CleaveConfig`  [INFERRED]
  tests/support/viz.py → cleave/config.py

## Import Cycles
- 3-file cycle: `cleave/viz/controls.py -> cleave/viz/wiring.py -> cleave/viz/timeline_controls.py -> cleave/viz/controls.py`
- 3-file cycle: `cleave/viz/controls.py -> cleave/viz/row_fields.py -> cleave/viz/row_sections.py -> cleave/viz/controls.py`

## Communities (103 total, 5 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (111): hard_cut_enabled_display(), preset_start_clean_display(), ui_fade_display(), Keyboard focus machine for the live tuning tree overlay., TuningControls, _apply_expand_subheader(), _apply_render_overlay_body_font(), _apply_render_overlay_body_font_size() (+103 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (79): format_fps_display(), panel_fps_layout(), Return the VALUE-role color for a row (before label/value split rendering)., Top-right FPS readout in the header region; shifts left for the scrollbar., Tree-style live tuning panel; holds visible after input, then fades out., Top-left x, y, width, height of the last drawn panel, if any., _row_bg_color(), _row_has_tree_focus() (+71 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (16): Stem layer data class., Unit tests for LayerFramePipeline add/remove helpers., _session(), _stem_layer(), test_apply_preview_resolutions_resizes_when_size_changes(), test_apply_preview_resolutions_skips_when_unchanged(), test_build_preview_resolutions_false_skips_scaling(), test_build_preview_resolutions_true_applies_scaling() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (84): dump_yaml(), ensure_project_viz_config(), _expand_path(), find_config_path(), load_config(), _parse_layers(), _parse_paths(), project_viz_config_path() (+76 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (68): layer_section(), HelpContent, sections_for(), timeline_strip_section(), HelpOverlay, Font, HelpContent, Surface (+60 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (46): _mutate_layer_z_order(), _desc(), _header_row(), _keydown(), Event, test_beat_sensitivity_clamps(), test_ctrl_quick_nav_blocked_during_move_mode(), test_ctrl_quick_nav_cycles_headers_and_transport() (+38 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (21): _row_text(), _expand_settings(), _expand_settings_ui(), _focus_index(), test_cycle_stem_to_full_mix(), test_render_overlay_body_font_size_row(), test_render_overlay_body_header_expand_arrow(), test_render_overlay_header_label_spacing() (+13 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (69): CleaveConfig, LayerConfig, PathsConfig, Return layers in compositor draw order (bottom-to-top)., default_render_overlay_runtime_values(), default_render_post_fx_runtime_values(), _load_original_dict(), next_unnamed_path() (+61 more)

### Community 9 - "Community 9"
Cohesion: 0.06
Nodes (95): Offline render output resolution from config., render_output_size(), RenderOverlayTextBlockConfig, RenderPostFxConfig, _build_render_overlay_background(), _build_render_overlay_border(), _build_render_overlay_config(), _build_render_overlay_text_block() (+87 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (80): RenderOverlayBackgroundConfig, RenderOverlayBorderConfig, RenderOverlayConfig, fade_alpha(), Shared easing helpers for visual fades and transitions., Return combined fade multiplier in [0, 1] using smoothstep easing., smoothstep(), _composite_render_overlay() (+72 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (15): init_playback(), PlaybackState, Playback timing and seek helpers for the visualizer., seek(), toggle_pause(), Keyboard input for the timeline panel overlay., Tests for cleave.viz.playback., test_current_sec_clamps_to_duration() (+7 more)

### Community 12 - "Community 12"
Cohesion: 0.14
Nodes (6): Clear to background and stack *layers* bottom-to-top., Multiply content-target RGB by *alpha* (render fade in/out)., Blit content FBO to the default framebuffer at display size., Read RGBA pixels from the default framebuffer for ffmpeg rawvideo., Draw *texture_id* onto the content FBO with SRCALPHA blending., test_lerp_tint_rgb_scales_hue_mix()

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (39): _nan_to_null(), ndarray, Path, Orchestrate per-stem feature extraction and write signals.json., run_analyse(), _stem_duration_sec(), BassSignals, extract_bass() (+31 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (55): TimelineCue, _anchor_visibility_for_slot(), build_record_punch_cues(), build_timeline_view_state(), committed_visible_outside_punch(), effective_layer_enabled(), FocusCursor, Timeline visibility algebra and per-frame layer enablement. (+47 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (51): _mutate_timeline_arm(), _mutate_timeline_preview_pause(), _mutate_timeline_recording_start(), _make_timeline_controls(), Unit tests for timeline panel keyboard controls., test_ctrl_enter_noop_while_recording(), test_ctrl_seek_when_not_recording(), test_ctrl_space_starts_record_when_paused() (+43 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (57): Row layout and visibility/navigability for the live tuning overlay., Row indices drawn in the panel (sub-rows hidden when collapsed)., Row indices reachable via Up/Down (sub-rows skipped when collapsed)., Row indices for Ctrl+Up/Down: settings, transport, layer, and render headers., row_draw_visible(), row_navigable(), RowLayout, _sub_row_expanded() (+49 more)

### Community 17 - "Community 17"
Cohesion: 0.23
Nodes (29): Bottom-anchored timeline panel drawn over the composited frame., TimelineOverlay, _abbrev_bg_pixel(), _draw(), Surface, Tests for the bottom timeline strip overlay., test_armed_not_recording_abbrev_always_red(), test_armed_recording_abbrev_flashes_with_rec() (+21 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (48): _archive_top_level_dir(), backup_project(), confirm_overwrite(), _is_archive_file_path(), Path, Backup and restore Cleave project directories as gzip tar archives., Extract a project archive into :func:`~cleave.paths.projects_dir`., Resolve a backup destination to the output archive path. (+40 more)

### Community 19 - "Community 19"
Cohesion: 0.16
Nodes (19): Map a sub-row to its section header using the composition tree., section_header_from_section_tree(), Map a sub-row descriptor to its section header for focus fallback., section_header_descriptor(), test_section_header_descriptor_mappings(), Tests for expandable section composition in row_sections., test_layout_includes_conditional_rows_when_predicates_pass(), test_layout_omits_conditional_rows_when_predicate_fails() (+11 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (45): _expand_layer_1(), _expand_render_overlay(), _expand_render_post_fx(), _expand_settings(), _expand_settings_ui(), _mutate_effects_expanded(), _mutate_focus_navigation(), _mutate_move_mode_without_confirm() (+37 more)

### Community 21 - "Community 21"
Cohesion: 0.15
Nodes (19): Anchor, panel_content_max_width_px(), Shared colors and layout constants for Milkdrop live tuning UI panels.  Typograp, Scaled bottom timeline strip height in pixels., Map persisted ui_width (20-200) to scaled panel content max width in pixels., scale_px(), timeline_panel_height_px(), timeline_ui_metrics() (+11 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (42): load_mix_pcm(), load_wav_pcm_44k(), ndarray, Path, Shared PCM loading for stems and mix playback., Load a wav as float32 PCM at 44.1 kHz in native channel layout., Load mix audio as interleaved stereo float32 at 44.1 kHz., _resample_stereo_interleaved() (+34 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): 1.1 Replace the `LAYER_SLOTS` constant, 1.2 Relax `parse_layers_section`, 1.3 Relax `parse_layer_z_order_section`, 1.4 Update `persist_layers`, 1.5 Update `parse_timeline_section`, 1.6 `CleaveConfig` — un-freeze and use `list`, 2.1 `GlCompositor.remove_layer_fbo(name: str)`, 2.2 `LayerFramePipeline.build_single` (+40 more)

### Community 24 - "Community 24"
Cohesion: 0.15
Nodes (43): ArgumentParser, build_parser(), cmd_backup(), cmd_play(), cmd_render(), cmd_restore(), cmd_separate(), _exit_error() (+35 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (40): Compositor blend mode names (no OpenGL / pygame dependency)., FocusCursor, Focus-driven live tuning input for the Milkdrop visualizer overlay., FocusContext, Shared focus and view-state access for tuning sub-controllers., build_focus_ring(), cursor_main_descriptor(), cursor_timeline_row() (+32 more)

### Community 26 - "Community 26"
Cohesion: 0.08
Nodes (31): _gl_bool_vector(), _gl_int(), GlPostProcess, _PingPongBuffers, _prepare_fixed_function_gl(), GPU post-processing (bloom) via moderngl sharing the active pygame GL context., Leave GL ready for the pygame compositor (fixed-function glBegin/glEnd)., Separable bloom pass on an existing layer FBO texture. (+23 more)

### Community 27 - "Community 27"
Cohesion: 0.21
Nodes (33): RenderConfig, Ensure *project_dir* is ready for offline render; return resolved path., validate_render_project(), _attach_render_post_fx_session(), _attach_session_from_cfg(), _mock_render_runtime(), Path, Tests for cleave.viz.render offline video pipeline. (+25 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (47): effect_help_description(), effect_help_title(), Save and quit orchestration for live tuning., Event, Return True when a modal dialog consumed the event., Handle a key down event for the main tuning tree., description_section(), DescriptionSection (+39 more)

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (35): _list_to_array(), load_signals(), ndarray, Path, Load and sample per-stem signals from signals.json., resolve_signals_path(), Signals, _validate_signals_data() (+27 more)

### Community 30 - "Community 30"
Cohesion: 0.07
Nodes (68): _bar_width(), _icon_height(), material_font(), Font, Surface, Material Icons rendering for the live tuning overlay., render_glyph(), render_transport_icons() (+60 more)

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (41): EffectRuntime, Owns per-row envelope state; tick updates signals then exposes modifiers., OpenGL FBO layer stack and black-key compositing., Preloaded per-stem PCM at 44.1 kHz for libprojectM audio feed., PCM samples for one live visual frame from elapsed wall time., samples_for_dt(), StemPcmBank, _init_compositor_and_post() (+33 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (6): _get_lib(), ProjectM, c_void_p, ndarray, Path, Context-manager-friendly wrapper around a libprojectM instance.

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (32): LiveVisualizerRuntime, Fully initialized live visualizer runtime., dispatch_keydown(), dispatch_keyup(), dispatch_should_notify_overlay(), _handle_global_keydown(), key_handler_for_runtime(), Event (+24 more)

### Community 34 - "Community 34"
Cohesion: 0.14
Nodes (19): Fixed eye slot width (glyph plus horizontal pad for solo background)., visibility_icon_slot_width(), layer_num_prefix(), playhead_x(), Font, Surface, Width of the row label prefix (num, abbrev, monitor eye slot)., rec_flash_visible() (+11 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (40): milk_files_in_dir(), Non-recursive ``*.milk`` files directly in ``dir``., Path, StemLayer, active_auto_preset_path(), apply_preset_switching(), _apply_projectm_timing(), _auto_preset_loaded_callback() (+32 more)

### Community 36 - "Community 36"
Cohesion: 0.16
Nodes (32): Return the stem wav directory inside a Cleave project., stems_dir(), project_stems_complete(), Path, Run Demucs stem separation and write stem wavs into a Cleave project., Separate and/or analyse a Cleave project from an audio file or project slug., Return True when every stem wav from :func:`stem_paths` exists., Return True when ``signals.json`` exists in *project_dir*. (+24 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (35): `cleave/analyse.py` and `cleave/extract.py`, `cleave/config.py`, `cleave/config_schema.py`, `cleave/effects/registry.py`, `cleave/effects/runtime.py`, `cleave/extract.py`, `cleave/preset_playlist.py`, `cleave/stem_pcm.py` (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (79): _make_controls(), _mutate_dirty(), _preset_row(), Unit-style tests for live tuning controls (no Milkdrop window)., _row(), _sub_rows_for_stem(), test_build_view_state_passes_fps(), test_ctrl_enter_toggles_lock() (+71 more)

### Community 39 - "Community 39"
Cohesion: 0.10
Nodes (36): apply_field_horizontal(), composite_header_prefix_part(), composite_header_suffix_part(), _full_line_branch_depth(), full_line_prefix(), labeled_row_prefix(), Branch glyph for tree depth; pixel indent comes from row_tree_indent_depth., row_composite_header_display_text() (+28 more)

### Community 40 - "Community 40"
Cohesion: 0.20
Nodes (29): VisualizerApp, _heavy_init_side_effect(), _key_handler_for_session(), _minimal_runtime(), Surface, Tests for VisualizerApp frame tick ordering., Mirror VisualizerApp.run KEYDOWN/KEYUP routing., _run_seed() (+21 more)

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
Cohesion: 0.15
Nodes (24): ModalViewState, draw(), _draw_message(), _draw_options(), draw_rect(), _measure_options(), _measure_panel(), _option_text() (+16 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (18): cycle_render_overlay_font(), _has_latin_glyphs(), System font discovery for render overlay tuning., True when *name* provides distinct Latin glyphs (not tofu placeholders)., Sorted Latin-capable pygame/SDL font names on this machine., Font name with ``(position/total)`` when *name* is in the Latin font list., render_overlay_font_display(), render_overlay_system_fonts() (+10 more)

### Community 49 - "Community 49"
Cohesion: 0.16
Nodes (20): _CleaveHelpFormatter, Offline render output frame rate from config., render_fps(), build_runtime_base(), Path, _default_output_path(), _is_partial_segment(), _progress() (+12 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (33): _build_handlers(), EffectHandler, handler_for(), Any, Registry of per-effect update and apply handlers for EffectRuntime., _apply_hue(), hue_mix_pct(), hue_rgb() (+25 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (41): dir_has_presets(), directory_display(), list_navigable_dirs(), navigable_parent(), _path_at_or_below(), preset_browse_floor(), preset_filename_display(), PresetPlaylist (+33 more)

### Community 52 - "Community 52"
Cohesion: 0.08
Nodes (37): allow_overwrite_for_path(), config_path_display(), Path, Active config path for the config header row (truncation happens at draw time)., Hide overwrite only for the repo-root template cleave-viz.yaml., _choose_overwrite(), _choose_save_as_new(), _config_header_row() (+29 more)

### Community 53 - "Community 53"
Cohesion: 0.20
Nodes (5): current_sec(), Event, Stop an in-progress timeline take without closing the panel., Keyboard focus for the bottom timeline strip when the panel is open., TimelineControls

### Community 54 - "Community 54"
Cohesion: 0.24
Nodes (23): load_manifest(), manifest_path(), mix_path(), ProjectManifest, Path, Project manifest (project.yaml) for Cleave projects., Update ``project.yaml`` *slug* and optional ``restored-from`` provenance., resolve_mix_path() (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.14
Nodes (14): ModalHost, ModalOption, ModalRequest, Event, Return True when the event is consumed (including while blocking)., Modal prompt host; consumes keys while active., _keydown(), Event (+6 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (26): _cue_modifies_armed_stem(), layer_visible_at(), _merge_cues_at_same_t(), punch_replace(), StemSource, Timeline cue evaluation and editing for per-slot layer visibility., should_accept_toggle(), stem_abbreviation() (+18 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (24): _apply_flash(), flash_alpha(), flash_threshold(), FlashBurstState, Per-layer flash overlay: threshold burst from normalized stem signals., update_burst(), _update_flash(), _def() (+16 more)

### Community 58 - "Community 58"
Cohesion: 0.22
Nodes (15): aberration_px(), _apply_grit(), grit_strength(), GritState, _update_grit(), _layer_runtime(), Tests for grit envelope, scaling, and EffectRuntime integration., _signals_with_stem_key() (+7 more)

### Community 59 - "Community 59"
Cohesion: 0.18
Nodes (6): GlCompositor, Stack tiered layer FBO textures into a content FBO, then present to display., Initialize GL state after a pygame OPENGL context exists., Resize an existing layer FBO, preserving compositor state fields., Destroy the named FBO and remove it from the compositor stack., Draw *texture_id* onto the display framebuffer with SRCALPHA blending.

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (6): ConfigSaveController, Path, Dirty tracking, save dialogs, and deferred quit., Return True once when quit was deferred (e.g. Don't save from unsaved dialog)., Handle a quit request. Return True when the app should exit now., FocusCursor

### Community 61 - "Community 61"
Cohesion: 0.20
Nodes (5): clamp_ui_fade(), clamp_ui_width(), Settings row mutations for live tuning., Mutations for settings rows., SettingsControls

### Community 62 - "Community 62"
Cohesion: 0.13
Nodes (11): Map layer opacity to glColor4f for the active layer blend mode.          GL_MODU, Tests for layer opacity mapping in the GL compositor., Runtime fallback blend is black-key; opacity must scale RGB., Flash draws a solid quad with add blend; strength must be glColor alpha., test_flash_rgba_puts_strength_in_alpha_for_add_blend(), test_layer_gl_color_add_keeps_hue_in_rgb_and_opacity_in_alpha(), test_layer_gl_color_bakes_opacity_into_rgb(), test_layer_gl_color_full_opacity_preserves_tint() (+3 more)

### Community 63 - "Community 63"
Cohesion: 0.27
Nodes (18): preview_layer_size(), preview_sizes_for_session(), VisualizerRenderMode, Live preview layer resolution from visualizer render mode and z-order., _requested_scale(), _cfg(), _layer_cfg(), Tests for live preview layer resolution from render mode and z-order. (+10 more)

### Community 64 - "Community 64"
Cohesion: 0.17
Nodes (22): _apply_flare(), bloom_strength(), flare_triggered(), FlareBurstState, Per-layer bloom flare: onset delta and threshold burst (drums only)., update_burst(), _update_flare(), update_smoothed() (+14 more)

### Community 65 - "Community 65"
Cohesion: 0.20
Nodes (15): Path, Helpers for per-layer user-defined preset lists., Format a user preset row label, numbering duplicate paths in the list., Return destination path and whether the source file must be copied., resolve_user_preset_dest(), _same_preset_file(), _unique_copy_dest(), user_preset_item_display_name() (+7 more)

### Community 66 - "Community 66"
Cohesion: 0.33
Nodes (14): _controls_with_playlist(), _make_sibling_dir_tree(), _preset_dir_row(), Return (preset_root, sibling_dirs) each with at least one .milk file., test_backspace_at_preset_root_is_noop(), test_ctrl_left_at_preset_root_is_noop(), test_directory_ctrl_arrows_descend_and_ascend(), test_directory_ctrl_arrows_do_not_repeat_parent_climb() (+6 more)

### Community 67 - "Community 67"
Cohesion: 0.14
Nodes (22): Per-layer film grain and chromatic aberration: envelope follow from signals., _apply_pulse(), effective_opacity(), PulseEnvelopeState, Opacity pulse: envelope follow from normalized stem signals., update_envelope(), _update_pulse(), Shared signal sampling helpers for compositor effects. (+14 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (15): `cleave`, `cleave` a track, Cleave effects, CLI, Compositing, Download Some Milkdrop Presets, Layer visibility timeline, Post-processing fade (+7 more)

### Community 69 - "Community 69"
Cohesion: 0.22
Nodes (13): Signal-driven compositor effects for the Milkdrop visualizer., all_stem_sources(), effect_roster(), effect_row_count(), StemSource, Per-stem effect roster: fixed effect and driver rows for the live tuning UI., validate_effect_entry(), Tests for the per-stem cleave effects registry. (+5 more)

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (29): data_dir(), default_project_config(), project_dir(), project_slug(), projects_dir(), Path, Filesystem layout for Cleave data and projects., Return Cleave data root (``CLEAVE_DATA`` or the repo / package root). (+21 more)

### Community 71 - "Community 71"
Cohesion: 0.36
Nodes (10): _mock_lib(), Path, Tests for cleave.projectm_playlist ctypes bindings., test_connect_installs_instant_load_callback(), test_create_connect_add_path_set_shuffle_destroy(), test_destroy_clears_preset_load_callback(), test_destroy_disconnects_before_free(), test_item_roundtrip_with_real_library() (+2 more)

### Community 72 - "Community 72"
Cohesion: 0.19
Nodes (13): parse_blend_mode(), BlendMode, Tests for compositor blend mode registry and config parsing., test_cycle_blend_recovers_from_unknown_mode(), test_cycle_blend_steps_backward(), test_cycle_blend_wraps_forward(), test_parse_blend_mode_accepts_all_modes(), test_parse_blend_mode_rejects_unknown() (+5 more)

### Community 73 - "Community 73"
Cohesion: 0.23
Nodes (17): fit_counter_label_to_width(), fit_path_label_to_width(), fit_text_to_width(), Font, Text fitting helpers for overlay labels., Shorten text with a trailing ellipsis until it fits max_px., Shorten a path for overlay width; keep the tail (subdir + filename)., Shorten a path or filename to max_px; preserve a trailing ``(N/TOTAL)`` counter. (+9 more)

### Community 74 - "Community 74"
Cohesion: 0.26
Nodes (10): ndarray, Resample native-rate analysis frames to a uniform 100 Hz grid., Linearly interpolate *values* onto a uniform 100 Hz time grid.      Grid covers, resample_to_100hz(), Tests for cleave.resample., test_resample_boundary_excludes_endpoint(), test_resample_empty_duration_returns_empty_array(), test_resample_linear_interpolation_at_known_points() (+2 more)

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (18): 1. Full uncached redraw every frame, 2. Per-row CPU cost is high, 3. All visible rows are built even when scrolled off-screen, 4. GL texture upload every frame, 5. `blit_tint` allocates per focused row, 6. View state and layout rebuilt every frame, 7. Full-viewport overlay clear, 8. FPS feedback loop (secondary) (+10 more)

### Community 76 - "Community 76"
Cohesion: 0.22
Nodes (4): LayerFbo, BlendMode, Configure GL blend for stacking layer FBOs onto the output framebuffer., Off-screen RGBA framebuffer for one compositor layer.

### Community 77 - "Community 77"
Cohesion: 0.39
Nodes (8): _mock_lib(), Tests for cleave.projectm PCM feeding., test_feed_pcm_chunks_above_max_samples(), test_feed_pcm_scales_by_beat_sensitivity(), test_feed_pcm_skips_empty(), test_feed_pcm_stereo_chunks_on_even_boundaries(), test_flush_pcm_uses_last_channel_layout(), test_set_beat_sensitivity_clamps_and_stores()

### Community 78 - "Community 78"
Cohesion: 0.25
Nodes (7): _discard_timeline_slot(), _manager(), Unit tests for LayerManager., test_add_layer_updates_cfg_session_and_collections(), test_can_add_and_can_remove_respect_limits(), test_discard_timeline_slot_strips_slot_from_timeline_state(), test_remove_layer_updates_cfg_session_and_collections()

### Community 79 - "Community 79"
Cohesion: 0.15
Nodes (18): Return the repository root directory., repo_root(), load_stem_signals(), Path, Visualizer bootstrap: config resolution, paths, and preset loading., Resolve config: CLI override, project default, then global search., resolve_config_path(), resolve_mix_path() (+10 more)

### Community 80 - "Community 80"
Cohesion: 0.29
Nodes (6): Architecture improvements, Phase 1 - Cache `build_row_layout` per frame, Phase 2 - Decouple FPS from transport color; route fps through the view builder, Phase 3 - Use `RowDescriptor` as the focus cursor, Phase 4 - Unified focus model for the timeline bridge, Phase 5 - Split overlay into layout/nav and draw modules

### Community 84 - "Community 84"
Cohesion: 0.27
Nodes (7): draw_loading_screen(), _loading_font_get(), Font, Centered loading message during visualizer boot., Tests for visualizer boot loading screen., test_draw_loading_screen_uploads_overlay_and_flips(), Mock GlCompositor helpers for unit tests (no OpenGL).

### Community 85 - "Community 85"
Cohesion: 0.22
Nodes (10): _live_overlay_ui_active(), FocusCursor, Show the bottom timeline strip while the main panel is visible or a row is focus, _tick_frame_live_overlay(), _timeline_strip_fade(), _timeline_strip_visible(), _tuning_view_state_needed(), test_live_overlay_ui_active_gating() (+2 more)

### Community 86 - "Community 86"
Cohesion: 0.43
Nodes (7): StemSource, stem_control_label(), stem_overlay_header(), Tests for stem source display helpers., test_display_helpers_cover_all_stem_sources(), test_stem_control_label(), test_stem_overlay_header()

### Community 87 - "Community 87"
Cohesion: 0.20
Nodes (9): Goals and budget, Independent review: findings beyond the first review, Live tuning UI performance plan, Phase 1: Measurement harness and hidden-panel guardrails, Phase 2: Compute layout and view state once per frame, Phase 3: Panel signature, row cache, and retained panel surface, Phase 4: Stable-size GPU upload, Phase 5: Decouple projectM fps from UI-loaded display fps (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.19
Nodes (7): FrameRateMeter, Wall-clock frame rate measurement for the live visualizer., Track achieved FPS from full main-loop iterations., Tests for live visualizer frame rate measurement., test_format_fps_display(), test_frame_rate_meter_first_frame(), test_frame_rate_meter_smoothing()

### Community 89 - "Community 89"
Cohesion: 0.36
Nodes (3): _gl_name(), Surface, Upload a pygame SRCALPHA surface as a GL texture (Y-flipped for GL).

### Community 90 - "Community 90"
Cohesion: 0.40
Nodes (3): clamp_effect_pct(), Shared clamps and per-driver pulse envelope constants., test_clamp_effect_pct()

### Community 91 - "Community 91"
Cohesion: 0.40
Nodes (5): armed_recording_defaults(), armed_recording_visible(), Visibility for a record-pass slot during an active take., test_backward_seek_during_record_fills_and_expands_punch_start(), test_forward_seek_during_record_fills_with_active_state()

### Community 92 - "Community 92"
Cohesion: 0.25
Nodes (12): _help_compose_kwargs(), Surface, _union_rect(), _mock_tuning_compose(), _overlay_surface_mock(), Tests that live UI overlays target the display framebuffer., test_draw_timeline_overlay_applies_visibility_alpha(), test_draw_timeline_overlay_uses_display_target() (+4 more)

### Community 93 - "Community 93"
Cohesion: 0.20
Nodes (10): _confirm_modal_yes(), _make_controls_with_manager(), _make_playlist(), test_add_layer_confirm_calls_manager(), test_add_layer_row_omitted_at_max(), test_cycle_render_mode_calls_apply_preview_resolutions(), test_delete_layer_at_min_shows_toast(), test_delete_layer_clamps_timeline_focus_row() (+2 more)

### Community 94 - "Community 94"
Cohesion: 0.33
Nodes (7): add_layer_to_session(), remove_layer_from_session(), Unit tests for session add/remove helpers., _runtime(), test_add_layer_to_session_appends_slot_and_runtime(), test_remove_layer_from_session_clears_solo(), test_remove_layer_from_session_drops_slot()

### Community 95 - "Community 95"
Cohesion: 0.28
Nodes (8): _bind_functions(), _library_candidates(), _pkg_config_candidates(), ProjectMLibraryError, CDLL, ctypes wrapper for libprojectM., libprojectM shared library not found or failed to load., OSError

### Community 96 - "Community 96"
Cohesion: 0.28
Nodes (8): _bind_functions(), _library_candidates(), _pkg_config_candidates(), ProjectMPlaylistLibraryError, CDLL, ctypes wrapper for libprojectM playlist library., libprojectM playlist shared library not found or failed to load., test_bind_functions_requires_symbols()

### Community 97 - "Community 97"
Cohesion: 0.10
Nodes (25): arm_abbrev_flash_active(), arm_abbrev_flash_visible(), armed_abbrev_bg_visible(), bar_segments_for_row(), bar_tick_times_for_row(), _clip_segments(), cue_times_for_stem(), prune_expired_arm_flashes() (+17 more)

### Community 98 - "Community 98"
Cohesion: 0.29
Nodes (5): ndarray, StemSource, Preloaded float32 PCM for *stem* (mono 1D or interleaved stereo)., Channel count for *stem* (1 mono, 2 interleaved stereo)., Return per-channel *n_samples* of float32 PCM from *t_sec*, zero-padded past end

### Community 100 - "Community 100"
Cohesion: 0.25
Nodes (8): _bar_visible_at(), Return the bar's visibility value for a slot at time t., After a backward seek during recording, the bar shows the fill state., Backward seek past record_start: bar still shows fill for skipped range., No backward seek: bar shows record_buffer only up to playhead., test_bar_shows_fill_for_backward_seek_with_expanded_punch_start(), test_bar_shows_fill_for_backward_skipped_range(), test_bar_without_high_water_mark_behaves_as_before()

## Knowledge Gaps
- **182 isolated node(s):** `Requirements`, `Setup`, `Download Some Milkdrop Presets`, ``cleave` a track`, `Project Directory` (+177 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TuningSession` connect `Community 8` to `Community 0`, `Community 1`, `Community 2`, `Community 9`, `Community 10`, `Community 11`, `Community 14`, `Community 15`, `Community 16`, `Community 25`, `Community 27`, `Community 28`, `Community 31`, `Community 33`, `Community 35`, `Community 38`, `Community 40`, `Community 48`, `Community 50`, `Community 51`, `Community 53`, `Community 57`, `Community 58`, `Community 60`, `Community 61`, `Community 63`, `Community 64`, `Community 66`, `Community 67`, `Community 72`, `Community 78`, `Community 85`, `Community 91`, `Community 93`, `Community 94`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `TuningControls` connect `Community 0` to `Community 4`, `Community 5`, `Community 6`, `Community 7`, `Community 8`, `Community 9`, `Community 11`, `Community 15`, `Community 16`, `Community 20`, `Community 25`, `Community 28`, `Community 30`, `Community 31`, `Community 33`, `Community 38`, `Community 39`, `Community 40`, `Community 48`, `Community 52`, `Community 55`, `Community 60`, `Community 61`, `Community 65`, `Community 66`, `Community 72`, `Community 90`, `Community 93`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `RowDescriptor` connect `Community 0` to `Community 1`, `Community 5`, `Community 6`, `Community 7`, `Community 14`, `Community 16`, `Community 19`, `Community 20`, `Community 25`, `Community 28`, `Community 30`, `Community 33`, `Community 38`, `Community 39`, `Community 40`, `Community 52`, `Community 72`, `Community 85`, `Community 92`, `Community 93`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Are the 22 inferred relationships involving `RowDescriptor` (e.g. with `TuningControls` and `MainFocus`) actually correct?**
  _`RowDescriptor` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `TuningControls` (e.g. with `LiveVisualizerRuntime` and `RenderVisualizerRuntime`) actually correct?**
  _`TuningControls` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 21 inferred relationships involving `TuningViewState` (e.g. with `TuningControls` and `FocusContext`) actually correct?**
  _`TuningViewState` has 21 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Cleave: stem-driven music visualizer.`, `Orchestrate per-stem feature extraction and write signals.json.`, `Backup and restore Cleave project directories as gzip tar archives.` to the rest of the system?**
  _540 weakly-connected nodes found - possible documentation gaps or missing edges._