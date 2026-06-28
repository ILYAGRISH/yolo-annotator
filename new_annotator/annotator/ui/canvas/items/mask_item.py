"""
MaskAnnotationItem — renders a MASK annotation as a filled polygon contour.

Masks are painted with BrushTool and stored as PNG bitmaps.
The polygon field (extracted from the bitmap contour) is what gets rendered.
No vertex handles — editing is done by re-entering BrushTool, not by dragging vertices.
"""
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPolygonF,
                          QPainterPath)
from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _cpen, _draw_label

_BOUNDING_MARGIN = 20.0


class MaskAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str, polygon_scene: list[tuple[float, float]],
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._points = [QPointF(x, y) for x, y in polygon_scene]
        self.label = label

    # ── SelectTool compatibility ──────────────────────────────────────────────

    def handle_at(self, pos: QPointF) -> int:
        """Masks have no draggable vertex handles."""
        return -1

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        w, h = image_size
        self.prepareGeometryChange()
        self._points = [QPointF(x * w, y * h)
                        for x, y in data.get("polygon", [])]
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        w, h = image_size
        return {"polygon": [[p.x() / w, p.y() / h] for p in self._points]}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        if not self._points:
            return QRectF()
        xs = [p.x() for p in self._points]
        ys = [p.y() for p in self._points]
        m = _BOUNDING_MARGIN
        return QRectF(min(xs) - m, min(ys) - m,
                      max(xs) - min(xs) + 2 * m,
                      max(ys) - min(ys) + 2 * m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if self._points:
            path.addPolygon(QPolygonF(self._points))
            path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        if len(self._points) < 3:
            return

        selected = self.isSelected()
        color = QColor(self.class_color)
        poly = QPolygonF(self._points)

        alpha = int(min(255, self.fill_opacity * 255 * (1.5 if selected else 1.0)))
        fill = QColor(color)
        fill.setAlpha(alpha)
        lw = self.line_width + (1.5 if selected else 0.0)

        painter.setBrush(QBrush(fill))
        painter.setPen(_cpen(color, lw))
        painter.drawPolygon(poly)

        if self.label and self._points:
            cx = sum(p.x() for p in self._points) / len(self._points)
            cy = sum(p.y() for p in self._points) / len(self._points)
            _draw_label(painter, QPointF(cx, cy), self.label, color)
