"""ML settings (stored with the other app preferences, keys "ml/...")."""
from __future__ import annotations

import os
from pathlib import Path

from annotator.app_settings import app_settings

_KEY_PYTHON = "ml/python"
_KEY_AUTOSTART = "ml/autostart"
_KEY_TEST_MODEL = "ml/test_model"

ENV_DIR_NAME = ".venv-ml"


def app_dir() -> Path:
    """Folder that holds main.py, ml_backend/ and .venv-ml (new_annotator/ or Deploy/)."""
    return Path(__file__).resolve().parents[2]


def default_python() -> Path:
    """Interpreter created by setup_ml_env.bat (may not exist yet)."""
    env = app_dir() / ENV_DIR_NAME
    return env / "Scripts" / "python.exe" if os.name == "nt" else env / "bin" / "python"


def saved_python() -> str:
    return str(app_settings().value(_KEY_PYTHON, "") or "")


def set_saved_python(path: str) -> None:
    app_settings().setValue(_KEY_PYTHON, path.strip())


def resolve_python(path: str | None = None) -> Path | None:
    """The interpreter to use: an explicit / saved path, else .venv-ml.
    None when nothing usable exists."""
    candidate = (path if path is not None else saved_python()).strip().strip('"')
    if candidate:
        p = Path(candidate)
        return p if p.is_file() else None
    p = default_python()
    return p if p.is_file() else None


def autostart() -> bool:
    return str(app_settings().value(_KEY_AUTOSTART, "false")).lower() == "true"


def set_autostart(on: bool) -> None:
    app_settings().setValue(_KEY_AUTOSTART, "true" if on else "false")


def test_model() -> str:
    return str(app_settings().value(_KEY_TEST_MODEL, "") or "")


def set_test_model(path: str) -> None:
    app_settings().setValue(_KEY_TEST_MODEL, path)


_KEY_SAM_MODEL = "ml/sam_model"


def sam_model() -> str:
    return str(app_settings().value(_KEY_SAM_MODEL, "") or "")


def set_sam_model(path: str) -> None:
    app_settings().setValue(_KEY_SAM_MODEL, path.strip())
