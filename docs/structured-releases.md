# Structured releases

Move Cleave from checkout-based development to versioned GitHub Releases.

Phase 1 is done (`v0.1.0`). Phase 2 is done (Windows play/render onedir zip, manual freeze). Phase 3 is done (3.1 CI freeze zip, 3.2 installer and argv normalisation, GPU proof from zip and Program Files). No tag and no `__version__` bump for Phases 2-3 beyond the existing `v0.1.0` source release. The next milestone tag ships Phase 1 source plus the Windows zip and setup exe. Phase 4 (Linux and macOS binaries) is next.

Related: [README.md](../README.md) (current Linux/WSL setup), [completed/user-data-and-config-plan.md](completed/user-data-and-config-plan.md) (install vs user data), [cleave/paths.py](../cleave/paths.py), [cleave/projectm.py](../cleave/projectm.py), [windows-freeze.md](windows-freeze.md) (paths, spec, FFmpeg sidecar, ctypes names, libprojectM build recommendation).

---

## Across all phases

Decide these once, then reuse. Refine per phase rather than reinventing them.

- **Versioning.** Semver. While pre-1.0, versions are `0.x` (`0.1.0`, `0.2.0`, ...); breaking changes are allowed on minor bumps until 1.0. Single source of truth: `cleave.__version__` in [cleave/__init__.py](../cleave/__init__.py). Tags are `vX.Y.Z` and must match that string. [pyproject.toml](../pyproject.toml) reads the same attr (`[tool.setuptools.dynamic]`); this is metadata only, not a pip install.
- **Changelog.** [CHANGELOG.md](../CHANGELOG.md) in Keep a Changelog format (`## [Unreleased]`, then `## [X.Y.Z] - YYYY-MM-DD` with Added / Changed / Fixed / Removed as appropriate). Each GitHub Release body is that version's section, extracted by [scripts/changelog_section.py](../scripts/changelog_section.py).
- **User data vs install.** Frozen or zip installs must not write projects, presets, or configs into the app folder. Linux data stays XDG (`~/.local/share/cleave/`, config in `~/.config/cleave/`). Windows data mirrors that tree under `Documents\cleave\`; only the global settings file lives in `%APPDATA%\cleave\`. macOS Application Support is Phase 4. See the user-data plan.
- **Editor vs `separate`.** Play and offline render need pygame, OpenGL, libprojectM, and FFmpeg. Stem split needs Demucs and PyTorch (and optionally CUDA). The first Windows freeze does not bundle torch. GPU torch stays a later extra.
- **Native deps.** libprojectM 4.2+ (core + playlist) and FFmpeg are not Python packages. Every binary OS needs a build or sidecar story. Frozen/Windows ctypes search is beside the exe, then `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`. Linux checkout still uses env, pkg-config, then system `.so` paths.
- **Build where you ship.** Produce Windows artifacts on Windows, macOS on macOS, Linux on Linux. Do not cross-compile the GUI stack from WSL.
- **Licenses.** Bundling FFmpeg, libprojectM, pygame/SDL, and preset packs means shipping their licenses and attribution, not only Cleave's MIT [LICENSE](../LICENSE).
- **GPU in CI.** GitHub-hosted runners cannot validate live compositing. Automate freeze and unit tests; keep a short manual GPU checklist per OS.
- **CI cost (public repo).** Standard GitHub-hosted runners are free and unlimited on a public repository, including `windows-latest`, `ubuntu-latest`, and `macos-latest`. Do not use larger runners (extra CPU, RAM, GPU, or static IPs); those are billed even on public repos. Windows and macOS minute multipliers apply only when minutes are billed (private repos). Keep freeze jobs on the standard labels.
- **Artifact storage.** Actions minutes for a freeze job are free; workflow artifact and cache storage are not unlimited. Ship the binary as a GitHub Release asset, not as a long-lived Actions artifact. Prefer attaching with `gh release upload` in the freeze job. If a workflow artifact is needed for a later job, give it a short retention and delete it once the Release upload succeeds. Do not upload intermediate freeze trees. Actions cache is a separate 10 GB per-repository allowance: cache pip/vcpkg keys, not FFmpeg zips or onedir output.
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

This is the first freeze, so most of the porting work lands here even if CI does not. Two slices, then one zip. Do not tag a `separate`-only Windows release. Phases 1-4 are not re-ordered. Do not freeze Demucs or PyTorch. Testers separate on Linux/WSL (or use an existing project) and copy `projects/` onto Windows. `separate` (CPU torch in-box vs "install torch yourself" vs skip) stays a later product choice, not a 2.2 gate. CUDA `separate` stays in Later.

### 2.1 Shared Windows foundation (done)

Landed in the tree. Manual proof on a native Windows box (not WSL): `cleave.exe --version` prints `cleave 0.1.0`; `cleave.exe --help` lists `separate` / `play` / `render` / `backup` / `restore`. No GPU, libprojectM DLLs, FFmpeg sidecar, or torch were required for that proof. No tag and no `__version__` bump; 2.1 is not a GitHub Release.

What landed:

- Relocatable roots in [cleave/paths.py](../cleave/paths.py): `is_frozen()`, `install_dir()` (exe dir / sidecars), `resource_dir()` (`sys._MEIPASS` / bundled files). Runtime template YAML and fonts use `resource_dir()`, not `repo_root()`.
- Windows data root `Documents\cleave\` (Known Folder, `CLEAVE_DATA` still overrides). User config `%APPDATA%\cleave\config.yaml`. Preset/texture defaults follow `data_dir()`.
- Frozen FFmpeg lookup in [cleave/ffmpeg.py](../cleave/ffmpeg.py): beside the exe only; no PATH fallback. Checkout still uses PATH.
- ctypes: frozen or `win32` searches `install_dir()` first (`projectM-4.dll` / `projectM-4-playlist.dll`), then env vars. Linux checkout order is unchanged.
- [packaging/cleave.spec](../packaging/cleave.spec): PyInstaller onedir, pygame and soxr collected, excludes `torch` / `demucs` / `beat_this` / `librosa` / `matplotlib`. `datas`: `cleave-viz.yaml` and `assets/fonts/` (including `MaterialIcons-Regular.ttf`).
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
- Support matrix: 64-bit Windows, GPU driver. Unsigned is fine (SmartScreen: Run anyway). Overlay tofu (system monospace vs bundled Material Icons) is a follow-up in [todos.md](todos.md), not a 2.2 gate.

### Locked

- **Layout.** Unpack a zip (built on a Windows machine) and run from that folder. Relocatable app paths as in 2.1. Not Program Files (that is Phase 3). Installer, signing, and CI wait for Phase 3.
- **One exe, CLI subcommands.** PyInstaller onedir with `cleave.exe`. Testers run it from cmd the same way as Linux (`cleave.exe play ...`, `cleave.exe render ...`). Drag-and-drop onto the window waits for Phase 3. Not two executables.
- **User data.** `Documents\cleave\` mirrors Linux `~/.local/share/cleave/`: `projects/`, `presets/` (including `favourites/`, `blacklist/`, `roles/`), `textures/`, and anything else that lives under the data root today. `CLEAVE_DATA` still overrides the data root.
- **User config.** Only the global settings file goes in AppData (`%APPDATA%\cleave\config.yaml`), matching Linux `~/.config/cleave/config.yaml`.
- **FFmpeg.** Ship a Windows `ffmpeg.exe` next to `cleave.exe`. Look beside the exe first, not PATH. Clear error if it is missing. Include the FFmpeg license in the zip.
- **libprojectM.** Maintainer builds 4.2+ DLLs (core + playlist) once per release and ships them next to the exe. Windows ctypes loader searches beside the exe, then `PROJECTM_LIB`. Testers do not compile or install Visual Studio. Include libprojectM licenses. pygame/SDL travel inside the freeze.
- **No torch in the MVP zip.** The first Windows freeze does not bundle Demucs or PyTorch. Support matrix: 64-bit Windows, GPU driver, and that testers bring an existing project (separate outside the app).

### Leave open

Whether a seed preset/texture pack ships in the zip versus a documented copy into `Documents\cleave\`. Overlay Latin/box-drawing TTF (see [todos.md](todos.md)). Do not ship MinGW DLLs unless ctypes names and extra runtimes are updated to match.

### Done when

Met. A tester on a typical Windows box can unzip, run `cleave.exe play` / `cleave.exe render` from cmd, load an existing project, and render a short clip.

---

## Phase 3 - Windows release + CI (done)

Goal: Windows is a first-class release target. Building it does not depend on a particular desktop.

Two slices, same pattern as Phase 2. 3.1 automated the CI freeze zip; 3.2 added the Inno Setup installer, argv normalisation, and Release wiring. GPU proof from zip and Program Files is met. Do not mix installer branding into the CI freeze.

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
- No arguments prints help (same pause rule). Start Menu shortcut targets that.
- pygame window drop (`DROPFILE`) stays optional and is not a gate.

#### 3.2.2 Local installer build (done)

- [packaging/windows/cleave.iss](../packaging/windows/cleave.iss) compiled by `iscc` against a staged `dist\cleave\`. Output `cleave-<version>-windows-x64-setup.exe` at the repo root. Version passed in from `cleave.__version__`; fixed `AppId` GUID forever so later versions upgrade in place.
- Default `{autopf}\Cleave` (per-machine, elevated), 64-bit only. Start Menu shortcut; desktop icon optional and off. Optional "add to PATH" task, off by default, so `cleave play ...` works from any terminal.
- Ships the same `licenses/` tree; the licence page shows Cleave's [LICENSE](../LICENSE).
- Uninstall removes the install dir only. It never touches `Documents\cleave\` or `%APPDATA%\cleave\`, and says so.
- Program Files stays read-only: install, run play and a short render as a normal user, confirm nothing is written under the install dir (met).

#### 3.2.3 CI and Release wiring (done)

- [windows-freeze.yml](../.github/workflows/windows-freeze.yml) builds the installer after the zip, reusing the same staged tree. The job installs Inno Setup on the runner (`choco install innosetup`).
- Headless installer smoke: silent install into a temp dir, run the installed `cleave.exe --version`, silent uninstall, assert the dir is gone.
- Upload the setup exe as a Release asset next to the zip, same `release_tag` rule as 3.1. Dispatch keeps the short-retention artifacts. The zip stays.
- Unsigned: document SmartScreen for the setup exe as well as the zip.

Manual GPU proof (met):

- Install from the setup exe into Program Files (read-only install dir).
- `cleave.exe play` on an existing project from the Start Menu shortcut, from a terminal, and by dropping a project folder onto `cleave.exe`.
- Audio plays on the system default output device; pattern mask compositing works at default `balanced` preview quality. Silent-playback debugging: [windows-freeze.md](windows-freeze.md) (Audio output device).
- The 2.2 tester path still works from the dispatch zip and from Program Files.
- Uninstall removes the install dir only; `Documents\cleave\` and `%APPDATA%\cleave\` survive.

### Locked

- **Layout.** The Release freeze is the 2.2 onedir: `cleave.exe` and sidecars beside each other, bundled files in `_internal`. The installer copies that tree into Program Files. Do not invent a second freeze layout. `install_dir()` stays the parent of the exe.
- **User data.** Unchanged from Phase 2: `Documents\cleave\` (projects, presets, textures). `CLEAVE_DATA` still overrides. Global settings stay in `%APPDATA%\cleave\config.yaml`.
- **When to freeze.** Tag and `workflow_dispatch` only. Never on every push.
- **Assets.** Upload the Windows binary as a GitHub Release asset, not a long-lived Actions artifact. Source zip/tarball from Phase 1 stay.
- **One exe, CLI subcommands.** Still PyInstaller onedir with `cleave.exe`. Not two executables. Not torch.
- **Signing.** Optional. Without a certificate, document SmartScreen and keep shipping unsigned.

### Leave open

Installer branding. Whether audio file associations (a "Play with Cleave" shell verb, never a default handler) ship as an optional installer task or stay out. Whether CUDA `separate` is ever in the Windows artifact (stays Later). Authenticode if a certificate appears.

**Resolved** (exact CI steps): committed libprojectM DLLs in [packaging/windows/](../packaging/windows/); FFmpeg downloaded by [scripts/windows_stage_freeze.py](../scripts/windows_stage_freeze.py) from a pinned Gyan essentials URL (`FFMPEG_URL` / `FFMPEG_SHA256` in that script). Not vcpkg in the job, not a committed FFmpeg binary.

### Done when

Met. A tag produces the zip and installer without a manual freeze. Testers can run play from the zip or Program Files. GPU proof from zip and setup exe is met.

---

## Phase 4 - Linux and macOS binaries

Next work. Phase 1-3 are done on `main`; the next tag still attaches Windows assets per Phase 3 while Phase 4 adds Linux and macOS binaries.

Goal: the same play/render product as Windows, as native artifacts. Source+requirements Linux remains available from Phase 1.

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

Do not block Phases 1-4 on these. Revisit after binaries exist.

- CUDA/GPU `separate` as an optional extra or second download.
- Nuitka freeze for possible startup and runtime gains (Phase 2 ships PyInstaller). See [roadmap.md](roadmap.md).
- In-app version string and a "check GitHub for updates" hint (full auto-update is a different project).
- Hosted preset/texture packs with a first-run downloader.
- Apple Developer and Windows code-signing accounts, if Phase 3/4 shipped unsigned.
- Crash/log upload, delta updates, Microsoft Store / Mac App Store.

---

## Suggested order of analysis

Phase 1, Phase 2, and Phase 3 are done. Next: Phase 4 (Linux and macOS binaries). Keep freeze implementation choices in [windows-freeze.md](windows-freeze.md), not in this overview.
