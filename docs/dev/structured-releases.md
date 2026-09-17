# Structured releases

Move Cleave from checkout-based development to versioned GitHub Releases.

Phase 1 is done (`v0.1.0`, source-only). Phase 2 is done (Windows play/render onedir zip, manual freeze). Phase 3.1 and 3.2 are done (CI freeze zip, installer and argv normalisation, GPU proof from zip and Program Files). Phase 3.3.1 is done (frozen CPU `separate` stack, dispatch zip, editor-first split). Phase 3.3.2 is done (CPU `separate` is the only Windows zip and setup exe; lean spec retired). Phases 2, 3.1, 3.2, 3.3.1, and 3.3.2 landed on `main` with no tag beyond `v0.1.0`. [`v0.2.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.2.0) is the first tag that attaches the Windows zip and setup exe (CPU `separate` plus play/render). The installer can download optional CUDA wheels (Phase 3.3.3); manual NVIDIA-box proof is still outstanding. Phase 4 (Linux and macOS binaries) follows 3.3.

Related: [README.md](../README.md) (current Linux/WSL setup), [completed/user-data-and-config-plan.md](completed/user-data-and-config-plan.md) (install vs user data), [cleave/paths.py](../cleave/paths.py), [cleave/projectm.py](../cleave/projectm.py), [windows-freeze.md](windows-freeze.md) (paths, spec, FFmpeg sidecar, ctypes names, libprojectM build recommendation).

---

## Across all phases

Decide these once, then reuse. Refine per phase rather than reinventing them.

- **Versioning.** Semver. While pre-1.0, versions are `0.x` (`0.1.0`, `0.2.0`, ...); breaking changes are allowed on minor bumps until 1.0. Single source of truth: `cleave.__version__` in [cleave/__init__.py](../cleave/__init__.py). Tags are `vX.Y.Z` and must match that string. [pyproject.toml](../pyproject.toml) reads the same attr (`[tool.setuptools.dynamic]`); this is metadata only, not a pip install.
- **Changelog.** [CHANGELOG.md](../CHANGELOG.md) in Keep a Changelog format (`## [Unreleased]`, then `## [X.Y.Z] - YYYY-MM-DD` with Added / Changed / Fixed / Removed as appropriate). Each GitHub Release body is that version's section, extracted by [scripts/changelog_section.py](../scripts/changelog_section.py).
- **User data vs install.** Frozen or zip installs must not write projects, presets, or configs into the app folder. Linux data stays XDG (`~/.local/share/cleave/`, config in `~/.config/cleave/`). Windows data mirrors that tree under `Documents\Cleave\`; only the global settings file lives in `%APPDATA%\Cleave\`. macOS Application Support is Phase 4. See the user-data plan.
- **Editor first.** The frozen Windows editor is the majority product (Start Menu, desktop, drop a file). CLI stays for Linux checkout, scripts, and CI. New user-facing work needs an in-window path; stderr is optional. Stance: [.cursor/rules/editor-first.mdc](../.cursor/rules/editor-first.mdc).
- **Editor vs `separate`.** Play and offline render need pygame, OpenGL, libprojectM, and FFmpeg. Stem split needs Demucs and PyTorch (CPU or CUDA; CUDA is optional, for faster Demucs). Play/render GPU is OpenGL, unrelated to CUDA torch. Phase 2's first Windows freeze did not bundle torch. Phase 3.3 is the Windows `separate` plan: 3.3.2 is the current Windows product (CPU `separate` in the zip and setup exe; Cleave does not ship without stem split). 3.3.3 adds an optional CUDA download in that same installer when an NVIDIA GPU is detected. Drop-a-wav into the editor is the 3.3 ship path; `cleave.exe separate` is the headless/CI path.
- **Native deps.** libprojectM 4.2+ (core + playlist) and FFmpeg are not Python packages. Every binary OS needs a build or sidecar story. Frozen/Windows ctypes search is beside the exe, then `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`. Linux checkout still uses env, pkg-config, then system `.so` paths.
- **Build where you ship.** Produce Windows artifacts on Windows, macOS on macOS, Linux on Linux. Do not cross-compile the GUI stack from WSL.
- **Licenses.** Bundling FFmpeg, libprojectM, pygame/SDL, and preset packs means shipping their licenses and attribution, not only Cleave's MIT [LICENSE](../LICENSE).
- **GPU in CI.** GitHub-hosted runners cannot validate live compositing. Automate freeze and unit tests; keep a short manual GPU checklist per OS.
- **CI cost (public repo).** Standard GitHub-hosted runners are free and unlimited on a public repository, including `windows-latest`, `ubuntu-latest`, and `macos-latest`. Do not use larger runners (extra CPU, RAM, GPU, or static IPs); those are billed even on public repos. Windows and macOS minute multipliers apply only when minutes are billed (private repos). Keep freeze jobs on the standard labels.
- **Artifact storage.** Actions minutes for a freeze job are free; workflow artifact and cache storage are not unlimited. Ship the binary as a GitHub Release asset, not as a long-lived Actions artifact. Prefer attaching with `gh release upload` in the freeze job. If a workflow artifact is needed for a later job, give it a short retention and delete it once the Release upload succeeds. Do not upload intermediate freeze trees. Actions cache is a separate 10 GB per-repository allowance: cache pip/vcpkg keys, not FFmpeg zips, CUDA torch wheels, or onedir output. Do not host CUDA torch wheels as Release assets; the installer fetches pinned wheels from download.pytorch.org.
- **Preset packs.** Milkdrop presets and textures are large and separately licensed. First-run download vs a huge installer is an open product choice, not a freeze detail. Do not put preset packs in workflow artifacts.

---

## Phase 1 - Tagged source releases (Linux) (done)

Goal: a repeatable GitHub Release that a Linux/WSL user can unpack and run from, without a frozen binary.

Shipped as [`v0.1.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0) (2026-08-31). Later source tags still follow the procedure below.

What it is: unpack a tagged source archive, install the repo's requirement files, run from the tree (`python -m cleave` / `cleave.py`). Same checkout workflow as development, pinned to a tag.

What it is not: pip-installable. No AppImage, `.deb`, or Linux frozen binary (those are Phase 4). No helper install script. No installer (Phase 3.2).

### Assets

GitHub's automatic source zip and tarball on the tag. Later tags also attach the Windows onedir zip and installer from the freeze job (`cleave-<version>-windows-x64.zip`, `cleave-<version>-windows-x64-setup.exe`). [`v0.1.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0) is source-only. Requirement pins already in the repo ([requirements.txt](../requirements.txt), [requirements-dev.txt](../requirements-dev.txt), [requirements-torch-cpu.txt](../requirements-torch-cpu.txt), [requirements-torch-cu130.txt](../requirements-torch-cu130.txt)) travel with the source archive.

Milkdrop presets and textures are not in the archive. Users follow [README.md](../README.md) "Get Some Milkdrop Presets".

### Version and CLI

`cleave --version` prints `cleave X.Y.Z` from `cleave.__version__` and exits 0 (no subcommand required). An in-editor version string stays in Later.

### When to tag

Tag from `main` when a milestone lands. No calendar cadence.

### Release procedure

This is the single source of truth for cutting a Phase 1 release:

1. Move [CHANGELOG.md](../CHANGELOG.md) `[Unreleased]` notes into a new `## [X.Y.Z] - YYYY-MM-DD` section. Leave `## [Unreleased]` in place (empty until the next cycle). Update the compare links at the bottom.
2. Set `__version__` in [cleave/__init__.py](../cleave/__init__.py) to `X.Y.Z`.
3. Commit those changes to `main`.
4. `git tag vX.Y.Z && git push --tags` (tag the commit that is on `main`).
5. CI ([.github/workflows/release.yml](../.github/workflows/release.yml)): unit tests via [tests.yml](../.github/workflows/tests.yml), then `publish` checks that the tag matches `cleave.__version__`, extracts the changelog section, and creates the GitHub Release (source zip/tarball attach automatically). Then `freeze` calls [windows-freeze.yml](../.github/workflows/windows-freeze.yml) with `release_tag` set to the tag and uploads `cleave-<version>-windows-x64.zip` and `cleave-<version>-windows-x64-setup.exe` onto that Release. If freeze fails, the source Release still exists and can be retried.
6. Spot-check the archive: unpack, install requirements, run `cleave --version`, confirm presets still come from the README steps.

### Done when

Met. A Linux/WSL user can unpack a tagged source archive from GitHub, install the requirement files, and run play/render with the existing system deps (Python 3.10+, FFmpeg, libprojectM 4.2+).

---

## Phase 2 - Windows MVP (done)

Goal: a usable Windows build of play (and ideally render) that you can hand to a tester. Manual build is fine. Unsigned is fine.

This is the first freeze, so most of the porting work lands here even if CI does not. Two slices, then one zip. Do not tag a `separate`-only Windows release. Phases 1-4 are not re-ordered. Do not freeze Demucs or PyTorch in this zip. Testers separate on Linux/WSL (or use an existing project) and copy `projects/` onto Windows. Windows `separate` is Phase 3.3.

### 2.1 Shared Windows foundation (done)

Landed in the tree. Manual proof on a native Windows box (not WSL): `cleave.exe --version` prints `cleave 0.1.0`; `cleave.exe --help` lists `separate` / `play` / `render` / `backup` / `restore`. No GPU, libprojectM DLLs, FFmpeg sidecar, or torch were required for that proof. No tag and no `__version__` bump; 2.1 is not a GitHub Release.

What landed:

- Relocatable roots in [cleave/paths.py](../cleave/paths.py): `is_frozen()`, `install_dir()` (exe dir / sidecars), `resource_dir()` (`sys._MEIPASS` / bundled files). Runtime template YAML and fonts use `resource_dir()`, not `repo_root()`.
- Windows data root `Documents\Cleave\` (Known Folder, `CLEAVE_DATA` still overrides). User config `%APPDATA%\Cleave\config.yaml`. Preset/texture defaults follow `data_dir()`.
- Frozen FFmpeg lookup in [cleave/ffmpeg.py](../cleave/ffmpeg.py): beside the exe only; no PATH fallback. Checkout still uses PATH.
- ctypes: frozen or `win32` searches `install_dir()` first (`projectM-4.dll` / `projectM-4-playlist.dll`), then env vars. Linux checkout order is unchanged.
- [packaging/cleave.spec](../packaging/cleave.spec): PyInstaller onedir, pygame and soxr collected, excludes `torch` / `demucs` / `beat_this` / `librosa` / `matplotlib`. `datas`: `assets/cleave-viz.yaml` and `assets/fonts/` (including `MaterialIcons-Regular.ttf`).
- Stem-split guard in [cleave/separate.py](../cleave/separate.py) (`require_stem_split`) for a short frozen error.
- Design note: [windows-freeze.md](windows-freeze.md).

How the 2.1 freeze was built (reuse this env on the same Windows machine):

- Native clone or copy at `C:\src\cleave` (not `\\wsl$\` and not WSL Python).
- Venv with `pyinstaller`, `pygame`, `PyYAML`, `numpy` only. Do not `pip install -r requirements.txt` (that pulls torch).
- `pyinstaller packaging/cleave.spec` from the repo root. Output: `dist\cleave\cleave.exe` next to `_internal\`.
- Sidecars (ffmpeg, DLLs) are a post-build copy into `dist\cleave\`, not `_internal`. 2.1 did not copy them.

### 2.2 Play and render freeze (done)

Phase 2 milestone. Manual freeze on a native Windows box (not WSL). No tag and no `__version__` bump; 2.2 is not a GitHub Release.

What landed:

- Torch-free play/render import graph: stem types in [cleave/stems.py](../cleave/stems.py); PCM resample via soxr in [cleave/pcm_io.py](../cleave/pcm_io.py). Analyse still uses librosa in [cleave/extract.py](../cleave/extract.py). Frozen `separate` and raw-audio `play` raise `STEM_SPLIT_MISSING_FROZEN`.
- Frozen Documents lookup uses `LONG` (not `HRESULT` from `ctypes.wintypes`). Pattern-mask plasma VAOs skip stripped `in_uv` on NVIDIA.
- [packaging/cleave.spec](../packaging/cleave.spec) collects pygame and soxr. Post-build copy into `dist\cleave\` (not `_internal`): `ffmpeg.exe`, `projectM-4.dll`, `projectM-4-playlist.dll`, extra non-system DLLs, `licenses/ffmpeg/`, `licenses/libprojectM/`.
- How to freeze: [windows-freeze.md](windows-freeze.md) (vcpkg + VS 2022 shared `x64-windows`; testers do not compile libprojectM).

Manual GPU proof (met):

- Unpack the onedir zip (or run from `dist\cleave\`).
- `cleave.exe play <existing-project>` opens the editor.
- Short `cleave.exe render` writes an MP4.
- `cleave.exe separate` and raw-audio `play` print the short stem-split message, not a traceback.
- Support matrix: 64-bit Windows, GPU driver. Unsigned is fine (SmartScreen: Run anyway).

### Locked

- **Layout.** Unpack a zip (built on a Windows machine) and run from that folder. Relocatable app paths as in 2.1. Not Program Files (that is Phase 3). Installer, signing, and CI wait for Phase 3.
- **One exe, CLI subcommands.** PyInstaller onedir with `cleave.exe`. Testers run it from cmd the same way as Linux (`cleave.exe play ...`, `cleave.exe render ...`). Drag-and-drop onto the window waits for Phase 3. Not two executables.
- **User data.** `Documents\Cleave\` mirrors Linux `~/.local/share/cleave/`: `projects/`, `presets/` (including `favourites/`, `blacklist/`, `roles/`), `textures/`, and anything else that lives under the data root today. `CLEAVE_DATA` still overrides the data root.
- **User config.** Only the global settings file goes in AppData (`%APPDATA%\Cleave\config.yaml`), matching Linux `~/.config/cleave/config.yaml`.
- **FFmpeg.** Ship a Windows `ffmpeg.exe` next to `cleave.exe`. Look beside the exe first, not PATH. Clear error if it is missing. Include the FFmpeg license in the zip.
- **libprojectM.** Maintainer builds 4.2+ DLLs (core + playlist) once per release and ships them next to the exe. Windows ctypes loader searches beside the exe, then `PROJECTM_LIB`. Testers do not compile or install Visual Studio. Include libprojectM licenses. pygame/SDL travel inside the freeze.
- **No torch in the MVP zip.** The first Windows freeze does not bundle Demucs or PyTorch. Support matrix: 64-bit Windows, GPU driver, and that testers bring an existing project (separate outside the app).

### Leave open

Whether a seed preset/texture pack ships in the zip versus a documented copy into `Documents\Cleave\`. Do not ship MinGW DLLs unless ctypes names and extra runtimes are updated to match.

### Done when

Met. A tester on a typical Windows box can unzip, run `cleave.exe play` / `cleave.exe render` from cmd, load an existing project, and render a short clip.

---

## Phase 3 - Windows release + CI (3.1, 3.2, 3.3.1, and 3.3.2 done)

Goal: Windows is a first-class release target. Building it does not depend on a particular desktop.

3.1 automated the CI freeze zip; 3.2 added the Inno Setup installer, argv normalisation, and Release wiring. GPU proof from zip and Program Files is met. 3.3.1 made CPU `separate` freeze-safe and editor-first. 3.3.2 retired the lean spec: one freeze job, CPU `separate` zip and setup exe, drop-a-wav proof met. Do not mix installer branding into the CI freeze. CUDA torch is not baked into the setup exe (3.3.3 downloads it when the user opts in).

### 3.1 CI freeze zip (done)

Automate the 2.2 recipe on standard `windows-latest` (not a larger runner). The freeze spec already lives in [packaging/cleave.spec](../packaging/cleave.spec); the layout, sidecars, and ctypes names are in [windows-freeze.md](windows-freeze.md).

- Workflow: [.github/workflows/windows-freeze.yml](../.github/workflows/windows-freeze.yml) (`workflow_dispatch` and `workflow_call`, not every push) on standard `windows-latest`. PyInstaller onedir via [packaging/cleave.spec](../packaging/cleave.spec), then [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py) copies sidecars into `dist\cleave\` (not `_internal`). Zip that folder as `cleave-<version>-windows-x64.zip`. Headless smoke only (`--version`, `--help`, frozen `separate` message); no GPU compositing.
- Dispatch uploads the zip as a 5-day Actions artifact (`cleave-windows-x64`). Tag pipeline: [release.yml](../.github/workflows/release.yml) runs tests, `publish` creates the GitHub Release, then `freeze` calls this workflow with `release_tag` set to the tag. A non-empty `release_tag` uses `gh release upload` and does not retain a workflow artifact.
- Cache pip only (`actions/setup-python` with `requirements-freeze.txt`). Do not cache FFmpeg zips or freeze output. Committed libprojectM DLLs; no vcpkg in the job.
- SmartScreen documented for an unsigned build ([README.md](../README.md) Windows zip). Friendlier in-app messages for missing GPU or preset root stay a follow-up, not a 3.1 gate. Missing FFmpeg already names the expected path.
- GPU compositing is not validated in CI; manual GPU proof from the dispatch zip is met (see 3.2).

Drag-and-drop onto the pygame window can land on `main` independently of 3.1. It is not a gate. Drop onto the exe is argv normalisation (3.2.1, done). File associations stay out.

### Done when

Met. `workflow_dispatch` on `windows-latest` produced a zip that opened `cleave.exe play` on an existing project (GPU). Headless CI smoke covers `--version`, `--help`, and the frozen `separate` message. The tag job is wired to upload that zip. No version bump and no installer. The first tag after this lands is a Phase 1 source release plus the Windows zip.

### 3.2 Installer (done)

Wrap the same onedir tree into Program Files. The installer packages 3.1's staged `dist\cleave\`; it does not get a second freeze layout. Tool: Inno Setup 6 ([packaging/windows/cleave.iss](../packaging/windows/cleave.iss)). Mechanics live in [windows-freeze.md](windows-freeze.md).

#### 3.2.1 Bare-path entry and drop (done)

Without argv normalisation, `cleave.exe <path>` is an argparse error (`command` is required), so dropping a file on the exe fails ugly.

- Normalise argv in [cleave/cli.py](../cleave/cli.py) `main`: a single argument that is not a known subcommand and resolves to an existing path or project slug runs `play`. One place, unit-testable on Linux.
- Frozen raw audio still prints the short stem-split message, not a traceback or argparse usage.
- Explorer launches (double-click, drop) close the console on exit. When frozen and the process owns its console, pause on error before exiting so the message is readable.
- No arguments printed help (same pause rule). Start Menu shortcut targeted that. Frozen no-args and `cleave play` with no target now open the in-window picker ([file-picker-plan.md](file-picker-plan.md) Phase 1).
- pygame window drop (`DROPFILE`) stays optional and is not a gate.

#### 3.2.2 Local installer build (done)

- [packaging/windows/cleave.iss](../packaging/windows/cleave.iss) compiled by `iscc` against a staged `dist\cleave\`. Output `cleave-<version>-windows-x64-setup.exe` at the repo root. Version passed in from `cleave.__version__`; fixed `AppId` GUID forever so later versions upgrade in place.
- Default `{autopf}\Cleave` (per-machine, elevated), 64-bit only. Start Menu shortcut; desktop icon optional and off. Optional "add to PATH" task, off by default, so `cleave play ...` works from any terminal.
- Ships the same `licenses/` tree; the licence page shows Cleave's [LICENSE](../LICENSE).
- Uninstall removes the install dir only. It never touches `Documents\Cleave\` or `%APPDATA%\Cleave\`, and says so.
- Program Files stays read-only: install, run play and a short render as a normal user, confirm nothing is written under the install dir (met).

#### 3.2.3 CI and Release wiring (done)

- [windows-freeze.yml](../.github/workflows/windows-freeze.yml) builds the installer after the zip, reusing the same staged tree. The job installs Inno Setup on the runner (`choco install innosetup`).
- Headless installer smoke: silent install into a temp dir, run the installed `cleave.exe --version`, silent uninstall, assert the dir is gone.
- Upload the setup exe as a Release asset next to the zip, same `release_tag` rule as 3.1. Dispatch keeps the short-retention artifacts. The zip stays.
- Unsigned: document SmartScreen for the setup exe as well as the zip.

Manual GPU proof (met):

- Install from the setup exe into Program Files (read-only install dir).
- `cleave.exe play` on an existing project from the Start Menu shortcut, from a terminal, and by dropping a project folder onto `cleave.exe`.
- Audio plays on the system default output device; pattern mask compositing works at default `full-quality` preview quality. Silent-playback debugging: [windows-freeze.md](windows-freeze.md) (Audio output device).
- The 2.2 tester path still works from the dispatch zip and from Program Files.
- Uninstall removes the install dir only; `Documents\Cleave\` and `%APPDATA%\Cleave\` survive.

### Locked

- **Layout.** The Release freeze is the 2.2 onedir: `cleave.exe` and sidecars beside each other, bundled files in `_internal`. The installer copies that tree into Program Files. Do not invent a second freeze layout. `install_dir()` stays the parent of the exe.
- **User data.** Unchanged from Phase 2: `Documents\Cleave\` (projects, presets, textures). `CLEAVE_DATA` still overrides. Global settings stay in `%APPDATA%\Cleave\config.yaml`.
- **When to freeze.** Tag and `workflow_dispatch` only. Never on every push.
- **Assets.** Upload the Windows binary as a GitHub Release asset, not a long-lived Actions artifact. Source zip/tarball from Phase 1 stay.
- **One exe, CLI subcommands.** Still PyInstaller onedir with `cleave.exe`. Not two executables. For 3.1 and 3.2 the Release zip and setup exe were the 2.2 play/render freeze (no torch). 3.3.2 shipped the CPU `separate` freeze under those names.
- **Signing.** Optional. Without a certificate, document SmartScreen and keep shipping unsigned.

### Leave open

Installer branding. Whether audio file associations (a "Play with Cleave" shell verb, never a default handler) ship as an optional installer task or stay out. Authenticode if a certificate appears.

**Resolved** (exact CI steps): committed libprojectM DLLs in [packaging/windows/](../packaging/windows/); FFmpeg downloaded by [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py) from a pinned Gyan essentials URL (`FFMPEG_URL` / `FFMPEG_SHA256` in that script). Not vcpkg in the job, not a committed FFmpeg binary.

### Done when

Met for 3.1 and 3.2. A tag produces the zip and installer without a manual freeze. Testers can run play from the zip or Program Files. GPU proof from zip and setup exe is met.

### 3.3 Windows stem split / `separate` (3.3.1 and 3.3.2 done; 3.3.3 in v0.2.0, NVIDIA proof outstanding)

Goal: a Windows user can drop a wav onto the editor (or pass it as the play target) and get a Cleave project (stems plus `signals.json`) without Linux or a terminal. Stem split is the product: the default Windows zip and setup exe include CPU `separate`. Do not ship a play/render-only Windows Release.

`separate` is Demucs plus analyse (librosa envelopes and Beat This). Play and render on an existing project do not import that stack. CPU torch ([requirements-torch-cpu.txt](../requirements-torch-cpu.txt)) is the Windows `separate` that runs everywhere. CUDA ([requirements-torch-cu130.txt](../requirements-torch-cu130.txt)) is an optional download for faster Demucs, not a second product. Play/render GPU is OpenGL; it is unrelated to CUDA torch.

What it is: one Windows product (CPU `separate` plus play/render) with stem split and first-run weight download inside the editor window. Testers no longer need a Linux-separated project.

What it is not: CUDA torch baked into the setup exe. A Cleave-hosted CUDA payload. A second Cleave installer or zip flavour. Weights in Program Files. A second freeze layout or a second exe. A play/render-only Release zip or setup exe. Linux/macOS binaries (Phase 4). A CLI-only split that finishes before the window opens.

Three slices. 3.3.1 is engineering (done); 3.3.2 is the default Windows zip and setup exe (done); 3.3.3 is the optional CUDA installer download (in `v0.2.0`; NVIDIA-box proof still outstanding).

#### 3.3.1 Frozen separate stack (CPU) (done)

Engineering foundation. Not a tester ship gate (that is 3.3.2). No tag and no `__version__` bump.

What landed:

- In-process Demucs (`demucs.pretrained.get_model` + `apply_model`) in [cleave/separate.py](../cleave/separate.py). Frozen mix load uses sidecar `ffmpeg.exe`; stem wavs are written with soundfile. Beat This uses `Audio2Beats` on librosa-loaded audio. Collect details: [windows-freeze.md](windows-freeze.md).
- Weights in user data (`model_cache_dir()` under `Documents\Cleave\models` on Windows). `torch.hub.set_dir` before Demucs and Beat This load. First-run download; not baked into the freeze.
- Editor window first on raw audio ([cleave/viz/loading.py](../cleave/viz/loading.py) `open_loading_window` / `LoadingWindow`; [cleave/viz/__init__.py](../cleave/viz/__init__.py) `continue_launch`). Named status plus a bar when fraction is known. `cleave separate` stays headless (stderr).
- First-run fetch names Demucs `htdemucs` / `htdemucs_ft` and Beat This `final0`, with a size hint and a bar when hub reports bytes. Cached hits stay quiet. Offline: in-window or stderr error that a network is required the first time ([cleave/model_weights.py](../cleave/model_weights.py)).
- Lean freeze still excluded `torch` / `demucs` / `beat_this` / `librosa` / `matplotlib`. `STEM_SPLIT_MISSING_FROZEN` was that artifact's message.
- What 3.3.1 shipped: dedicated spec `packaging/cleave-separate.spec` (one `cleave.exe`, CUDA binaries filtered). `freeze-separate` in [windows-freeze.yml](../.github/workflows/windows-freeze.yml) smoked `cleave.exe separate` on [tests/fixtures/smoke-separate.wav](../tests/fixtures/smoke-separate.wav). Dispatch inputs `include_freeze` and `include_separate` were independent (both default true on dispatch; tag `workflow_call` left separate off). No `gh release upload` for the separate zip.

Manual proof (met): dispatch `cleave-windows-x64-separate` zip on a native Windows box. `cleave.exe play <wav>` opens the window, downloads weights into `Documents\Cleave\models`, splits, analyses, then opens the editor. `cleave.exe separate` from cmd writes stems and `signals.json`. Lean zip still printed `STEM_SPLIT_MISSING_FROZEN`.

#### Done when

Met. Frozen CPU `separate` runs on Windows without Linux. One exe. Weights stay in user data. Play/render freeze stays torch-free. The separate freeze is not a GitHub Release asset yet.

#### 3.3.2 Ship CPU separate as the default Windows product (done)

Product and CI. One Windows Release, not a play/render zip plus a `separate` extra. No tag and no `__version__` bump.

What landed:

- The CPU-separate onedir is `cleave-<version>-windows-x64.zip` and `cleave-<version>-windows-x64-setup.exe`. Inno wraps that tree into Program Files. One `cleave.exe`, CLI subcommands unchanged. `install_dir()` stays the parent of the exe. Not a second exe (`cleave-separate.exe`). Not a `-separate` suffix on the Release assets.
- Lean spec retired. [packaging/cleave.spec](../packaging/cleave.spec) is the CPU-torch freeze (CUDA binaries filtered, matplotlib excluded).
- CI: one `freeze` job on standard `windows-latest` in [windows-freeze.yml](../.github/workflows/windows-freeze.yml): [requirements-freeze.txt](../requirements-freeze.txt), then [requirements-torch-cpu.txt](../requirements-torch-cpu.txt), analyse pins, PyInstaller, sidecars, `--version` / `--help`, then `cleave.exe separate` on [tests/fixtures/smoke-separate.wav](../tests/fixtures/smoke-separate.wav). Zip, Inno setup, installer smoke. Tag `workflow_call` waits on CPU Demucs and uses `gh release upload`. Dispatch: 5-day artifacts. Do not cache torch wheels as long-lived artifacts.
- [README.md](../README.md) Windows zip: drop a wav (or `cleave.exe play <wav>`), first-run weights in `Documents\Cleave\models`, named progress in the loading window. CPU `separate` is slow; optional CUDA download in the installer is 3.3.3.

Manual proof (met): dispatch zip and Program Files install on a typical Windows box (no NVIDIA, no terminal). Drop a short wav onto `cleave.exe`; named download / split progress in the loading window; project opens. Warm-cache second run skips download chatter. `cleave.exe separate` from cmd writes stems and `signals.json`. Uninstall removes the install dir only.

#### Done when

Met. CPU `separate` is the default Windows zip and setup exe. Drop-a-wav from zip and Program Files works. Lean spec retired.

#### 3.3.3 CUDA extra (optional) (in v0.2.0; NVIDIA proof outstanding)

NVIDIA users. Does not block 3.3.2. Wizard, download, verify, and unpack are in [packaging/windows/cleave.iss](../packaging/windows/cleave.iss) and ship in the `v0.2.0` installer. Manual NVIDIA-box proof is still outstanding; this phase is not marked Done.

One setup exe on the Releases page. The CPU onedir is always installed. CUDA torch is not baked into that exe. Cleave does not build or host a CUDA payload.

When the wizard detects an NVIDIA GPU, it asks Yes/No (default No) with this copy. The size is a hardcoded estimate (2 GB), not a live network sum:

NVIDIA graphics card detected - do you wish to download the CUDA toolkit for faster stem splitting? (2 GB)

Do not show that question when NVIDIA is not detected. Silent and very silent installs skip the page. The extra is the PyTorch CUDA wheels in [requirements-torch-cu130.txt](../requirements-torch-cu130.txt) (cu130, `cp310` `win_amd64` to match the freeze Python). Fetch them from `https://download.pytorch.org/whl/cu130/`. That is not NVIDIA's developer CUDA Toolkit from nvidia.com. Do not download that Toolkit. Do not pip-install into the freeze (no pip in the onedir). Wheels are zip files: download, verify SHA-256, unpack into `{app}\_internal` (replace CPU `torch` / `torchaudio` / `torchcodec`, not overlay DLLs). Document driver expectations with the cu130 pin (Windows driver 580.88 or newer).

Yes, or silent `/CUDA=1`: the installer fetches those pinned wheels after the CPU tree is copied. Uninstall removes them with `{app}`. Same `cleave.exe`; `install_dir()` stays the parent of the exe. `/CUDA=1` still downloads when no NVIDIA GPU is detected (explicit request). The GUI prompt stays NVIDIA-only.

No, download failure, or no opt-in: finish the install. Stem split stays on CPU (slower, not a missing-split error). Do not fail the whole install.

Runtime: prefer CUDA torch when that tree is present and usable; otherwise use the bundled CPU torch.

Not a second setup exe, not a second Cleave zip, not a Cleave-hosted CUDA asset, not a manual unzip into an overlay folder. The portable zip stays CPU-only. Adding CUDA later means running the installer again (in-window fetch is Later).

CI does not build or upload a CUDA payload. Silent and CI installer smoke (`/VERYSILENT /TASKS=`) do not download the wheels. `/CUDA=1` is the silent opt-in.

Pin exact wheel filenames and SHA-256 in the installer (same pattern as FFmpeg). Do not scrape the PyTorch index at install time. Exact URLs, checksums, the 2 GB label, WMI detect, unpack layout, and `/CUDA=1` are in [windows-freeze.md](windows-freeze.md) and [packaging/windows/cleave.iss](../packaging/windows/cleave.iss).

#### Locked

- **One Windows product.** After 3.3.2 the default zip and setup exe include CPU `separate` plus play/render. Do not ship a play/render-only GitHub Release. One setup exe; CUDA torch is not baked in (3.3.3 downloads it when NVIDIA is detected and the user says yes).
- **CPU `separate` is the Windows split.** Works without NVIDIA. CUDA is 3.3.3 only, and only if the installer download succeeded.
- **One exe.** Still `cleave.exe`. Not `cleave-separate.exe`. CLI subcommands stay for scripts and CI; they are not the Windows default UX.
- **Editor-first split.** Drop or `play` on a wav opens the window first. Stem split, analyse, and first-run weight download report on the loading screen (name plus bar). Failures stay in the window. Explorer / Start Menu / drop must not depend on a console for that.
- **Layout.** `install_dir()` stays the parent of the exe. The 3.3.2 freeze is a full onedir, not an overlay onto a lean tree.
- **Weights in user data.** `Documents\Cleave\` (or `CLEAVE_DATA`). First-run download; fail clearly offline. Never Program Files.
- **Download feedback.** First fetch of each model names it and shows progress in the editor; stderr when a console is attached. Cached hits stay quiet.
- **Lean freeze is retired.** [packaging/cleave.spec](../packaging/cleave.spec) is the CPU `separate` freeze. `STEM_SPLIT_MISSING_FROZEN` is a runtime guard if frozen torch is missing, not a product smoke testers see on a Release build.
- **CI.** Standard `windows-latest`. CPU freeze job as in 3.3.2. No CUDA payload build and no CUDA Release asset. Do not cache torch wheels as long-lived artifacts. Headless smoke keeps `cleave.exe separate` on the fixture wav and does not download CUDA wheels.
- **Installer CUDA prompt.** Show it only when an NVIDIA GPU is detected. Locked copy above. Fetch pinned cu130 wheels from download.pytorch.org; skip or fail leaves CPU `separate`. Files land under `{app}` so uninstall removes them. Do not host those wheels on GitHub.

#### Leave open

Windowed PE (`console=False` plus attach-to-parent for terminals) can land with 3.3 or beside it; it must not block treating the editor as the split UI. NVIDIA detect (WMI `Win32_VideoController`), pinned wheel URLs / SHA-256, and unpack into `{app}\_internal` live in [windows-freeze.md](windows-freeze.md). Manual NVIDIA-box proof of the CUDA extra is still open.

**Resolved:** one-exe freeze is possible (`cleave.exe` from [packaging/cleave.spec](../packaging/cleave.spec)); do not add `cleave-separate.exe`. One Windows Release product (CPU `separate` is not a second zip or setup exe). The lean spec is retired. CUDA delivery is an optional download of pinned PyTorch cu130 wheels from download.pytorch.org in that one installer, not two flavours, not a Cleave-hosted payload, and not a user-facing overlay zip.

#### Done when

Met. A tester on 64-bit Windows, with no Linux, no NVIDIA requirement, and no terminal, can drop a short wav onto the shipped zip or Program Files install, see named first-run weight download and split progress in the window, then play that project. A later run with cache warm skips the download chatter. `cleave.exe separate` still works from cmd for scripts and CI. The GitHub Release attaches that zip and setup exe only (no play/render-only extra). Optional CUDA download in the installer is 3.3.3 and does not block that.

---

## Phase 4 - Linux and macOS binaries

After Phase 3.3. Phase 1, Phase 2, 3.1, 3.2, 3.3.1, and 3.3.2 are done on `main`. `v0.2.0` attaches the CPU-`separate` Windows zip and setup exe (plus source). Phase 3.3.3 is the optional CUDA installer download in that installer; NVIDIA-box proof is still outstanding. Phase 4 adds Linux and macOS binaries. Windows `separate` is 3.3, not this phase.

Goal: the same product as Windows (CPU `separate` plus play/render), as native artifacts. Source+requirements Linux remains available from Phase 1.

Sketch:

- **Linux:** AppImage (closest to a single executable) and/or a `.deb` for Ubuntu. Build on the oldest Ubuntu you intend to support so glibc does not strand users. Keep the existing checkout workflow for development.
- **macOS:** `.app` in a `.dmg`. Apple Silicon at minimum; Intel as a second build if needed. OpenGL is deprecated but still the current stack. Notarization and codesign are required for anyone who did not compile it themselves.
- Per-OS data dirs and libprojectM (`.so` / `.dylib`) using the relocatable work from Phase 2, not a third path scheme.
- CI matrix next to the Windows job: Linux and macOS freeze on tag, on standard `ubuntu-latest` / `macos-latest` (not larger runners). Same limits: no GPU compositing on hosted runners; Release assets, not long-lived workflow artifacts.
- FFmpeg: bundled sidecar vs distro package on Linux is a product choice; macOS should bundle or fail clearly, like Windows.

Leave open: AppImage vs `.deb` vs both, universal2 vs separate Mac archs, Homebrew cask later, and whether Linux binaries replace or sit beside the Phase 1 source Release.

Done when: a tag attaches Linux, Windows, and macOS artifacts (plus source) and each OS has a one-page install note.

---

## Later (not a phase yet)

Do not block Phases 1-4 on these. Revisit after binaries exist. CUDA `separate` lives in Phase 3.3.3 (installer download), not here. In-window CUDA fetch for people who skipped the installer prompt, or who get an NVIDIA GPU later, can land after 3.3.3.

- Nuitka freeze for possible startup and runtime gains (Phase 2 ships PyInstaller). See [roadmap.md](roadmap.md).
- In-window CUDA fetch for people who skipped the installer prompt, or who get an NVIDIA GPU later (same pinned PyTorch wheels as 3.3.3).
- In-app version string and a "check GitHub for updates" hint (full auto-update is a different project).
- Hosted preset/texture packs with a first-run downloader.
- Apple Developer and Windows code-signing accounts, if Phase 3/4 shipped unsigned.
- Crash/log upload, delta updates, Microsoft Store / Mac App Store.

---

## Suggested order of analysis

Phase 1, Phase 2, Phase 3.1-3.2, 3.3.1, and 3.3.2 are done. `v0.2.0` attaches the Windows zip and setup exe. Next: Phase 3.3.3 NVIDIA-box proof of the optional CUDA installer download, then Phase 4 (Linux and macOS binaries). Keep freeze implementation choices in [windows-freeze.md](windows-freeze.md), not in this overview.
