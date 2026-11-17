"""Write the README version badge for the commit about to be made.

A release commit (``main``, or a cut whose ``v{__version__}`` tag does not
exist yet) shows the release, such as ``v0.3.0``. Any other commit is on a
pre-release branch and shows the dev build the About dialog reports, without
the hash, which a commit cannot know about itself: ``v0.3.0-13 (dev build)``
for the 13th commit past the tag.

Run before every commit (the ``scripts/git-hooks/pre-commit`` hook does this).
The badge line is rewritten in the working tree and in the index, so other
unstaged README edits stay unstaged.

    python scripts/version_badge.py           # update for the next commit
    python scripts/version_badge.py --check   # exit 1 if the index is stale

Standard library only, so the hook runs without the project environment.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parent.parent
README = "README.md"
GITHUB = "https://github.com/SpoddyCoder/cleave"
BADGE_RE = re.compile(r"^\[!\[Version\]\([^)]*\)\]\([^)]*\) ?", re.MULTILINE)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True, check=check
    )


def current_version() -> str:
    text = (REPO / "cleave" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
    if match is None:
        sys.exit("version_badge: no __version__ in cleave/__init__.py")
    return match.group(1)


def tag_exists(tag: str) -> bool:
    return git("rev-parse", "-q", "--verify", f"refs/tags/{tag}", check=False).returncode == 0


def branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip()


def _shield(text: str) -> str:
    return quote(text.replace("-", "--").replace("_", "__"), safe="")


def badge_for_next_commit() -> tuple[str, str]:
    """(badge markdown, label) for the commit about to be made."""
    tag = f"v{current_version()}"
    if branch() == "main" or not tag_exists(tag):
        label = tag
        url = f"https://img.shields.io/badge/version-{_shield(label)}-blue"
        link = f"{GITHUB}/releases/tag/{tag}"
    else:
        ahead = int(git("rev-list", "--count", f"{tag}..HEAD").stdout.strip()) + 1
        label = f"{tag}-{ahead} (dev build)"
        url = f"https://img.shields.io/badge/version-{_shield(label)}-orange"
        link = f"{GITHUB}/compare/{tag}...{branch()}"
    return f"[![Version]({url})]({link}) ", label


def with_badge(text: str, badge: str) -> str:
    if BADGE_RE.search(text):
        return BADGE_RE.sub(lambda _m: badge, text, count=1)
    # First badge line sits under the title; put the version first.
    return re.sub(r"^(\[!\[)", lambda m: badge + m.group(1), text, count=1, flags=re.MULTILINE)


def staged_readme() -> str:
    return git("show", f":{README}").stdout


def write_index(text: str) -> None:
    blob = subprocess.run(
        ["git", "hash-object", "-w", "--stdin"],
        cwd=REPO, input=text, capture_output=True, text=True, check=True,
    ).stdout.strip()
    mode = git("ls-files", "-s", README).stdout.split()[0]
    git("update-index", "--cacheinfo", f"{mode},{blob},{README}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if the staged badge is stale")
    args = parser.parse_args()

    badge, label = badge_for_next_commit()
    staged = staged_readme()
    fixed = with_badge(staged, badge)
    if args.check:
        if fixed != staged:
            print(f"version_badge: README badge should read {label}", file=sys.stderr)
            return 1
        return 0
    if fixed != staged:
        write_index(fixed)
    path = REPO / README
    work = path.read_text(encoding="utf-8")
    new_work = with_badge(work, badge)
    if new_work != work:
        path.write_text(new_work, encoding="utf-8")
    print(f"version badge: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
