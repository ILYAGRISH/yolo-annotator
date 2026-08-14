"""PointAnnotationItem — renders a single point on the canvas."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _draw_label

PT_SCREEN_R = 6.0   # screen-pixel radius
PT_HIT = 10.0       # scene-unit hit radius


class PointAnnotationItem(BaseAnnotationItem):

    def __init__(self, annotation_id: str, point_scene: tuple[float, float],
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._x, self._y = point_scene
        self.label = label
        self._lod: float = 1.0

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def handle_at(self, pos: QPointF) -> int:
        hit_r = max(PT_HIT, PT_SCREEN_R * 1.5 / max(self._lod, 0.05))
        return 0 if (QPointF(self._x, self._y) - pos).manhattanLength() <= hit_r else -1

    def move_handle(self, index: int, new_pos: QPointF):
        self.prepareGeometryChange()
        self._x, self._y = new_pos.x(), new_pos.y()
        self.update()

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        w, h = image_size
        self.prepareGeometryChange()
        self._x = data["x"] * w
        self._y = data["y"] * h
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        w, h = image_size
        return {"x": self._x / w, "y": self._y / h}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        m = 20.0
        # Label is drawn in screen pixels; convert ~200px budget to scene units.
        label_w = 200.0 / max(self._lod, 0.05)
        return QRectF(self._x - m, self._y - m, m + label_w, m * 2)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addEllipse(QPointF(self._x, self._y), PT_HIT, PT_HIT)
        return path

    def paint(self, painter: QPainter, option, widget=None):
        self._lod = option.levelOfDetailFromTransform(painter.worldTransform())
        r = PT_SCREEN_R / self._lod

        selected = self.isSelected()
        color = QColor(self.class_color)
        color.setAlpha(230 if selected else 200)

        border_pen = QPen(Qt.GlobalColor.white, 1.5)
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(self._x, self._y), r, r)

        if selected:
            ring_pen = QPen(Qt.GlobalColor.white, 2.0)
            ring_pen.setCosmetic(True)
            painter.setPen(ring_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(self._x, self._y),
                                r + 4.0 / self._lod, r + 4.0 / self._lod)

        if self.label:
            _draw_label(painter, QPointF(self._x + r + 4, self._y + r / 2),
                        self.label, QColor(self.class_color))
