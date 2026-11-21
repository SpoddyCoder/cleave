"""Ask how to split a song: 4 stems, 4 stems High Quality, or 6 stems.

Used for a new project (on the loading window, before the split) and by
Project > Re-separate stems (in the live session).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cleave.stems import StemCount
from cleave.viz.modal import ButtonRole, ModalHost, ModalOption

NEW_PROJECT_STEMS_TITLE = "Split into how many stems?"
RESEPARATE_TITLE = "Re-separate stems"
STEM_COUNT_BODY = (
    "4 stems: drums, bass, vocals, other. 4 stems HQ separates more cleanly "
    "but takes longer. 6 stems adds guitar and piano; piano separates less "
    "cleanly than the others."
)
RESEPARATE_BODY = (
    "Splits the song again and re-extracts its signals. Going from 6 stems "
    "to 4 moves guitar and piano layers to other and clears their effects."
)


@dataclass(frozen=True)
class SplitChoice:
    """One answer to the dialog: stem count, and High Quality separation."""

    stem_count: StemCount
    high_quality: bool = False

    @property
    def label(self) -> str:
        suffix = " HQ" if self.high_quality else ""
        return f"{self.stem_count} stems{suffix}"


SPLIT_CHOICES = (SplitChoice(4), SplitChoice(4, high_quality=True), SplitChoice(6))
DEFAULT_SPLIT = SPLIT_CHOICES[0]


def project_split(project_dir: Path) -> SplitChoice:
    """How *project_dir* was last split, from the Demucs model in its manifest."""
    from cleave.model_weights import DEMUCS_HQ_MODEL
    from cleave.project import load_manifest, manifest_path
    from cleave.stems import project_stem_count

    count = project_stem_count(project_dir)
    high_quality = (
        manifest_path(project_dir).is_file()
        and load_manifest(project_dir).demucs_model == DEMUCS_HQ_MODEL
    )
    return SplitChoice(count, high_quality=high_quality)


def split_label(choice: SplitChoice, *, current: SplitChoice | None = None) -> str:
    return f"{choice.label} (current)" if choice == current else choice.label


def prompt_split(
    host: ModalHost,
    title: str,
    on_pick: Callable[[SplitChoice], None],
    on_cancel: Callable[[], None] | None = None,
    *,
    current: SplitChoice | None = None,
    default: SplitChoice = DEFAULT_SPLIT,
    body: str = STEM_COUNT_BODY,
) -> None:
    """One button per :data:`SPLIT_CHOICES`, then Cancel.

    Focus starts on *default* for a new project, or on the first choice that
    differs from *current* when it is given.
    """
    if current is None:
        focus = default
    else:
        focus = next(c for c in SPLIT_CHOICES if c != current)

    def pick(choice: SplitChoice) -> Callable[[], None]:
        return lambda: on_pick(choice)

    def cancel() -> None:
        if on_cancel is not None:
            on_cancel()

    options = [
        ModalOption(
            split_label(choice, current=current),
            pick(choice),
            ButtonRole.PRIMARY if choice == focus else ButtonRole.PLAIN,
        )
        for choice in SPLIT_CHOICES
    ]
    options.append(ModalOption("Cancel", cancel))
    host.prompt_buttons(
        title,
        options,
        on_dismiss=on_cancel,
        initial_focus_index=SPLIT_CHOICES.index(focus),
        body=body,
    )
