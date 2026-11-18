# Dependency updates

How to move Cleave's Python version, Python packages, libprojectM, and FFmpeg to their latest versions on Linux and Windows. Do this on the pre-release branch before cutting a release, as its own change. The [update-dependencies skill](../../.claude/skills/update-dependencies/SKILL.md) walks through this page step by step. The [cut-release skill](../../.claude/skills/cut-release/SKILL.md) does not refresh pins; it only flags stale ones.

Related: [windows-freeze.md](windows-freeze.md) (freeze design), [packaging/windows/README.md](../../packaging/windows/README.md) (committed DLLs), [structured-releases.md](structured-releases.md) (release process), [projectm-api-coverage.md](projectm-api-coverage.md) (projectM API in use).

Checklist:

```
Dependency update:
- [ ] Python version and pins (every copy)
- [ ] CUDA extra wheels
- [ ] FFmpeg Windows sidecar
- [ ] GitHub Actions versions
- [ ] Local Linux / WSL env + native libs
- [ ] Windows libprojectM DLLs
- [ ] projectM minimum version (only if raised)
- [ ] Tests, freeze dispatch, GPU check
- [ ] Changelog bullet
```

---

## Constraints

- The goal is latest everything, Python included. Nothing we control (the Python version, the CUDA build, our own code) is a reason to hold a package back. Cap a package only when an upstream gap leaves no other choice, and record why in the proposal.
- One CPython version runs everywhere: the Windows freeze, all three CI workflows, the CUDA wheel tags, and the dev env. It moves everywhere at once (see [Python version](#python-version)).
- torch, torchaudio, and torchcodec are released as a matched set. Pick versions that PyTorch publishes together for the same CPU and CUDA indexes.
- numpy is often held back by numba (pulled in by librosa). Check what the newest numba supports before raising numpy.
- A major jump with API breaks (imgui-bundle, librosa, numpy) means code changes in the same update. Read the upstream changelog and grep Cleave's use of the package before proposing it; editor UI breakage from imgui-bundle shows only in the manual editor check, not in unit tests.
- Never `pip install -r requirements.txt` in the Windows freeze venv. It has no torch extra index and can pull a CUDA wheel.

## 1. Python version and pins

### Python version

Pick the Python version first; it decides which package releases are reachable.

1. Target the newest CPython for which the latest release of every pinned package publishes `win_amd64` and `manylinux` `x86_64` wheels, and PyTorch publishes the torch set on both the CPU and the chosen CUDA index.
2. If no version satisfies every package, pick the one that holds back the fewest, and list the blockers (package, newest Python it supports).
3. When the version changes, update every copy in the same edit:

| File | Holds |
| --- | --- |
| [.github/workflows/tests.yml](../../.github/workflows/tests.yml), [windows-freeze.yml](../../.github/workflows/windows-freeze.yml), [release.yml](../../.github/workflows/release.yml) | `python-version` |
| [pyproject.toml](../../pyproject.toml) | `requires-python` |
| [cleave/cuda_extra.py](../../cleave/cuda_extra.py) | Wheel filename tag (`cpXY-cpXY`) and its comment |
| [README.md](../../README.md) | Requirements line and the `conda create` command |
| [windows-freeze.md](windows-freeze.md) | CUDA extra wheel tags and filenames |
| This page | [Local freeze](#local-freeze-optional) Python install |

Changing the wheel tag means new CUDA wheels, so do section 2 as well. Existing CUDA installs re-download.

### Pins

Every version is written out in full. Change all copies of a pin in the same edit.

| File | Holds |
| --- | --- |
| [requirements.txt](../../requirements.txt) | Full checkout set (analyse, editor, render) |
| [requirements-freeze.txt](../../requirements-freeze.txt) | Windows freeze set for play / render, plus PyInstaller |
| [requirements-torch-cpu.txt](../../requirements-torch-cpu.txt) | CPU torch, torchaudio, torchcodec, and the PyTorch CPU index |
| [requirements-torch-cu132.txt](../../requirements-torch-cu132.txt) | CUDA torch, torchaudio, torchcodec, and the PyTorch CUDA index |
| [requirements-dev.txt](../../requirements-dev.txt) | pytest |

The analyse pins (demucs, beat-this, librosa, einops, rotary-embedding-torch, tqdm, setuptools) are also typed out on one `pip install` line in three more places. Keep them identical to `requirements.txt`:

- [.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml), the analyse install step
- [windows-freeze.md](windows-freeze.md), the freeze venv recipe
- [packaging/windows/README.md](../../packaging/windows/README.md), the local freeze steps

Demucs weights are pinned separately: `_DEMUCS_HF_REPOS` in [cleave/model_weights.py](../../cleave/model_weights.py) holds each bag's Hugging Face repo commit and the SHA-256 of every safetensors file (from `https://huggingface.co/api/models/adefossez/<repo>/tree/main`, the LFS `oid`). When demucs moves, check that the bags in its `remote/*.yaml` still match.

Packages shared between files (pygame-ce, imgui-bundle, numpy, soxr, moderngl, PyOpenGL, soundfile, PyYAML) must carry the same version in `requirements.txt` and `requirements-freeze.txt`.

If PyTorch has moved to a newer CUDA build than cu132, rename `requirements-torch-cu132.txt` and change the index URL, every reference to the file, and the CUDA wording in [windows-freeze.md](windows-freeze.md) and [structured-releases.md](structured-releases.md) (driver minimum, "CUDA 13.2"). A new CUDA minor version raises the driver minimum: change `MIN_CUDA_DRIVER_VERSION` in [cleave/cuda_extra.py](../../cleave/cuda_extra.py) (`cuDriverGetVersion` value, such as 13020 for 13.2) and the driver wording in [README.md](../../README.md), [docs/user-guide/README.md](../user-guide/README.md) if it names one, and CHANGELOG.md. NVIDIA no longer publishes a Windows build number per CUDA release, only a driver branch (R595 for 13.2), so name the branch.

## 2. CUDA extra wheels

The editor's optional CUDA download uses fixed wheels, not a pip resolve. When torch, torchaudio, or torchcodec change:

1. In [cleave/cuda_extra.py](../../cleave/cuda_extra.py), update each `CUDA_WHEELS` entry: version, SHA-256, and size in bytes, taken from the `win_amd64` wheels for the freeze CPython on the PyTorch CUDA index. A wheel published as `py3-none` instead of `cpXY-cpXY` needs the filename logic in `cuda_extra.py` changed to match.
2. Change `CUDA_EXTRA_KEY` to match the new versions. That makes existing installs download the new set and remove the old folder.
3. In [windows-freeze.md](windows-freeze.md) (CUDA extra section), update the wheel filenames, sizes, and the total in bytes and MiB. The welcome step shows that total.
4. Confirm the Windows torch wheel still has no `nvidia-*` requirements (check its METADATA). If it gained some, the download design needs revisiting before release.

## 3. FFmpeg Windows sidecar

1. Pick the latest gyan.dev release essentials zip (the versioned GitHub asset, not the rolling "latest" link).
2. Set `FFMPEG_URL` and `FFMPEG_SHA256` at the top of [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py).
3. Update the "Pinned build" version line in [windows-freeze.md](windows-freeze.md).
4. Delete `.cache/ffmpeg-windows.zip` on any machine that freezes locally, so the new zip downloads.

The essentials build must still include libx264 and aac (Cleave's MP4 render). Do not commit `ffmpeg.exe`.

## 4. GitHub Actions versions

Bump `actions/checkout`, `actions/setup-python`, and `actions/upload-artifact` in [.github/workflows/](../../.github/workflows/) to their current major versions.

## 5. Local Linux / WSL

1. If the Python version changed, rebuild the `cleave` env on it first, keeping the same name so its path stays `/home/fernpa/anaconda3/envs/cleave`:

   ```bash
   conda env remove -n cleave
   ```

   ```bash
   conda create -n cleave python=X.Y
   ```

   Then update the env from the new pins. Use the CPU torch file instead on a box without CUDA:

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/pip install -r requirements-torch-cu132.txt
   ```

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/pip install -r requirements-dev.txt
   ```

2. Rebuild FFmpeg and libprojectM with [wsl-builds](https://github.com/spoddycoder/wsl-builds). Pick the libprojectM source first (see [libprojectM source](#libprojectm-source)). For `master`, answer yes to "Install bleeding-edge libprojectM from git master"; `--force` offers a clean rebuild of an existing install.

   ```bash
   ./wsl-builder.sh media ffmpeg,libprojectm --force
   ```

3. Confirm the new library is the one Cleave loads. On a Linux checkout the search order is `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`, then pkg-config, then system `.so` paths, so an old build earlier in that order wins.

   ```bash
   pkg-config --modversion projectM-4
   ```

   wsl-builds sets `PKG_CONFIG_PATH` in the shell rc, so check from a new shell.

4. Run the full test suite (dependency changes are cross-cutting):

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py
   ```

5. Manual check in the editor: open an existing project, play it with several layers, and run a short offline render. Unit tests do not exercise GPU output or projectM rendering. Also split a new music file to check Demucs, Beat This, and librosa.

## 6. Windows libprojectM DLLs

CI does not build libprojectM. The committed DLLs in [packaging/windows/](../../packaging/windows/) are what ships. Build on native Windows, not WSL. First time on a machine, do [Windows host setup](#windows-host-setup-one-time) first.

### libprojectM source

Cleave needs libprojectM 4.2+. Use the newest upstream release when one meets that; until 4.2 is released, build `master` at one pinned commit on both Linux and Windows and record it in `NOTICE.txt`. The vcpkg `projectm` port only builds releases.

1. Update vcpkg from a Developer PowerShell for VS 2022: `git pull`, then `.\bootstrap-vcpkg.bat`, in the vcpkg folder.
2. Build the shared x64 triplet with the playlist library (see [Playlist library](#playlist-library)) from the same libprojectM source as WSL. The committed overlay port [packaging/windows/vcpkg-overlay/projectm/](../../packaging/windows/vcpkg-overlay/projectm/) pins it: to move it, set `REF` to the new commit or tag and `SHA512` to the SHA-512 of `https://github.com/projectM-visualizer/projectm/archive/<ref>.tar.gz`, compare the rest with vcpkg's own `ports/projectm` (drop patches that no longer apply), and set `version`. Then `vcpkg install projectm:x64-windows --overlay-ports=<repo>\packaging\windows\vcpkg-overlay` (the repo can be the WSL share).
3. Check the version you built (see [Check the built version](#check-the-built-version)), then copy `projectM-4.dll` and `projectM-4-playlist.dll` from `installed\x64-windows\bin\` in the vcpkg folder into `packaging/windows/` (see [Getting the DLLs into the repo](#getting-the-dlls-into-the-repo)).
4. List both DLLs' imports: `dumpbin /dependents` in a Developer PowerShell, or `objdump -p <dll> | grep "DLL Name"` from WSL after copying. Commit any non-system DLL listed (zlib is the usual one) into the same directory; the staging script copies every DLL there.
5. Update the version, source commit, and install command in [packaging/windows/licenses/libprojectM/NOTICE.txt](../../packaging/windows/licenses/libprojectM/NOTICE.txt), and the version table and dependents list in [packaging/windows/README.md](../../packaging/windows/README.md). Replace `LICENSE.txt` if upstream changed it.
6. Optional local freeze, following [packaging/windows/README.md](../../packaging/windows/README.md), then `cleave.exe play` on a real project.

## 7. projectM minimum version (only if raised)

Cleave requires libprojectM 4.2+. A newer projectM does not have to raise that. Raise it only when Cleave starts using an API that older releases lack.

1. Read the upstream changelog for removed or changed functions. Check them against [projectm-api-coverage.md](projectm-api-coverage.md).
2. Add the new symbols to `_REQUIRED_SYMBOLS` in [cleave/projectm.py](../../cleave/projectm.py) and update the "need 4.2+" error text there.
3. Update every "4.2+" mention: [README.md](../../README.md) requirements, [docs/user-guide/README.md](../user-guide/README.md), [structured-releases.md](structured-releases.md), [windows-freeze.md](windows-freeze.md), [packaging/windows/README.md](../../packaging/windows/README.md), and `NOTICE.txt`.

## 8. Verify in CI

1. Push the pre-release branch. The tests workflow runs on push.
2. Run the windows-freeze workflow by hand (workflow_dispatch). It covers the frozen `--version` / `--help` smoke, a CPU `separate` on the fixture, and the installer round trip.
3. Download the dispatch zip or setup exe and check play and render on a Windows machine with a GPU. CI has no GPU.
4. On an NVIDIA machine, if the CUDA wheels changed: run the CUDA download from Settings > Download packages and split a track.

## 9. Changelog

Add one bullet under `## [Unreleased]` > `### Changed` in [CHANGELOG.md](../../CHANGELOG.md) naming the user-visible upgrades, for example: "Updated libprojectM to X.Y.Z, FFmpeg to X.Y, and PyTorch to X.Y.Z." Pin-only Python bumps with no user-visible effect need no bullet.

## Windows host setup (one time)

Only needed on a Windows machine that has not built the DLLs before, or after a reinstall. CI sets up its own runner; none of this is needed for the CI freeze.

### Build tools

1. Install [Git for Windows](https://git-scm.com/download/win).
2. Install Visual Studio 2022 (Community is fine) with the **Desktop development with C++** workload. That brings MSVC, the Windows SDK, and the Developer PowerShell for VS 2022 shortcut. vcpkg downloads its own CMake and Ninja.
3. Clone and bootstrap vcpkg in a short path without spaces:

   ```
   git clone https://github.com/microsoft/vcpkg C:\dev\vcpkg
   cd C:\dev\vcpkg
   .\bootstrap-vcpkg.bat -disableMetrics
   ```

4. Optional: set `VCPKG_ROOT` to `C:\dev\vcpkg` and add it to PATH, so `vcpkg` works from any folder.

Run every vcpkg build from **Developer PowerShell for VS 2022** so `dumpbin` is on PATH too.

### Playlist library

Cleave needs both the core DLL and `projectM-4-playlist.dll`. Before the first build, check how the current `projectm` port ships the playlist library:

```
vcpkg search projectm
```

Also read `ports\projectm\vcpkg.json` in the vcpkg folder. If it lists a playlist feature, install with it enabled (`vcpkg install "projectm[<feature>]:x64-windows"`). If the playlist library is built by default, the plain `vcpkg install projectm:x64-windows` is enough. After the build, confirm both DLLs are in `installed\x64-windows\bin\`.

Record the exact install command you used in [packaging/windows/licenses/libprojectM/NOTICE.txt](../../packaging/windows/licenses/libprojectM/NOTICE.txt) (Build recipe), so the next update does not have to work it out again.

### Check the built version

```
vcpkg list projectm
```

That prints the port version. The version the DLL itself reports is what Cleave sees; check it with any Windows Python (no packages needed):

```
python -c "import ctypes; l=ctypes.CDLL(r'C:\dev\vcpkg\installed\x64-windows\bin\projectM-4.dll'); l.projectm_get_version_string.restype=ctypes.c_char_p; print(l.projectm_get_version_string().decode())"
```

Write that version into `NOTICE.txt` and [packaging/windows/README.md](../../packaging/windows/README.md).

### Getting the DLLs into the repo

The repo is checked out in WSL. Copy straight into it from Windows through the WSL share (replace `<distro>` with the name `wsl -l` shows, or `echo $WSL_DISTRO_NAME` in WSL):

```
copy C:\dev\vcpkg\installed\x64-windows\bin\projectM-4*.dll \\wsl.localhost\<distro>\home\fernpa\cleave\packaging\windows\
```

Then commit from WSL as usual. Do not commit from a separate Windows checkout; it would need its own hooks setup and can disagree with the WSL tree on line endings.

### Local freeze (optional)

Only needed to test a freeze before pushing; CI builds the release.

1. Install 64-bit Python from python.org at the version in `python-version` of [windows-freeze.yml](../../.github/workflows/windows-freeze.yml).
2. Install Inno Setup 6, for example `winget install JRSoftware.InnoSetup`.
3. Install the [Visual C++ Redistributable for VS 2022 (x64)](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist) if the machine does not already have it. Visual Studio usually installs it.
4. Follow the manual freeze steps in [packaging/windows/README.md](../../packaging/windows/README.md) from a native Windows checkout (not the WSL share). Use that checkout for building only; commit from WSL.
