from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    All annotation tools implement this interface.
    The AnnotationScene holds an active_tool and forwards all
    mouse / keyboard events to it.
    """

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def cursor(self):
        """Return a QCursor for this tool (override in subclasses)."""
        from PyQt6.QtCore import Qt
        return Qt.CursorShape.ArrowCursor

    def activate(self, scene):
        """Called when this tool becomes the active tool."""

    def deactivate(self):
        """Called when switching to another tool."""

    @abstractmethod
    def on_press(self, pos, modifiers, button): ...

    @abstractmethod
    def on_move(self, pos, modifiers): ...

    @abstractmethod
    def on_release(self, pos, modifiers, button): ...

    def on_double_click(self, pos, modifiers, button): ...

    def on_key_press(self, key, modifiers): ...
