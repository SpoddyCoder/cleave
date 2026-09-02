# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for Cleave (Windows Phase 2 freeze skeleton).

Build on Windows (do not cross-compile from WSL)::

    pyinstaller packaging/cleave.spec

Output: dist/cleave/cleave.exe plus _internal/.

Post-build (not done by this spec): copy ffmpeg.exe and, for Phase 2.2,
projectM-4.dll and projectM-4-playlist.dll into dist/cleave/ next to
cleave.exe, not into _internal. See docs/windows-freeze.md.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPECDIR = Path(SPECPATH).resolve()
REPO = SPECDIR.parent

pygame_datas, pygame_binaries, pygame_hiddenimports = collect_all("pygame")

datas = [
    (str(REPO / "cleave-viz.yaml"), "."),
    (str(REPO / "assets" / "fonts"), "assets/fonts"),
]
datas += pygame_datas

a = Analysis(
    [str(REPO / "cleave.py")],
    pathex=[str(REPO)],
    binaries=pygame_binaries,
    datas=datas,
    hiddenimports=list(pygame_hiddenimports),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "demucs",
        "beat_this",
        "librosa",
        "matplotlib",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="cleave",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="cleave",
)
