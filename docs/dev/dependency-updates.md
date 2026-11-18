# Dependency updates

How to move Cleave's Python packages, libprojectM, and FFmpeg to newer versions on Linux and Windows. Do this on the pre-release branch before cutting a release, as its own change. The [cut-release skill](../../.claude/skills/cut-release/SKILL.md) does not refresh pins; it only flags stale ones.

Related: [windows-freeze.md](windows-freeze.md) (freeze design), [packaging/windows/README.md](../../packaging/windows/README.md) (committed DLLs), [structured-releases.md](structured-releases.md) (release process), [projectm-api-coverage.md](projectm-api-coverage.md) (projectM API in use).

Checklist:

```
Dependency update:
- [ ] Python pins (every copy)
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

- The Windows freeze and both CI workflows use CPython 3.10 (`cp310`). A package whose latest release drops 3.10 must be capped below that release, or the Python version moves everywhere at once (both workflows, the CUDA wheel tags, and the docs that say 3.10).
- torch, torchaudio, and torchcodec are released as a matched set. Pick versions that PyTorch publishes together for the same CPU and CUDA indexes.
- numpy is often held back by numba (pulled in by librosa). Check what the newest numba supports before raising numpy.
- Demucs 4.0.1 is the last upstream release; leave it.
- Never `pip install -r requirements.txt` in the Windows freeze venv. It has no torch extra index and can pull a CUDA wheel.

## 1. Python pins

Every version is written out in full. Change all copies of a pin in the same edit.

| File | Holds |
| --- | --- |
| [requirements.txt](../../requirements.txt) | Full checkout set (analyse, editor, render) |
| [requirements-freeze.txt](../../requirements-freeze.txt) | Windows freeze set for play / render, plus PyInstaller |
| [requirements-torch-cpu.txt](../../requirements-torch-cpu.txt) | CPU torch, torchaudio, torchcodec, and the PyTorch CPU index |
| [requirements-torch-cu130.txt](../../requirements-torch-cu130.txt) | CUDA torch, torchaudio, torchcodec, and the PyTorch CUDA index |
| [requirements-dev.txt](../../requirements-dev.txt) | pytest |

The analyse pins (demucs, beat-this, librosa, einops, rotary-embedding-torch, tqdm, setuptools) are also typed out on one `pip install` line in three more places. Keep them identical to `requirements.txt`:

- [.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml), the analyse install step
- [windows-freeze.md](windows-freeze.md), the freeze venv recipe
- [packaging/windows/README.md](../../packaging/windows/README.md), the local freeze steps

Packages shared between files (pygame, imgui-bundle, numpy, soxr, moderngl, PyOpenGL, soundfile, PyYAML) must carry the same version in `requirements.txt` and `requirements-freeze.txt`.

If PyTorch has moved to a newer CUDA build than cu130, rename `requirements-torch-cu130.txt` and change the index URL, every reference to the file, and the CUDA wording in [windows-freeze.md](windows-freeze.md) and [structured-releases.md](structured-releases.md) (driver minimum, "CUDA 13").

## 2. CUDA extra wheels

The editor's optional CUDA download uses fixed wheels, not a pip resolve. When torch, torchaudio, or torchcodec change:

1. In [cleave/cuda_extra.py](../../cleave/cuda_extra.py), update each `CUDA_WHEELS` entry: version, SHA-256, and size in bytes, taken from the `cp310` `win_amd64` wheels on the PyTorch CUDA index.
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

1. Update the conda env from the new pins. Use the CPU torch file instead on a box without CUDA:

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/pip install -r requirements-torch-cu130.txt
   ```

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/pip install -r requirements-dev.txt
   ```

2. Rebuild FFmpeg and libprojectM with [wsl-builds](https://github.com/spoddycoder/wsl-builds). If it pins a libprojectM tag, move that to the latest release first.

   ```bash
   ./wsl-builder.sh media ffmpeg,libprojectm
   ```

3. Confirm the new library is the one Cleave loads. On a Linux checkout the search order is `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`, then pkg-config, then system `.so` paths, so an old build earlier in that order wins.

   ```bash
   pkg-config --modversion libprojectM
   ```

4. Run the full test suite (dependency changes are cross-cutting):

   ```bash
   /home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py
   ```

5. Manual check in the editor: open an existing project, play it with several layers, and run a short offline render. Unit tests do not exercise GPU output or projectM rendering. Also split a new music file to check Demucs, Beat This, and librosa.

## 6. Windows libprojectM DLLs

CI does not build libprojectM. The committed DLLs in [packaging/windows/](../../packaging/windows/) are what ships. Build on native Windows, not WSL.

1. Update vcpkg (`git pull`, then `bootstrap-vcpkg.bat`) with Visual Studio 2022 installed.
2. Build the shared x64 triplet with the playlist component: `vcpkg install projectm:x64-windows`. If the vcpkg port is older than the latest projectM release, use an overlay port pointing at the release tag.
3. Copy `projectM-4.dll` and `projectM-4-playlist.dll` from the vcpkg `bin/` tree into `packaging/windows/`.
4. Run `dumpbin /dependents` on both DLLs. Commit any non-system DLL it lists (zlib is the usual one) into the same directory; the staging script copies every DLL there.
5. Update the version in [packaging/windows/licenses/libprojectM/NOTICE.txt](../../packaging/windows/licenses/libprojectM/NOTICE.txt), and the version table and dependents list in [packaging/windows/README.md](../../packaging/windows/README.md). Replace `LICENSE.txt` if upstream changed it.
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
