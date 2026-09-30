"""Plugin loader — scans plugins/*.py for BaseTool subclasses.

Usage (called once at app startup):
    from annotator.plugins.loader import load_plugins
    tools = load_plugins(Path("plugins/"))
    for tool in tools:
        registry[tool.name] = tool

Rules:
- Files whose name starts with '_' are skipped.
- Each .py file is imported as an isolated module.
- All BaseTool subclasses found in the module are instantiated.
- Import errors or instantiation errors in one plugin never crash the loader.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from annotator.tools.base import BaseTool


def load_plugins(plugins_dir: Path) -> list[BaseTool]:
    """Return a list of instantiated BaseTool objects from plugins_dir/*.py."""
    tools: list[BaseTool] = []
    if not plugins_dir.is_dir():
        return tools

    for plugin_file in sorted(plugins_dir.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue
        _load_one(plugin_file, tools)

    return tools


def _load_one(plugin_file: Path, tools: list[BaseTool]) -> None:
    module_name = f"_annotator_plugin_{plugin_file.stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        print(f"[plugin loader] failed to import {plugin_file.name}: {exc}")
        return

    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (isinstance(attr, type)
                and issubclass(attr, BaseTool)
                and attr is not BaseTool):
            try:
                tool = attr()
                tools.append(tool)
            except Exception as exc:
                print(f"[plugin loader] {plugin_file.name}: "
                      f"cannot instantiate {attr_name}: {exc}")
