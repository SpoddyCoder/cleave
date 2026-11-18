---
name: update-dependencies
description: >-
  Walk the user through updating Cleave's dependencies to latest: Python
  pins, PyTorch and the CUDA extra wheels, the Windows FFmpeg sidecar,
  GitHub Actions versions, the local Linux/WSL env and native libs, the
  Windows libprojectM DLL rebuild, and CI verification. Explains the whole
  process first, then goes one step at a time, doing the in-repo edits and
  handing the user exact commands for the local and Windows steps. Use when
  asked to update, upgrade, or refresh dependencies, pins, projectM,
  FFmpeg, or torch.
---

# Update dependencies

Guided, interactive run of [docs/dev/dependency-updates.md](../../../docs/dev/dependency-updates.md). That doc is the procedure and the list of files; this skill is how to walk the user through it. Read the doc in full before starting. Do not copy its file lists into replies from memory; re-read the relevant section at each step.

## Hard stops

- One step at a time. After each step, report what changed and wait for the user before starting the next.
- Show proposed versions and get approval before editing any pin.
- Do not `git commit`, `git push`, run the freeze workflow, or create a release unless the user asks. Offer a commit at the end.
- Do not launch the editor. Steps that need the editor, a GPU, Windows, or the user's own machine are the user's: give exact commands and wait for their result.
- Do not `pip install` into the agent env except the env refresh in step 5, and only after the user approves it.
- Never put the user's name, email, or project details in requests to PyPI, PyTorch, GitHub, or any other service.
- Work on the pre-release branch. If HEAD is `main`, stop and ask which branch to create.

## 0. Explain, then agree the plan

Before touching anything, give the user a short overview of the whole process in plain language:

1. What gets updated: Python packages, PyTorch (CPU and CUDA), the CUDA download wheels, FFmpeg for Windows, GitHub Actions, libprojectM on Linux and Windows.
2. Who does what: the agent edits files in the repo and looks up versions and hashes. The user refreshes their Linux/WSL env, rebuilds native libraries, builds the Windows DLLs on a Windows machine, runs the CI freeze, and checks the result on a GPU.
3. The constraints from the doc (Python 3.10, matched torch set, numpy/numba, Demucs 4.0.1).
4. Roughly how long: the repo edits are quick; the Windows DLL build and the CI freeze (up to about three hours) are the slow parts.

Then copy this checklist into the reply, ask whether any step should be skipped, and wait:

```
Dependency update:
- [ ] 1. Python pins (every copy)
- [ ] 2. CUDA extra wheels
- [ ] 3. FFmpeg Windows sidecar
- [ ] 4. GitHub Actions versions
- [ ] 5. Local Linux / WSL env + native libs   (user)
- [ ] 6. Windows libprojectM DLLs              (user, then agent docs edits)
- [ ] 7. projectM minimum version (only if raised)
- [ ] 8. Tests, freeze dispatch, GPU check     (agent tests, user CI + GPU)
- [ ] 9. Changelog bullet
```

Re-post the checklist with ticks at the start of each step, so the user always sees where they are.

## 1. Python pins (agent)

1. Read every file in the doc's section 1 table plus the three hand-typed analyse lines.
2. Look up the latest release of each pinned package (PyPI JSON API, `https://pypi.org/pypi/<name>/json`; torch family from the PyTorch indexes). For each, check `requires_python` and wheel tags still allow CPython 3.10. For numpy, check what the latest numba supports.
3. Show a table: package, current pin, latest, proposed pin, and a reason when proposed is not latest (drops 3.10, numba cap, torch set). Call out any major-version jump and suggest the user skim its changelog.
4. If PyTorch's CUDA build has moved past cu130, say so and ask whether to move (doc section 1, last paragraph). That is a larger change; get explicit approval.
5. After approval, edit every copy in one pass. Then grep the repo (only the files the doc names) to confirm no old version string of a changed package remains.

## 2. CUDA extra wheels (agent)

Skip if torch, torchaudio, and torchcodec did not change.

1. From the PyTorch CUDA index page, read the `cp310` `win_amd64` wheel filenames. The SHA-256 is in each link's `#sha256=` fragment. Get each size from the `Content-Length` of a HEAD request. Do not download the wheels.
2. Edit `CUDA_WHEELS` and `CUDA_EXTRA_KEY` in [cleave/cuda_extra.py](../../../cleave/cuda_extra.py), then the wheel list and totals (bytes and MiB) in [docs/dev/windows-freeze.md](../../../docs/dev/windows-freeze.md).
3. If the agent cannot reach the index or the fragment has no hash, give the user the commands to fetch them and wait.
4. Tell the user step 2 of section 2 means existing CUDA installs will re-download.

## 3. FFmpeg Windows sidecar (agent)

1. Find the latest GyanD/codexffmpeg GitHub release and its essentials zip asset. Show current and new versions.
2. Get the SHA-256: use the published checksum if the release has one; otherwise download the zip into its own new, empty directory in the scratchpad and hash it there. Do not extract or run anything from it.
3. Edit `FFMPEG_URL` and `FFMPEG_SHA256` in [scripts/windows_stage_freeze.py](../../../scripts/windows_stage_freeze.py) and the pinned-build line in [docs/dev/windows-freeze.md](../../../docs/dev/windows-freeze.md).
4. Remind the user to delete `.cache/ffmpeg-windows.zip` on any machine that freezes locally.

## 4. GitHub Actions versions (agent)

List every `uses:` in [.github/workflows/](../../../.github/workflows/) with its current and latest major version, get approval, then edit. Flag any action whose new major changes inputs the workflows use.

## 5. Local Linux / WSL (user)

Hand the user the commands from the doc's section 5, one fenced `bash` block per command. Ask whether this box has CUDA to choose the torch file. Offer to run the pip refresh in the agent env (`/home/fernpa/anaconda3/envs/cleave/bin/pip`) if they approve; the wsl-builds rebuild is theirs.

Wait for them to report back, then:

1. Ask for the output of `pkg-config --modversion libprojectM` and confirm it is the new version. If not, walk through the `PROJECTM_LIB` / pkg-config / system path order to find the stale copy.
2. Run the full test suite yourself and report failures with output. Fix failures caused by the upgrades (API changes, deprecations) as part of this step, one at a time, explaining each.
3. Ask the user to do the manual editor check from section 5 (play with layers, short render, split a new file) and report anything odd.

## 6. Windows libprojectM DLLs (user, then agent)

1. Tell the user the latest projectM release tag, and whether the vcpkg `projectm` port already has it (check the vcpkg repo's port version). If not, explain the overlay port option.
2. Give the Windows steps from the doc's section 6 as a numbered list, with commands for a Developer PowerShell for VS 2022. Ask them to paste the `dumpbin /dependents` output for both DLLs and tell you the projectM version, then wait.
3. When they have copied the DLLs into `packaging/windows/`, confirm with `git status` that both changed. Optionally check dependents with `objdump -p` from WSL to confirm what they pasted.
4. Edit `NOTICE.txt` and the version table and dependents list in [packaging/windows/README.md](../../../packaging/windows/README.md). If `dumpbin` listed a new non-system DLL, make sure it is in `packaging/windows/` and named in the README.

## 7. projectM minimum version (agent, only if needed)

Compare the upstream changelog between the old and new projectM versions against [docs/dev/projectm-api-coverage.md](../../../docs/dev/projectm-api-coverage.md) and `_REQUIRED_SYMBOLS` in [cleave/projectm.py](../../../cleave/projectm.py). Report removed or changed functions Cleave uses, and any new ones worth knowing about. Only raise the minimum if the user wants to use a new API; then follow the doc's section 7 list.

## 8. Verify in CI (user)

1. Run the full test suite once more and report the result.
2. Ask the user whether to commit now (suggest a message). The freeze workflow needs the changes pushed.
3. Give the user the command to dispatch the freeze on their branch:

   ```bash
   gh workflow run windows-freeze.yml --ref <branch>
   ```

   Offer to watch it with `gh run watch` if they want; otherwise wait for them to report.
4. Ask them to check play and render from the dispatch zip or installer on a Windows GPU machine, and the CUDA download on an NVIDIA machine if the wheels changed (doc section 8).

## 9. Changelog and wrap-up (agent)

1. Add one `### Changed` bullet under `## [Unreleased]` in [CHANGELOG.md](../../../CHANGELOG.md) naming the user-visible upgrades (libprojectM, FFmpeg, PyTorch, CUDA build). Skip it if only invisible Python pins moved.
2. If anything in the procedure turned out wrong or missing, update [docs/dev/dependency-updates.md](../../../docs/dev/dependency-updates.md) so next time is accurate.
3. Final reply: the ticked checklist, a table of old and new versions, files changed, anything skipped or still pending on the user's side, and a suggested commit message. Run `scripts/version_badge.py` before any commit the user asks for.
