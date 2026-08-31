"""Package-boundary guards for cleave.effects."""

from __future__ import annotations

from cleave.paths import repo_root


def test_effects_package_does_not_import_viz() -> None:
    effects_dir = repo_root() / "cleave" / "effects"
    offenders: list[str] = []
    for path in sorted(effects_dir.rglob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if not (stripped.startswith("import ") or stripped.startswith("from ")):
                continue
            if "cleave.viz" in stripped:
                rel = path.relative_to(effects_dir)
                offenders.append(f"{rel}:{lineno}: {stripped}")
    assert offenders == []
