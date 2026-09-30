"""
SemanticAnnotationItem — renders a SEMANTIC layer straight from its PNG bitmap.

Pixel-exact (holes and every disconnected region are shown), drawn below
instance annotations. Hit-testing uses the bitmap, so clicking a painted pixel
selects the layer while clicks elsewhere fall through to what lies beneath.
No handles — the layer is edited with SemanticBrushTool.
"""
from collections import OrderedDict

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap, QPolygonF

from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _cpen, _draw_label

# Colored pixmaps keyed by (mask path, color). Mask files are immutable, and
# the scene recreates every item on each edit, so this avoids recolouring
# unchanged layers after every stroke.
_PIXMAP_CACHE: "OrderedDict[tuple[str, str], QPixmap]" = OrderedDict()
_PIXMAP_CACHE_BUDGET = 256 * 1024 * 1024   # bytes (approx. 4 B/px)


def _colored_pixmap(key: tuple[str, str], bitmap: np.ndarray, color: str) -> QPixmap:
    pix = _PIXMAP_CACHE.get(key)
    if pix is not None:
        _PIXMAP_CACHE.move_to_end(key)
        return pix
    h, w = bitmap.shape
    c = QColor(color)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[bitmap > 0] = (c.red(), c.green(), c.blue(), 255)
    raw = rgba.tobytes()   # named local keeps the buffer alive through QImage()
    img = QImage(raw, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
    pix = QPixmap.fromImage(img)
    _PIXMAP_CACHE[key] = pix
    total = sum(p.width() * p.height() * 4 for p in _PIXMAP_CACHE.values())
    while total > _PIXMAP_CACHE_BUDGET and len(_PIXMAP_CACHE) > 1:
        _, old = _PIXMAP_CACHE.popitem(last=False)
        total -= old.width() * old.height() * 4
    return pix


class SemanticAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str, bitmap: np.ndarray | None,
                 cache_key: str, image_size: tuple[int, int],
                 polygons_scene: list[list[tuple[float, float]]],
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self.label = label
        self._w, self._h = image_size
        self._bitmap = bitmap
        self._pixmap = (_colored_pixmap((cache_key, class_color), bitmap, class_color)
                        if bitmap is not None and bitmap.any() else None)
        self._polys = [QPolygonF([QPointF(x, y) for x, y in poly])
                       for poly in polygons_scene if len(poly) >= 3]

    # ── SelectTool compatibility ──────────────────────────────────────────────

    def handle_at(self, pos: QPointF) -> int:
        return -1

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        """Geometry comes from the PNG — the scene rebuilds the item instead."""

    def to_data(self, image_size: tuple[int, int]) -> dict:
        return {}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def contains(self, point: QPointF) -> bool:
        if self._bitmap is None:
            return False
        bh, bw = self._bitmap.shape
        x = int(point.x() * bw / max(1, self._w))
        y = int(point.y() * bh / max(1, self._h))
        return 0 <= x < bw and 0 <= y < bh and bool(self._bitmap[y, x])

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        for poly in self._polys:
            path.addPolygon(poly)
            path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        if self._pixmap is None:
            return
        selected = self.isSelected()
        painter.save()
        painter.setOpacity(min(1.0, self.fill_opacity * (1.8 if selected else 1.0)))
        painter.drawPixmap(QRectF(0, 0, self._w, self._h), self._pixmap,
                           QRectF(self._pixmap.rect()))
        painter.restore()

        color = QColor(self.class_color)
        if selected:
            painter.setPen(_cpen(color, self.line_width + 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for poly in self._polys:
                painter.drawPolygon(poly)
        if self.label and self._polys:
            r = self._polys[0].boundingRect()   # largest region
            _draw_label(painter, r.center(), self.label, color)
