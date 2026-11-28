"""Settings > Manage tags: see every favourite tag and act on one.

One dialog lists the tags with how many presets each holds, then New tag….
Pick a tag and an action: Show presets opens the preset browser in that tag;
Rename and Delete open their own dialog, then come back here. The dialogs
themselves belong to :class:`PresetCurationController`, shared with the
preset browser's right-click menu.
"""

from __future__ import annotations

from collections.abc import Callable

from cleave.preset_library import FavouriteTag, PresetLibrary
from cleave.viz.modal import FormField, FormSpec, FormValues, ModalHost
from cleave.viz.preset_curation_controls import (
    NEW_TAG_LABEL,
    PresetCurationController,
    preset_count_phrase,
)

MANAGE_TAGS_TITLE = "Manage tags"
NEW_TAG_BUTTON = "New tag"
NO_TAGS_BODY = (
    "You have no tags yet. Tags sort your favourites into groups of your own. "
    "Make one here, or press T on a preset (or right-click it and open Tags)."
)
ACTIONS: tuple[str, ...] = ("Show presets", "Rename…", "Delete…")
_SHOW, _RENAME, _DELETE = range(len(ACTIONS))


def tag_option_label(tag: str, count: int) -> str:
    return f"{tag} ({preset_count_phrase(count)})"


class TagManagerController:
    """Open the Manage tags dialog and run the chosen action.

    ``show_tag`` opens the preset browser in a tag.
    """

    def __init__(
        self,
        library: PresetLibrary,
        modal_host: ModalHost,
        curation: PresetCurationController,
        *,
        show_tag: Callable[[FavouriteTag], None],
    ) -> None:
        self._library = library
        self._modal = modal_host
        self._curation = curation
        self._show_tag = show_tag

    def prompt(self, *, select: str | None = None) -> None:
        """Open the dialog, with *select* (a tag name) chosen when given."""
        if self._modal.active:
            return
        tags = self._library.tags()
        if not tags:
            self._modal.prompt_confirm(
                MANAGE_TAGS_TITLE,
                NEW_TAG_BUTTON,
                lambda: self._curation.prompt_new_tag(on_done=self._reopen),
                body=NO_TAGS_BODY,
            )
            return
        options = (
            *(tag_option_label(tag, self._library.tag_count(tag)) for tag in tags),
            NEW_TAG_LABEL,
        )
        new_index = len(tags)
        self._modal.prompt_form(
            FormSpec(
                title=MANAGE_TAGS_TITLE,
                fields=(
                    FormField(
                        "tag",
                        "tag",
                        options,
                        tags.index(select) if select in tags else 0,
                        help=(
                            "Your favourite tags, with how many presets each holds. "
                            "Choose New tag… to add one.",
                        ),
                        vertical=True,
                    ),
                    FormField(
                        "action",
                        "action",
                        ACTIONS,
                        visible=lambda values: values["tag"] != new_index,
                        help=(
                            "Show presets opens the preset browser in the tag. "
                            "Delete takes the tag off its presets; they stay favourites.",
                        ),
                    ),
                ),
                confirm_label="OK",
                cancel_label="Close",
                on_confirm=lambda values: self._run(tags, values),
                help=(
                    "Tags sort your favourites into groups of your own. In the "
                    "preset browser they are folders inside Favourites.",
                ),
            )
        )

    def _reopen(self, select: str | None = None) -> None:
        self.prompt(select=select)

    def _run(self, tags: tuple[str, ...], values: FormValues) -> None:
        index = values["tag"]
        if index >= len(tags):
            self._curation.prompt_new_tag(on_done=self._reopen)
            return
        tag = tags[index]
        action = values["action"]
        if action == _SHOW:
            self._show_tag(FavouriteTag(tag))
        elif action == _RENAME:
            self._curation.prompt_rename_tag(
                tag, on_done=lambda: self._reopen(self._renamed(tag))
            )
        elif action == _DELETE:
            self._curation.prompt_delete_tag(tag, on_done=self._reopen)

    def _renamed(self, tag: str) -> str | None:
        """*tag* after a rename: itself if unchanged, else None (the first tag)."""
        return tag if tag in self._library.tags() else None
