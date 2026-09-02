"""Filesystem layout for Cleave data, install, and bundled resources."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root when running from a checkout (`cleave/` package lives here).
_REPO_ROOT = Path(__file__).resolve().parent.parent

# FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
_FOLDERID_DOCUMENTS = (
    0xFDD39AD0,
    0x238F,
    0x46AF,
    (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
)


def is_frozen() -> bool:
    """Return True when running from a frozen (PyInstaller) executable."""
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Return the repository root directory.

    Always the checkout, including when tests run against a frozen-style
    monkeypatch of :func:`is_frozen`. Use :func:`resource_dir` for bundled files.
    """
    return _REPO_ROOT.resolve()


def install_dir() -> Path:
    """Return the directory that holds the executable and native sidecars.

    Frozen: parent of ``sys.executable`` (onedir folder root). Checkout: repo root.
    FFmpeg and libprojectM DLLs live here, not in :func:`resource_dir`.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return repo_root()


def resource_dir() -> Path:
    """Return the directory that holds bundled app files.

    Frozen: ``sys._MEIPASS`` (onedir ``_internal``). Checkout: repo root.
    Template YAML and ``assets/fonts`` live here.
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
        return install_dir()
    return repo_root()


def native_lib_sidecar_first() -> bool:
    """True when native libs are searched beside the install dir before env vars."""
    return is_frozen() or sys.platform == "win32"


def install_sidecar_lib_paths(*relative_names: str) -> list[str]:
    """Return install-dir paths for native library filenames."""
    root = install_dir()
    return [str(root / name) for name in relative_names]


def windows_documents_dir() -> Path:
    """Return the Windows Documents known folder, or ``~/Documents``."""
    try:
        from ctypes import POINTER, Structure, byref, c_wchar_p, windll
        from ctypes.wintypes import BYTE, DWORD, HANDLE, LONG, WORD

        class GUID(Structure):
            _fields_ = [
                ("Data1", DWORD),
                ("Data2", WORD),
                ("Data3", WORD),
                ("Data4", BYTE * 8),
            ]

        data1, data2, data3, data4 = _FOLDERID_DOCUMENTS
        folder_id = GUID(data1, data2, data3, (BYTE * 8)(*data4))
        path_ptr = c_wchar_p()
        get_path = windll.shell32.SHGetKnownFolderPath
        get_path.argtypes = [
            POINTER(GUID),
            DWORD,
            HANDLE,
            POINTER(c_wchar_p),
        ]
        get_path.restype = LONG
        result = get_path(byref(folder_id), 0, None, byref(path_ptr))
        if result != 0 or not path_ptr.value:
            raise OSError(f"SHGetKnownFolderPath failed: {result}")
        try:
            return Path(path_ptr.value)
        finally:
            windll.ole32.CoTaskMemFree(path_ptr)
    except (AttributeError, ImportError, OSError, ValueError):
        return Path.home() / "Documents"


def data_dir() -> Path:
    """Return Cleave data root.

    ``CLEAVE_DATA`` overrides on every OS. Otherwise Windows uses
    ``Documents/cleave``; Linux uses XDG (``XDG_DATA_HOME/cleave`` or
    ``~/.local/share/cleave``).
    """
    override = os.environ.get("CLEAVE_DATA")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        return (windows_documents_dir() / "cleave").resolve()
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return (Path(xdg_data_home) / "cleave").resolve()
    return (Path.home() / ".local" / "share" / "cleave").resolve()


def default_preset_root() -> Path:
    """Return the default Milkdrop preset directory under :func:`data_dir`."""
    return (data_dir() / "presets").resolve()


def default_texture_paths() -> tuple[Path, ...]:
    """Return the default texture search paths under :func:`data_dir`."""
    return ((data_dir() / "textures").resolve(),)


def projects_dir() -> Path:
    """Return the directory that holds per-track project folders."""
    return data_dir() / "projects"


def project_dir(slug: str) -> Path:
    """Return the project directory for *slug* under :func:`projects_dir`."""
    return projects_dir() / slug


def validate_project_slug(slug: str) -> None:
    """Raise :class:`ValueError` when *slug* is not a safe project identifier."""
    if "/" in slug or "\\" in slug or slug in (".", ".."):
        raise ValueError(f"invalid project slug: {slug!r}")


def resolve_project(path_or_slug: Path | str) -> Path:
    """Resolve a project slug or path to an existing project directory.

    * Slug: ``sights-and-sounds-26`` -> ``projects_dir() / slug``
    * Relative: ``projects/sights-and-sounds-26`` -> under :func:`data_dir`
    * Absolute: path to the project directory as-is
    """
    raw = Path(path_or_slug)

    if raw.is_absolute():
        candidate = raw.resolve()
    elif len(raw.parts) >= 2 and raw.parts[0] == "projects":
        candidate = (data_dir() / raw).resolve()
    else:
        slug = os.fspath(path_or_slug)
        validate_project_slug(slug)
        candidate = project_dir(slug).resolve()

    if not candidate.is_dir():
        raise FileNotFoundError(f"project not found: {candidate}")

    return candidate


def project_slug(audio_path: Path) -> str:
    """Derive a project slug from an audio file path (stem of the filename)."""
    return audio_path.stem


def default_project_config(project: Path) -> Path:
    """Return the default per-project visualizer config path inside *project*."""
    from cleave.config import VIZ_CONFIG_FILENAME

    return project / VIZ_CONFIG_FILENAME
