"""First-run Milkdrop preset and texture pack downloads into ``data_dir``.

The editor offers each pack as its own line in the welcome step
(``cleave.first_run``). This module is pygame-free: fetch a zipball, extract
the GitHub top-level folder, and move it into place. A repo that wraps its
content in one subfolder (``Milkdrop-Original/``, ``textures/``) is hoisted
so the pack folder holds the presets directly. Failed fetches raise
:class:`StarterPackError`.
"""

from __future__ import annotations

import os
import shutil
import ssl
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from cleave.paths import data_dir, default_preset_root
from cleave.preset_playlist import dir_has_presets

StarterPackProgress = Callable[[str, float | None], None]

_GITHUB_OWNER = "projectM-visualizer"
_ZIP_BRANCH = "master"
_USER_AGENT = "Cleave"
_DOWNLOAD_TIMEOUT_S = 300
_CHUNK_SIZE = 64 * 1024
_PROGRESS_MIN_INTERVAL_SEC = 0.1
_PROGRESS_MIN_DELTA = 0.01
_EXTRACT_PULSE_EVERY = 100


class StarterPackError(RuntimeError):
    """Starter pack download or extraction failed."""


@dataclass(frozen=True)
class PackSpec:
    """One GitHub zipball and its destination under :func:`data_dir`."""

    repo: str
    dest_parent_key: str
    size_mb: int

    @property
    def dest_name(self) -> str:
        return self.repo

    @property
    def url(self) -> str:
        return (
            f"https://github.com/{_GITHUB_OWNER}/{self.repo}/"
            f"archive/refs/heads/{_ZIP_BRANCH}.zip"
        )


MILKDROP_ORIGINAL = PackSpec("presets-milkdrop-original", "presets", 2)
MILKDROP_TEXTURES = PackSpec("presets-milkdrop-texture-pack", "textures", 4)
CREAM_OF_THE_CROP = PackSpec("presets-cream-of-the-crop", "presets", 31)
PROJECTM_CLASSIC = PackSpec("presets-projectm-classic", "presets", 9)
EN_D = PackSpec("presets-en-d", "presets", 3)

STARTER_PACKS: tuple[PackSpec, ...] = (
    MILKDROP_ORIGINAL,
    MILKDROP_TEXTURES,
    CREAM_OF_THE_CROP,
    PROJECTM_CLASSIC,
    EN_D,
)


def starter_packs_needed() -> bool:
    """True when the default preset root is missing or has no ``.milk`` files."""
    root = default_preset_root()
    if not root.is_dir():
        return True
    return not dir_has_presets(root)


def pack_needed(pack: PackSpec) -> bool:
    """True when *pack* is not yet in :func:`data_dir`."""
    return not _already_present(_pack_dest(pack))


def download_pack(
    pack: PackSpec,
    on_progress: StarterPackProgress | None = None,
) -> None:
    """Download *pack* into :func:`data_dir` unless it is already there.

    *on_progress* is the editor loading-screen hook ``(message, fraction)``.
    Fraction stays in 0-1 after download starts; missing Content-Length
    reports 0 until the pack finishes, not None.
    """
    if not pack_needed(pack):
        return
    message = f"Downloading {pack.repo} (~{pack.size_mb} MB)…"
    _report(on_progress, message, 0.0)
    aggregator = _DownloadProgress(1, on_progress, message)
    try:
        _download_one_pack(pack, aggregator)
        aggregator.finish_file()
    except StarterPackError:
        raise
    except (
        urllib.error.URLError,
        TimeoutError,
        ConnectionError,
        ssl.SSLError,
        OSError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ) as exc:
        raise StarterPackError(
            f"Failed to download {pack.repo}. "
            "A network connection is required the first time."
        ) from exc


def _pack_dest(pack: PackSpec) -> Path:
    return data_dir() / pack.dest_parent_key / pack.dest_name


def _already_present(dest: Path) -> bool:
    if dest.is_file():
        return dest.stat().st_size > 0
    if dest.is_dir():
        return any(dest.iterdir())
    return False


def _download_one_pack(pack: PackSpec, aggregator: _DownloadProgress) -> None:
    dest = _pack_dest(pack)
    parent = dest.parent
    parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{pack.dest_name}.", dir=parent))
    zip_path = work / "pack.zip"
    try:
        _download_url(pack.url, zip_path, aggregator)
        unpacked = work / "unpacked"
        inner = _hoist_lone_subfolder(
            _extract_zip(zip_path, unpacked, pack.repo, aggregator)
        )
        named = inner.parent / pack.dest_name
        if inner.resolve() != named.resolve():
            inner.rename(named)
        if dest.exists() and dest.is_dir() and not any(dest.iterdir()):
            dest.rmdir()
        os.replace(named, dest)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _hoist_lone_subfolder(root: Path) -> Path:
    """Return the folder that holds *root*'s content, skipping lone wrappers.

    While *root* has exactly one subfolder, step into it. Loose top-level
    files (README, LICENSE) move along with it unless the subfolder already
    has a file of that name.
    """
    while True:
        children = list(root.iterdir())
        dirs = [child for child in children if child.is_dir()]
        if len(dirs) != 1:
            return root
        inner = dirs[0]
        for child in children:
            if child is inner:
                continue
            target = inner / child.name
            if not target.exists():
                child.rename(target)
        root = inner


def _download_url(
    url: str, dest: Path, aggregator: _DownloadProgress
) -> None:
    tmp = dest.with_name(dest.name + ".part")
    try:
        with _urlopen_zipball(url) as resp, tmp.open("wb") as out:
            total = _content_length(resp)
            downloaded = 0
            aggregator.on_bytes(0, total)
            while True:
                chunk = resp.read(_CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                aggregator.on_bytes(downloaded, total)
        tmp.replace(dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _urlopen(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_S)


def _urlopen_zipball(url: str):
    try:
        return _urlopen(url)
    except urllib.error.HTTPError as exc:
        alt = _alternate_branch_url(url)
        if exc.code != 404 or alt is None:
            raise
        exc.close()
        return _urlopen(alt)


def _alternate_branch_url(url: str) -> str | None:
    if url.endswith("/main.zip"):
        return url[: -len("main.zip")] + "master.zip"
    if url.endswith("/master.zip"):
        return url[: -len("master.zip")] + "main.zip"
    return None


def _content_length(resp: object) -> int | None:
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Content-Length")
    if raw is None or raw == "":
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _expected_roots(repo: str) -> tuple[str, ...]:
    return (f"{repo}-master", f"{repo}-main")


def _member_parts(name: str) -> tuple[str, ...]:
    return tuple(part for part in PurePosixPath(name).parts if part not in (".",))


def _zip_root_name(zf: zipfile.ZipFile, repo: str) -> str:
    found: set[str] = set()
    for info in zf.infolist():
        parts = _member_parts(info.filename)
        if parts:
            found.add(parts[0])
    for name in _expected_roots(repo):
        if name in found:
            return name
    raise StarterPackError(
        f"zip for {repo} is missing expected top-level folder"
    )


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK(info.external_attr >> 16)


def _is_zip_dir(info: zipfile.ZipInfo) -> bool:
    if info.filename.endswith("/"):
        return True
    return stat.S_ISDIR(info.external_attr >> 16)


def _safe_join(root: Path, member: str) -> Path:
    relative = PurePosixPath(member)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise StarterPackError(f"unsafe zip path: {member}")
    target = (root / Path(*relative.parts)).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise StarterPackError(f"unsafe zip path: {member}") from exc
    return target


def _extract_zip(
    zip_path: Path,
    dest: Path,
    repo: str,
    aggregator: _DownloadProgress,
) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    dest_resolved = dest.resolve()
    with zipfile.ZipFile(zip_path) as zf:
        root_name = _zip_root_name(zf, repo)
        extracted = 0
        for info in zf.infolist():
            parts = _member_parts(info.filename)
            if not parts or parts[0] != root_name:
                continue
            if _is_zip_symlink(info):
                raise StarterPackError(f"refusing zip symlink: {info.filename}")
            target = _safe_join(dest_resolved, "/".join(parts))
            if _is_zip_dir(info):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
            extracted += 1
            if extracted % _EXTRACT_PULSE_EVERY == 0:
                aggregator.pulse()
    inner = dest / root_name
    if not inner.is_dir():
        raise StarterPackError(f"zip for {repo} did not extract {root_name}/")
    return inner


def _report(
    on_progress: StarterPackProgress | None, message: str, fraction: float | None
) -> None:
    if on_progress is not None:
        on_progress(message, fraction)
        return
    if fraction is None:
        print(message, file=sys.stderr, flush=True)


def _clamp01(fraction: float) -> float:
    return max(0.0, min(1.0, float(fraction)))


class _DownloadProgress:
    """Map per-pack byte progress onto one 0-1 fraction for *file_count* packs."""

    def __init__(
        self,
        file_count: int,
        on_progress: StarterPackProgress | None,
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
            self._emit(self._pack_fraction())
            return
        file_frac = min(1.0, n / float(total))
        overall = (self._files_done + file_frac) / self._file_count
        self._emit(overall)

    def finish_file(self) -> None:
        self._files_done += 1
        if self._on_progress is not None:
            self._emit(self._pack_fraction())

    def pulse(self) -> None:
        if self._on_progress is None:
            return
        fraction = (
            self._last_frac if self._last_frac >= 0.0 else self._pack_fraction()
        )
        self._on_progress(self._message, _clamp01(fraction))

    def _pack_fraction(self) -> float:
        return self._files_done / float(self._file_count)

    def _emit(self, fraction: float) -> None:
        fraction = _clamp01(fraction)
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
