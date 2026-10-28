"""
MaskAnnotationItem — renders a MASK annotation straight from its PNG bitmap.

Pixel-exact like SemanticAnnotationItem: holes and every disconnected piece of
the mask are shown, and the outline follows all their edges. The stored
polygon (largest outer contour, used by YOLO Seg / LabelMe) is only a fallback
when the PNG is missing.
No vertex handles — editing is done by re-entering BrushTool / FillTool.
"""
from collections import OrderedDict

import numpy as np
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import (QPainter, QBrush, QColor, QPolygonF,
                          QPainterPath)
from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _cpen, _draw_label
from annotator.ui.canvas.items.semantic_item import _colored_pixmap

_BOUNDING_MARGIN = 20.0

# Outline polygons (bitmap pixels) keyed by mask path — mask files are immutable.
_OUTLINE_CACHE: "OrderedDict[str, list[np.ndarray]]" = OrderedDict()
_OUTLINE_CACHE_SIZE = 512


def _outline(key: str, bitmap: np.ndarray) -> list[np.ndarray]:
    """Every outer and hole contour of the mask, (N, 2) int arrays."""
    contours = _OUTLINE_CACHE.get(key)
    if contours is not None:
        _OUTLINE_CACHE.move_to_end(key)
        return contours
    import cv2
    found, _ = cv2.findContours((bitmap > 0).astype(np.uint8),
                                cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    contours = [cv2.approxPolyDP(c, 1.0, True).reshape(-1, 2)
                for c in found if len(c) >= 3]
    _OUTLINE_CACHE[key] = contours
    while len(_OUTLINE_CACHE) > _OUTLINE_CACHE_SIZE:
        _OUTLINE_CACHE.popitem(last=False)
    return contours


class MaskAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str, polygon_scene: list[tuple[float, float]],
                 class_color: str, label: str = "", parent=None,
                 bitmap: np.ndarray | None = None, cache_key: str = "",
                 image_size: tuple[int, int] = (0, 0)):
        super().__init__(annotation_id, class_color, parent)
        self._points = [QPointF(x, y) for x, y in polygon_scene]
        self.label = label
        self._bitmap = bitmap if bitmap is not None and bitmap.any() else None
        self._w, self._h = image_size
        self._pixmap = None
        self._outline = QPainterPath()
        if self._bitmap is not None:
            self._pixmap = _colored_pixmap((cache_key, class_color), self._bitmap, class_color)
            bh, bw = self._bitmap.shape
            sx, sy = self._w / bw, self._h / bh
            for c in _outline(cache_key, self._bitmap):
                self._outline.addPolygon(QPolygonF([QPointF(x * sx, y * sy) for x, y in c]))
                self._outline.closeSubpath()
            self._outline.setFillRule(Qt.FillRule.OddEvenFill)

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
        m = _BOUNDING_MARGIN
        if self._bitmap is not None:
            return self._outline.boundingRect().adjusted(-m, -m, m, m)
        if not self._points:
            return QRectF()
        xs = [p.x() for p in self._points]
        ys = [p.y() for p in self._points]
        return QRectF(min(xs) - m, min(ys) - m,
                      max(xs) - min(xs) + 2 * m,
                      max(ys) - min(ys) + 2 * m)

    def contains(self, point: QPointF) -> bool:
        if self._bitmap is None:
            return super().contains(point)
        bh, bw = self._bitmap.shape
        x = int(point.x() * bw / max(1, self._w))
        y = int(point.y() * bh / max(1, self._h))
        return 0 <= x < bw and 0 <= y < bh and bool(self._bitmap[y, x])

    def shape(self) -> QPainterPath:
        if self._bitmap is not None:
            return self._outline
        path = QPainterPath()
        if self._points:
            path.addPolygon(QPolygonF(self._points))
            path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        selected = self.isSelected()
        color = QColor(self.class_color)
        lw = self.line_width + (1.5 if selected else 0.0)

        if self._pixmap is not None:
            painter.save()
            painter.setOpacity(min(1.0, self.fill_opacity * (1.5 if selected else 1.0)))
            painter.drawPixmap(QRectF(0, 0, self._w, self._h), self._pixmap,
                               QRectF(self._pixmap.rect()))
            painter.restore()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(_cpen(color, lw, self.outline_style))
            painter.drawPath(self._outline)
        elif len(self._points) >= 3:
            fill = QColor(color)
            fill.setAlpha(int(min(255, self.fill_opacity * 255 * (1.5 if selected else 1.0))))
            painter.setBrush(QBrush(fill))
            painter.setPen(_cpen(color, lw, self.outline_style))
            painter.drawPolygon(QPolygonF(self._points))
        else:
            return

        if self.label and self._points:
            cx = sum(p.x() for p in self._points) / len(self._points)
            cy = sum(p.y() for p in self._points) / len(self._points)
            _draw_label(painter, QPointF(cx, cy), self.label, color)
