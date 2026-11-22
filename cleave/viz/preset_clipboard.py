"""One copied preset, shared by every layer: copy, cut, and paste.

Copy takes a preset list entry, the layer's current preset, or a preset in
the browser. Paste puts it over a list entry, before or after one, or plays it
on a layer as a preview. Pasting into a list copies the file into the project
when it lives anywhere else (the library, or another project's presets), the
same as Add to preset list. The clipboard lasts for the editor session.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cleave.preset_list_entry import PresetListEntry
from cleave.viz.layer_mutations import LayerMutations
from cleave.viz.preset_list_controls import PresetListController
from cleave.viz.user_presets import preview_anchor

NOTHING_COPIED_HINT = "Nothing copied"
COPIED_MISSING_HINT = "Copied preset file is missing"


class PresetClipboard:
    """Holds the copied preset and pastes it through the preset list controller."""

    def __init__(
        self,
        preset_list: PresetListController,
        layer_mutations: LayerMutations,
        *,
        on_notification: Callable[[str], None] | None = None,
    ) -> None:
        self._preset_list = preset_list
        self._mutations = layer_mutations
        self._on_notification = on_notification
        self._entry: PresetListEntry | None = None

    @property
    def entry(self) -> PresetListEntry | None:
        return self._entry

    def paste_hint(self) -> str | None:
        """Why paste is unavailable, or None when it can run."""
        if self._entry is None:
            return NOTHING_COPIED_HINT
        if not self._entry.file.is_file():
            return COPIED_MISSING_HINT
        return None

    @property
    def can_paste(self) -> bool:
        return self.paste_hint() is None

    # -- copy ----------------------------------------------------------------

    def copy_entry(self, slot: str, index: int) -> None:
        entry = self._preset_list.entry(slot, index)
        if entry is not None:
            self._take(entry)

    def copy_current(self, slot: str) -> None:
        path = self._preset_list.current_preset_path(slot)
        if path is not None:
            self.copy_path(path)

    def copy_path(self, path: Path) -> None:
        self._take(PresetListEntry(path=str(path.resolve())))

    def cut_entry(self, slot: str, index: int) -> None:
        entry = self._preset_list.entry(slot, index)
        if entry is None:
            return
        self._entry = entry
        self._preset_list.remove(slot, index, label="Cut preset", verb="Cut")

    # -- paste ---------------------------------------------------------------

    def paste_over(self, slot: str, index: int) -> None:
        if self.can_paste and self._entry is not None:
            self._preset_list.replace(
                slot, index, self._entry, label="Paste preset", verb="Pasted"
            )

    def paste_before(self, slot: str, index: int) -> None:
        if self.can_paste and self._entry is not None:
            self._preset_list.insert(
                slot, index, self._entry, label="Paste preset", verb="Pasted"
            )

    def paste_after(self, slot: str, index: int) -> None:
        if self.can_paste and self._entry is not None:
            self._preset_list.insert(
                slot, index + 1, self._entry, label="Paste preset", verb="Pasted"
            )

    def paste_at_end(self, slot: str) -> None:
        """Append the copied preset to the end of *slot*'s list (an empty list too)."""
        if self.can_paste and self._entry is not None:
            self._preset_list.insert(
                slot,
                len(self._preset_list.session.layers[slot].preset_list),
                self._entry,
                label="Paste preset",
                verb="Pasted",
            )

    def paste_preview(self, slot: str) -> None:
        """Play the copied preset on *slot* as a preview; no list changes."""
        if not self.can_paste or self._entry is None:
            return
        self._mutations.browse_to_preset(slot, preview_anchor(self._entry))

    def _take(self, entry: PresetListEntry) -> None:
        self._entry = entry
        if self._on_notification is not None:
            self._on_notification(f"Copied preset: {entry.display_name}")


@dataclass(frozen=True)
class PresetEditTarget:
    """The preset row the Edit menu's clipboard commands act on.

    ``index`` is the preset list entry, or None for the layer's Milkdrop
    Preset row. ``locked`` is True while the layer's section lock blocks edits.
    """

    slot: str
    index: int | None
    locked: bool
