#!/usr/bin/env python3
"""Copy Windows freeze sidecars into a PyInstaller onedir root.

Reusable from CI and a local Windows freeze. After
``pyinstaller packaging/cleave.spec``, run::

    python scripts/windows_stage_freeze.py [--dist dist/cleave] [--repo-root .]

Sidecars go next to ``cleave.exe`` (default ``dist/cleave/``), never into
``_internal/``.

Copies ``packaging/windows/*.dll`` and
``packaging/windows/licenses/libprojectM/``, then downloads a pinned FFmpeg
zip, verifies SHA-256, extracts ``ffmpeg.exe``, and copies that build's
LICENSE/COPYING/NOTICE files into ``licenses/ffmpeg/``.

Pinned FFmpeg
-------------

GyanD/codexffmpeg **9.0.1 essentials** (64-bit Windows, static, GPLv3).

This is the well-known gyan.dev "release essentials" Windows build, mirrored
as a versioned GitHub Release asset so the URL does not float. Essentials
includes libx264 and aac, which Cleave uses for MP4 render. The zip (not 7z)
extracts with stdlib ``zipfile``. Static GPLv3 means one ``ffmpeg.exe`` and
no extra FFmpeg DLLs; ship the zip's LICENSE (GPLv3) under ``licenses/ffmpeg/``.

URL and SHA-256 are ``FFMPEG_URL`` and ``FFMPEG_SHA256`` below. The downloaded
zip is cached at ``<repo-root>/.cache/ffmpeg-windows.zip`` (gitignored).
Do not commit FFmpeg binaries.

See docs/windows-freeze.md.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

# GyanD/codexffmpeg 9.0.1 essentials (gyan.dev Windows release essentials).
# Asset: https://github.com/GyanD/codexffmpeg/releases/tag/9.0.1
FFMPEG_URL = (
    "https://github.com/GyanD/codexffmpeg/releases/download/"
    "9.0.1/ffmpeg-9.0.1-essentials_build.zip"
)
FFMPEG_SHA256 = "fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9"

REQUIRED_DLLS = ("projectM-4.dll", "projectM-4-playlist.dll")
SIDECAR_NAMES = ("ffmpeg.exe", *REQUIRED_DLLS)
CLEAVE_EXE = "cleave.exe"

_CACHE_REL = Path(".cache") / "ffmpeg-windows.zip"
_PACKAGING_WINDOWS = Path("packaging") / "windows"
_LIBPROJECTM_LICENSES = Path("licenses") / "libprojectM"
_FFMPEG_LICENSES = Path("licenses") / "ffmpeg"

_LICENSE_BASENAME_RE = re.compile(
    r"^(LICENSE|COPYING|NOTICE)(\..+)?$",
    re.IGNORECASE,
)

_DOWNLOAD_TIMEOUT_S = 120
_USER_AGENT = "cleave-windows-stage-freeze"


class StageFreezeError(RuntimeError):
    """Raised when freeze staging or layout checks fail."""


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_dist_dir(repo_root: Path) -> Path:
    return repo_root / "dist" / "cleave"


def default_cache_path(repo_root: Path) -> Path:
    return repo_root / _CACHE_REL


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_windows_dlls(repo_root: Path, dist: Path) -> None:
    """Copy ``packaging/windows/*.dll`` into the onedir root."""
    src_dir = repo_root / _PACKAGING_WINDOWS
    if not src_dir.is_dir():
        raise StageFreezeError(f"missing packaging dir: {src_dir}")
    dlls = sorted(src_dir.glob("*.dll"))
    names = {dll.name for dll in dlls}
    missing = [name for name in REQUIRED_DLLS if name not in names]
    if missing:
        raise StageFreezeError(
            f"missing DLLs in {src_dir}: {', '.join(missing)}"
        )
    dist.mkdir(parents=True, exist_ok=True)
    for dll in dlls:
        shutil.copy2(dll, dist / dll.name)


def copy_libprojectm_licenses(repo_root: Path, dist: Path) -> None:
    """Copy libprojectM licenses into ``dist/licenses/libprojectM/``."""
    src = repo_root / _PACKAGING_WINDOWS / _LIBPROJECTM_LICENSES
    if not src.is_dir():
        raise StageFreezeError(f"missing libprojectM licenses: {src}")
    dest = dist / _LIBPROJECTM_LICENSES
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, dirs_exist_ok=True)


def _urlopen(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    return urllib.request.urlopen(request, timeout=_DOWNLOAD_TIMEOUT_S)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    try:
        with _urlopen(url) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.replace(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def _ensure_ffmpeg_zip(cache_path: Path, url: str, sha256: str) -> Path:
    expected = sha256.lower()
    if cache_path.is_file() and sha256_file(cache_path).lower() == expected:
        print(f"Using cached FFmpeg zip ({cache_path})", file=sys.stderr)
        return cache_path
    print(f"Downloading {url} -> {cache_path}", file=sys.stderr)
    try:
        _download(url, cache_path)
    except urllib.error.URLError as exc:
        raise StageFreezeError(f"FFmpeg download failed: {exc}") from exc
    actual = sha256_file(cache_path).lower()
    if actual != expected:
        cache_path.unlink(missing_ok=True)
        raise StageFreezeError(
            f"FFmpeg SHA-256 mismatch for {cache_path}: "
            f"expected {expected}, got {actual}"
        )
    return cache_path


def _zip_member_name(name: str) -> str:
    return name.replace("\\", "/").rstrip("/")


def _is_license_member(name: str) -> bool:
    base = Path(_zip_member_name(name)).name
    return bool(_LICENSE_BASENAME_RE.match(base))


def _find_ffmpeg_exe_member(names: list[str]) -> str:
    matches = [
        name
        for name in names
        if Path(_zip_member_name(name)).name.lower() == "ffmpeg.exe"
    ]
    if not matches:
        raise StageFreezeError("FFmpeg zip does not contain ffmpeg.exe")
    for name in matches:
        if Path(_zip_member_name(name)).parent.name.lower() == "bin":
            return name
    return matches[0]


def extract_ffmpeg(zip_path: Path, dist: Path) -> None:
    """Extract ``ffmpeg.exe`` and license files from a verified zip."""
    dist.mkdir(parents=True, exist_ok=True)
    license_dir = dist / _FFMPEG_LICENSES
    license_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = [
            info.filename
            for info in zf.infolist()
            if not info.is_dir()
        ]
        exe_member = _find_ffmpeg_exe_member(names)
        dest_exe = dist / "ffmpeg.exe"
        with zf.open(exe_member) as src, dest_exe.open("wb") as out:
            shutil.copyfileobj(src, out)
        copied_licenses: list[str] = []
        for name in names:
            if not _is_license_member(name):
                continue
            dest = license_dir / Path(_zip_member_name(name)).name
            with zf.open(name) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            copied_licenses.append(dest.name)
        if not copied_licenses:
            raise StageFreezeError(
                f"FFmpeg zip has no LICENSE/COPYING/NOTICE files: {zip_path}"
            )


def stage_ffmpeg(
    dist: Path,
    cache_path: Path,
    *,
    url: str = FFMPEG_URL,
    sha256: str = FFMPEG_SHA256,
) -> None:
    zip_path = _ensure_ffmpeg_zip(cache_path, url, sha256)
    extract_ffmpeg(zip_path, dist)


def assert_onedir_layout(dist: Path, *, check_exe: bool = True) -> None:
    """Require sidecars beside the exe, never under ``_internal/``."""
    missing: list[str] = []
    if check_exe and not (dist / CLEAVE_EXE).is_file():
        missing.append(CLEAVE_EXE)
    for name in SIDECAR_NAMES:
        if not (dist / name).is_file():
            missing.append(name)
    if missing:
        raise StageFreezeError(
            f"onedir root {dist} missing: {', '.join(missing)}"
        )
    internal = dist / "_internal"
    leaked = [name for name in SIDECAR_NAMES if (internal / name).is_file()]
    if leaked:
        raise StageFreezeError(
            f"sidecars must not be under {internal}: {', '.join(leaked)}"
        )


def stage_freeze(
    repo_root: Path,
    dist: Path,
    *,
    check_exe: bool = True,
    cache_path: Path | None = None,
    ffmpeg_url: str = FFMPEG_URL,
    ffmpeg_sha256: str = FFMPEG_SHA256,
) -> None:
    repo_root = repo_root.resolve()
    dist = dist.resolve()
    if cache_path is None:
        cache_path = default_cache_path(repo_root)
    copy_windows_dlls(repo_root, dist)
    copy_libprojectm_licenses(repo_root, dist)
    stage_ffmpeg(
        dist,
        cache_path,
        url=ffmpeg_url,
        sha256=ffmpeg_sha256,
    )
    assert_onedir_layout(dist, check_exe=check_exe)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy Windows freeze sidecars (DLLs, licenses, pinned FFmpeg) "
            "into a PyInstaller onedir root."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Checkout root (default: parent of scripts/)",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        default=None,
        help="Onedir root (default: <repo-root>/dist/cleave)",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="FFmpeg zip cache path (default: <repo-root>/.cache/ffmpeg-windows.zip)",
    )
    parser.add_argument(
        "--no-exe-check",
        action="store_true",
        help="Skip requiring cleave.exe (unit tests on Linux)",
    )
    args = parser.parse_args(argv)
    repo_root = (
        args.repo_root.expanduser().resolve()
        if args.repo_root is not None
        else default_repo_root()
    )
    dist = (
        args.dist.expanduser().resolve()
        if args.dist is not None
        else default_dist_dir(repo_root)
    )
    cache_path = (
        args.cache.expanduser().resolve()
        if args.cache is not None
        else default_cache_path(repo_root)
    )
    try:
        stage_freeze(
            repo_root,
            dist,
            check_exe=not args.no_exe_check,
            cache_path=cache_path,
            ffmpeg_url=FFMPEG_URL,
            ffmpeg_sha256=FFMPEG_SHA256,
        )
    except StageFreezeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
