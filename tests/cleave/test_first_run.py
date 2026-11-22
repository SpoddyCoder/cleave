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
    required: bool = False,
    download: Callable[..., None] = lambda _progress: None,
) -> FirstRunItem:
    return FirstRunItem(
        id=item_id,
        name=item_id.value,
        purpose="",
        size_mb=10,
        default_on=default_on,
        needed=lambda: needed,
        download=download,
        required=required,
    )


PRESETS = _item(FirstRunItemId.MILKDROP_ORIGINAL)
REQUIRED = _item(FirstRunItemId.MILKDROP_TEXTURES, required=True)
CLASSIC = _item(FirstRunItemId.PROJECTM_CLASSIC, default_on=False)
DEMUCS = _item(FirstRunItemId.DEMUCS)
HQ = _item(FirstRunItemId.DEMUCS_HQ, default_on=False)


@pytest.mark.parametrize(
    ("needed", "done", "missing", "expected"),
    [
        ((), False, True, False),
        ((PRESETS,), True, True, True),
        ((PRESETS,), True, False, False),
        ((PRESETS,), False, False, True),
        ((CLASSIC,), True, True, True),
        ((CLASSIC,), False, False, False),
        ((DEMUCS,), False, False, True),
        ((DEMUCS,), True, False, False),
        ((HQ,), False, False, False),
        ((HQ, PRESETS), True, True, True),
        ((REQUIRED,), True, False, True),
    ],
)
def test_welcome_needed(needed, done, missing, expected) -> None:
    state = FirstRunState(welcome_done=done)
    assert welcome_needed(needed, state, presets_missing=missing) is expected


def test_preset_packs_are_separate_items() -> None:
    from cleave.first_run import PRESET_PACK_IDS, first_run_items

    items = {item.id: item for item in first_run_items()}
    assert PRESET_PACK_IDS <= set(items)
    on = {i for i in PRESET_PACK_IDS if items[i].default_on}
    assert on == {FirstRunItemId.MILKDROP_ORIGINAL, FirstRunItemId.MILKDROP_TEXTURES}
    required = {i for i, item in items.items() if item.required}
    assert required == on
    # Packs first; CUDA still before any weight download.
    order = list(items)
    assert set(order[: len(PRESET_PACK_IDS)]) == PRESET_PACK_IDS


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
    result = run_downloads(items, lambda item, _m, f: seen.append((item.name, f)))

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
        _item(FirstRunItemId.MILKDROP_ORIGINAL, download=first),
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


def test_download_note_replaces_done() -> None:
    item = _item(FirstRunItemId.CUDA, download=lambda _progress: "restart")
    result = run_downloads((item,), lambda *_a: None)
    assert result.results[0].outcome is ItemOutcome.DONE
    assert result.results[0].note == "restart"


def test_cuda_item_only_when_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    import cleave.cuda_extra as cuda_extra
    from cleave.first_run import first_run_items

    monkeypatch.setattr(cuda_extra, "cuda_extra_supported", lambda: False)
    assert FirstRunItemId.CUDA not in {item.id for item in first_run_items()}

    monkeypatch.setattr(cuda_extra, "cuda_extra_supported", lambda: True)
    monkeypatch.setattr(cuda_extra, "cuda_extra_installed", lambda: False)
    items = {item.id: item for item in first_run_items()}
    cuda = items[FirstRunItemId.CUDA]
    assert cuda.default_on is False
    assert cuda.needed()
    # Before the weights, so it activates before one imports CPU torch.
    order = list(items)
    assert order.index(FirstRunItemId.CUDA) < order.index(FirstRunItemId.DEMUCS)

    monkeypatch.setattr(cuda_extra, "cuda_extra_installed", lambda: True)
    items = {item.id: item for item in first_run_items()}
    assert not items[FirstRunItemId.CUDA].needed()
