"""
PointTool — click to place a single-point annotation.

Workflow:
  - Left-click → place point immediately (no Enter needed)
  - Esc        → cancel ghost preview
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QBrush, QColor

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool


class PointTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._temp_items: list = []

    @property
    def name(self) -> str:
        return "point"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._clear_preview()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene or button != Qt.MouseButton.LeftButton:
            return
        self._clear_preview()
        self._commit(self._clamp(pos))

    def on_move(self, pos, modifiers):
        if self._scene:
            self._refresh_preview(self._clamp(pos))

    def on_release(self, pos, modifiers, button): ...
    def on_double_click(self, pos, modifiers, button): ...

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._clear_preview()

    # ── internal ──────────────────────────────────────────────────────────────

    def _clamp(self, pos: QPointF) -> QPointF:
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(w, pos.x())), max(0.0, min(h, pos.y())))

    def _commit(self, pos: QPointF):
        if not self._ctrl or not self._scene:
            return
        w, h = self._scene.image_size
        ann = Annotation.new(
            self._class_id, AnnotationType.POINT,
            {"x": pos.x() / w, "y": pos.y() / h},
            tool=self.name,
        )
        self._ctrl.add_annotation(ann)

    def _clear_preview(self):
        if not self._scene:
            return
        for item in self._temp_items:
            if item.scene():
                self._scene.removeItem(item)
        self._temp_items.clear()

    def _refresh_preview(self, cursor: QPointF):
        self._clear_preview()
        lod = self._view_lod()
        r = 6.0 / max(lod, 0.05)
        pen = self._cosmetic_pen("#FFFFFF", 1.5, Qt.PenStyle.DashLine)
        brush = QBrush(QColor(255, 255, 255, 70))
        dot = self._scene.addEllipse(
            cursor.x() - r, cursor.y() - r, r * 2, r * 2, pen, brush)
        dot.setZValue(20)
        self._temp_items.append(dot)
