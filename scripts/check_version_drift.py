#!/usr/bin/env python3
"""Version-drift guard.

Fails CI if VERSION, pyproject.toml, CITATION.cff, and the CHANGELOG
header disagree on the canonical release version. Run locally too:
    python scripts/check_version_drift.py

Reading rule:
  - VERSION                -> first line, stripped, lowercase 'v' allowed
  - pyproject.toml         -> `version = "X.Y.Z"` under [project]
  - CITATION.cff           -> `version: X.Y.Z` top-level
  - CHANGELOG.md           -> first `## [X.Y.Z]` heading

All four MUST agree. Exit 0 = pass, Exit 1 = drift detected.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_version_file() -> str:
    raw = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    return raw.lstrip("v")


def read_pyproject_version() -> str:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"\s*$', text, re.MULTILINE)
    if not m:
        raise RuntimeError("pyproject.toml: no `version = \"...\"` under [project]")
    return m.group(1).strip()


def read_citation_version() -> str:
    text = (REPO_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    m = re.search(r"^version:\s*([^\s#]+)\s*$", text, re.MULTILINE)
    if not m:
        raise RuntimeError("CITATION.cff: no top-level `version:` line")
    return m.group(1).strip()


def read_changelog_head() -> str:
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^##\s*\[([^\]]+)\]", text, re.MULTILINE)
    if not m:
        raise RuntimeError("CHANGELOG.md: no `## [X.Y.Z]` header")
    return m.group(1).strip()


def main() -> int:
    sources = {
        "VERSION": read_version_file(),
        "pyproject.toml": read_pyproject_version(),
        "CITATION.cff": read_citation_version(),
        "CHANGELOG.md (head)": read_changelog_head(),
    }
    unique = sorted(set(sources.values()))
    print("Version sources:")
    for name, value in sources.items():
        print(f"  {name:24s} -> {value}")
    if len(unique) == 1:
        print(f"\nOK: all sources agree on {unique[0]}")
        return 0
    print(f"\nFAIL: {len(unique)} different versions found: {unique}", file=sys.stderr)
    print("Fix the drift before merging.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
