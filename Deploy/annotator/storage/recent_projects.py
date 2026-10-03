"""
Recently opened projects — an app-level list kept in app_settings(),
next to the UI language and user name.

Most recent first, no duplicates, at most MAX_RECENT entries. Paths are stored
as given (absolute .annproj folders); entries whose folder disappeared are kept
until the user picks them — a network drive may just be offline.
"""
from __future__ import annotations

import os
from pathlib import Path

MAX_RECENT = 10
_KEY = "recent_projects"


def _settings(settings=None):
    if settings is not None:
        return settings
    from annotator.app_settings import app_settings
    return app_settings()


def _norm(path) -> str:
    return str(Path(path).resolve())


def _same(a, b) -> bool:
    """Path equality by the OS rules (case-insensitive on Windows)."""
    return os.path.normcase(_norm(a)) == os.path.normcase(_norm(b))


def load(settings=None) -> list[str]:
    value = _settings(settings).value(_KEY, [])
    if isinstance(value, str):          # QSettings returns a bare str for 1 item
        value = [value]
    return [str(v) for v in (value or []) if v][:MAX_RECENT]


def _save(paths: list[str], settings=None) -> None:
    _settings(settings).setValue(_KEY, paths[:MAX_RECENT])


def add(path, settings=None) -> list[str]:
    """Put a project on top of the list. Returns the new list."""
    p = _norm(path)
    paths = [p] + [x for x in load(settings) if not _same(x, p)]
    _save(paths, settings)
    return paths[:MAX_RECENT]


def remove(path, settings=None) -> list[str]:
    paths = [x for x in load(settings) if not _same(x, path)]
    _save(paths, settings)
    return paths


def clear(settings=None) -> None:
    _save([], settings)


def is_project(path) -> bool:
    return (Path(path) / "project.json").is_file()
