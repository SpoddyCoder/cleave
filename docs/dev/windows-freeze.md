# Windows freeze

How Cleave locates files when frozen, how testers unpack a Windows onedir zip, and how to build libprojectM 4.2+ DLLs. Product decisions live in [structured-releases.md](structured-releases.md). This note is the implementation design for the freeze (paths, spec, FFmpeg, ctypes, libprojectM). One spec ([packaging/cleave.spec](../../packaging/cleave.spec)) and one CI job ([.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml)): CPU torch, CUDA binaries filtered, matplotlib excluded. The job zips `dist/cleave/` as `cleave-<version>-windows-x64.zip` and compiles the Phase 3.2 installer (`cleave-<version>-windows-x64-setup.exe`) from that same tree. Phase 3.3.3 adds an optional in-editor download of pinned PyTorch CUDA wheels from download.pytorch.org; see [CUDA extra](#cuda-extra-phase-333).

Do not cross-compile the GUI stack from WSL. Build on Windows, run [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py), then zip `dist/cleave/` and compile [packaging/windows/cleave.iss](../../packaging/windows/cleave.iss). CI does that on `windows-latest`.

Related: [cleave/paths.py](../../cleave/paths.py), [cleave/ffmpeg.py](../../cleave/ffmpeg.py), [packaging/cleave.spec](../../packaging/cleave.spec), [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py), [cleave/projectm.py](../../cleave/projectm.py), [cleave/projectm_playlist.py](../../cleave/projectm_playlist.py).

---

## Relocatable path model

Three roots. Do not treat the checkout layout as the install layout.

| Helper | Frozen | Checkout | Holds |
| --- | --- | --- | --- |
| `install_dir()` | Parent of `sys.executable` (onedir folder root) | Repo root | Sidecars: `ffmpeg.exe`, later `projectM-4.dll` / `projectM-4-playlist.dll` |
| `resource_dir()` | `sys._MEIPASS` (onedir `_internal`) | Repo root | Bundled files: `assets/cleave-viz.yaml`, `assets/fonts/` |
| `data_dir()` | User data (not the zip) | Same | Projects, presets, textures, model weights (`models/`) |

`is_frozen()` is `bool(getattr(sys, "frozen", False))`. `repo_root()` is always the checkout (tests and source scans). Runtime code that needs bundled files uses `resource_dir()`.

User data is never written into the app folder.

- `CLEAVE_DATA` overrides the data root on every OS.
- Linux (when unset): `XDG_DATA_HOME/cleave` or `~/.local/share/cleave`.
- Windows (when unset): Known Folder Documents (`FOLDERID_Documents` via ctypes) `/Cleave`, fallback `Path.home() / "Documents" / "Cleave"`.
- Global settings only: Linux `~/.config/cleave/config.yaml` (or `XDG_CONFIG_HOME`); Windows `%APPDATA%\Cleave\config.yaml`.

Preset and texture defaults are `data_dir() / "presets"` and `data_dir() / "textures"` ([cleave/paths.py](../../cleave/paths.py) `default_preset_root` / `default_texture_paths`). First write still creates directories; import does not.

Stem split calls Demucs in-process (`demucs.pretrained.get_model` and `demucs.apply.apply_model` in [cleave/separate.py](../../cleave/separate.py)), not `python -m demucs`. Frozen mix load uses the sidecar ffmpeg CLI rather than Demucs `load_track`. Stem wavs are written with soundfile (16-bit PCM), not Demucs `save_audio` / torchaudio. Beat This runs as `Audio2Beats` on audio already loaded with librosa/soundfile, not `File2Beats` (`torchaudio.load`). Before model load, Demucs and Beat This call `torch.hub.set_dir` so checkpoints land in `data_dir() / "models"` (`model_cache_dir()`). First-run download still happens; weights are not baked into the freeze.

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
    assets/cleave-viz.yaml
    assets/fonts/
```

Sidecars must sit next to `cleave.exe`. Files in `_internal` are bundled resources. Mixing those two is a common freeze bug.

Manual 2.1 proof (met; no GPU, no DLLs, no torch):

```
cleave.exe --version
cleave.exe --help
```

Phase 2.2 proof (met): `cleave.exe play <existing-project>` and a short `cleave.exe render` on a Windows box with a GPU driver. Copy `projects/` from Linux; that zip did not run `separate`. Frozen `separate` and raw-audio `play` raised the short stem-split message.

Phase 3.1 GPU proof (met): the same play path from a `workflow_dispatch` zip built on `windows-latest` (`cleave.exe play` on an existing project). CI headless smoke covered `--version`, `--help`, and frozen `separate`.

---

## FFmpeg sidecar

Frozen lookup: `install_dir() / "ffmpeg.exe"` (Windows) or `install_dir() / "ffmpeg"` (Linux freeze). If missing, raise `FileNotFoundError` naming that path. No PATH fallback when frozen. Checkout still uses `shutil.which` and the "not on PATH" error.

Demucs 4.0.1 `load_track` (`demucs.audio.AudioFile`) shells out to `ffmpeg` and `ffprobe` by name on PATH, then falls back to torchaudio/torchcodec (shared FFmpeg DLLs). `save_audio` always uses `torchaudio.save`, which loads TorchCodec. The freeze ships static `ffmpeg.exe` only, not ffprobe or those DLLs. Frozen stem split prepends `install_dir()` to PATH (`sidecar_ffmpeg_on_path` in [cleave/ffmpeg.py](../../cleave/ffmpeg.py)) and decodes the mix with `ffmpeg_executable()` into a tensor for `apply_model`. Checkout still uses Demucs `load_track` and PATH ffmpeg for mix decode. Before that, wav sources are copied into the project and other supported inputs (mp3, flac, m4a, aac, ogg, aiff, aif) are converted to PCM WAV with `ffmpeg_executable()` (`-vn`, `pcm_s16le`, native sample rate). An existing project mix stays as stored, including an older non-wav filename. Demucs then runs on that project mix. Both frozen and checkout write stem wavs with soundfile. A missing sidecar raises `FileNotFoundError` naming `install_dir() / ffmpeg.exe`.

Do not commit a Windows FFmpeg binary. [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py) downloads a pinned official Windows essentials build, verifies SHA-256, copies `ffmpeg.exe` next to `cleave.exe`, and drops that build's LICENSE/COPYING/NOTICE files into `licenses/ffmpeg/`. URL and checksum are the `FFMPEG_URL` and `FFMPEG_SHA256` constants at the top of that script. The zip is cached at `.cache/ffmpeg-windows.zip` (gitignored).

Pinned build: GyanD/codexffmpeg 9.0.1 essentials (64-bit Windows, static, GPLv3; the gyan.dev release essentials zip, versioned GitHub asset). Essentials includes libx264 and aac for Cleave's MP4 render. Ship the zip's LICENSE (GPLv3) with the freeze.

---

## PyInstaller spec

[packaging/cleave.spec](../../packaging/cleave.spec) is the Windows freeze: CPU torch, CUDA binaries filtered, matplotlib excluded. One `cleave.exe`. `install_dir()` is the parent of the exe. Sidecars come from [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py). Weights stay in user data (`model_cache_dir()`); they are not datas in the spec.

Do not `pip install -r requirements.txt` in the freeze venv: that file has no torch extra index and can pull a CUDA wheel from PyPI.

### Venv install order (Windows)

From the repo root:

```
python -m pip install -r requirements-freeze.txt
python -m pip install -r requirements-torch-cpu.txt
python -m pip install demucs==4.0.1 beat-this==1.1.0 librosa==0.11.0 einops==0.8.2 rotary-embedding-torch==0.9.1 tqdm==4.67.3 setuptools==80.8.0
```

1. [requirements-freeze.txt](../../requirements-freeze.txt) is the play/render freeze set (PyInstaller, pygame, soxr, numpy, soundfile, ...). It does not install torch.
2. [requirements-torch-cpu.txt](../../requirements-torch-cpu.txt) pins CPU `torch` / `torchaudio` / `torchcodec` and sets `--extra-index-url https://download.pytorch.org/whl/cpu`. Install this before Demucs so pip does not resolve a CUDA wheel from PyPI.
3. Analyse extras from [requirements.txt](../../requirements.txt): `demucs`, `beat-this`, `librosa`, plus the model helpers those packages need (`einops`, `rotary-embedding-torch`, `tqdm`, `setuptools`). Their remaining deps (numba, scipy, scikit-learn, julius, lameenc, openunmix, audioread, ...) come in as transitive installs.

Do not install `matplotlib`. librosa lists it as the `display` extra; [cleave/extract.py](../../cleave/extract.py) and [cleave/analyse.py](../../cleave/analyse.py) do not import it. The spec excludes `matplotlib` (and Beat This training extras: `pytorch_lightning`, `mir_eval`, `madmom`).

### Freeze and stage

```
pyinstaller packaging/cleave.spec
python scripts/windows_stage_freeze.py --dist dist/cleave
```

COLLECT `name="cleave"`, so output is `dist/cleave/cleave.exe` plus `_internal/`. Stage into that folder. `console=False` (windowed PE), `upx=False`.

The exe does not open a terminal on Start Menu, desktop, or drop-on-exe. [cleave/win_console.py](../../cleave/win_console.py) `attach_parent_console()` keeps redirected stdout/stderr (pipes and files, including CI `capture_output`) and otherwise attaches to the parent console when launched from cmd or PowerShell, so `--help`, `--version`, and CLI output still print. If attach fails (Explorer / Start Menu), pre-window fatal errors use a Windows message box (`MessageBoxW`). In-window errors stay in the editor.

That copies `packaging/windows/*.dll` and libprojectM licenses, fetches the pinned FFmpeg zip, and asserts `cleave.exe`, `ffmpeg.exe`, and the projectM DLLs sit in the onedir root. Use `--no-exe-check` only in tests that have no exe.

- Entry: [cleave.py](../../cleave.py) (`cleave.cli:main`). EXE name `cleave`. COLLECT name `cleave` (writes `dist/cleave/`).
- `datas`: `assets/cleave-viz.yaml` and `assets/fonts/` (includes `MaterialIcons-Regular.ttf`, `DejaVuSansMono.ttf`, `DejaVuSansMono-Bold.ttf`, and their licenses).
- Play on an existing project (stems + `signals.json`) must not import torch or librosa at module load. Dropping a music file (wav, mp3, flac, m4a, aac, ogg, aiff, or aif) or running `cleave.exe play <audio>` opens the loading window, downloads weights, splits, and analyses. The project mix is PCM WAV.

`librosa` is collected for analyse. Play/render stay freeze-safe on a complete project: stem types and paths live in [cleave/stems.py](../../cleave/stems.py); PCM resample uses soxr in [cleave/pcm_io.py](../../cleave/pcm_io.py). [cleave/extract.py](../../cleave/extract.py) imports librosa for analyse only. `STEM_SPLIT_MISSING_FROZEN` remains a runtime guard if frozen torch is missing; it is not the product smoke.

### What the spec collects

`collect_all` for pygame and soxr, then torch, torchaudio, torchcodec, demucs, beat_this, librosa, and the installed packages those need that carry binaries or package data: soundfile, audioread, numba, scipy, sklearn, julius, lameenc, openunmix, einops, rotary_embedding_torch, omegaconf, dora, joblib, pooch.

Hidden imports cover Demucs pickle/load (`demucs.pretrained`, `demucs.hdemucs`, `demucs.htdemucs`, `demucs.apply`, `demucs.audio`), Beat This inference (`beat_this.inference`, `beat_this.model.beat_tracker`), librosa / soundfile / audioread, and numpy 2 `_core` internals.

`datas`: `assets/cleave-viz.yaml` and `assets/fonts/`. Demucs `remote/*.yaml` travels with `collect_all("demucs")`.

CUDA binaries are dropped after collect: names matching `cudart`, `cublas`, `cudnn`, `nccl`, `nvrtc`, and similar (`torch_cuda`, `c10_cuda`, ...). The `torch` Python package is not excluded. CPU wheels already omit CUDA; the filter is so PyInstaller does not copy stubs.

---

## CI freeze

One job named `freeze` on standard `windows-latest` (`timeout-minutes: 180`). Workflow: [.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml) (`workflow_dispatch` and `workflow_call`, not every push). Tag [release.yml](../../.github/workflows/release.yml) calls this workflow after `publish` with `release_tag` set to the tag. Tags wait on the CPU Demucs smoke.

Install order matches the venv recipe above: [requirements-freeze.txt](../../requirements-freeze.txt), then [requirements-torch-cpu.txt](../../requirements-torch-cpu.txt), then the analyse pins (demucs, beat-this, librosa, einops, rotary-embedding-torch, tqdm, setuptools). Do not `pip install -r requirements.txt`. Pip cache keys those two requirement files; do not cache FFmpeg zips, freeze output, or torch wheels as workflow artifacts. Model weights download on first run into `CLEAVE_DATA` (`models/`); they are not baked into the freeze.

- Sidecars: committed libprojectM DLLs from [packaging/windows/](../../packaging/windows/) (convention in that directory's [README.md](../../packaging/windows/README.md)); FFmpeg from `FFMPEG_URL` / `FFMPEG_SHA256` at the top of [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py). No vcpkg in the job. Do not commit `ffmpeg.exe`.
- Headless smoke: `cleave.exe --version` must print `cleave X.Y.Z`, `--help` lists `separate` / `play` / `render` / `backup` / `restore`, then `cleave.exe separate` on [tests/fixtures/smoke-separate.wav](../../tests/fixtures/smoke-separate.wav) (2 s PCM sine). Assert `stems/{drums,bass,vocals,other}.wav` exist and `signals.json` `version` equals `SIGNALS_VERSION` ([cleave/signals.py](../../cleave/signals.py); checker [scripts/assert_separate_project.py](../../scripts/assert_separate_project.py)). The separate step has a 90-minute timeout. No CUDA. No GPU compositing. Do not assert `STEM_SPLIT_MISSING_FROZEN`.
- Zip layout is `cleave/cleave.exe` inside `cleave-<version>-windows-x64.zip`.
- After the zip, Inno Setup wraps the same `dist\cleave\` tree into `cleave-<version>-windows-x64-setup.exe` (see Installer below).
- Dispatch uploads 5-day Actions artifacts (`cleave-windows-x64` zip, `cleave-windows-x64-setup` installer). A non-empty `release_tag` uses `gh release upload` for both assets and does not retain a workflow artifact. Never both.

GPU proof from zip and Program Files (play an existing project) is met for 3.1/3.2. Drop-a-wav proof on this freeze is met (3.3.2): dispatch zip and Program Files, named first-run weight download and split in the loading window, then the project opens. Warm-cache second run skips download chatter. `cleave.exe separate` from cmd still writes stems and `signals.json`.

---

## Audio output device

[cleave/viz/mix_player.py](../../cleave/viz/mix_player.py) opens one SDL output device by name, because `pygame._sdl2.AudioDevice` rejects an empty name and so cannot ask SDL for the default the way `SDL_OpenAudioDevice(NULL, ...)` does. `sdl_default_output_device()` reads the default endpoint from the SDL library pygame already loaded (`SDL_GetDefaultAudioInfo`, SDL 2.24+) and `select_output_device` prefers it. SDL's enumeration order is arbitrary on Windows WASAPI, so the first enumerated name is only a last resort; picking it can send playback to a silent endpoint (digital output, an HDMI monitor with no speakers) while the transport clock still advances.

Two environment variables help when playback is silent or lands on the wrong endpoint:

- `CLEAVE_AUDIO_DEBUG=1` prints the enumerated devices, SDL's default, the chosen endpoint, the requested format, and the mix PCM peak/RMS to stderr.
- `CLEAVE_AUDIO_DEVICE=<name>` forces an endpoint by exact or case-insensitive substring match (for example `CLEAVE_AUDIO_DEVICE=Speakers`).

---

## OpenGL error checking

The frozen build turns off PyOpenGL's `glGetError` check after every GL call ([cleave/gl_error_checking.py](../../cleave/gl_error_checking.py)), which the ImGui renderer pays per draw command. A checkout keeps it on. For a GL bug report from the frozen build, set `CLEAVE_GL_ERROR_CHECKING=1` so a failing call raises where it happens.

---

## ctypes search (code in 2.1; DLLs in 2.2)

[cleave/projectm.py](../../cleave/projectm.py) and [cleave/projectm_playlist.py](../../cleave/projectm_playlist.py):

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

The projectM pair is committed in [packaging/windows/](../../packaging/windows/) (`projectM-4.dll`, `projectM-4-playlist.dll`, LGPL tree under `licenses/libprojectM/`). CI and local freezes copy `packaging/windows/*.dll`. Rebuild notes and `dumpbin` dependents: [packaging/windows/README.md](../../packaging/windows/README.md). Put extra non-system DLLs (if `dumpbin /dependents` reports any) in that same directory so the script copies them with the projectM pair. Do not commit `ffmpeg.exe`.

Build on Windows, same machine (or same arch) that runs PyInstaller. After `pyinstaller packaging/cleave.spec`:

```
python scripts/windows_stage_freeze.py --dist dist/cleave
```

Then zip `dist/cleave/`.

---

## Installer (Phase 3.2)

Inno Setup 6 wraps the staged onedir tree. No second freeze and no second layout: `iscc` reads `dist\cleave\` exactly as [scripts/windows_stage_freeze.py](../../scripts/windows_stage_freeze.py) leaves it, so `install_dir()` stays the parent of `cleave.exe` (now under Program Files by default).

- Script: [packaging/windows/cleave.iss](../../packaging/windows/cleave.iss). Source `dist\cleave\*` with `recursesubdirs`; `DestDir: {app}`. Override the source with `/DDistDir=...` if needed.
- `AppId` is a fixed GUID chosen once (`{caf89057-3432-458e-a1de-1dba1176a4ba}`). Never change it. `AppVersion` comes from the build (`iscc /DAppVersion=X.Y.Z`), read from `cleave.__version__`; the `.iss` `#error`s if it is missing.
- `DefaultDirName={autopf}\Cleave`, `ArchitecturesAllowed=x64compatible`, `ArchitecturesInstallIn64BitMode=x64compatible`, `PrivilegesRequired=admin` with `PrivilegesRequiredOverridesAllowed=dialog` so a non-admin can install per user.
- `OutputBaseFilename=cleave-<version>-windows-x64-setup` at the repo root (same place as the zip).
- Tasks (both unchecked by default): `desktopicon` (`{autodesktop}\Cleave`), `addtopath` (append `{app}` to HKLM PATH when admin, HKCU when per-user; remove that entry on uninstall without duplicating PATH).
- Start Menu shortcut `{autoprograms}\Cleave` targets `cleave.exe` with no arguments. That opens the editor window and the in-window file picker, so the user can browse for an audio file (wav, mp3, flac, m4a, aac, ogg, aiff, or aif) or a project without a terminal.
- Uninstall removes `{app}` only. User data (`Documents\Cleave\`) and `%APPDATA%\Cleave\` survive. The finished and uninstall pages say so.

CI in [.github/workflows/windows-freeze.yml](../../.github/workflows/windows-freeze.yml), after the zip step and reusing the same `dist\cleave\`:

```
choco install innosetup -y --no-progress
iscc /DAppVersion=<version> packaging\windows\cleave.iss
```

Headless smoke: `setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR=<temp> /TASKS=`, run `<temp>\cleave.exe --version`, then `unins000.exe /VERYSILENT` and assert `<temp>` is gone or empty. No GPU. `/TASKS=` leaves PATH unchanged on the runner. Dispatch uploads a 5-day `cleave-windows-x64-setup` artifact; a non-empty `release_tag` uses `gh release upload` for the setup exe next to the zip.

Drop onto the exe uses the argv normalisation in [cleave/cli.py](../../cleave/cli.py) (single existing path with no subcommand runs `play`). Frozen errors in a parent terminal print to that console. Explorer-launched fatal errors before the window opens use a message box.

Manual GPU proof (met): install from the setup exe into Program Files; `cleave.exe play` on an existing project from the Start Menu shortcut, a terminal, and by dropping a project folder onto `cleave.exe`; audio on the default output device; pattern mask at default `full-quality` preview quality; same behaviour from the dispatch zip and the installer; uninstall removes the install dir only. See [Audio output device](#audio-output-device) for silent-playback debugging.

---

## CUDA extra (Phase 3.3.3)

Product decision: [structured-releases.md](structured-releases.md) 3.3.3. The setup exe and the zip are CPU-only. CUDA torch is an optional download in the editor's Welcome to Cleave step, on first launch and from Settings > Download Packages.... Cleave does not build or host a CUDA payload. The installer has no CUDA page and no `/CUDA=1`.

The extra is the PyTorch CUDA wheels in [requirements-torch-cu130.txt](../../requirements-torch-cu130.txt) (cu130), not NVIDIA's developer CUDA Toolkit from nvidia.com. Do not download that Toolkit. User-facing copy still says "CUDA Toolkit". Wheels come from `https://download.pytorch.org/whl/cu130/`. Match the freeze CPython (`cp310`, `win_amd64`).

Windows cu130 does not need separate `nvidia-*` wheels. A platform-tagged pip resolve of [requirements-torch-cu130.txt](../../requirements-torch-cu130.txt) for `cp310` `win_amd64` yields only the three CUDA wheels below plus pure-Python torch deps already in the CPU freeze (`filelock`, `typing-extensions`, `setuptools`, `sympy`, `networkx`, `jinja2`, `fsspec`, ...). Torch METADATA on that wheel has no `nvidia-*` Requires-Dist. The CUDA 13 runtime DLLs (cudart, cublas, cudnn, cufft, curand, cusolver, cusparse, nvrtc, ...) live inside `torch/lib/` of the Windows torch wheel. Linux cu130 is different: it pulls `nvidia-*` packages.

Pinned wheels: `CUDA_WHEELS` in [cleave/cuda_extra.py](../../cleave/cuda_extra.py) (filename, URL, SHA-256, size). Do not scrape the PyTorch index at run time. Do not `pip install` into the freeze (no pip in the onedir). Do not attach the wheels as Release assets. When the pins change, change `CUDA_EXTRA_KEY` with them.

- `torch-2.12.0+cu130-cp310-cp310-win_amd64.whl`, 1926375050 bytes
- `torchaudio-2.11.0+cu130-cp310-cp310-win_amd64.whl`, 1722730 bytes
- `torchcodec-0.14.0+cu130-cp310-cp310-win_amd64.whl`, 3574648 bytes

Sum: 1931672428 bytes (1842 MiB, the size the welcome step shows). URLs use `%2B` for the `+` in the wheel filename; the PyTorch R2 CDN (behind a 301 from `download.pytorch.org`) handles the encoded form more reliably.

Offer (`cleave.first_run`, item `CUDA Toolkit`, default off): only on the frozen Windows build, when `nvcuda.dll` loads and `cuDriverGetVersion` reports 13000 or more (CUDA 13.0, NVIDIA driver 580.88 or newer), and the overlay is not installed yet. An off-by-default item never brings the welcome step back on its own.

Download (`download_cuda_extra`, on the welcome step's worker thread): stream each wheel into a staging folder with a running SHA-256, then unpack all three with `zipfile` and check that `torch`, `torchaudio`, and `torchcodec` exist. Only then write the `complete` marker and rename staging into place, so a failure, hash mismatch, or Cancel leaves nothing half-installed. Older `CUDA_EXTRA_KEY` folders are removed after a successful install. The progress bar spends 90% on the download and 10% on the unpack.

Location: `%LOCALAPPDATA%\Cleave\cuda\<CUDA_EXTRA_KEY>\` (`paths.cuda_extra_root`; `<CLEAVE_DATA>\cuda` when that override is set). Local app data, not Documents (OneDrive) or the roaming profile, and not the install folder: Program Files needs admin rights, and Windows locks torch's DLLs once a split has loaded them. Uninstall leaves this folder; delete it by hand to reclaim the space or fall back to CPU torch.

Activation (`activate_cuda_extra`, first thing in `cli.main`): when the marker exists on the frozen Windows build, insert `_OverlayFinder` at the front of `sys.meta_path` (ahead of PyInstaller's importer, which would otherwise serve the bundled CPU torch from the PYZ) and the overlay folder at the front of `sys.path`. The finder resolves only `torch`, `functorch`, `torchgen`, `torchaudio`, and `torchcodec` and their submodules. Torch's own `__init__` adds the overlay's `torch\lib` to the DLL search path, so the CPU and CUDA native builds are never mixed. A download finished before anything imported torch activates in the same run; otherwise the welcome step shows "Done - restart Cleave to use it".

Runtime: `torch.cuda.is_available()` in [cleave/separate.py](../../cleave/separate.py) picks CUDA when the overlay loads; otherwise CPU. Missing extra is a slower split, not `STEM_SPLIT_MISSING_FROZEN`.

Not yet proven on an NVIDIA box: that the overlay torch imports cleanly inside the freeze and `torch.cuda.is_available()` is True.

---

## Seed presets and textures

The zip does not bundle preset or texture packs. On launch, when the presets directory is empty, the editor's Welcome to Cleave step offers to download starter packs (with the model weights) into `Documents\Cleave\presets` and `Documents\Cleave\textures` (same tree as Linux `~/.local/share/cleave/`). Play/render do not require a pack in the zip.

---

## Out of scope here

Signing; macOS Application Support.
