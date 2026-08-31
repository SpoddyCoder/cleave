#!/usr/bin/env python3
"""Print a CHANGELOG.md section body for a given version."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

_HEADING_RE = re.compile(r"^## \[([^\]]+)\](?:\s+-.*)?\s*$", re.MULTILINE)
_LINK_REF_RE = re.compile(r"^\[[^\]]+\]:\s+\S+")


class ChangelogSectionError(LookupError):
    """Raised when a changelog section is missing or empty."""


def normalize_version(version: str) -> str:
    version = version.strip()
    if len(version) >= 2 and version[0] in "vV" and version[1].isdigit():
        return version[1:]
    return version


def extract_section(text: str, version: str) -> str:
    """Return the body under ``## [version]`` (heading excluded).

    ``version`` may be ``0.1.0`` or ``v0.1.0``. Raises
    ``ChangelogSectionError`` if the section is missing or empty.
    """
    wanted = normalize_version(version)
    matches = list(_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        if match.group(1) != wanted:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _strip_link_refs(text[start:end])
        if not body:
            raise ChangelogSectionError(f"changelog section [{wanted}] is empty")
        return body
    raise ChangelogSectionError(f"changelog section [{wanted}] not found")


def _strip_link_refs(block: str) -> str:
    lines = block.strip().splitlines()
    while lines and (not lines[-1].strip() or _LINK_REF_RE.match(lines[-1])):
        lines.pop()
    return "\n".join(lines).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a CHANGELOG.md section body for a version or tag."
    )
    parser.add_argument(
        "version",
        help="Version or tag, e.g. 0.1.0 or v0.1.0",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        default=CHANGELOG_PATH,
        help="Changelog path (default: repo-root CHANGELOG.md)",
    )
    args = parser.parse_args(argv)
    try:
        text = args.file.read_text(encoding="utf-8")
        print(extract_section(text, args.version))
    except ChangelogSectionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
