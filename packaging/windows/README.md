# Windows freeze sidecars (Phase 3.1)

Prebuilt native binaries and license trees for the Cleave Windows onedir zip
and installer. End users run `cleave.exe` as in [README.md](../../README.md)
(Windows zip and installer). This file is the sidecar convention for
maintainers.

PyInstaller bundles Python and pygame/SDL into `dist/cleave/_internal/`; these
files are copied **next to** `cleave.exe` after the freeze. See
[docs/dev/windows-freeze.md](../../docs/dev/windows-freeze.md) and
[docs/dev/structured-releases.md](../../docs/dev/structured-releases.md).

## Repo layout

```
packaging/windows/
  cleave.iss                     # Inno Setup 6 installer (Phase 3.2)
  projectM-4.dll                 # libprojectM core (committed)
  projectM-4-playlist.dll        # libprojectM playlist (committed)
  licenses/
    libprojectM/
      LICENSE.txt                # LGPL-2.1 (from upstream)
      NOTICE.txt                 # version, source, build notes
  README.md
```

DLLs live at this directory root (not under `dlls/`) so CI and manual freezes
can copy `packaging/windows/*.dll` in one step. License files mirror the
install layout under `dist/cleave/licenses/libprojectM/`.

FFmpeg is **not** committed here. [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py)
downloads a pinned Windows essentials zip, verifies SHA-256, and writes
`ffmpeg.exe` plus `dist/cleave/licenses/ffmpeg/` at freeze time. URL and checksum
are `FFMPEG_URL` and `FFMPEG_SHA256` in that script.

## libprojectM

| Item | Value |
| --- | --- |
| Version | 4.2.0 (embedded in committed DLLs; Cleave requires 4.2+) |
| Build | vcpkg + Visual Studio 2022, `x64-windows` shared triplet |
| Upstream | [projectM-visualizer/projectm](https://github.com/projectM-visualizer/projectm) (LGPL-2.1) |

### `dumpbin /dependents` (committed DLLs)

Checked with `objdump -p` on the committed PE files. Neither DLL pulls in
extra vcpkg runtime DLLs (for example zlib) in this build:

**projectM-4.dll:** `KERNEL32`, `MSVCP140`, `VCRUNTIME140`, `VCRUNTIME140_1`,
UCRT (`api-ms-win-crt-*`).

**projectM-4-playlist.dll:** `projectM-4.dll`, same MSVC/UCRT set.

Re-run `dumpbin /dependents` after rebuilding DLLs. Commit any new non-system
DLLs into this directory so [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py)
copies them beside the exe. OpenGL comes from the GPU driver
(`opengl32.dll`); do not bundle it.

Testers need the [Visual C++ Redistributable for VS 2022 (x64)](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
unless the freeze ships app-local CRT copies.

## Freeze output layout

After `pyinstaller packaging/cleave.spec` and [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py):

```
dist/cleave/
  cleave.exe
  ffmpeg.exe                     # from scripts/windows_stage_freeze.py; not in git
  projectM-4.dll                 # from packaging/windows/
  projectM-4-playlist.dll
  licenses/
    ffmpeg/                      # from the pinned FFmpeg zip
    libprojectM/                 # from packaging/windows/licenses/libprojectM/
  _internal/                     # PyInstaller bundle (not sidecars)
```

## How files get into `dist/cleave/`

### Manual freeze

From a native Windows checkout (not WSL). Do not `pip install -r requirements.txt` (that file has no torch extra index and can pull a CUDA wheel).

1. `pip install -r requirements-freeze.txt`
2. `pip install -r requirements-torch-cpu.txt`
3. `pip install demucs==4.0.1 beat-this==1.1.0 librosa==0.11.0 einops==0.8.2 rotary-embedding-torch==0.9.1 tqdm==4.67.3 setuptools==80.8.0`
4. `pyinstaller packaging/cleave.spec`
5. `python scripts/windows_stage_freeze.py --dist dist/cleave`
   (copies `packaging/windows/*.dll` and libprojectM licenses, fetches pinned
   FFmpeg, asserts sidecars sit next to `cleave.exe` not under `_internal/`)
6. Zip `dist\cleave\`.

Commit extra non-system DLLs from `dumpbin /dependents` into
[packaging/windows/](./) so step 5 copies them. The script caches the FFmpeg
zip at `.cache/ffmpeg-windows.zip` (gitignored).

### CI freeze

[.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml)
runs one `freeze` job on standard `windows-latest` (`workflow_dispatch` and
`workflow_call`, not every push). Pip cache on
[requirements-freeze.txt](../../requirements-freeze.txt) and
[requirements-torch-cpu.txt](../../requirements-torch-cpu.txt); no FFmpeg,
freeze-tree, or torch-wheel cache. Headless smoke (`cleave.exe --version` /
`--help`, then `cleave.exe separate` on
[tests/fixtures/smoke-separate.wav](../../tests/fixtures/smoke-separate.wav)).
No GPU compositing. See [docs/dev/windows-freeze.md](../../docs/dev/windows-freeze.md).

1. Install [requirements-freeze.txt](../../requirements-freeze.txt), then
   [requirements-torch-cpu.txt](../../requirements-torch-cpu.txt), then the
   analyse pins (demucs, beat-this, librosa, einops, rotary-embedding-torch,
   tqdm, setuptools). Do not `pip install -r requirements.txt`.
2. Run `pyinstaller packaging/cleave.spec`.
3. Run `python scripts/windows_stage_freeze.py --dist dist/cleave`.
4. Zip `dist/cleave/` as `cleave-<version>-windows-x64.zip` (archive root is a
   `cleave/` folder). Then compile [cleave.iss](cleave.iss) to
   `cleave-<version>-windows-x64-setup.exe`. Dispatch uploads both as 5-day
   Actions artifacts (`cleave-windows-x64`, `cleave-windows-x64-setup`).
   `workflow_call` with a non-empty `release_tag` input uses `gh release upload`
   for both and does not retain a workflow artifact.

Updating libprojectM for a release: rebuild on Windows with vcpkg, replace the
two DLLs in `packaging/windows/`, refresh `NOTICE.txt` and `dumpbin` notes if
the dependency set changes, and commit.

## Installer

[cleave.iss](cleave.iss) is the Inno Setup 6 script. Compile it on Windows after
staging `dist\cleave\` (same tree as the zip; no second freeze layout). Version
comes from `cleave.__version__`; do not hardcode it in the `.iss`.

```
iscc /DAppVersion=X.Y.Z packaging\windows\cleave.iss
```

Output at the repo root: `cleave-<version>-windows-x64-setup.exe`. CI runs this
after the zip step in
[.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml).
Dispatch uploads a 5-day `cleave-windows-x64-setup` artifact; a non-empty
`release_tag` uses `gh release upload` for the setup exe next to the zip.

GPU proof from the setup exe is met. Full installer details: [docs/dev/windows-freeze.md](../../docs/dev/windows-freeze.md). The same setup exe can optionally download pinned PyTorch cu130 wheels from download.pytorch.org when it detects an NVIDIA GPU, or when silent setup is given `/CUDA=1`. CI does not build or attach a CUDA payload and does not pass `/CUDA=1`.
