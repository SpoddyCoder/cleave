"""First-run downloads gathered for the editor's welcome step.

Each projectM curated preset pack, the Demucs and Beat This weights, and (on the frozen
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
    MILKDROP_ORIGINAL = "milkdrop_original"
    MILKDROP_TEXTURES = "milkdrop_textures"
    CREAM_OF_THE_CROP = "cream_of_the_crop"
    PROJECTM_CLASSIC = "projectm_classic"
    EN_D = "en_d"
    DEMUCS = "demucs"
    DEMUCS_HQ = "demucs_hq"
    DEMUCS_6S = "demucs_6s"
    BEAT_THIS = "beat_this"
    CUDA = "cuda"


PRESET_PACK_IDS = frozenset(
    {
        FirstRunItemId.MILKDROP_ORIGINAL,
        FirstRunItemId.MILKDROP_TEXTURES,
        FirstRunItemId.CREAM_OF_THE_CROP,
        FirstRunItemId.PROJECTM_CLASSIC,
        FirstRunItemId.EN_D,
    }
)

@dataclass(frozen=True)
class FirstRunItem:
    """One download in the welcome step.

    ``name`` and ``purpose`` are user-facing: what the download is, and what
    Cleave uses it for. ``default_on`` items are ticked in the step, and only
    they bring the step back while ``welcome_done`` is unset. ``required``
    items always download with the step and cannot be switched off; while
    missing they bring the step back even after it was completed. ``needed`` and
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
    required: bool = False

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


def _pack_items() -> tuple[FirstRunItem, ...]:
    from cleave import starter_packs as packs

    def item(
        item_id: FirstRunItemId,
        pack: packs.PackSpec,
        *,
        name: str,
        purpose: str,
        default_on: bool,
        required: bool = False,
    ) -> FirstRunItem:
        return FirstRunItem(
            id=item_id,
            name=name,
            purpose=purpose,
            size_mb=pack.size_mb,
            default_on=default_on or required,
            needed=lambda: packs.pack_needed(pack),
            download=lambda on_progress: packs.download_pack(pack, on_progress),
            required=required,
        )

    return (
        item(
            FirstRunItemId.MILKDROP_ORIGINAL,
            packs.MILKDROP_ORIGINAL,
            name="Milkdrop Original",
            purpose="the presets from the last official Milkdrop release",
            default_on=True,
            required=True,
        ),
        item(
            FirstRunItemId.MILKDROP_TEXTURES,
            packs.MILKDROP_TEXTURES,
            name="Milkdrop Textures",
            purpose="the textures many presets draw with",
            default_on=True,
            required=True,
        ),
        item(
            FirstRunItemId.CREAM_OF_THE_CROP,
            packs.CREAM_OF_THE_CROP,
            name="Cream of the Crop",
            purpose="Jason Fletcher's pick of the best Milkdrop presets",
            default_on=False,
        ),
        item(
            FirstRunItemId.PROJECTM_CLASSIC,
            packs.PROJECTM_CLASSIC,
            name="projectM Classic",
            purpose="about 4,200 presets from earlier projectM releases",
            default_on=False,
        ),
        item(
            FirstRunItemId.EN_D,
            packs.EN_D,
            name="En D",
            purpose="about 50 presets created or remixed by En D",
            default_on=False,
        ),
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
    """Offered only on the frozen Windows build with a CUDA 13.2 NVIDIA driver."""
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
    """Every download the welcome step can offer, in download order.

    The preset packs come first, then the CUDA overlay: the weight downloads
    import torch, and once the bundled CPU torch is loaded the overlay only
    takes effect after a restart, so a split straight after the welcome step
    would run on the CPU.
    """
    from cleave.model_weights import (
        DEMUCS_6S_MODEL,
        DEMUCS_HQ_MODEL,
        DEMUCS_MODEL,
        beat_this_weight_spec,
        demucs_weight_spec,
    )

    candidates = (
        *_pack_items(),
        _cuda_item(),
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
            FirstRunItemId.DEMUCS_6S,
            lambda: demucs_weight_spec(DEMUCS_6S_MODEL),
            name="Demucs 6-stem",
            purpose="adds guitar and piano stems",
            default_on=False,
        ),
        _weight_item(
            FirstRunItemId.BEAT_THIS,
            beat_this_weight_spec,
            name="BeatThis!",
            purpose="beat detection AI model by the IoCP",
            default_on=True,
        ),
    )
    return tuple(item for item in candidates if item is not None)


def needed_items(items: tuple[FirstRunItem, ...]) -> tuple[FirstRunItem, ...]:
    return tuple(item for item in items if item.needed())


def welcome_needed(
    needed: tuple[FirstRunItem, ...],
    state: FirstRunState,
    *,
    presets_missing: bool,
) -> bool:
    """Show the step when a required item is missing, the preset folder has
    no presets and a pack is still offered, or a default-on item is missing
    and the step has not been completed yet. *needed* is already filtered.
    """
    for item in needed:
        if item.required:
            return True
        if presets_missing and item.id in PRESET_PACK_IDS:
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
