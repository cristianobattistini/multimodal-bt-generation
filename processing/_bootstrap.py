"""
Bootstrap helper to ensure repo root is on sys.path when running scripts directly.
"""
from __future__ import annotations

import os
import sys


def ensure_repo_root() -> None:
    here = os.path.abspath(os.path.dirname(__file__))
    repo_root = os.path.abspath(os.path.join(here, os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
