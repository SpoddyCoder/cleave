---
name: cut-release
description: >-
  Prepare Cleave's next versioned GitHub Release from Unreleased changelog
  notes: bump cleave.__version__, date a Keep a Changelog section, leave
  empty Added/Changed/Fixed headings, fix doc drift, and move finished
  plans to docs/dev/plans-completed/. Use when asked to cut a release, ship
  the next full release, bump the version, or move Unreleased into a dated
  X.Y.Z section. Suggests a commit message. Does not commit, tag, or publish.
---

# Cut a release

Prepare the tree for the next `vX.Y.Z` tag. Product SOP (tag, CI, freeze): [docs/dev/structured-releases.md](../../../docs/dev/structured-releases.md). Stance: [versioned-releases.mdc](../../rules/versioned-releases.mdc).

Copy this checklist and tick it as you go:

```
Cut progress:
- [ ] Choose X.Y.Z
- [ ] Changelog + version
- [ ] Docs drift + completed plans
- [ ] Tests + release-notes preview
- [ ] Suggest commit message (do not commit)
```

## Hard stops

Do **not** `git commit`, `git tag`, `git push`, or `gh release create`. Leave that to the user after review.

Do **not** bump `cleave.__version__` or add a dated changelog section unless this skill is the task (user asked to cut / ship / version a release).

Do **not** launch the editor or run a Windows freeze.

If `[Unreleased]` has no bullets, stop and say there is nothing to ship.

## 1. Choose the version

Single source of truth: `cleave.__version__` in [cleave/__init__.py](../../../cleave/__init__.py). Tags are `vX.Y.Z` and must match. [pyproject.toml](../../../pyproject.toml) is `{attr = "cleave.__version__"}`; [packaging/windows/cleave.iss](../../../packaging/windows/cleave.iss) injects `AppVersion` at freeze time. Do not hardcode the version in those files.

If the user named a version, use it. Otherwise infer from current `__version__` and Unreleased (pre-1.0: breaking changes are allowed on minor bumps):

| Unreleased content | Next version |
| --- | --- |
| Any `Added` or `Changed` (a "full" release) | bump minor (`0.1.0` -> `0.2.0`) |
| Only `Fixed` | bump patch (`0.1.0` -> `0.1.1`) |
| User asked for a named `X.Y.Z` | that version |

State the chosen version in the handoff. Date is today's `YYYY-MM-DD`.

Prefer `main`. If HEAD is not `main`, say so and continue only if the user already waived that.

## 2. Changelog and version

[CHANGELOG.md](../../../CHANGELOG.md) is Keep a Changelog. GitHub Release body is that version's section, extracted by [scripts/changelog_section.py](../../../scripts/changelog_section.py).

1. Move every Unreleased bullet into a new `## [X.Y.Z] - YYYY-MM-DD` block, keeping `### Added` / `Changed` / `Fixed` / `Removed` that have bullets. Drop empty groups from the dated section.
2. Keep bullet wording. You may collapse extra blank lines inside a group. Do not add, drop, or rewrite notes during the cut. Do not edit older dated sections.
3. Set `__version__` in `cleave/__init__.py` to `X.Y.Z`.
4. Do not edit [LICENSE](../../../LICENSE). It is Apache License 2.0 with Commons Clause and is not versioned per release.
5. Leave this empty Unreleased block (headings present, no bullets). Omit `### Removed` unless the user asks:

```markdown
## [Unreleased]

### Added

### Changed

### Fixed
```

6. Update the link refs at the bottom. Keep the existing GitHub org/repo from those lines:

```markdown
[unreleased]: https://github.com/ORG/REPO/compare/vX.Y.Z...HEAD
[X.Y.Z]: https://github.com/ORG/REPO/releases/tag/vX.Y.Z
[0.1.0]: https://github.com/ORG/REPO/releases/tag/v0.1.0
```

`[unreleased]` must compare from the new tag, not the previous one.

## 3. Documentation

Style: [documentation-style.mdc](../../rules/documentation-style.mdc). Living references stay in `docs/dev/`. Do not rewrite [docs/dev/structured-releases.md](../../../docs/dev/structured-releases.md) history; only fix sentences that the new tag makes false.

Tree:

- [docs/user-guide/](../../../docs/user-guide/) - end-user pages
- [docs/dev/](../../../docs/dev/) - living development notes, todos, roadmap
- [docs/dev/plans/](../../../docs/dev/plans/) - outstanding plans
- [docs/dev/plans-completed/](../../../docs/dev/plans-completed/) - shipped plans

### Drift

Read Unreleased (now the dated section) and check these for "until a tag", "next tagged release", "source-only", "no `__version__` bump", or "testers use Actions artifacts until then":

- [README.md](../../../README.md) (Releases / Windows zip)
- [docs/dev/structured-releases.md](../../../docs/dev/structured-releases.md) (lead, current product, remaining work)
- [docs/dev/todos.md](../../../docs/dev/todos.md)
- [docs/dev/windows-freeze.md](../../../docs/dev/windows-freeze.md) only if a user-facing sentence is now wrong

After the first tag that attaches the Windows zip and setup exe, README should describe those as Release assets, not as "the next tag will attach them". `v0.1.0` staying source-only is historical and can remain.

Leave `docs/dev/todos.md` items that are still open. Strike or remove only work this cut actually shipped, and only when the todo would otherwise claim it is still outstanding.

### Completed plans

Live design plans sit in `docs/dev/plans/`. Living references never move out of `docs/dev/`: `structured-releases.md`, `windows-freeze.md`, `roadmap.md`, `todos.md`, `architecture-review.md`, `projectm-api-coverage.md`.

Move a plan to `docs/dev/plans-completed/` only when remaining work is shipped **or** explicitly parked in `todos.md` / `roadmap.md`. Mixed plans: extract shipped slices to `plans-completed/`; leave outstanding slices in `plans/`.

`docs/dev/plans-completed/` is in `.cursorignore`. List it and `git mv` via Shell with `required_permissions: ["all"]`:

```bash
git mv docs/dev/plans/<plan>.md docs/dev/plans-completed/<plan>.md
```

Then:

- In the moved file, sibling links that were `../foo.md` (living `docs/dev/` files) stay. Links to repo-root paths (`../../../cleave/...`) stay. Links to other outstanding plans become `../plans/<plan>.md`.
- In live docs, rules, and README, retarget inbound links to `docs/dev/plans-completed/<plan>.md`.
- Do not rewrite the moved plan's design content.

### Other docs hygiene

- Changelog bullets that describe current product behaviour should match README (picker, Windows zip/installer, CUDA extra, data dirs). Fix README if it lags; do not invent features.
- Do not add a changelog bullet for this cut (docs/refactors/tests stay out per project-context).
- Do not bump anything in `.cursor/rules/` except inbound plan links you broke by `git mv`.

## 4. Health checks

Repo Python: `/home/fernpa/anaconda3/envs/cleave/bin/python`.

```bash
/home/fernpa/anaconda3/envs/cleave/bin/python tests/run_unit_tests.py -k "changelog_section or test_version"
/home/fernpa/anaconda3/envs/cleave/bin/python scripts/changelog_section.py X.Y.Z
```

The extract must print the dated section body (starts with `### `) and must not be empty. `test_changelog_has_section_for_current_version` fails if `__version__` has no dated section.

Also:

- `git status` / `git diff`: only intended files. Warn on unrelated dirty files; do not revert them.
- Confirm you did not edit `pyproject.toml` version, hardcode `AppVersion` in `cleave.iss`, or edit [LICENSE](../../../LICENSE).

Useful, still in-tree only:

- If Unreleased mixed several milestones, do not split versions unless the user asked. One dated section for this cut.
- If README still tells testers to grab 5-day Actions artifacts *instead of* a Release, fix that once this tag will attach the zip.
- Do not refresh requirement pins or freeze sidecars unless the user asked; note them in the handoff if they look stale.

## 5. Handoff (no commit)

In the reply:

1. Version, date, and a one-line summary of what this cut ships.
2. Files changed (changelog, `__init__.py`, docs, moved plans).
3. Preview of the GitHub Release body (`scripts/changelog_section.py` output).
4. A suggested commit message. Do not run `git commit`. Prefer:

```
Cut X.Y.Z.

Move Unreleased notes into a dated changelog section and set cleave.__version__.
```

Tune the second line if docs moves or README drift dominated.

5. After the user reviews and commits, they still need to (do not run these):

```bash
git tag vX.Y.Z
git push origin main
git push origin vX.Y.Z
```

Tag the commit that is on `main`. CI ([.github/workflows/release.yml](../../../.github/workflows/release.yml)) checks the tag against `__version__`, creates the GitHub Release from the changelog section, then attaches `cleave-<version>-windows-x64.zip` and `cleave-<version>-windows-x64-setup.exe`. If freeze fails, the source Release still exists and can be retried. Manual GPU proof stays a human checklist in structured-releases; do not treat CI green as compositor proof.
