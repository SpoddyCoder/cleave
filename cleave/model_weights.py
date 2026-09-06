"""First-run Demucs and Beat This weight downloads into ``model_cache_dir``.

Pre-checks torch-hub ``checkpoints/`` before fetching. Missing weights get a
named status line (and a byte bar when hub tqdm exposes a total). Cached hits
are silent. Failed fetches raise :class:`WeightDownloadError`.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError

from cleave.paths import model_cache_dir

WeightProgress = Callable[[str, float | None], None]

# Demucs 4.0.1 ``remote/files.txt`` has no byte sizes. Typical Hybrid Transformer
# ``.th`` is ~80 MB; Beat This ``final0`` is ~78 MB (hub file_name below).
_DEMUCS_CHECKPOINT_MB = 80
_BEAT_THIS_CHECKPOINT_MB = 78
_DEMUCS_ROOT_URL = "https://dl.fbaipublicfiles.com/demucs/"
# Matches ``beat_this.inference.CHECKPOINT_URL`` (beat_this 1.1.0); do not import
# that module here (it pulls torch).
_BEAT_THIS_CHECKPOINT_URL = (
    "https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp"
)
_HUB_HASH_REGEX = re.compile(r"-([a-f0-9]*)\.")
_PROGRESS_MIN_INTERVAL_SEC = 0.1
_PROGRESS_MIN_DELTA = 0.01

BEAT_THIS_CHECKPOINT = "final0"


class WeightDownloadError(RuntimeError):
    """First-run weight fetch failed; a network is required the first time."""


@dataclass(frozen=True)
class WeightFile:
    """One torch-hub checkpoint: cache filename and download URL."""

    filename: str
    url: str


@dataclass(frozen=True)
class WeightSpec:
    """User-facing label plus the hub files that must exist before load."""

    label: str
    size_hint: str
    files: tuple[WeightFile, ...]


def hub_checkpoints_dir(cache_dir: Path | None = None) -> Path:
    """Return ``<hub dir>/checkpoints`` (torch hub default under ``set_dir``)."""
    root = Path(cache_dir) if cache_dir is not None else model_cache_dir()
    return root / "checkpoints"


def download_start_message(spec: WeightSpec) -> str:
    return (
        f"Downloading {spec.label} ({spec.size_hint}, "
        "one-time into the data dir)..."
    )


def download_done_message(spec: WeightSpec) -> str:
    return f"Downloaded {spec.label}."


def download_failed_message(spec: WeightSpec) -> str:
    return (
        f"Failed to download {spec.label}. "
        "A network connection is required the first time."
    )


def beat_this_weight_spec(checkpoint: str = BEAT_THIS_CHECKPOINT) -> WeightSpec:
    """Beat This hub file ``beat_this-<checkpoint>.ckpt`` (``final0`` by default)."""
    filename = f"beat_this-{checkpoint}.ckpt"
    url = f"{_BEAT_THIS_CHECKPOINT_URL}/{checkpoint}.ckpt"
    return WeightSpec(
        label=f"Beat This {checkpoint}",
        size_hint=f"~{_BEAT_THIS_CHECKPOINT_MB} MB",
        files=(WeightFile(filename=filename, url=url),),
    )


def demucs_weight_spec(model: str) -> WeightSpec:
    """Resolve Demucs bag *model* to hub ``.th`` files from the installed repo.

    Reads ``demucs/remote/*.yaml`` and ``files.txt`` (no torch). Cleave uses
    ``htdemucs`` (one file) and ``htdemucs_ft`` (four-file bag).
    """
    import yaml

    import demucs

    remote = Path(demucs.__file__).resolve().parent / "remote"
    urls = _parse_demucs_remote_files(remote / "files.txt")
    yaml_path = remote / f"{model}.yaml"
    if yaml_path.is_file():
        bag = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        signatures = list(bag["models"])
    elif model in urls:
        signatures = [model]
    else:
        raise ValueError(f"unknown Demucs model: {model}")

    files: list[WeightFile] = []
    for sig in signatures:
        try:
            url = urls[sig]
        except KeyError as exc:
            raise ValueError(
                f"Demucs model {model!r} references missing signature {sig!r}"
            ) from exc
        files.append(WeightFile(filename=url.rsplit("/", 1)[-1], url=url))
    if not files:
        raise ValueError(f"Demucs model {model!r} has no checkpoint files")
    size_mb = _DEMUCS_CHECKPOINT_MB * len(files)
    return WeightSpec(
        label=f"Demucs {model}",
        size_hint=f"~{size_mb} MB",
        files=tuple(files),
    )


def missing_weight_files(
    spec: WeightSpec, cache_dir: Path | None = None
) -> tuple[WeightFile, ...]:
    """Return hub files that are not already present under ``checkpoints/``."""
    dest_dir = hub_checkpoints_dir(cache_dir)
    return tuple(
        item
        for item in spec.files
        if not _checkpoint_present(dest_dir / item.filename)
    )


def ensure_weight_files(
    spec: WeightSpec,
    *,
    on_progress: WeightProgress | None = None,
    cache_dir: Path | None = None,
) -> bool:
    """Download missing checkpoints for *spec*.

    Return True when a fetch ran. Cached hits are silent. *on_progress* is the
    editor loading-screen hook; when omitted, start/done lines go to stderr
    (``cleave separate``, checkout, CI). Byte totals from hub tqdm map to
    fraction 0-1; if hub gives no total, the start line still includes the
    size hint.
    """
    import ssl

    import torch
    from torch.hub import download_url_to_file

    cache = Path(cache_dir) if cache_dir is not None else model_cache_dir()
    torch.hub.set_dir(str(cache))
    dest_dir = hub_checkpoints_dir(cache)
    dest_dir.mkdir(parents=True, exist_ok=True)

    missing = missing_weight_files(spec, cache)
    if not missing:
        return False

    start = download_start_message(spec)
    _report(on_progress, start, None)
    aggregator = _DownloadProgress(len(missing), on_progress, start)
    try:
        with _intercept_hub_tqdm(
            aggregator.on_bytes, show_console=on_progress is None
        ):
            for item in missing:
                download_url_to_file(
                    item.url,
                    str(dest_dir / item.filename),
                    hash_prefix=_hub_hash_prefix(item.filename),
                    progress=True,
                )
                aggregator.finish_file()
    except (URLError, TimeoutError, ConnectionError, ssl.SSLError) as exc:
        raise WeightDownloadError(download_failed_message(spec)) from exc

    _report(on_progress, download_done_message(spec), None)
    return True


def _checkpoint_present(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _hub_hash_prefix(filename: str) -> str | None:
    match = _HUB_HASH_REGEX.search(filename)
    prefix = match.group(1) if match else None
    return prefix or None


def _parse_demucs_remote_files(remote_file_list: Path) -> dict[str, str]:
    """Same layout as ``demucs.pretrained._parse_remote_files`` (no torch)."""
    root = ""
    models: dict[str, str] = {}
    for raw in remote_file_list.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("root:"):
            root = line.split(":", 1)[1].strip()
            continue
        sig = line.split("-", 1)[0]
        models[sig] = _DEMUCS_ROOT_URL + root + line
    return models


def _report(
    on_progress: WeightProgress | None, message: str, fraction: float | None
) -> None:
    if on_progress is not None:
        on_progress(message, fraction)
        return
    if fraction is None:
        print(message, file=sys.stderr, flush=True)


class _DownloadProgress:
    """Map per-file hub tqdm bytes onto one 0-1 fraction for *file_count* files."""

    def __init__(
        self,
        file_count: int,
        on_progress: WeightProgress | None,
        message: str,
    ) -> None:
        self._file_count = max(1, file_count)
        self._on_progress = on_progress
        self._message = message
        self._files_done = 0
        self._last_frac = -1.0
        self._last_t = 0.0

    def on_bytes(self, n: int, total: int | None) -> None:
        if self._on_progress is None:
            return
        if total is None or total <= 0:
            self._on_progress(self._message, None)
            return
        file_frac = min(1.0, n / float(total))
        overall = (self._files_done + file_frac) / self._file_count
        self._emit(overall)

    def finish_file(self) -> None:
        self._files_done += 1
        if self._on_progress is not None:
            self._emit(self._files_done / self._file_count)

    def _emit(self, fraction: float) -> None:
        now = time.monotonic()
        if (
            fraction < 1.0
            and self._last_frac >= 0.0
            and (now - self._last_t) < _PROGRESS_MIN_INTERVAL_SEC
            and abs(fraction - self._last_frac) < _PROGRESS_MIN_DELTA
        ):
            return
        self._last_t = now
        self._last_frac = fraction
        self._on_progress(self._message, fraction)


@contextmanager
def _intercept_hub_tqdm(
    on_bytes: Callable[[int, int | None], None],
    *,
    show_console: bool,
) -> Iterator[None]:
    """Wrap ``torch.hub.tqdm`` so byte updates reach *on_bytes* (and the window)."""
    import torch.hub as hub

    inner_cls = hub.tqdm

    class HubTqdm:
        def __init__(self, *args: object, **kwargs: object) -> None:
            kw = dict(kwargs)
            if not show_console:
                kw["disable"] = True
            self._inner = inner_cls(*args, **kw)
            total = kw.get("total")
            self.total = int(total) if isinstance(total, (int, float)) else None
            self.n = 0
            on_bytes(0, self.total)

        def update(self, n: int = 1) -> None:
            self.n += n
            self._inner.update(n)
            on_bytes(self.n, self.total)

        def close(self) -> None:
            self._inner.close()

        def __enter__(self) -> HubTqdm:
            self._inner.__enter__()
            return self

        def __exit__(self, *exc: object) -> bool | None:
            return self._inner.__exit__(*exc)

        def __getattr__(self, name: str) -> object:
            return getattr(self._inner, name)

    hub.tqdm = HubTqdm  # type: ignore[misc, assignment]
    try:
        yield
    finally:
        hub.tqdm = inner_cls
