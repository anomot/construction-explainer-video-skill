#!/usr/bin/env python3
"""Shared env loading and timeline constants for construction-explainer scripts."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_FILENAMES = (".env.local", ".env")

# Scene padding around narration audio; single source of truth for all scripts.
HEAD_PAD = 0.65
TAIL_PAD = 0.9
DEFAULT_MIN_DURATION = 5.5


def estimate_duration(narration: str, min_duration: float = DEFAULT_MIN_DURATION) -> float:
    """Estimate scene duration from narration length when real audio is absent."""
    return round(max(float(min_duration), len(narration) / 4.5 + HEAD_PAD + TAIL_PAD), 3)


def _parse_env_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _candidate_dirs(start: Path) -> list[Path]:
    dirs: list[Path] = []
    current = start.resolve()
    while True:
        dirs.append(current)
        if current.parent == current:
            break
        current = current.parent
    return dirs


def load_env(explicit: Path | None = None, *, quiet: bool = False) -> Path | None:
    """Load env vars from a dotenv file without overriding existing environment.

    Search order:
    1. Explicit ``--env-file`` path (error if missing).
    2. ``.env.local`` / ``.env`` walking up from the current working directory.
    3. ``.env.local`` / ``.env`` walking up from this script's directory
       (covers the skill repository even when installed via symlink).
    """
    if explicit is not None:
        if not explicit.exists():
            print(f"ERROR: env file not found: {explicit}", file=sys.stderr)
            raise SystemExit(1)
        _parse_env_file(explicit)
        if not quiet:
            print(f"Loaded env: {explicit}")
        return explicit

    seen: set[Path] = set()
    search: list[Path] = []
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for directory in _candidate_dirs(start):
            if directory not in seen:
                seen.add(directory)
                search.append(directory)
    for directory in search:
        for name in ENV_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                _parse_env_file(candidate)
                if not quiet:
                    print(f"Loaded env: {candidate}")
                return candidate
    return None
