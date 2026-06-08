#!/usr/bin/env python3
"""Canonical entry point for Cleave unit tests.

Run from the repo root::

    ./tests/run_unit_tests.py
    python tests/run_unit_tests.py

Extra pytest arguments (``-k``, ``-m``, ``-x``, etc.) are passed through.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT))
    sys.exit(pytest.main([str(REPO_ROOT / "tests"), *sys.argv[1:]]))
