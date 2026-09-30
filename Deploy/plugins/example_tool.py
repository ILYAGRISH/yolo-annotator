"""
Example plugin — demonstrates how to add a custom tool via the plugin API.

To create your own tool:
1. Subclass BaseTool and implement the required methods.
2. Place the file in new_annotator/plugins/.
3. The loader discovers it automatically on next app start.

This file is intentionally minimal. The tool does nothing when used —
its purpose is to show that plugin discovery and registration works.
"""
from __future__ import annotations

from annotator.tools.base import BaseTool


class ExampleStampTool(BaseTool):
    """
    Minimal example plugin tool.

    Replace on_press / on_release with real drawing logic to make
    this tool create annotations.
    """

    @property
    def name(self) -> str:
        return "example_stamp"

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._scene = None
        self._ctrl = None

    def on_press(self, pos, modifiers, button):
        pass   # implement: create annotation at pos

    def on_move(self, pos, modifiers):
        pass   # implement: update preview

    def on_release(self, pos, modifiers, button):
        pass   # implement: finalize if needed
