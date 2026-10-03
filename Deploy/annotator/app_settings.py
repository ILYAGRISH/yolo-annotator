"""
App-level preferences (UI language, user name, recent projects).

Always go through app_settings() instead of QSettings("Annotator", "App"):
setting the environment variable ANNOTATOR_SETTINGS=<path to .ini> redirects
every read/write to that file — tests use it so they never touch the real
user settings (Windows registry: HKCU\\Software\\Annotator\\App).
"""
from __future__ import annotations

import os

ENV_VAR = "ANNOTATOR_SETTINGS"


def app_settings():
    from PyQt6.QtCore import QSettings
    path = os.environ.get(ENV_VAR)
    if path:
        return QSettings(path, QSettings.Format.IniFormat)
    return QSettings("Annotator", "App")
