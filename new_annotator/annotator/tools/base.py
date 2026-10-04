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


class ShiftLine:
    """
    Photoshop-style straight strokes for brush tools: after a stroke ends,
    Shift+click paints a straight line from that end point to the click
    (repeat to chain a polyline). While Shift is held, a dashed guide shows
    where the line will go. The anchor belongs to one image — switching
    images never connects strokes across them.
    """

    def __init__(self):
        self._anchor = None          # QPointF, image pixels
        self._image = None           # image the anchor belongs to
        self._item = None            # QGraphicsLineItem guide
        self._scene = None

    @staticmethod
    def held(modifiers) -> bool:
        from PyQt6.QtCore import Qt
        return bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

    def set_anchor(self, pos, image) -> None:
        from PyQt6.QtCore import QPointF
        self._anchor = QPointF(pos)
        self._image = image

    def anchor_for(self, image):
        """The anchor if it belongs to `image`, else None."""
        return self._anchor if self._anchor is not None and image == self._image else None

    def start_point(self, pos, modifiers, image):
        """Where a new stroke starts: the anchor on Shift+click, else `pos`."""
        anchor = self.anchor_for(image) if self.held(modifiers) else None
        return anchor if anchor is not None else pos

    def update_guide(self, scene, pos, modifiers, image) -> None:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QGraphicsLineItem
        anchor = self.anchor_for(image)
        if scene is None or anchor is None or not self.held(modifiers):
            self.hide_guide()
            return
        if self._item is None or self._item.scene() is not scene:
            self._item = QGraphicsLineItem()
            self._item.setPen(BaseTool._cosmetic_pen("#FFFFFF", 1.0, Qt.PenStyle.DashLine))
            self._item.setZValue(6)
            scene.addItem(self._item)
            self._scene = scene
        self._item.setLine(anchor.x(), anchor.y(), pos.x(), pos.y())

    def hide_guide(self) -> None:
        if self._item is not None and self._scene is not None:
            if self._item.scene() is self._scene:
                self._scene.removeItem(self._item)
        self._item = None
        self._scene = None

    def reset(self) -> None:
        self._anchor = None
        self._image = None
        self.hide_guide()
