# Windows freeze

How Cleave locates files when frozen, how testers unpack a Windows onedir zip, and how to build libprojectM 4.2+ DLLs. Product decisions live in [structured-releases.md](structured-releases.md). This note is the implementation design for the freeze (paths, spec, FFmpeg, ctypes, libprojectM). Phase 3.1 CI is [.github/workflows/windows-freeze.yml](../.github/workflows/windows-freeze.yml). The same workflow builds the Phase 3.2 installer after the zip.

Do not cross-compile the GUI stack from WSL. Build on Windows, run [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py), then zip `dist/cleave/` and compile [packaging/windows/cleave.iss](../packaging/windows/cleave.iss) (CI does the same on `windows-latest`).

Related: [cleave/paths.py](../cleave/paths.py), [cleave/ffmpeg.py](../cleave/ffmpeg.py), [packaging/cleave.spec](../packaging/cleave.spec), [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py), [cleave/projectm.py](../cleave/projectm.py), [cleave/projectm_playlist.py](../cleave/projectm_playlist.py).

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

PyInstaller onedir, one `cleave.exe`, CLI subcommands (`cleave.exe play ...`). Unpack the zip and run from that folder. The installer copies this same tree into Program Files.

```
cleave/
  cleave.exe
  ffmpeg.exe                 # copied after freeze; not inside _internal
  projectM-4.dll
  projectM-4-playlist.dll
  licenses/
    ffmpeg/
    libprojectM/
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

Phase 2.2 proof (met): `cleave.exe play <existing-project>` and a short `cleave.exe render` on a Windows box with a GPU driver. Copy `projects/` from Linux; do not run `separate` in this zip. Frozen `separate` and raw-audio `play` raise the short stem-split message.

Phase 3.1 GPU proof (met): the same play path from a `workflow_dispatch` zip built on `windows-latest` (`cleave.exe play` on an existing project). CI headless smoke covers `--version`, `--help`, and frozen `separate`.

---

## FFmpeg sidecar

Frozen lookup: `install_dir() / "ffmpeg.exe"` (Windows) or `install_dir() / "ffmpeg"` (Linux freeze). If missing, raise `FileNotFoundError` naming that path. No PATH fallback when frozen. Checkout still uses `shutil.which` and the "not on PATH" error.

Do not commit a Windows FFmpeg binary. [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py) downloads a pinned official Windows essentials build, verifies SHA-256, copies `ffmpeg.exe` next to `cleave.exe`, and drops that build's LICENSE/COPYING/NOTICE files into `licenses/ffmpeg/`. URL and checksum are the `FFMPEG_URL` and `FFMPEG_SHA256` constants at the top of that script. The zip is cached at `.cache/ffmpeg-windows.zip` (gitignored).

Pinned build: GyanD/codexffmpeg 9.0.1 essentials (64-bit Windows, static, GPLv3; the gyan.dev release essentials zip, versioned GitHub asset). Essentials includes libx264 and aac for Cleave's MP4 render. Ship the zip's LICENSE (GPLv3) with the freeze.

---

## PyInstaller spec

[packaging/cleave.spec](../packaging/cleave.spec) is an onedir skeleton. Run it on Windows:

```
pyinstaller packaging/cleave.spec
```

Then stage sidecars (not into `dist/cleave/_internal/`):

```
python scripts/windows_stage_freeze.py --dist dist/cleave
```

That copies `packaging/windows/*.dll` and libprojectM licenses, fetches the pinned FFmpeg zip, and asserts `cleave.exe`, `ffmpeg.exe`, and the projectM DLLs sit in the onedir root. Use `--no-exe-check` only in tests that have no exe.

- Entry: [cleave.py](../cleave.py) (`cleave.cli:main`).
- Collect pygame (SDL binaries and hiddenimports travel with that hook) and soxr (native resample in [cleave/pcm_io.py](../cleave/pcm_io.py)).
- `datas`: repo-root `cleave-viz.yaml` and `assets/fonts/` (includes `MaterialIcons-Regular.ttf`, `DejaVuSansMono.ttf`, `DejaVuSansMono-Bold.ttf`, and their licenses).
- `excludes`: `torch`, `demucs`, `beat_this`, `librosa`, `matplotlib`. Stem split is not in this freeze.

`play` on an existing project (stems + `signals.json`) must not import torch or librosa. `play` on raw audio, and `separate`, fail with a short message that stem split is not in this Windows build; copy a project from Linux.

`librosa` is excluded because analysis is not in the zip. Play/render stay freeze-safe: stem types and paths live in [cleave/stems.py](../cleave/stems.py); PCM resample uses soxr in [cleave/pcm_io.py](../cleave/pcm_io.py). [cleave/extract.py](../cleave/extract.py) imports librosa for analyse only. Frozen `separate` reaches `require_stem_split` and raises `STEM_SPLIT_MISSING_FROZEN`.

---

## CI freeze (Phase 3.1)

Same recipe as the manual steps above, on standard `windows-latest`. Workflow: [.github/workflows/windows-freeze.yml](../.github/workflows/windows-freeze.yml) (`workflow_dispatch` and `workflow_call`, not every push).

- Pip cache only (`requirements-freeze.txt`); do not cache FFmpeg zips or freeze output.
- Sidecars: committed libprojectM DLLs from [packaging/windows/](../packaging/windows/) (convention in that directory's [README.md](../packaging/windows/README.md)); FFmpeg from `FFMPEG_URL` / `FFMPEG_SHA256` at the top of [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py). No vcpkg in the job. Do not commit `ffmpeg.exe`.
- Headless smoke: `cleave.exe --version` must print `cleave X.Y.Z`, `--help` lists `separate` / `play` / `render` / `backup` / `restore`, and `cleave.exe separate` with a dummy file prints `STEM_SPLIT_MISSING_FROZEN` (no traceback). No GPU compositing.
- Zip layout is `cleave/cleave.exe` inside `cleave-<version>-windows-x64.zip`.
- After the zip, Inno Setup wraps the same `dist\cleave\` tree into `cleave-<version>-windows-x64-setup.exe` (see Installer below).
- Dispatch uploads 5-day Actions artifacts (`cleave-windows-x64` zip, `cleave-windows-x64-setup` installer). Tag pipeline: [.github/workflows/release.yml](../.github/workflows/release.yml) calls this workflow after `publish` with `release_tag` set to the tag; a non-empty `release_tag` uses `gh release upload` for both assets and does not retain a workflow artifact.
- GPU proof (met): unpack the dispatch zip or install from the setup exe on a Windows box with a GPU driver; run `cleave.exe play` on an existing project (audio on the default output device; pattern mask at default `balanced` preview quality). A short `cleave.exe render` is the same 2.2 path if you want extra coverage.

---

## Audio output device

[cleave/viz/mix_player.py](../cleave/viz/mix_player.py) opens one SDL output device by name, because `pygame._sdl2.AudioDevice` rejects an empty name and so cannot ask SDL for the default the way `SDL_OpenAudioDevice(NULL, ...)` does. `sdl_default_output_device()` reads the default endpoint from the SDL library pygame already loaded (`SDL_GetDefaultAudioInfo`, SDL 2.24+) and `select_output_device` prefers it. SDL's enumeration order is arbitrary on Windows WASAPI, so the first enumerated name is only a last resort; picking it can send playback to a silent endpoint (digital output, an HDMI monitor with no speakers) while the transport clock still advances.

Two environment variables help when playback is silent or lands on the wrong endpoint:

- `CLEAVE_AUDIO_DEBUG=1` prints the enumerated devices, SDL's default, the chosen endpoint, the requested format, and the mix PCM peak/RMS to stderr.
- `CLEAVE_AUDIO_DEVICE=<name>` forces an endpoint by exact or case-insensitive substring match (for example `CLEAVE_AUDIO_DEVICE=Speakers`).

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

Copy the DLLs next to `cleave.exe` after freeze. Testers must not compile Visual Studio.

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

The projectM pair is committed in [packaging/windows/](../packaging/windows/) (`projectM-4.dll`, `projectM-4-playlist.dll`, LGPL tree under `licenses/libprojectM/`). CI and local freezes copy `packaging/windows/*.dll`. Rebuild notes and `dumpbin` dependents: [packaging/windows/README.md](../packaging/windows/README.md). Put extra non-system DLLs (if `dumpbin /dependents` reports any) in that same directory so the script copies them with the projectM pair. Do not commit `ffmpeg.exe`.

Build on Windows, same machine (or same arch) that runs PyInstaller. After `pyinstaller packaging/cleave.spec`:

```
python scripts/windows_stage_freeze.py --dist dist/cleave
```

Then zip `dist/cleave/`.

---

## Installer (Phase 3.2)

Inno Setup 6 wraps the staged onedir tree. No second freeze and no second layout: `iscc` reads `dist\cleave\` exactly as [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py) leaves it, so `install_dir()` stays the parent of `cleave.exe` (now under Program Files by default).

- Script: [packaging/windows/cleave.iss](../packaging/windows/cleave.iss). Source `dist\cleave\*` with `recursesubdirs`; `DestDir: {app}`. Override the source with `/DDistDir=...` if needed.
- `AppId` is a fixed GUID chosen once (`{caf89057-3432-458e-a1de-1dba1176a4ba}`). Never change it. `AppVersion` comes from the build (`iscc /DAppVersion=X.Y.Z`), read from `cleave.__version__`; the `.iss` `#error`s if it is missing.
- `DefaultDirName={autopf}\Cleave`, `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`, `PrivilegesRequired=admin` with `PrivilegesRequiredOverridesAllowed=dialog` so a non-admin can install per user.
- `OutputBaseFilename=cleave-<version>-windows-x64-setup` at the repo root (same place as the zip).
- Tasks (both unchecked by default): `desktopicon` (`{autodesktop}\Cleave`), `addtopath` (append `{app}` to HKLM PATH when admin, HKCU when per-user; remove that entry on uninstall without duplicating PATH).
- Start Menu shortcut `{autoprograms}\Cleave` targets `cleave.exe` with no arguments, which prints help.
- Uninstall removes `{app}` only. User data (`Documents\cleave\`) and `%APPDATA%\cleave\` survive. The finished and uninstall pages say so.

CI in [.github/workflows/windows-freeze.yml](../.github/workflows/windows-freeze.yml), after the zip step and reusing the same `dist\cleave\`:

```
choco install innosetup -y --no-progress
iscc /DAppVersion=<version> packaging\windows\cleave.iss
```

Headless smoke: `setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<temp> /TASKS=`, run `<temp>\cleave.exe --version`, then `unins000.exe /VERYSILENT` and assert `<temp>` is gone or empty. No GPU. `/TASKS=` leaves PATH unchanged on the runner. Dispatch uploads a 5-day `cleave-windows-x64-setup` artifact; a non-empty `release_tag` uses `gh release upload` for the setup exe next to the zip.

Drop onto the exe uses the argv normalisation in [cleave/cli.py](../cleave/cli.py) (single existing path with no subcommand runs `play`), plus a pause before exit when a frozen process owns its console, or an Explorer-launched error vanishes with the window.

Manual GPU proof (met): install from the setup exe into Program Files; `cleave.exe play` on an existing project from the Start Menu shortcut, a terminal, and by dropping a project folder onto `cleave.exe`; audio on the default output device; pattern mask at default `balanced` preview quality; same behaviour from the dispatch zip and the installer; uninstall removes the install dir only. See [Audio output device](#audio-output-device) for silent-playback debugging.

---

## Seed presets and textures

Still open: whether a seed preset/texture pack ships in the zip, or testers copy packs into `Documents\cleave\presets` and `Documents\cleave\textures` (same tree as Linux `~/.local/share/cleave/`). First-run download is Later. Play/render do not require a pack in the zip.

---

## Out of scope here

Signing; torch in the zip; macOS Application Support.
