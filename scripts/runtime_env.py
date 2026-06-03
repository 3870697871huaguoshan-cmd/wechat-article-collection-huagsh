#!/usr/bin/env python3
"""Runtime environment helpers for Hermes/local script execution."""

from __future__ import annotations

import os
from pathlib import Path


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#") or "=" not in text:
        return None
    key, value = text.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_env_files(extra_paths: list[str | Path] | None = None, include_defaults: bool = True) -> list[str]:
    """Load simple KEY=VALUE files without overriding existing variables."""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    candidates: list[Path] = []
    if include_defaults:
        candidates.extend([
            Path.home() / ".hermes" / ".env",
            project_root / ".env",
            Path.cwd() / ".env",
        ])
    if extra_paths:
        candidates.extend(Path(p).expanduser() for p in extra_paths)

    loaded: list[str] = []
    seen: set[Path] = set()
    for path in candidates:
        path = path.expanduser()
        if path in seen:
            continue
        seen.add(path)
        if not path.exists() or not path.is_file():
            continue

        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding="gb18030").splitlines()

        changed = False
        for line in lines:
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            if key not in os.environ:
                os.environ[key] = value
                changed = True
        if changed:
            loaded.append(str(path))
    return loaded
