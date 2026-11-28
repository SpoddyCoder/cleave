"""Settings > Back up / Restore preset curation.

Back up says what it will save and where, then on confirm writes the
library's favourites, tags, blacklist, and roles to the backups folder (no file
dialog) and says what it wrote. Restore picks a backup in the
file picker, previews it, and applies it as Merge or Replace on the live
library, after saving the current curation as a backup of its own.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from cleave.preset_curation import (
    Curation,
    CurationBackupError,
    RestorePreview,
    back_up_library,
    count_curation,
    library_curation,
    preview_restore,
    read_backup,
    restore_into,
)
from cleave.preset_library import PresetLibrary
from cleave.viz.modal import ButtonRole, ModalHost, ModalLabeledLine, ModalOption

BACK_UP_TITLE = "Back up preset curation"
BACK_UP_LABEL = "Back up"
BACK_UP_BODY = (
    "Saves your favourites, tags, blacklist marks, and roles to a new file in the "
    "backups folder. Nothing in your presets or curation changes. Copy the "
    "file to another computer and use Restore preset curation there to bring "
    "them back."
)
BACKED_UP_TITLE = "Preset curation backed up"
NOTHING_TITLE = "Nothing to back up"
NOTHING_BODY = (
    "No preset is a favourite, blacklisted, or given a role yet. "
    "Curate some presets first."
)
BACKUP_FAILED_TITLE = "Could not back up preset curation"
RESTORE_TITLE = "Restore preset curation"
RESTORE_FAILED_TITLE = "Could not restore preset curation"
EMPTY_BACKUP_BODY = "This backup has no curated presets in it."
SHOW_IN_FOLDER = "Show in folder"
MERGE_LABEL = "Merge"
REPLACE_LABEL = "Replace"


def restore_body(preview: RestorePreview) -> str:
    """Explain Merge and Replace for this backup."""
    replace = (
        f"Replace clears your current curation ({preview.current.summary()}) first."
        if preview.current.presets
        else "You have no curation yet, so Merge and Replace do the same."
    )
    return (
        "Merge adds this backup's favourites, tags, blacklist marks, and roles "
        "to yours; a tag joins one of yours with the same name; where a preset "
        "already has a different role, the backup's wins. "
        f"{replace} Your current curation is saved as a backup before anything "
        "changes."
    )


def restore_lines(path: Path, preview: RestorePreview) -> tuple[ModalLabeledLine, ...]:
    total = preview.counts.presets
    missing = total - preview.installed
    installed = f"{preview.installed:,} of {total:,}"
    if missing:
        installed += "; the rest apply when you add those presets"
    lines = [
        ModalLabeledLine("File", path.name),
        ModalLabeledLine("Contains", preview.counts.summary()),
        ModalLabeledLine("In your presets", installed),
    ]
    changes = preview.role_changes
    if changes:
        who = "1 preset gets" if changes == 1 else f"{changes:,} presets get"
        lines.append(
            ModalLabeledLine("Role changes", f"{who} a different role on Merge")
        )
    return tuple(lines)


def restored_message(replace: bool, preview: RestorePreview, safety: Path | None) -> str:
    verb = "replaced" if replace else "merged"
    message = f"Preset curation {verb}: {preview.counts.summary()}"
    if safety is not None:
        message += f". Previous curation saved as {safety.name}"
    return message


class CurationBackupController:
    """Back up and restore the library's curation from the Settings menu.

    ``prompt_pick_backup`` opens the file picker and calls back with the
    chosen file. ``open_folder`` shows a folder in the file manager.
    """

    def __init__(
        self,
        library: PresetLibrary,
        modal_host: ModalHost,
        *,
        backups_dir: Callable[[], Path],
        prompt_pick_backup: Callable[[Callable[[Path], None]], None],
        open_folder: Callable[[Path], None],
        on_notification: Callable[[str], None],
    ) -> None:
        self._library = library
        self._modal = modal_host
        self._backups_dir = backups_dir
        self._prompt_pick_backup = prompt_pick_backup
        self._open_folder = open_folder
        self._notify = on_notification

    def prompt_back_up(self) -> None:
        """Say what a backup will hold and where it goes; Back up writes it."""
        if self._modal.active:
            return
        curation = library_curation(self._library)
        if curation.empty:
            self._modal.prompt_notice(NOTHING_TITLE, body=NOTHING_BODY)
            return
        self._modal.prompt_confirm(
            BACK_UP_TITLE,
            BACK_UP_LABEL,
            self._back_up,
            body=BACK_UP_BODY,
            labeled_lines=(
                ModalLabeledLine("Contains", count_curation(curation).summary()),
                ModalLabeledLine("Folder", str(self._backups_dir())),
            ),
        )

    def _back_up(self) -> None:
        folder = self._backups_dir()
        try:
            path, counts = back_up_library(self._library, folder)
        except CurationBackupError as exc:
            self._modal.prompt_notice(BACKUP_FAILED_TITLE, body=str(exc))
            return
        self._modal.prompt_buttons(
            BACKED_UP_TITLE,
            [
                ModalOption(SHOW_IN_FOLDER, lambda: self._show_folder(folder)),
                ModalOption("OK", lambda: None, ButtonRole.PRIMARY),
            ],
            initial_focus_index=1,
            body=f"Saved {counts.summary()}.",
            labeled_lines=(ModalLabeledLine("File", str(path)),),
        )

    def prompt_restore(self) -> None:
        if self._modal.active:
            return
        self._prompt_pick_backup(self.restore_from)

    def restore_from(self, path: Path) -> None:
        """Preview *path* and ask Merge, Replace, or Cancel."""
        try:
            curation = read_backup(path)
        except CurationBackupError as exc:
            self._modal.prompt_notice(RESTORE_FAILED_TITLE, body=str(exc))
            return
        if curation.empty:
            self._modal.prompt_notice(RESTORE_TITLE, body=EMPTY_BACKUP_BODY)
            return
        preview = preview_restore(self._library, curation)
        self._modal.prompt_buttons(
            RESTORE_TITLE,
            [
                ModalOption(
                    MERGE_LABEL,
                    lambda: self._apply(curation, preview, replace=False),
                    ButtonRole.PRIMARY,
                ),
                ModalOption(
                    REPLACE_LABEL, lambda: self._apply(curation, preview, replace=True)
                ),
                ModalOption("Cancel", lambda: None),
            ],
            body=restore_body(preview),
            labeled_lines=restore_lines(path, preview),
        )

    def _apply(
        self,
        curation: Curation,
        preview: RestorePreview,
        *,
        replace: bool,
    ) -> None:
        try:
            safety = restore_into(
                self._library,
                curation,
                replace=replace,
                safety_dir=self._backups_dir(),
            )
        except CurationBackupError as exc:
            self._modal.prompt_notice(
                RESTORE_FAILED_TITLE,
                body=f"Your current curation could not be saved first, so nothing changed. {exc}",
            )
            return
        self._notify(restored_message(replace, preview, safety))

    def _show_folder(self, folder: Path) -> None:
        try:
            self._open_folder(folder)
        except OSError as exc:
            self._notify(f"Could not open the backups folder: {exc}")
