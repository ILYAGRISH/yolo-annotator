"""OBBTool — drag to draw an oriented bounding box (initial angle = 0°)."""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPen, QBrush, QColor

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool

MIN_PX = 4


class OBBTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id = 0
        self._start: QPointF | None = None
        self._preview = None

    @property
    def name(self) -> str:
        return "obb"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._cancel()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id

    def on_press(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton:
            self._start = self._clamp(pos)
            self._update_preview(self._start)

    def on_move(self, pos, modifiers):
        if self._start is not None:
            self._update_preview(self._clamp(pos))

    def on_release(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton and self._start is not None:
            self._commit(self._clamp(pos))

    def on_double_click(self, pos, modifiers, button): ...

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._cancel()

    # ── internal ──────────────────────────────────────────────────────────────

    def _clamp(self, pos: QPointF) -> QPointF:
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(w, pos.x())), max(0.0, min(h, pos.y())))

    def _rect_from(self, end: QPointF) -> QRectF:
        return QRectF(
            min(self._start.x(), end.x()), min(self._start.y(), end.y()),
            abs(end.x() - self._start.x()), abs(end.y() - self._start.y()),
        )

    def _cancel(self):
        if self._preview and self._scene and self._preview.scene():
            self._scene.removeItem(self._preview)
        self._preview = None
        self._start = None

    def _update_preview(self, current: QPointF):
        if self._preview and self._preview.scene():
            self._scene.removeItem(self._preview)
        rect = self._rect_from(current)
        pen = QPen(QColor("#FFAA00"), 2.0, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        self._preview = self._scene.addRect(rect, pen, QBrush(QColor(255, 170, 0, 70)))
        self._preview.setZValue(20)

    def _commit(self, end: QPointF):
        rect = self._rect_from(end)
        self._cancel()
        if rect.width() < MIN_PX or rect.height() < MIN_PX:
            return
        iw, ih = self._scene.image_size
        ann = Annotation.new(
            self._class_id, AnnotationType.OBB,
            {
                "cx": (rect.x() + rect.width() / 2) / iw,
                "cy": (rect.y() + rect.height() / 2) / ih,
                "w": rect.width() / iw,
                "h": rect.height() / ih,
                "angle_deg": 0.0,
            },
            tool="obb",
        )
        self._ctrl.add_annotation(ann)
