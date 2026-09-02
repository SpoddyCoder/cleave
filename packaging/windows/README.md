# Windows freeze sidecars (Phase 3.1)

Prebuilt native binaries and license trees for the Cleave Windows onedir zip.
End users unpack the zip and run `cleave.exe` as in [README.md](../../README.md)
(Windows zip). This file is the sidecar convention for maintainers.

PyInstaller bundles Python and pygame/SDL into `dist/cleave/_internal/`; these
files are copied **next to** `cleave.exe` after the freeze. See
[docs/windows-freeze.md](../../docs/windows-freeze.md) and
[docs/structured-releases.md](../../docs/structured-releases.md).

## Repo layout

```
packaging/windows/
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

### Manual freeze (Phase 2 recipe)

From a native Windows checkout (not WSL):

1. `pip install -r requirements-freeze.txt`
2. `pyinstaller packaging/cleave.spec`
3. `python scripts/windows_stage_freeze.py --dist dist/cleave`
   (copies `packaging/windows/*.dll` and libprojectM licenses, fetches pinned
   FFmpeg, asserts sidecars sit next to `cleave.exe` not under `_internal/`)
4. Zip `dist\cleave\`.

Commit extra non-system DLLs from `dumpbin /dependents` into
[packaging/windows/](./) so step 3 copies them. The script caches the FFmpeg
zip at `.cache/ffmpeg-windows.zip` (gitignored).

### CI freeze (Phase 3.1)

[.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml)
runs on standard `windows-latest` (`workflow_dispatch` and `workflow_call`, not
every push). Pip cache only (`requirements-freeze.txt`); no FFmpeg or freeze-tree
cache. Headless smoke (`cleave.exe --version` / `--help` / frozen `separate`
message). No GPU compositing.

1. Install Python deps from [requirements-freeze.txt](../../requirements-freeze.txt)
   (no torch, demucs, librosa, or analyse stack).
2. Run `pyinstaller packaging/cleave.spec`.
3. Run `python scripts/windows_stage_freeze.py --dist dist/cleave`.
4. Zip `dist/cleave/` as `cleave-<version>-windows-x64.zip` (archive root is a
   `cleave/` folder). Dispatch uploads that zip as a 5-day Actions artifact
   (`cleave-windows-x64`). `workflow_call` with a non-empty `release_tag` input
   uses `gh release upload` and does not retain a workflow artifact.

Updating libprojectM for a release: rebuild on Windows with vcpkg, replace the
two DLLs in `packaging/windows/`, refresh `NOTICE.txt` and `dumpbin` notes if
the dependency set changes, and commit.
