"""Shared environment-variable access, used by anything that needs a required config value."""

from __future__ import annotations

import os


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
