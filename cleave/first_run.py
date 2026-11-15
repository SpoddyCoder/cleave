"""First-run downloads gathered for the editor's welcome step.

Milkdrop starter packs, the Demucs and Beat This weights, and (on the frozen
Windows build with a new enough NVIDIA driver) the CUDA torch overlay, each as
one :class:`FirstRunItem`. No viz and no torch at import: checking what is missing
only reads the data dir and the hub cache. The editor presents the step
(``cleave.viz.welcome_host``); split-time downloads stay as the fallback for
anything the user skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from cleave.config_schema.first_run import FirstRunState

if TYPE_CHECKING:
    from cleave.model_weights import WeightSpec

DownloadProgress = Callable[[str, float | None], None]
# A download may return a note shown in place of "Done" (for example, a
# restart is needed before it takes effect).
DownloadFn = Callable[[DownloadProgress], str | None]


class FirstRunCancelled(Exception):
    """Raised from a progress callback to stop the current download."""


class FirstRunItemId(Enum):
    PRESETS = "presets"
    DEMUCS = "demucs"
    DEMUCS_HQ = "demucs_hq"
    BEAT_THIS = "beat_this"
    CUDA = "cuda"


@dataclass(frozen=True)
class FirstRunItem:
    """One download in the welcome step.

    ``name`` and ``purpose`` are user-facing: what the download is, and what
    Cleave uses it for. ``default_on`` items are ticked in the step, and only
    they bring the step back while ``welcome_done`` is unset. ``needed`` and
    ``download`` do the work; ``download`` raises the module's own error type
    on failure and may return a note to show in place of "Done".
    """

    id: FirstRunItemId
    name: str
    purpose: str
    size_mb: int
    default_on: bool
    needed: Callable[[], bool]
    download: DownloadFn

    @property
    def size_hint(self) -> str:
        return f"~{self.size_mb} MB"


class ItemOutcome(Enum):
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ItemResult:
    item: FirstRunItem
    outcome: ItemOutcome
    error: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class FirstRunResult:
    results: tuple[ItemResult, ...]

    @property
    def failed(self) -> tuple[ItemResult, ...]:
        return tuple(r for r in self.results if r.outcome is ItemOutcome.FAILED)

    @property
    def cancelled(self) -> bool:
        return any(r.outcome is ItemOutcome.CANCELLED for r in self.results)


def _presets_item() -> FirstRunItem:
    from cleave.starter_packs import (
        STARTER_PACKS_SIZE_MB,
        download_starter_packs,
        starter_packs_needed,
    )

    return FirstRunItem(
        id=FirstRunItemId.PRESETS,
        name="Milkdrop Presets",
        purpose="standard projectM preset and texture packs",
        size_mb=STARTER_PACKS_SIZE_MB,
        default_on=True,
        needed=starter_packs_needed,
        download=download_starter_packs,
    )


def _weight_item(
    item_id: FirstRunItemId,
    spec_factory: Callable[[], WeightSpec],
    *,
    name: str,
    purpose: str,
    default_on: bool,
) -> FirstRunItem | None:
    from cleave.model_weights import ensure_weight_files, missing_weight_files

    try:
        spec = spec_factory()
    except (ImportError, OSError, ValueError):
        return None

    def needed() -> bool:
        return bool(missing_weight_files(spec))

    def download(on_progress: DownloadProgress) -> None:
        ensure_weight_files(spec, on_progress=on_progress)

    return FirstRunItem(
        id=item_id,
        name=name,
        purpose=purpose,
        size_mb=spec.size_mb,
        default_on=default_on,
        needed=needed,
        download=download,
    )


def _cuda_item() -> FirstRunItem | None:
    """Offered only on the frozen Windows build with a CUDA 13 NVIDIA driver."""
    from cleave.cuda_extra import (
        CUDA_EXTRA_SIZE_MB,
        cuda_extra_installed,
        cuda_extra_supported,
        download_cuda_extra,
    )

    if not cuda_extra_supported():
        return None
    return FirstRunItem(
        id=FirstRunItemId.CUDA,
        name="CUDA Toolkit",
        purpose="much faster stem separation on your NVIDIA graphics card",
        size_mb=CUDA_EXTRA_SIZE_MB,
        default_on=False,
        needed=lambda: not cuda_extra_installed(),
        download=download_cuda_extra,
    )


def first_run_items() -> tuple[FirstRunItem, ...]:
    """Every download the welcome step can offer, in download order."""
    from cleave.model_weights import (
        DEMUCS_HQ_MODEL,
        DEMUCS_MODEL,
        beat_this_weight_spec,
        demucs_weight_spec,
    )

    candidates = (
        _presets_item(),
        _weight_item(
            FirstRunItemId.DEMUCS,
            lambda: demucs_weight_spec(DEMUCS_MODEL),
            name="Demucs",
            purpose="stem separation AI model by Meta",
            default_on=True,
        ),
        _weight_item(
            FirstRunItemId.DEMUCS_HQ,
            lambda: demucs_weight_spec(DEMUCS_HQ_MODEL),
            name="Demucs HQ",
            purpose="higher quality but slower stem separation",
            default_on=False,
        ),
        _weight_item(
            FirstRunItemId.BEAT_THIS,
            beat_this_weight_spec,
            name="BeatThis!",
            purpose="beat detection AI model by the IoCP",
            default_on=True,
        ),
        _cuda_item(),
    )
    return tuple(item for item in candidates if item is not None)


def needed_items(items: tuple[FirstRunItem, ...]) -> tuple[FirstRunItem, ...]:
    return tuple(item for item in items if item.needed())


def welcome_needed(
    needed: tuple[FirstRunItem, ...], state: FirstRunState
) -> bool:
    """Show the step when presets are missing, or a default weight is missing
    and the step has not been completed yet. *needed* is already filtered.
    """
    for item in needed:
        if item.id is FirstRunItemId.PRESETS:
            return True
        if item.default_on and not state.welcome_done:
            return True
    return False


def download_error_types() -> tuple[type[Exception], ...]:
    from cleave.cuda_extra import CudaExtraError
    from cleave.model_weights import WeightDownloadError
    from cleave.starter_packs import StarterPackError

    return (StarterPackError, WeightDownloadError, CudaExtraError)


def run_downloads(
    items: tuple[FirstRunItem, ...],
    on_progress: Callable[[FirstRunItem, str, float | None], None],
    on_result: Callable[[ItemResult], None] | None = None,
) -> FirstRunResult:
    """Download each item in order. A failure moves on to the next item.

    *on_progress* may raise :class:`FirstRunCancelled`; that item and the rest
    are reported as cancelled and nothing more runs.
    """
    errors = download_error_types()
    results: list[ItemResult] = []

    def report(result: ItemResult) -> None:
        results.append(result)
        if on_result is not None:
            on_result(result)

    for index, item in enumerate(items):
        try:
            note = item.download(
                lambda message, fraction: on_progress(item, message, fraction)
            )
        except FirstRunCancelled:
            for rest in items[index:]:
                report(ItemResult(rest, ItemOutcome.CANCELLED))
            break
        except errors as exc:
            report(ItemResult(item, ItemOutcome.FAILED, str(exc) or type(exc).__name__))
            continue
        report(ItemResult(item, ItemOutcome.DONE, note=note))
    return FirstRunResult(tuple(results))
