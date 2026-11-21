"""Ask whether to split into 4 or 6 stems.

Used for a new project (on the loading window, before the split) and by
Project > Re-separate stems (in the live session).
"""

from __future__ import annotations

from collections.abc import Callable

from cleave.stems import DEFAULT_STEM_COUNT, STEM_COUNTS, StemCount
from cleave.viz.modal import ButtonRole, ModalHost, ModalOption

NEW_PROJECT_STEMS_TITLE = "Split into how many stems?"
RESEPARATE_TITLE = "Re-separate stems"
STEM_COUNT_BODY = (
    "4 stems: drums, bass, vocals, other. 6 stems adds guitar and piano; "
    "piano separates less cleanly than the others."
)
RESEPARATE_BODY = (
    "Splits the song again and re-extracts its signals. Going from 6 stems "
    "to 4 moves guitar and piano layers to other and clears their effects."
)


def stem_count_label(count: StemCount, *, current: StemCount | None = None) -> str:
    label = f"{count} stems"
    return f"{label} (current)" if count == current else label


def prompt_stem_count(
    host: ModalHost,
    title: str,
    on_pick: Callable[[StemCount], None],
    on_cancel: Callable[[], None] | None = None,
    *,
    current: StemCount | None = None,
    body: str = STEM_COUNT_BODY,
) -> None:
    """One button per stem count, then Cancel.

    Focus starts on 4 stems for a new project, or on the count the project
    does not have yet when *current* is given.
    """
    if current is None:
        focus_count: StemCount = DEFAULT_STEM_COUNT
    else:
        focus_count = next(c for c in STEM_COUNTS if c != current)

    def pick(count: StemCount) -> Callable[[], None]:
        return lambda: on_pick(count)

    def cancel() -> None:
        if on_cancel is not None:
            on_cancel()

    options = [
        ModalOption(
            stem_count_label(count, current=current),
            pick(count),
            ButtonRole.PRIMARY if count == focus_count else ButtonRole.PLAIN,
        )
        for count in STEM_COUNTS
    ]
    options.append(ModalOption("Cancel", cancel))
    host.prompt_buttons(
        title,
        options,
        on_dismiss=on_cancel,
        initial_focus_index=STEM_COUNTS.index(focus_count),
        body=body,
    )
