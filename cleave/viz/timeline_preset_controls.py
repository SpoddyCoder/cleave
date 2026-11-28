"""Generate and Reset timeline dialogs and their clear+apply orchestration."""

from __future__ import annotations

import random
import traceback
from collections.abc import Callable, Mapping, Sequence

from cleave.signals import Signals
from cleave.timeline import (
    TimelineLane,
    copy_lane,
    empty_lane,
    shift_bars_by_beats,
    snap_lane_to_beats,
    snap_lanes_to_song_markers,
)
from cleave.config_schema.layers import preset_switching_mode_for_trigger
from cleave.timeline_presets.lanes import compose_layers_timeline
from cleave.timeline_presets.layer_setup import (
    FULL_OPACITY_PCT,
    change_presets_display,
    opacity_display,
)
from cleave.timeline_presets.pattern_mask_arrange import compose_pattern_mask_timeline
from cleave.timeline_presets.conductor import timeline_preset_conductor_display
from cleave.pattern_mask_transition import transition_seconds
from cleave.timeline_presets.mask_options import (
    KEEP,
    TIMELINE_PRESET_MASK_CHANGES_OPTIONS,
    TIMELINE_PRESET_MASK_PATTERN_OPTIONS,
    timeline_preset_mask_changes_display,
    timeline_preset_mask_pattern_display,
)
from cleave.timeline_presets.mode import (
    TIMELINE_PRESET_MODE_OPTIONS,
    timeline_preset_mode_display,
)
from cleave.timeline_presets.cue_snap import (
    TIMELINE_PRESET_CUE_SNAP_OPTIONS,
    timeline_preset_cue_snap_display,
)
from cleave.timeline_presets.density import (
    TIMELINE_PRESET_DENSITY_OPTIONS,
    density_bias_for,
    timeline_preset_density_display,
)
from cleave.timeline_presets.repopulate import (
    DEFAULT_TIMELINE_PRESET_REPOPULATE,
    TIMELINE_PRESET_REPOPULATE_OPTIONS,
    TimelinePresetRepopulate,
    timeline_preset_repopulate_display,
)
from cleave.timeline_presets.song_marker_snap import (
    TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
    timeline_preset_song_marker_snap_display,
)
from cleave.timeline_presets.timeline_cuts import (
    TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
    TimelinePresetTimelineCuts,
    timeline_preset_timeline_cuts_display,
)
from cleave.viz.modal import (
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
)
from cleave.viz.session import TuningSession
from cleave.viz.timeline_clip_edits import row_clips
from cleave.viz.timeline_cut_controls import apply_cut_to_lanes
from cleave.viz.clip_presets import (
    is_each_clip,
    locked_each_clip_reason,
)
from cleave.viz.edit_history import EditHistory

_GENERATE_TITLE = "Generate timeline"
_RESET_TITLE = "Reset timeline?"
_CONDUCTOR_OPTIONS = (False, True)
_RESET_LAYER_OPTIONS = ("off", "on")
# Generate dialog sections: what the arrangement is, then how its cues are
# tidied, then which layer settings it overrides.
_ARRANGEMENT_SECTION = "Arrangement"
_PATTERN_MASK_SECTION = "Pattern mask"
_CUES_SECTION = "Clip timing and cuts"
_LAYER_SETTINGS_SECTION = "Layer settings"

_GENERATE_HELP = (
    "Builds a new timeline from these settings, replacing the current clips. Arrangement decides which layers play when, clip timing and cuts then tidy every generated clip, and each layer whose presets change on each clip gets a preset for every new clip, dealt from its preset list.",
    "Each section is arranged to suit its song marker's type and intensity: how many layers play, which one leads, how bright each is, and how often presets change. Back-to-back markers of one type make one longer section, such as a build that rises across all of them. Settings are kept for the rest of the session.",
    "In pattern mask mode every change of layers is a wipe. Two or more layers are on, though a calm section can drop to one, every song marker changes them, and between markers they change as often as the section's intensity asks.",
    "Layer settings change the same settings on each layer's own pages, so the plan shows as planned. keep leaves them as they are. Locked layers are always left as they are, and Ctrl+Z undoes the changes with the rest of Generate.",
)
_DENSITY_HELP = (
    "How many layers tend to play at once: sparse favours solos, dense keeps more of the stack in.",
)
_CUE_SNAP_HELP = ("Moves the edges of every generated clip onto the beat or bar grid.",)
_CUE_SNAP_OPTION_HELP = {
    "none": "keep the generated clip times.",
    "beats": "move each clip edge to the nearest beat.",
    "bars": "move each clip edge to the nearest bar.",
}
_SONG_MARKER_SNAP_HELP = (
    "Pulls the nearest clip edge on each layer onto each song marker, if it is within this distance. none leaves the clips where they are.",
)
_TIMELINE_CUTS_HELP = (
    "The cut type each generated clip edge gets. Fade lengths for each type come from Timeline > Clip Fades.",
)
_TIMELINE_CUTS_OPTION_HELP = {
    "by marker": "hard cuts on song markers, soft cuts elsewhere.",
    "all soft": "every clip edge is a soft cut.",
    "all hard": "every clip edge is a hard cut.",
    "none": "keep the cut each clip edge was made with.",
}
_PRESET_LIST_HELP = (
    "The layer's Preset List, dealt onto the new clips in order on each layer whose presets change on each clip. Shown only when there is such a layer.",
)
_PRESET_LIST_OPTION_HELP = {
    "keep": "the layer's own presets, starting again from the top when there are more clips than presets; an empty list gets a new shuffled one.",
    "directory random": "a new list from the layer's preset folder, shuffled.",
    "directory sequential": "a new list from the layer's preset folder, in order.",
    "cue roles": "a new list with a preset picked for each clip's role.",
}
_CONDUCTOR_HELP = (
    "Uses the stems' audio to decide which layer leads each phrase and to give layers roles, which set their blend modes. In layers mode a chorus or drop opens with an accent on one layer. It needs the song's audio analysis and is skipped without it.",
)
_CONDUCTOR_OPTION_HELP = {
    False: "layers take turns leading, and keep their own blend modes.",
    True: "the busiest stem leads, and layers get roles.",
}
_MODE_HELP = ("How the arrangement brings layers in and out.",)
_MODE_OPTION_HELP = {
    "layers": "clips bring whole layers in and out, at the opacity each section calls for.",
    "pattern_mask": (
        "layers wipe in and out through the pattern mask, at every song marker "
        "and as often as each section's intensity asks; turns the mask on."
    ),
}
_MASK_PATTERN_HELP = (
    "The Pattern Mask page's pattern, which shapes the regions and how they wipe.",
)
_MASK_PATTERN_OPTION_HELP = {
    "keep": "the pattern the Pattern Mask page has now.",
    "strips": "vertical strips that slide to make room.",
    "bars": "horizontal bars that slide to make room.",
    "radial": "slices of a circle that turn to make room.",
    "checker": "a checkerboard that dissolves from one layout to the next.",
    "plasma": "flowing blobs that dissolve from one layout to the next.",
}
_MASK_CHANGES_HELP = (
    "How often layers come and go between song markers. The section's intensity sets the pace, calm sections slower and intense ones faster; this sets how busy every section is. Markers always change, and each change waits for the last wipe to finish, so a long Pattern Mask transition spaces them out.",
)
_MASK_CHANGES_OPTION_HELP = {
    "fewer": "long holds: every eight bars or more when very calm, every bar or two when very intense.",
    "normal": "every two or three bars when very calm, down to every half bar when intense.",
    "more": "every bar or two when very calm, down to every beat or two when intense.",
}
_ON_OFF = (False, True)
_OPACITY_HELP = (
    "The layer's Compositing > opacity, which multiplies the opacity of its clips.",
)
_OPACITY_OPTION_HELP = {
    False: "layers below 100% look dimmer than planned.",
    True: "the brightness Generate plans shows as planned.",
}
_CHANGE_PRESETS_HELP = (
    "The layer's Preset Switching > change presets. Generate plans a new preset at song markers and every few bars, and those changes play only on layers set to each clip.",
)
_CHANGE_PRESETS_OPTION_HELP = {
    False: "layers on a timer, projectM decides, or never keep it, and their preset lists.",
    True: "every layer plays the planned preset changes.",
}
_RESET_HELP = ("Removes every clip on the timeline.",)
_RESET_LAYERS_HELP = ("What every layer does for the whole song after the reset.",)
_RESET_LAYERS_OPTION_HELP = (
    "every layer stays off.",
    "every layer stays on.",
)


def _choice_field(
    field_id: str,
    label: str,
    options: Sequence[object],
    current: object,
    display: Callable[..., str],
    *,
    help: tuple[str, ...] = (),
    option_help: Mapping[object, str] | None = None,
    section: str | None = None,
    visible: Callable[[FormValues], bool] | None = None,
    vertical: bool = False,
) -> FormField:
    return FormField(
        field_id,
        label,
        tuple(display(option) for option in options),
        options.index(current),
        help=help,
        option_help=()
        if option_help is None
        else tuple(option_help[option] for option in options),
        section=section,
        visible=visible,
        vertical=vertical,
    )


def _pattern_mask_mode(values: FormValues) -> bool:
    """Whether the draft dialog is set to pattern mask mode."""
    return TIMELINE_PRESET_MODE_OPTIONS[values["mode"]] == "pattern_mask"


def _clips_label(count: int) -> str:
    return "1 clip" if count == 1 else f"{count} clips"


class TimelinePresetController:
    """Prompt for and apply procedural timeline presets from the tuning panel."""

    def __init__(
        self,
        session: TuningSession,
        modal_host: ModalHost,
        beat_times: Sequence[float] = (),
        bar_times: Sequence[float] = (),
        *,
        signals: Signals | None = None,
        on_notification: Callable[[str], None] | None = None,
        on_repopulate: Callable[[], None] | None = None,
        has_role_presets: Callable[[], bool] | None = None,
        history: EditHistory | None = None,
    ) -> None:
        self.session = session
        self._modal = modal_host
        self._history = history if history is not None else EditHistory(session)
        self._beat_times = tuple(beat_times)
        self._bar_times = tuple(bar_times)
        self._signals = signals
        self._on_notification = on_notification
        self._on_repopulate = on_repopulate
        self._has_role_presets = has_role_presets
        # Reset's last "layers after reset" choice, for this session.
        self._last_reset_layers = 0

    def _repopulate_options(self) -> tuple[TimelinePresetRepopulate, ...]:
        """Refill choices; clip roles only when the library tags any preset with a role."""
        if self._has_role_presets is not None and self._has_role_presets():
            return TIMELINE_PRESET_REPOPULATE_OPTIONS
        return tuple(
            option
            for option in TIMELINE_PRESET_REPOPULATE_OPTIONS
            if option != "cue roles"
        )

    def prompt(self, duration_sec: float) -> None:
        tl = self.session.timeline
        if tl.locked or self._refuse_locked_layers():
            return
        repopulate_options = self._repopulate_options()
        repopulate_current = (
            tl.timeline_preset_repopulate
            if tl.timeline_preset_repopulate in repopulate_options
            else DEFAULT_TIMELINE_PRESET_REPOPULATE
        )
        self._modal.prompt_form(
            FormSpec(
                title=_GENERATE_TITLE,
                fields=(
                    _choice_field(
                        "mode",
                        "mode",
                        TIMELINE_PRESET_MODE_OPTIONS,
                        tl.timeline_preset_mode,
                        timeline_preset_mode_display,
                        help=_MODE_HELP,
                        option_help=_MODE_OPTION_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "density",
                        "density",
                        TIMELINE_PRESET_DENSITY_OPTIONS,
                        tl.timeline_preset_density,
                        timeline_preset_density_display,
                        help=_DENSITY_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "conductor",
                        "conductor",
                        _CONDUCTOR_OPTIONS,
                        tl.timeline_preset_conductor,
                        timeline_preset_conductor_display,
                        help=_CONDUCTOR_HELP,
                        option_help=_CONDUCTOR_OPTION_HELP,
                        section=_ARRANGEMENT_SECTION,
                    ),
                    _choice_field(
                        "mask_pattern",
                        "pattern",
                        TIMELINE_PRESET_MASK_PATTERN_OPTIONS,
                        tl.timeline_preset_mask_pattern,
                        timeline_preset_mask_pattern_display,
                        help=_MASK_PATTERN_HELP,
                        option_help=_MASK_PATTERN_OPTION_HELP,
                        section=_PATTERN_MASK_SECTION,
                        visible=_pattern_mask_mode,
                    ),
                    _choice_field(
                        "mask_changes",
                        "layer changes",
                        TIMELINE_PRESET_MASK_CHANGES_OPTIONS,
                        tl.timeline_preset_mask_changes,
                        timeline_preset_mask_changes_display,
                        help=_MASK_CHANGES_HELP,
                        option_help=_MASK_CHANGES_OPTION_HELP,
                        section=_PATTERN_MASK_SECTION,
                        visible=_pattern_mask_mode,
                    ),
                    _choice_field(
                        "cue_snap",
                        "snap to grid",
                        TIMELINE_PRESET_CUE_SNAP_OPTIONS,
                        tl.timeline_preset_cue_snap,
                        timeline_preset_cue_snap_display,
                        help=_CUE_SNAP_HELP,
                        option_help=_CUE_SNAP_OPTION_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "song_marker_snap",
                        "snap to song markers",
                        TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS,
                        tl.timeline_preset_song_marker_snap,
                        timeline_preset_song_marker_snap_display,
                        help=_SONG_MARKER_SNAP_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "timeline_cuts",
                        "cut type",
                        TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS,
                        tl.timeline_preset_timeline_cuts,
                        timeline_preset_timeline_cuts_display,
                        help=_TIMELINE_CUTS_HELP,
                        option_help=_TIMELINE_CUTS_OPTION_HELP,
                        section=_CUES_SECTION,
                    ),
                    _choice_field(
                        "opacity",
                        "opacity",
                        _ON_OFF,
                        tl.timeline_preset_full_opacity,
                        opacity_display,
                        help=_OPACITY_HELP,
                        option_help=_OPACITY_OPTION_HELP,
                        section=_LAYER_SETTINGS_SECTION,
                        visible=lambda values: not _pattern_mask_mode(values),
                    ),
                    _choice_field(
                        "change_presets",
                        "change presets",
                        _ON_OFF,
                        tl.timeline_preset_each_clip,
                        change_presets_display,
                        help=_CHANGE_PRESETS_HELP,
                        option_help=_CHANGE_PRESETS_OPTION_HELP,
                        section=_LAYER_SETTINGS_SECTION,
                    ),
                    _choice_field(
                        "preset_list",
                        "preset list",
                        repopulate_options,
                        repopulate_current,
                        timeline_preset_repopulate_display,
                        help=_PRESET_LIST_HELP,
                        option_help=_PRESET_LIST_OPTION_HELP,
                        section=_LAYER_SETTINGS_SECTION,
                        visible=self._preset_list_used,
                        vertical=True,
                    ),
                ),
                confirm_label="Generate",
                on_confirm=lambda values: self._confirm_generate(
                    values, duration_sec, repopulate_options
                ),
                info=lambda _values: self._generate_info(duration_sec),
                help=_GENERATE_HELP,
            )
        )

    def _refuse_locked_layers(self) -> bool:
        """Name the locked layers whose clips hold presets. True when there are any."""
        reason = locked_each_clip_reason(self.session)
        if reason is None:
            return False
        self._notify(reason)
        return True

    def _generate_info(self, duration_sec: float) -> str | None:
        """How many clips Generate would replace."""
        count = self._clip_count(duration_sec)
        return f"Replaces {_clips_label(count)} on the timeline" if count else None

    def _preset_list_used(self, values: FormValues) -> bool:
        """Whether any layer would change presets on each clip after Generate."""
        if _ON_OFF[values["change_presets"]] and self._layers_to_convert():
            return True
        return any(is_each_clip(self.session, slot) for slot in self.session.layer_z_order)

    def _layers_to_convert(self) -> list[str]:
        """Unlocked layers whose presets do not yet change on each clip."""
        session = self.session
        return [
            slot
            for slot in session.layer_z_order
            if not session.layers[slot].locked and not is_each_clip(session, slot)
        ]

    def _set_up_layers(self) -> None:
        """Apply the dialog's layer opacity and change presets choices."""
        tl = self.session.timeline
        for slot in self.session.layer_z_order:
            layer = self.session.layers[slot]
            if layer.locked:
                continue
            # The pattern mask overrides opacity, so only layers mode sets it.
            if tl.timeline_preset_full_opacity and tl.timeline_preset_mode == "layers":
                layer.opacity_pct = FULL_OPACITY_PCT
        if not tl.timeline_preset_each_clip:
            return
        for slot in self._layers_to_convert():
            layer = self.session.layers[slot]
            if layer.preset_switching_trigger == "off":
                # The preset chosen with switching off stays the layer's own.
                layer.layer_preset = layer.playlist.anchor
            layer.preset_switching_trigger = "timeline"
            layer.preset_switching = preset_switching_mode_for_trigger("timeline")

    def _clip_count(self, duration_sec: float) -> int:
        return sum(
            len(row_clips(self.session, slot, duration_sec))
            for slot in self.session.timeline.lanes
            if slot in self.session.layers
        )

    def _confirm_generate(
        self,
        values: FormValues,
        duration_sec: float,
        repopulate_options: Sequence[TimelinePresetRepopulate],
    ) -> None:
        if self._refuse_locked_layers():
            return
        tl = self.session.timeline
        tl.timeline_preset_density = TIMELINE_PRESET_DENSITY_OPTIONS[values["density"]]
        tl.timeline_preset_cue_snap = TIMELINE_PRESET_CUE_SNAP_OPTIONS[
            values["cue_snap"]
        ]
        tl.timeline_preset_song_marker_snap = TIMELINE_PRESET_SONG_MARKER_SNAP_OPTIONS[
            values["song_marker_snap"]
        ]
        tl.timeline_preset_timeline_cuts = TIMELINE_PRESET_TIMELINE_CUTS_OPTIONS[
            values["timeline_cuts"]
        ]
        tl.timeline_preset_repopulate = repopulate_options[values["preset_list"]]
        tl.timeline_preset_conductor = _CONDUCTOR_OPTIONS[values["conductor"]]
        tl.timeline_preset_mode = TIMELINE_PRESET_MODE_OPTIONS[values["mode"]]
        tl.timeline_preset_mask_pattern = TIMELINE_PRESET_MASK_PATTERN_OPTIONS[
            values["mask_pattern"]
        ]
        tl.timeline_preset_mask_changes = TIMELINE_PRESET_MASK_CHANGES_OPTIONS[
            values["mask_changes"]
        ]
        tl.timeline_preset_full_opacity = _ON_OFF[values["opacity"]]
        tl.timeline_preset_each_clip = _ON_OFF[values["change_presets"]]
        before = self._history.begin("Generate timeline")
        try:
            self._apply(duration_sec)
            self._history.commit()
        except Exception as exc:
            # A failed generate must not end the session and lose unsaved work.
            traceback.print_exc()
            self._history.rollback(before)
            reason = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
            self._notify(f"Generate timeline failed, timeline unchanged: {reason}")

    def prompt_reset(self, duration_sec: float) -> None:
        if self.session.timeline.locked or self._refuse_locked_layers():
            return
        count = self._clip_count(duration_sec)
        self._modal.prompt_form(
            FormSpec(
                title=_RESET_TITLE,
                info=lambda _values: f"Removes {_clips_label(count)}",
                fields=(
                    FormField(
                        "layers",
                        "layers after reset",
                        _RESET_LAYER_OPTIONS,
                        self._last_reset_layers,
                        help=_RESET_LAYERS_HELP,
                        option_help=_RESET_LAYERS_OPTION_HELP,
                    ),
                ),
                confirm_label="Reset timeline",
                on_confirm=self._confirm_reset,
                destructive=True,
                help=_RESET_HELP,
            )
        )

    def _apply(self, duration_sec: float) -> None:
        if not self._bar_times:
            self._notify("No bars available; re-run separate")
            return
        if not self._beat_times:
            self._notify("No beats available; re-run separate")
            return
        grid = shift_bars_by_beats(
            self._bar_times,
            self._beat_times,
            self.session.timeline.bar_phase_offset,
        )
        if not grid:
            self._notify("No bars available; re-run separate")
            return
        tl = self.session.timeline
        slots = list(self.session.layer_z_order)
        markers = list(self.session.song_markers.markers)
        marker_times = [m.time for m in markers]
        rng = random.Random()
        builder_kwargs: dict = {
            "bar_times": grid,
            "song_markers": markers,
            "density_bias": density_bias_for(tl.timeline_preset_density),
        }
        conductor_skipped = False
        if tl.timeline_preset_conductor:
            if self._signals is None:
                conductor_skipped = True
            else:
                builder_kwargs["signals"] = self._signals
                builder_kwargs["slot_stems"] = {
                    slot: self.session.layers[slot].stem for slot in slots
                }
        if tl.timeline_preset_mode == "pattern_mask":
            self._enable_pattern_mask()
            built = compose_pattern_mask_timeline(
                slots,
                duration_sec,
                rng,
                beat_times=self._beat_times,
                transition_duration=transition_seconds(
                    self.session.pattern_mask.transition,
                    self.session.pattern_mask.transition_unit,
                    self.session.song_tempo,
                ),
                changes=tl.timeline_preset_mask_changes,
                **builder_kwargs,
            )
            message = "Generated pattern mask timeline"
        else:
            built = compose_layers_timeline(slots, duration_sec, rng, **builder_kwargs)
            message = "Generated timeline"
        built = {
            slot: copy_lane(built.get(slot, empty_lane())) for slot in slots
        }
        self._apply_cue_snap(built, grid)
        self._apply_song_marker_snap(built, marker_times, slots)
        self._apply_timeline_cuts(built, marker_times, tl.timeline_preset_timeline_cuts)
        self._clear_timeline_state()
        tl.enabled = True
        for slot in slots:
            tl.lanes[slot] = built[slot]
        self._set_up_layers()
        if self._on_repopulate is not None:
            self._on_repopulate()
        if conductor_skipped:
            self._notify("No signals; conductor skipped")
        else:
            self._notify(message)

    def _enable_pattern_mask(self) -> None:
        """Turn the mask on with the dialog's pattern."""
        tl = self.session.timeline
        pm = self.session.pattern_mask
        pm.enabled = True
        if tl.timeline_preset_mask_pattern != KEEP:
            pm.type = tl.timeline_preset_mask_pattern

    def _cue_snap_grid(self, bar_grid: Sequence[float]) -> Sequence[float]:
        """The grid clip edges snap to; empty when snap to grid is off."""
        cue_snap = self.session.timeline.timeline_preset_cue_snap
        if cue_snap == "beats":
            return self._beat_times
        return bar_grid if cue_snap == "bars" else ()

    def _apply_cue_snap(
        self,
        lanes: dict[str, TimelineLane],
        bar_grid: Sequence[float],
    ) -> None:
        grid = self._cue_snap_grid(bar_grid)
        if not grid:
            return
        for slot in list(lanes):
            lanes[slot] = snap_lane_to_beats(lanes[slot], grid)

    def _apply_song_marker_snap(
        self,
        lanes: dict[str, TimelineLane],
        markers: Sequence[float],
        slots: Sequence[str],
    ) -> None:
        proximity = self.session.timeline.timeline_preset_song_marker_snap
        if proximity is None:
            return
        updated, _moved = snap_lanes_to_song_markers(
            lanes,
            markers,
            proximity=float(proximity),
            layer_z_order=slots,
            slots=slots,
            mode="each_layer",
        )
        for slot in slots:
            lanes[slot] = updated[slot]

    def _apply_timeline_cuts(
        self,
        lanes: dict[str, TimelineLane],
        markers: Sequence[float],
        cuts: TimelinePresetTimelineCuts,
    ) -> None:
        if cuts == "none":
            return
        if cuts == "by marker":
            apply_cut_to_lanes(
                lanes, "soft", song_marker_times=markers, scope="all"
            )
            apply_cut_to_lanes(
                lanes, "hard", song_marker_times=markers, scope="markers_only"
            )
            return
        if cuts == "all soft":
            apply_cut_to_lanes(
                lanes, "soft", song_marker_times=markers, scope="all"
            )
            return
        if cuts == "all hard":
            apply_cut_to_lanes(
                lanes, "hard", song_marker_times=markers, scope="all"
            )

    def _confirm_reset(self, values: FormValues) -> None:
        if self._refuse_locked_layers():
            return
        self._last_reset_layers = values["layers"]
        with self._history.recording("Reset timeline"):
            self._reset(all_on=values["layers"] == 1)

    def _reset(self, *, all_on: bool) -> None:
        self._clear_timeline_state()
        tl = self.session.timeline
        tl.enabled = True
        tl.lanes = {
            slot: TimelineLane(baseline=1.0 if all_on else 0.0, cues=[])
            for slot in self.session.layer_z_order
        }
        message = (
            "Reset timeline: all layers on"
            if all_on
            else "Reset timeline: all layers off"
        )
        self._notify(message)

    def _clear_timeline_state(self) -> None:
        tl = self.session.timeline
        tl.lanes = {
            slot: empty_lane() for slot in self.session.layer_z_order
        }
        tl.record_buffer = {}
        tl.recording = False
        tl.record_start_sec = None
        tl.record_baseline = {}
        tl.record_slot_start_sec = {}
        tl.record_high_water_mark = None
        tl.armed_slots.clear()
        tl.override_slots.clear()
        tl.override_visible.clear()
        tl.arm_flash_start_ms.clear()

    def _notify(self, message: str) -> None:
        if self._on_notification is not None:
            self._on_notification(message)
