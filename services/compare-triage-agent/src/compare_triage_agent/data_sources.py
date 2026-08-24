"""
Loads the three source-of-record JSON exports the tools read from.

Paths default to the bundled `data/` sample fixtures (same files the agent was
built against) but can be pointed at a fresher export via env vars, so the
tools work unchanged once these are replaced by live API calls later.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_ENV_OVERRIDES = {
    "compare_results": "COMPARE_RESULTS_PATH",
    "boarding_status": "BOARDING_STATUS_PATH",
    "failure_list": "FAILURE_LIST_PATH",
}

_DEFAULT_FILENAMES = {
    "compare_results": "customercompareresults.json",
    "boarding_status": "HoganAccountBoardingStatusResponse.json",
    "failure_list": "FailureListResponse.json",
}


def _resolve_path(dataset: str) -> Path:
    override = os.environ.get(_ENV_OVERRIDES[dataset])
    if override:
        return Path(override)
    return _DATA_DIR / _DEFAULT_FILENAMES[dataset]


@lru_cache
def _load_json(path_str: str) -> Any:
    with open(path_str, encoding="utf-8") as f:
        return json.load(f)


def load_compare_results() -> list[dict]:
    return _load_json(str(_resolve_path("compare_results")))


def load_boarding_status() -> list[dict]:
    return _load_json(str(_resolve_path("boarding_status")))["accounts"]


def load_failure_list() -> list[dict]:
    return _load_json(str(_resolve_path("failure_list")))


def clear_cache() -> None:
    """Test-only: drop cached file contents so a test can point at different fixtures."""
    _load_json.cache_clear()
