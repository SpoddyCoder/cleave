# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for a CPU-torch separate-capable Cleave freeze.

Dedicated sibling of packaging/cleave.spec so the lean play/render freeze
cannot collect torch. Same entry (cleave.py), same exe name (cleave), same
COLLECT name (cleave -> dist/cleave/). Do not mix the two builds in one
dist tree; run one spec at a time.

Build on Windows (do not cross-compile from WSL). Venv install order is in
docs/windows-freeze.md (freeze requirements, then CPU torch, then analyse
extras). Then::

    pyinstaller packaging/cleave-separate.spec
    python scripts/windows_stage_freeze.py --dist dist/cleave

Weights are not bundled; runtime uses model_cache_dir(). CUDA binaries are
filtered out. matplotlib is excluded (librosa display extra; analyse does
not import it).
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_all

SPECDIR = Path(SPECPATH).resolve()
REPO = SPECDIR.parent

# Inspected from Demucs 4.0.1, beat_this 1.1.0, librosa 0.11.0, and their
# installed runtime deps (CPU torch extra). Native or data-bearing packages
# plus the lazy-imported analyse stack that Analysis will not see from
# cleave.py (those imports live in function bodies).
COLLECT_PACKAGES = (
    "pygame",
    "soxr",
    "torch",
    "torchaudio",
    "torchcodec",
    "demucs",
    "beat_this",
    "librosa",
    "soundfile",
    "audioread",
    "numba",
    "scipy",
    "sklearn",
    "julius",
    "lameenc",
    "openunmix",
    "einops",
    "rotary_embedding_torch",
    "omegaconf",
    "dora",
    "joblib",
    "pooch",
)

# pickle/dynamic imports that collect_all can still miss.
EXTRA_HIDDENIMPORTS = (
    "demucs.pretrained",
    "demucs.hdemucs",
    "demucs.htdemucs",
    "demucs.demucs",
    "demucs.apply",
    "demucs.audio",
    "beat_this.inference",
    "beat_this.model.beat_tracker",
    "beat_this.preprocessing",
    "librosa",
    "librosa.feature",
    "librosa.onset",
    "soundfile",
    "audioread",
    "audioread.ffdec",
    "audioread.rawread",
    "numpy._core._multiarray_umath",
    "numpy._core.multiarray",
    "numpy._core.umath",
    "numpy._core._dtype_ctypes",
)

# Filename / path fragments for NVIDIA CUDA toolkit libs and torch CUDA
# binaries. CPU wheels omit these; filter anyway so stubs do not ship.
# Do not put "torch" here (that would drop the CPU package).
CUDA_BINARY_MARKERS = (
    "cudart",
    "cublas",
    "cudnn",
    "nccl",
    "nvrtc",
    "cusparse",
    "cufft",
    "curand",
    "cusolver",
    "nvjitlink",
    "cupti",
    "cufile",
    "nvtoolsext",
    "torch_cuda",
    "c10_cuda",
    "libtorch_cuda",
)

# Training / display extras. Analyse uses librosa; matplotlib is the
# librosa display extra and is not imported on the extract path.
ANALYSIS_EXCLUDES = (
    "matplotlib",
    "pytorch_lightning",
    "lightning",
    "mir_eval",
    "madmom",
)


def _collect_packages(names: tuple[str, ...]):
    datas: list = []
    binaries: list = []
    hidden: list = []
    for name in names:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(name)
        datas += pkg_datas
        binaries += pkg_binaries
        hidden += list(pkg_hidden)
    return datas, binaries, hidden


def _is_cuda_binary(entry: tuple) -> bool:
    src = str(entry[0]).replace("\\", "/").lower()
    dest = str(entry[1]).replace("\\", "/").lower() if len(entry) > 1 else ""
    name = Path(src).name
    haystack = f"{name} {src} {dest}"
    return any(marker in haystack for marker in CUDA_BINARY_MARKERS)


pkg_datas, pkg_binaries, pkg_hidden = _collect_packages(COLLECT_PACKAGES)
pkg_binaries = [entry for entry in pkg_binaries if not _is_cuda_binary(entry)]

datas = [
    (str(REPO / "cleave-viz.yaml"), "."),
    (str(REPO / "assets" / "fonts"), "assets/fonts"),
]
datas += pkg_datas

a = Analysis(
    [str(REPO / "cleave.py")],
    pathex=[str(REPO)],
    binaries=pkg_binaries,
    datas=datas,
    hiddenimports=list(dict.fromkeys([*pkg_hidden, *EXTRA_HIDDENIMPORTS])),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=list(ANALYSIS_EXCLUDES),
    noarchive=False,
    optimize=0,
)

a.binaries = [entry for entry in a.binaries if not _is_cuda_binary(entry)]

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
