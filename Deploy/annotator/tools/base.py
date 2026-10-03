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


class BrushRing:
    """
    Dashed circle that follows the cursor and shows the brush radius in image
    pixels — so its on-screen size tracks the zoom, like the stroke itself.
    Used by BrushTool and SemanticBrushTool.
    """

    def __init__(self):
        self._item = None
        self._scene = None

    def update(self, scene, pos, radius: float):
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QGraphicsEllipseItem
        if scene is None:
            return
        if self._item is None or self._item.scene() is not scene:
            self._item = QGraphicsEllipseItem()
            self._item.setPen(BaseTool._cosmetic_pen("#FFFFFF", 1.0, Qt.PenStyle.DashLine))
            self._item.setZValue(6)
            scene.addItem(self._item)
            self._scene = scene
        self._item.setRect(pos.x() - radius, pos.y() - radius, 2 * radius, 2 * radius)

    def remove(self):
        if self._item is not None and self._scene is not None:
            if self._item.scene() is self._scene:
                self._scene.removeItem(self._item)
        self._item = None
        self._scene = None
