# Windows freeze sidecars (Phase 3.1)

Prebuilt native binaries and license trees for the Cleave Windows onedir zip.
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

FFmpeg is **not** committed here. The freeze job downloads a Windows `ffmpeg.exe`
and drops its license files into `dist/cleave/licenses/ffmpeg/` at build time.

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

Re-run `dumpbin /dependents` after rebuilding DLLs. Copy any new non-system
DLLs into `dist/cleave/` beside the exe. OpenGL comes from the GPU driver
(`opengl32.dll`); do not bundle it.

Testers need the [Visual C++ Redistributable for VS 2022 (x64)](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
unless the freeze ships app-local CRT copies.

## Freeze output layout

After `pyinstaller packaging/cleave.spec` and post-build copy:

```
dist/cleave/
  cleave.exe
  ffmpeg.exe                     # fetched in CI / manual copy; not in git
  projectM-4.dll                 # from packaging/windows/
  projectM-4-playlist.dll
  licenses/
    ffmpeg/                      # from FFmpeg build (CI / manual)
    libprojectM/                 # from packaging/windows/licenses/libprojectM/
  _internal/                     # PyInstaller bundle (not sidecars)
```

## How files get into `dist/cleave/`

### Manual freeze (Phase 2 recipe)

From a native Windows checkout (not WSL):

1. `pip install -r requirements-freeze.txt`
2. `pyinstaller packaging/cleave.spec`
3. Copy sidecars into `dist\cleave\` (not `_internal\`):
   - `ffmpeg.exe` from an official Windows FFmpeg build
   - `packaging\windows\projectM-4.dll`
   - `packaging\windows\projectM-4-playlist.dll`
   - Any extra non-system DLLs reported by `dumpbin /dependents`
   - `packaging\windows\licenses\libprojectM\` -> `dist\cleave\licenses\libprojectM\`
   - FFmpeg license tree -> `dist\cleave\licenses\ffmpeg\`
4. Zip `dist\cleave\`.

### CI freeze (Phase 3.1)

The GitHub Actions workflow (tag and `workflow_dispatch` on `windows-latest`)
will:

1. Install Python deps from [requirements-freeze.txt](../../requirements-freeze.txt)
   (no torch, demucs, librosa, or analyse stack).
2. Run `pyinstaller packaging/cleave.spec`.
3. Copy `packaging/windows/*.dll` into `dist/cleave/`.
4. Copy `packaging/windows/licenses/libprojectM/` into `dist/cleave/licenses/libprojectM/`.
5. Download `ffmpeg.exe` and its license files into `dist/cleave/` and
   `dist/cleave/licenses/ffmpeg/`.
6. Zip `dist/cleave/` and attach it to the GitHub Release (not a long-lived
   Actions artifact).

Updating libprojectM for a release: rebuild on Windows with vcpkg, replace the
two DLLs in `packaging/windows/`, refresh `NOTICE.txt` and `dumpbin` notes if
the dependency set changes, and commit.
