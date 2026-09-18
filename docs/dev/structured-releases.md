# Structured releases

Versioned GitHub Releases for Cleave. Freeze mechanics: [windows-freeze.md](windows-freeze.md). Finished phase write-ups: [plans-completed/structured-releases-phases-1-3.3.2.md](plans-completed/structured-releases-phases-1-3.3.2.md).

Related: [README.md](../../README.md), [plans-completed/user-data-and-config-plan.md](plans-completed/user-data-and-config-plan.md), [cleave/paths.py](../../cleave/paths.py), [cleave/projectm.py](../../cleave/projectm.py).

---

## Current product

[`v0.2.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.2.0) attaches the Windows zip and setup exe (CPU `separate` plus play/render), plus source. [`v0.1.0`](https://github.com/SpoddyCoder/cleave/releases/tag/v0.1.0) is source-only.

The Windows product is one `cleave.exe`: CPU stem split in the zip and installer, drop-a-wav into the editor, first-run weights in `Documents\Cleave\models`. The installer can download optional CUDA wheels (Phase 3.3.3); manual NVIDIA-box proof is still outstanding. Linux/macOS binaries are Phase 4. Linux/WSL checkout remains the source path in [README.md](../../README.md).

---

## Remaining work

1. **Phase 3.3.3 NVIDIA-box proof** of the optional CUDA installer download. Wizard, download, verify, and unpack already ship in the `v0.2.0` installer ([packaging/windows/cleave.iss](../../packaging/windows/cleave.iss)). This phase is not marked Done until that proof. Mechanics: [windows-freeze.md](windows-freeze.md) (CUDA extra).
2. **Phase 4** Linux and macOS binaries (same product as Windows: CPU `separate` plus play/render).
3. **Later** (do not block 3.3.3 or Phase 4): Nuitka freeze ([roadmap.md](roadmap.md)); in-window CUDA fetch after a skipped installer prompt; in-app version string; hosted preset/texture packs; code signing; crash/log upload, delta updates, stores.

Windowed PE (`console=False` plus attach-to-parent for terminals) can land with 3.3 or beside it; it must not block treating the editor as the split UI.

### Phase 3.3.3 (CUDA extra)

One setup exe. The CPU onedir is always installed. CUDA torch is not baked in. Cleave does not build or host a CUDA payload. The portable zip stays CPU-only.

When the wizard detects an NVIDIA GPU, it asks Yes/No (default No) with this copy. The size is a hardcoded estimate (2 GB), not a live network sum:

NVIDIA graphics card detected - do you wish to download the CUDA toolkit for faster stem splitting? (2 GB)

Do not show that question when NVIDIA is not detected. Silent and very silent installs skip the page. Yes, or silent `/CUDA=1`, fetches pinned PyTorch cu130 wheels from download.pytorch.org into `{app}\_internal`. No, download failure, or no opt-in: finish the install; stem split stays on CPU. CI does not download the wheels. Driver 580.88 or newer.

### Phase 4 - Linux and macOS binaries

After 3.3. Source+requirements Linux remains available.

Sketch:

- **Linux:** AppImage and/or a `.deb` for Ubuntu. Build on the oldest Ubuntu you intend to support so glibc does not strand users. Keep the existing checkout workflow for development.
- **macOS:** `.app` in a `.dmg`. Apple Silicon at minimum; Intel as a second build if needed. OpenGL is deprecated but still the current stack. Notarization and codesign are required for anyone who did not compile it themselves.
- Per-OS data dirs and libprojectM (`.so` / `.dylib`) using the relocatable Windows work, not a third path scheme.
- CI matrix next to the Windows job: Linux and macOS freeze on tag, on standard `ubuntu-latest` / `macos-latest` (not larger runners). No GPU compositing on hosted runners; Release assets, not long-lived workflow artifacts.
- FFmpeg: bundled sidecar vs distro package on Linux is a product choice; macOS should bundle or fail clearly, like Windows.

Leave open: AppImage vs `.deb` vs both, universal2 vs separate Mac archs, Homebrew cask later, and whether Linux binaries replace or sit beside the source Release.

Done when: a tag attaches Linux, Windows, and macOS artifacts (plus source) and each OS has a one-page install note.

---

## Across all phases

Decide these once, then reuse.

- **Versioning.** Semver. While pre-1.0, versions are `0.x` (`0.1.0`, `0.2.0`, ...); breaking changes are allowed on minor bumps until 1.0. Single source of truth: `cleave.__version__` in [cleave/__init__.py](../../cleave/__init__.py). Tags are `vX.Y.Z` and must match that string. [pyproject.toml](../../pyproject.toml) reads the same attr (`[tool.setuptools.dynamic]`); this is metadata only, not a pip install.
- **Changelog.** [CHANGELOG.md](../../CHANGELOG.md) in Keep a Changelog format (`## [Unreleased]`, then `## [X.Y.Z] - YYYY-MM-DD` with Added / Changed / Fixed / Removed as appropriate). Each GitHub Release body is that version's section, extracted by [scripts/changelog_section.py](../../scripts/changelog_section.py).
- **User data vs install.** Frozen or zip installs must not write projects, presets, or configs into the app folder. Linux data stays XDG (`~/.local/share/cleave/`, config in `~/.config/cleave/`). Windows data mirrors that tree under `Documents\Cleave\`; only the global settings file lives in `%APPDATA%\Cleave\`. macOS Application Support is Phase 4. See the user-data plan.
- **Editor first.** The frozen Windows editor is the majority product (Start Menu, desktop, drop a file). CLI stays for Linux checkout, scripts, and CI. New user-facing work needs an in-window path; stderr is optional. Stance: [.cursor/rules/editor-first.mdc](../../.cursor/rules/editor-first.mdc).
- **Editor vs `separate`.** Play and offline render need pygame, OpenGL, libprojectM, and FFmpeg. Stem split needs Demucs and PyTorch (CPU or CUDA; CUDA is optional, for faster Demucs). Play/render GPU is OpenGL, unrelated to CUDA torch. CPU `separate` is in the zip and setup exe; Cleave does not ship without stem split. 3.3.3 adds an optional CUDA download in that same installer when an NVIDIA GPU is detected. Drop-a-wav into the editor is the ship path; `cleave.exe separate` is the headless/CI path.
- **Native deps.** libprojectM 4.2+ (core + playlist) and FFmpeg are not Python packages. Every binary OS needs a build or sidecar story. Frozen/Windows ctypes search is beside the exe, then `PROJECTM_LIB` / `PROJECTM_PLAYLIST_LIB`. Linux checkout still uses env, pkg-config, then system `.so` paths.
- **Build where you ship.** Produce Windows artifacts on Windows, macOS on macOS, Linux on Linux. Do not cross-compile the GUI stack from WSL.
- **Licenses.** Bundling FFmpeg, libprojectM, pygame/SDL, and preset packs means shipping their licenses and attribution, not only Cleave's [LICENSE](../../LICENSE).
- **GPU in CI.** GitHub-hosted runners cannot validate live compositing. Automate freeze and unit tests; keep a short manual GPU checklist per OS.
- **CI cost (public repo).** Standard GitHub-hosted runners are free and unlimited on a public repository, including `windows-latest`, `ubuntu-latest`, and `macos-latest`. Do not use larger runners (extra CPU, RAM, GPU, or static IPs); those are billed even on public repos. Windows and macOS minute multipliers apply only when minutes are billed (private repos). Keep freeze jobs on the standard labels.
- **Artifact storage.** Actions minutes for a freeze job are free; workflow artifact and cache storage are not unlimited. Ship the binary as a GitHub Release asset, not as a long-lived Actions artifact. Prefer attaching with `gh release upload` in the freeze job. If a workflow artifact is needed for a later job, give it a short retention and delete it once the Release upload succeeds. Do not upload intermediate freeze trees. Actions cache is a separate 10 GB per-repository allowance: cache pip/vcpkg keys, not FFmpeg zips, CUDA torch wheels, or onedir output. Do not host CUDA torch wheels as Release assets; the installer fetches pinned wheels from download.pytorch.org.
- **Preset packs.** Milkdrop presets and textures are large and separately licensed. First-run download vs a huge installer is an open product choice, not a freeze detail. Do not put preset packs in workflow artifacts.

---

## Release procedure

1. Move [CHANGELOG.md](../../CHANGELOG.md) `[Unreleased]` notes into a new `## [X.Y.Z] - YYYY-MM-DD` section. Leave `## [Unreleased]` in place (empty until the next cycle). Update the compare links at the bottom.
2. Set `__version__` in [cleave/__init__.py](../../cleave/__init__.py) to `X.Y.Z`.
3. Commit those changes to `main`.
4. `git tag vX.Y.Z && git push --tags` (tag the commit that is on `main`).
5. CI ([.github/workflows/release.yml](../../.github/workflows/release.yml)): unit tests via [tests.yml](../../.github/workflows/tests.yml), then `publish` checks that the tag matches `cleave.__version__`, extracts the changelog section, and creates the GitHub Release (source zip/tarball attach automatically). Then `freeze` calls [windows-freeze.yml](../../.github/workflows/windows-freeze.yml) with `release_tag` set to the tag and uploads `cleave-<version>-windows-x64.zip` and `cleave-<version>-windows-x64-setup.exe` onto that Release. If freeze fails, the source Release still exists and can be retried.
6. Spot-check the archive: unpack, install requirements, run `cleave --version`, confirm presets still come from the README steps.

Prepare the tree with [.cursor/skills/cut-release/SKILL.md](../../.cursor/skills/cut-release/SKILL.md) (changelog, version, docs). Do not commit or tag unless asked.
