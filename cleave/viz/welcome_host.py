"""The "Welcome to Cleave" first-run step on an already-open loading window.

One form lists every missing download (presets and model weights). Download
runs them in order under a progress dialog with a status line per item and a
Cancel button. Failures are reported in the same step, with Retry.
"""

from __future__ import annotations

import pygame
import yaml

from cleave.config_schema.first_run import FirstRunState
from cleave.first_run import (
    FirstRunCancelled,
    FirstRunItem,
    FirstRunResult,
    ItemOutcome,
    ItemResult,
    run_downloads,
)
from cleave.user_config import persist_first_run_state
from cleave.viz.loading import LoadingWindow
from cleave.viz.loading_modal import present_modal_frame, run_modal
from cleave.viz.modal import (
    ButtonRole,
    FormField,
    FormSpec,
    FormValues,
    ModalHost,
    ModalLabeledLine,
    ModalOption,
)

WELCOME_TITLE = "Welcome to Cleave"
_WELCOME_BODY = (
    "Cleave needs a few one-time downloads. "
    "Anything you skip downloads when it is first needed."
)
_SECTION = "Downloads"
_OFF_ON = ("Off", "On")
_FAILED_TITLE = "Some downloads failed"
_FAILED_BODY = "A network connection is required the first time."
_CANCELLING = "Cancelling..."

_WAITING = "Waiting"
_DOWNLOADING = "Downloading"
_DONE = "Done"
_FAILED = "Failed"
_CANCELLED = "Cancelled"


def _choose(
    window: LoadingWindow, host: ModalHost, items: tuple[FirstRunItem, ...]
) -> tuple[FirstRunItem, ...] | None:
    """Return the ticked items (empty on Skip), or None when the window closed."""
    chosen: list[tuple[FirstRunItem, ...]] = [()]

    def selected(values: FormValues) -> tuple[FirstRunItem, ...]:
        return tuple(item for item in items if values.get(item.id.value) == 1)

    def info(values: FormValues) -> str:
        total = sum(item.size_mb for item in selected(values))
        return f"~{total} MB to download" if total else "nothing to download"

    def confirm(values: FormValues) -> None:
        chosen[0] = selected(values)

    host.prompt_form(
        FormSpec(
            title=WELCOME_TITLE,
            body=_WELCOME_BODY,
            fields=tuple(
                FormField(
                    id=item.id.value,
                    label=f"{item.label} ({item.size_hint})",
                    options=_OFF_ON,
                    value=1 if item.default_on else 0,
                    help=(item.help,),
                    section=_SECTION,
                )
                for item in items
            ),
            confirm_label="Download",
            on_confirm=confirm,
            cancel_label="Skip",
            info=info,
            help=(_WELCOME_BODY,),
        )
    )
    if not run_modal(window, host):
        return None
    return chosen[0]


class _DownloadView:
    """Status lines and overall fraction for one download pass."""

    def __init__(self, items: tuple[FirstRunItem, ...]) -> None:
        self.items = items
        self.status = {item.id: _WAITING for item in items}
        self.fraction = 0.0

    def lines(self) -> tuple[ModalLabeledLine, ...]:
        return tuple(
            ModalLabeledLine(item.label, self.status[item.id]) for item in self.items
        )

    def progress(self, item: FirstRunItem, fraction: float | None) -> None:
        index = self.items.index(item)
        item_frac = 0.0 if fraction is None else max(0.0, min(1.0, fraction))
        if fraction is None:
            self.status[item.id] = _DOWNLOADING
        else:
            self.status[item.id] = f"{_DOWNLOADING} {round(item_frac * 100)}%"
        self.fraction = (index + item_frac) / len(self.items)

    def finish(self, result: ItemResult) -> None:
        if result.outcome is ItemOutcome.DONE:
            self.status[result.item.id] = _DONE
        elif result.outcome is ItemOutcome.FAILED:
            self.status[result.item.id] = _FAILED
        else:
            self.status[result.item.id] = _CANCELLED
        done = sum(1 for status in self.status.values() if status != _WAITING)
        self.fraction = done / len(self.items)


def _download(
    window: LoadingWindow, host: ModalHost, items: tuple[FirstRunItem, ...]
) -> FirstRunResult | None:
    """Download *items* under a progress dialog. None when the window closed."""
    view = _DownloadView(items)
    cancelled = [False]
    clock = pygame.time.Clock()

    def cancel() -> None:
        cancelled[0] = True
        host.prompt_progress(
            _CANCELLING, labeled_lines=view.lines(), fraction=view.fraction
        )

    def frame(message: str | None = None) -> None:
        host.update_progress(view.fraction, message=message, labeled_lines=view.lines())
        present_modal_frame(window, host, clock.tick() / 1000.0)

    def on_progress(item: FirstRunItem, _message: str, fraction: float | None) -> None:
        if not cancelled[0]:
            view.progress(item, fraction)
            frame(f"Downloading {item.label}...")
        else:
            frame()
        if cancelled[0] or window.quit_requested:
            raise FirstRunCancelled()

    def on_result(result: ItemResult) -> None:
        view.finish(result)
        frame()

    host.prompt_progress(
        f"Downloading {items[0].label}...",
        labeled_lines=view.lines(),
        on_cancel=cancel,
    )
    result = run_downloads(items, on_progress, on_result)
    host.dismiss()
    if window.quit_requested:
        return None
    return result


def _ask_retry(
    window: LoadingWindow, host: ModalHost, failed: tuple[ItemResult, ...]
) -> bool | None:
    """True for Retry, False for Continue, None when the window closed."""
    answer = [False]

    def retry() -> None:
        answer[0] = True

    host.prompt_buttons(
        _FAILED_TITLE,
        [
            ModalOption("Retry", retry, ButtonRole.PRIMARY),
            ModalOption("Continue", lambda: None),
        ],
        labeled_lines=tuple(
            ModalLabeledLine(r.item.label, r.error or _FAILED) for r in failed
        ),
        body=_FAILED_BODY,
    )
    if not run_modal(window, host):
        return None
    return answer[0]


def _mark_done() -> None:
    try:
        persist_first_run_state(FirstRunState(welcome_done=True))
    except (OSError, ValueError, yaml.YAMLError):
        return


def run_welcome(window: LoadingWindow, items: tuple[FirstRunItem, ...]) -> None:
    """Offer *items* (already filtered to the missing ones) and download the choice.

    Downloading or skipping marks the step done in the user config. Closing
    the window leaves it unmarked, so it shows again next launch.
    """
    if not items:
        return
    host = ModalHost()
    chosen = _choose(window, host, items)
    if chosen is None:
        return
    while chosen:
        result = _download(window, host, chosen)
        if result is None:
            return
        if result.cancelled or not result.failed:
            break
        retry = _ask_retry(window, host, result.failed)
        if retry is None:
            return
        if not retry:
            break
        chosen = tuple(r.item for r in result.failed)
    _mark_done()
