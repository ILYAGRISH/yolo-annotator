"""
PolygonAnnotationItem — renders SEGMENT (closed) and POLYLINE (open) annotations.
Migrated from old_app with key changes:
  - decoupled from domain model (accepts plain scene coords)
  - implements BaseAnnotationItem interface
  - closed parameter controls polygon vs polyline rendering
"""
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPolygonF,
                          QPainterPath)
from PyQt6.QtWidgets import QGraphicsItem

from annotator.ui.canvas.items.base_item import BaseAnnotationItem

HANDLE_R = 5.0
HANDLE_HIT = 9.0


class PolygonAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str, points_scene: list,
                 class_color: str, label: str = "",
                 closed: bool = True, parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._points = [QPointF(x, y) for x, y in points_scene]
        self.label = label
        self.closed = closed
        self._hover_handle = -1
        self.setAcceptHoverEvents(True)

    # ── geometry accessors ────────────────────────────────────────────────────

    @property
    def points(self) -> list[QPointF]:
        return self._points

    def move_vertex(self, index: int, new_pos: QPointF):
        self.prepareGeometryChange()
        self._points[index] = new_pos
        self.update()

    def handle_at(self, pos: QPointF) -> int:
        for i, pt in enumerate(self._points):
            if (pt - pos).manhattanLength() <= HANDLE_HIT:
                return i
        return -1

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        w, h = image_size
        self.prepareGeometryChange()
        self._points = [QPointF(x * w, y * h) for x, y in data.get("points", [])]
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        w, h = image_size
        return {"points": [[p.x() / w, p.y() / h] for p in self._points]}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        if not self._points:
            return QRectF()
        xs = [p.x() for p in self._points]
        ys = [p.y() for p in self._points]
        m = HANDLE_R + 2
        return QRectF(min(xs) - m, min(ys) - m,
                      max(xs) - min(xs) + 2 * m,
                      max(ys) - min(ys) + 2 * m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self._points:
            path.addPolygon(QPolygonF(self._points))
            if self.closed:
                path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        if len(self._points) < 2:
            return
        selected = self.isSelected()
        color = QColor(self.class_color)
        poly = QPolygonF(self._points)

        fill = QColor(color)
        fill.setAlpha(55 if not selected else 90)

        if self.closed:
            painter.setBrush(QBrush(fill))
            painter.setPen(QPen(color, 1.5 if not selected else 2.5))
            painter.drawPolygon(poly)
        else:
            # Polyline: no fill, thicker line
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(color, 2.0 if not selected else 3.0))
            painter.drawPolyline(poly)

        if selected:
            for i, pt in enumerate(self._points):
                if i == self._hover_handle:
                    painter.setBrush(QBrush(QColor(255, 220, 0)))
                    painter.setPen(QPen(Qt.GlobalColor.black, 1))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(color, 1.5))
                painter.drawEllipse(pt, HANDLE_R, HANDLE_R)

        if self.label and self._points:
            cx = sum(p.x() for p in self._points) / len(self._points)
            cy = sum(p.y() for p in self._points) / len(self._points)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(QPointF(cx + 1, cy + 1), self.label)
            painter.setPen(QPen(color))
            painter.drawText(QPointF(cx, cy), self.label)

    def hoverMoveEvent(self, event):
        if self.isSelected():
            idx = self.handle_at(event.pos())
            if idx != self._hover_handle:
                self._hover_handle = idx
                self.update()
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self._hover_handle = -1
        self.update()
        super().hoverLeaveEvent(event)
