"""First-run item selection and the download runner, without a network."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cleave.config_schema.first_run import FirstRunState
from cleave.first_run import (
    FirstRunCancelled,
    FirstRunItem,
    FirstRunItemId,
    ItemOutcome,
    needed_items,
    run_downloads,
    welcome_needed,
)
from cleave.model_weights import WeightDownloadError


def _item(
    item_id: FirstRunItemId,
    *,
    default_on: bool = True,
    needed: bool = True,
    download: Callable[..., None] = lambda _progress: None,
) -> FirstRunItem:
    return FirstRunItem(
        id=item_id,
        label=item_id.value,
        size_mb=10,
        default_on=default_on,
        help="",
        needed=lambda: needed,
        download=download,
    )


PRESETS = _item(FirstRunItemId.PRESETS)
DEMUCS = _item(FirstRunItemId.DEMUCS)
HQ = _item(FirstRunItemId.DEMUCS_HQ, default_on=False)


@pytest.mark.parametrize(
    ("needed", "done", "expected"),
    [
        ((), False, False),
        ((PRESETS,), True, True),
        ((DEMUCS,), False, True),
        ((DEMUCS,), True, False),
        ((HQ,), False, False),
        ((HQ, PRESETS), True, True),
    ],
)
def test_welcome_needed(needed, done, expected) -> None:
    assert welcome_needed(needed, FirstRunState(welcome_done=done)) is expected


def test_needed_items_filters() -> None:
    have = _item(FirstRunItemId.BEAT_THIS, needed=False)
    assert needed_items((PRESETS, have, DEMUCS)) == (PRESETS, DEMUCS)


def test_run_downloads_continues_past_a_failure() -> None:
    def fail(_progress) -> None:
        raise WeightDownloadError("no network")

    calls: list[str] = []

    def ok(progress) -> None:
        progress("msg", 0.5)
        calls.append("ok")

    seen: list[tuple[str, float | None]] = []
    items = (
        _item(FirstRunItemId.DEMUCS, download=fail),
        _item(FirstRunItemId.BEAT_THIS, download=ok),
    )
    result = run_downloads(items, lambda item, _m, f: seen.append((item.label, f)))

    assert [r.outcome for r in result.results] == [ItemOutcome.FAILED, ItemOutcome.DONE]
    assert result.failed[0].error == "no network"
    assert calls == ["ok"]
    assert seen == [("beat_this", 0.5)]
    assert not result.cancelled


def test_run_downloads_cancel_stops_the_rest() -> None:
    later: list[str] = []

    def first(progress) -> None:
        progress("msg", 0.1)

    items = (
        _item(FirstRunItemId.PRESETS, download=first),
        _item(FirstRunItemId.DEMUCS, download=lambda _p: later.append("x")),
    )

    def on_progress(_item, _message, _fraction) -> None:
        raise FirstRunCancelled()

    result = run_downloads(items, on_progress)
    assert [r.outcome for r in result.results] == [
        ItemOutcome.CANCELLED,
        ItemOutcome.CANCELLED,
    ]
    assert result.cancelled
    assert later == []
