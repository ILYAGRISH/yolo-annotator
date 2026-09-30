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

    # ── rendering helpers ──────────────────────────────────────────────────────

    def _view_lod(self) -> float:
        """Current view zoom (scale factor). Used to size cosmetic preview items."""
        scene = getattr(self, "_scene", None)
        if scene and scene.views():
            return scene.views()[0].transform().m11()
        return 1.0

    @staticmethod
    def _cosmetic_pen(color, width: float = 1.5, style=None):
        """Pen with constant screen-space width (cosmetic) regardless of zoom."""
        from PyQt6.QtGui import QPen, QColor
        from PyQt6.QtCore import Qt
        p = QPen(QColor(color), width, style or Qt.PenStyle.SolidLine)
        p.setCosmetic(True)
        return p
