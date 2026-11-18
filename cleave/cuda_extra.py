"""Optional CUDA torch for the frozen Windows build, kept in local app data.

The freeze ships CPU torch. On a machine whose NVIDIA driver supports CUDA 13.2,
the welcome step (``cleave.first_run``) can download the pinned PyTorch cu132
wheels, verify them, and unpack them under :func:`cuda_extra_dir`. At startup
:func:`activate_cuda_extra` puts an import finder ahead of PyInstaller's, so
``torch``, ``torchaudio``, and ``torchcodec`` load from that folder instead of
the bundled CPU builds. Nothing under the install folder changes, so no admin
rights are needed.

No torch, pygame, or viz at import.
"""

from __future__ import annotations

import ctypes
import hashlib
import importlib.abc
import importlib.machinery
import shutil
import sys
import time
import urllib.request
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from cleave.paths import cuda_extra_root, is_frozen

CudaProgress = Callable[[str, float | None], None]

# Folder name under cuda_extra_root(). Change it with the pins so an app
# upgrade never loads wheels built for another torch.
CUDA_EXTRA_KEY = "cu132-torch2.15.0"
# cuDriverGetVersion value for CUDA 13.2 (an R595 NVIDIA driver or newer).
MIN_CUDA_DRIVER_VERSION = 13020

_PACKAGES = frozenset({"torch", "functorch", "torchgen", "torchaudio", "torchcodec"})
_REQUIRED_DIRS = ("torch", "torchaudio", "torchcodec")
_MARKER = "complete"
_STAGING_SUFFIX = ".partial"
_USER_AGENT = "Cleave"
_DOWNLOAD_TIMEOUT_S = 300
_CHUNK_SIZE = 1024 * 1024
_PROGRESS_MIN_INTERVAL_SEC = 0.1
# Share of the bar for the download; unpacking fills the rest.
_DOWNLOAD_SHARE = 0.9
_DOWNLOAD_MESSAGE = "Downloading CUDA Toolkit…"
_UNPACK_MESSAGE = "Unpacking CUDA Toolkit…"
RESTART_NOTE = "Done - restart Cleave to use it"


class CudaExtraError(RuntimeError):
    """CUDA wheel download, verification, or unpack failed."""


@dataclass(frozen=True)
class CudaWheel:
    filename: str
    url: str
    sha256: str
    size: int


def _wheel(
    name: str, version: str, sha256: str, size: int, tag: str = "cp314-cp314"
) -> CudaWheel:
    filename = f"{name}-{version}+cu132-{tag}-win_amd64.whl"
    # %2B: the PyTorch CDN is more reliable with the encoded "+".
    url = "https://download.pytorch.org/whl/cu132/" + filename.replace("+", "%2B")
    return CudaWheel(filename, url, sha256, size)


# Match requirements-torch-cu132.txt and the freeze CPython (cp314 win_amd64).
CUDA_WHEELS: tuple[CudaWheel, ...] = (
    _wheel(
        "torch",
        "2.15.0",
        "f070bea62298fa4964c365b0d8788754a2f50610ea5885f7a3d1d103bb8de64b",
        2115653661,
    ),
    # torchaudio ships one py3 wheel per platform, not one per CPython.
    _wheel(
        "torchaudio",
        "2.11.1",
        "c3a9228e74828810bc7afcf6cc3df5bd8f6557ba07fc73d14d66c981b221b3ab",
        1774928,
        tag="py3-none",
    ),
    _wheel(
        "torchcodec",
        "0.17.0",
        "637992360ba0aca06dc56855ee392922209ef745d7b97e32510cfe13aa4345fd",
        14722138,
    ),
)
CUDA_EXTRA_SIZE_MB = sum(wheel.size for wheel in CUDA_WHEELS) // (1024 * 1024)


def cuda_extra_dir() -> Path:
    return cuda_extra_root() / CUDA_EXTRA_KEY


def cuda_driver_version() -> int | None:
    """CUDA version the NVIDIA driver supports (13000 is 13.0), or None."""
    if sys.platform != "win32":
        return None
    try:
        lib = ctypes.WinDLL("nvcuda.dll")  # type: ignore[attr-defined]
        version = ctypes.c_int(0)
        rc = lib.cuDriverGetVersion(ctypes.byref(version))
    except (AttributeError, OSError):
        return None
    return version.value if rc == 0 else None


def cuda_extra_supported() -> bool:
    """True on the frozen Windows build with an NVIDIA driver new enough for cu132."""
    if not is_frozen() or sys.platform != "win32":
        return False
    version = cuda_driver_version()
    return version is not None and version >= MIN_CUDA_DRIVER_VERSION


def cuda_extra_installed() -> bool:
    return (cuda_extra_dir() / _MARKER).is_file()


class _OverlayFinder(importlib.abc.MetaPathFinder):
    """Resolve the torch packages from the overlay before PyInstaller's importer."""

    def __init__(self, root: Path) -> None:
        self.root = str(root)

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if fullname.partition(".")[0] not in _PACKAGES:
            return None
        search = [self.root] if path is None or "." not in fullname else list(path)
        return importlib.machinery.PathFinder.find_spec(fullname, search)


def activate_cuda_extra() -> bool:
    """Load the torch packages from the overlay from now on.

    Call before anything imports torch. False when the overlay is missing,
    this is not the frozen Windows build, or torch is already imported (then
    it takes effect on the next launch).
    """
    if not is_frozen() or sys.platform != "win32" or not cuda_extra_installed():
        return False
    if any(isinstance(finder, _OverlayFinder) for finder in sys.meta_path):
        return True
    if any(name.partition(".")[0] in _PACKAGES for name in sys.modules):
        return False
    root = cuda_extra_dir()
    sys.meta_path.insert(0, _OverlayFinder(root))
    sys.path.insert(0, str(root))
    return True


class _Progress:
    def __init__(self, on_progress: CudaProgress | None) -> None:
        self._on_progress = on_progress
        self._last = 0.0

    def report(self, message: str, fraction: float, *, force: bool = False) -> None:
        if self._on_progress is None:
            return
        now = time.monotonic()
        if not force and now - self._last < _PROGRESS_MIN_INTERVAL_SEC:
            return
        self._last = now
        self._on_progress(message, max(0.0, min(1.0, fraction)))


def _download_wheel(
    wheel: CudaWheel, dest: Path, on_bytes: Callable[[int], None]
) -> None:
    request = urllib.request.Request(wheel.url, headers={"User-Agent": _USER_AGENT})
    digest = hashlib.sha256()
    received = 0
    with (
        urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_S) as resp,
        dest.open("wb") as out,
    ):
        while True:
            chunk = resp.read(_CHUNK_SIZE)
            if not chunk:
                break
            out.write(chunk)
            digest.update(chunk)
            received += len(chunk)
            on_bytes(received)
    got = digest.hexdigest()
    if got != wheel.sha256:
        raise CudaExtraError(f"{wheel.filename}: SHA-256 mismatch (got {got})")


def _unpack(
    wheels: Sequence[Path], dest: Path, on_fraction: Callable[[float], None]
) -> None:
    archives = [zipfile.ZipFile(path) for path in wheels]
    try:
        members = [(zf, info) for zf in archives for info in zf.infolist()]
        for index, (zf, info) in enumerate(members):
            zf.extract(info, dest)
            on_fraction((index + 1) / len(members))
    finally:
        for zf in archives:
            zf.close()
    for name in _REQUIRED_DIRS:
        if not (dest / name).is_dir():
            raise CudaExtraError(f"CUDA unpack is missing {name}")


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def download_cuda_extra(on_progress: CudaProgress | None = None) -> str | None:
    """Download, verify, and unpack the pinned wheels into :func:`cuda_extra_dir`.

    All or nothing: work happens in a staging folder that is renamed into
    place only when every wheel is verified and unpacked. Returns a note for
    the welcome step when the CUDA build only loads after a restart.
    """
    root = cuda_extra_root()
    final = cuda_extra_dir()
    staging = root / (CUDA_EXTRA_KEY + _STAGING_SUFFIX)
    downloads = staging / "wheels"
    unpacked = staging / "site"
    progress = _Progress(on_progress)
    total = sum(wheel.size for wheel in CUDA_WHEELS)
    try:
        _remove_tree(staging)
        downloads.mkdir(parents=True)
        progress.report(_DOWNLOAD_MESSAGE, 0.0, force=True)
        done = 0
        paths: list[Path] = []
        for wheel in CUDA_WHEELS:
            path = downloads / wheel.filename

            def on_bytes(received: int, base: int = done) -> None:
                frac = (base + received) / total
                progress.report(_DOWNLOAD_MESSAGE, frac * _DOWNLOAD_SHARE)

            _download_wheel(wheel, path, on_bytes)
            paths.append(path)
            done += wheel.size

        def on_unpack(frac: float) -> None:
            share = _DOWNLOAD_SHARE + frac * (1.0 - _DOWNLOAD_SHARE)
            progress.report(_UNPACK_MESSAGE, share)

        progress.report(_UNPACK_MESSAGE, _DOWNLOAD_SHARE, force=True)
        _unpack(paths, unpacked, on_unpack)
        (unpacked / _MARKER).write_text(CUDA_EXTRA_KEY + "\n", encoding="utf-8")
        _remove_tree(final)
        unpacked.rename(final)
    except CudaExtraError:
        _remove_tree(staging)
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        # URLError, SSLError, and socket timeouts are OSErrors.
        _remove_tree(staging)
        raise CudaExtraError(str(exc) or type(exc).__name__) from exc
    except BaseException:
        _remove_tree(staging)
        raise
    _remove_tree(staging)
    for other in root.iterdir():
        if other != final and other.is_dir():
            _remove_tree(other)
    progress.report(_UNPACK_MESSAGE, 1.0, force=True)
    return None if activate_cuda_extra() else RESTART_NOTE
