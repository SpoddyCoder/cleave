# Windows freeze (Phase 2)

How Cleave locates files when frozen, how testers unpack a Windows onedir zip, and how to build libprojectM 4.2+ DLLs for Phase 2.2. Product decisions and 2.2 pickup live in [structured-releases.md](structured-releases.md). This note is the implementation design: 2.1 paths/spec/FFmpeg/ctypes (done) and the Windows native-build analysis for 2.2.

2.1 is proven on a native Windows box: `cleave.exe --version` and `cleave.exe --help`. Do not cross-compile the GUI stack from WSL. 2.2 still builds on Windows, copies sidecars next to the exe, and proves play/render.

Related: [cleave/paths.py](../cleave/paths.py), [cleave/ffmpeg.py](../cleave/ffmpeg.py), [packaging/cleave.spec](../packaging/cleave.spec), [cleave/projectm.py](../cleave/projectm.py), [cleave/projectm_playlist.py](../cleave/projectm_playlist.py).

---

## Relocatable path model

Three roots. Do not treat the checkout layout as the install layout.

| Helper | Frozen | Checkout | Holds |
| --- | --- | --- | --- |
| `install_dir()` | Parent of `sys.executable` (onedir folder root) | Repo root | Sidecars: `ffmpeg.exe`, later `projectM-4.dll` / `projectM-4-playlist.dll` |
| `resource_dir()` | `sys._MEIPASS` (onedir `_internal`) | Repo root | Bundled files: `cleave-viz.yaml`, `assets/fonts/` |
| `data_dir()` | User data (not the zip) | Same | Projects, presets, textures |

`is_frozen()` is `bool(getattr(sys, "frozen", False))`. `repo_root()` is always the checkout (tests and source scans). Runtime code that needs bundled files uses `resource_dir()`.

User data is never written into the app folder.

- `CLEAVE_DATA` overrides the data root on every OS.
- Linux (when unset): `XDG_DATA_HOME/cleave` or `~/.local/share/cleave`.
- Windows (when unset): Known Folder Documents (`FOLDERID_Documents` via ctypes) `/cleave`, fallback `Path.home() / "Documents" / "cleave"`.
- Global settings only: Linux `~/.config/cleave/config.yaml` (or `XDG_CONFIG_HOME`); Windows `%APPDATA%\cleave\config.yaml`.

Preset and texture defaults are `data_dir() / "presets"` and `data_dir() / "textures"` ([cleave/paths.py](../cleave/paths.py) `default_preset_root` / `default_texture_paths`). First write still creates directories; import does not.

---

## Onedir layout testers unpack

PyInstaller onedir, one `cleave.exe`, CLI subcommands (`cleave.exe play ...`). Unpack the zip and run from that folder. Not Program Files (Phase 3).

```
cleave/
  cleave.exe
  ffmpeg.exe                 # copied after freeze; not inside _internal
  projectM-4.dll             # Phase 2.2
  projectM-4-playlist.dll    # Phase 2.2
  licenses/
    ffmpeg/
    libprojectM/             # Phase 2.2
  _internal/                 # sys._MEIPASS: Python, pygame/SDL, datas
    cleave-viz.yaml
    assets/fonts/
```

Sidecars must sit next to `cleave.exe`. Files in `_internal` are bundled resources. Mixing those two is a common freeze bug.

Manual 2.1 proof (met; no GPU, no DLLs, no torch):

```
cleave.exe --version
cleave.exe --help
```

Phase 2.2 proof: `cleave.exe play <existing-project>` and a short `cleave.exe render` on a Windows box with a GPU driver. Copy `projects/` from Linux; do not run `separate` in this zip. Fix the librosa import graph first (see PyInstaller spec below); 2.1 `separate` currently traceback instead of the short frozen message.

---

## FFmpeg sidecar

Frozen lookup: `install_dir() / "ffmpeg.exe"` (Windows) or `install_dir() / "ffmpeg"` (Linux freeze). If missing, raise `FileNotFoundError` naming that path. No PATH fallback when frozen. Checkout still uses `shutil.which` and the "not on PATH" error.

Do not commit a Windows FFmpeg binary. After freeze, copy an official Windows build (essentials or full, 64-bit) next to `cleave.exe`, and drop its license files into `licenses/ffmpeg/` in the zip. FFmpeg licensing depends on the build (LGPL vs GPL); ship whatever the chosen binary requires.

---

## PyInstaller spec

[packaging/cleave.spec](../packaging/cleave.spec) is an onedir skeleton. Run it on Windows:

```
pyinstaller packaging/cleave.spec
```

Then copy `ffmpeg.exe` (and 2.2 DLLs) into `dist/cleave/`, not `dist/cleave/_internal/`.

- Entry: [cleave.py](../cleave.py) (`cleave.cli:main`).
- Collect pygame (SDL binaries and hiddenimports travel with that hook).
- `datas`: repo-root `cleave-viz.yaml` and `assets/fonts/` (includes `MaterialIcons-Regular.ttf` and its license).
- `excludes`: `torch`, `demucs`, `beat_this`, `librosa`, `matplotlib`. Stem split is not in this freeze.
- No CI freeze job in 2.1. PyInstaller is not on the default test path.

`play` on an existing project (stems + `signals.json`) must not import torch. `play` on raw audio, and `separate`, fail with a short message that stem split is not in this Windows build; copy a project from Linux.

`librosa` is excluded because analysis is not in the zip. That exclude is not freeze-safe yet:

- [cleave/cli.py](../cleave/cli.py) `cmd_separate` imports [cleave/config.py](../cleave/config.py), which loads [cleave/effects/](../cleave/effects/) then [cleave/extract.py](../cleave/extract.py) (`import librosa` at module level). Proven on Windows: `cleave.exe separate <wav>` raises `ModuleNotFoundError: No module named 'librosa'` instead of `require_stem_split`.
- Phase 2.2 play/render loads stem PCM through [cleave/pcm_io.py](../cleave/pcm_io.py), which imports librosa for resample.

2.2 must make those paths work without torch. Prefer lazy imports and soxr (already in [requirements.txt](../requirements.txt)) over bundling librosa. Do not add torch.

---

## ctypes search (code in 2.1; DLLs in 2.2)

[cleave/projectm.py](../cleave/projectm.py) and [cleave/projectm_playlist.py](../cleave/projectm_playlist.py):

- Frozen (any OS) or `win32`: search `install_dir()` for platform names first, then `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`.
- Checkout Linux: env var, pkg-config, then system `.so` paths (so `PROJECTM_LIB` still overrides).

Exact Windows filenames the loader looks for:

- Core: `projectM-4.dll`
- Playlist: `projectM-4-playlist.dll`

Linux frozen names stay `libprojectM-4.so` and `libprojectM-4-playlist.so` (plus the `libprojectM-4-playlist-4.so` alias).

---

## Windows libprojectM 4.2+ build

Do not run this build until 2.2. 2.2 copies the DLLs next to `cleave.exe`. Testers must not compile Visual Studio.

### Recommendation

**vcpkg + Visual Studio 2022, `x64-windows`, shared (DLL) triplet.** That yields MSVC DLLs named `projectM-4.dll` and `projectM-4-playlist.dll`, matches the ctypes search, and avoids shipping a MinGW runtime. Use the projectM 4.2 (or newer 4.x) port or a CMake overlay if vcpkg's version is older than 4.2.

CMake + Visual Studio without vcpkg is fine if you vendor glm (and any other CMake deps) yourself. Same target names.

MSYS2/MinGW works for a developer box but is a poor zip: you also ship `libgcc`, `libstdc++`, and possibly `libwinpthread`. Do not use MinGW DLLs for the tester zip unless the ctypes names are updated to `libprojectM-4.dll` and you accept those extra runtimes.

### Expected outputs

| File | Role |
| --- | --- |
| `projectM-4.dll` | Core renderer |
| `projectM-4-playlist.dll` | Playlist helper (depends on the core DLL) |
| `projectM-4.lib`, `projectM-4-playlist.lib` | Import libs; not needed at runtime |

Copy both DLLs into the onedir root. Add any other vcpkg dependency DLLs that `dumpbin /dependents` reports as non-system (zlib is the usual extra; OpenGL is `opengl32.dll` from Windows).

### OpenGL and CRT

projectM 4.x talks to OpenGL 3. The GPU driver provides that. pygame/SDL inside the freeze creates the context.

MSVC builds need the Visual C++ Redistributable (VS 2022 x64) on the tester machine, or app-local copies of `vcruntime140.dll` / `msvcp140.dll` next to the exe. Prefer documenting the redistributable for 2.2; app-local CRT is an option if testers cannot install it.

Ship libprojectM licenses next to FFmpeg's under `licenses/libprojectM/`.

### Where files go

Build on Windows, same machine (or same arch) that runs PyInstaller. After `pyinstaller packaging/cleave.spec`, copy:

- `ffmpeg.exe` -> `dist/cleave/`
- `projectM-4.dll`, `projectM-4-playlist.dll`, and extra non-system DLLs -> `dist/cleave/`
- license trees -> `dist/cleave/licenses/`

Then zip `dist/cleave/`.

---

## Seed presets and textures

Still open: whether a seed preset/texture pack ships in the zip, or testers copy packs into `Documents\cleave\presets` and `Documents\cleave\textures` (same tree as Linux `~/.local/share/cleave/`). First-run download is Later. 2.2 may choose either; do not block play/render on a bundled pack.

---

## Out of scope here

Installer, signing, and CI freeze (Phase 3); torch in the zip; macOS Application Support. 2.2 owns libprojectM build execution, pygame GPU editor proof, and play/render freeze proof.
