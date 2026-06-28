"""PoseAnnotationItem — renders POSE keypoints and skeleton edges on the canvas."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

from annotator.ui.canvas.items.base_item import BaseAnnotationItem, _draw_label

KP_SCREEN_R = 5.0    # screen-pixel keypoint radius
KP_HIT = 9.0         # scene-unit hit radius


class PoseAnnotationItem(BaseAnnotationItem):
    """
    keypoints_scene: list of (x, y, v) in pixel coords
    skeleton_edges:  list of (i, j) index pairs (i < j)
    """

    def __init__(self, annotation_id: str,
                 keypoints_scene: list[tuple[float, float, int]],
                 skeleton_edges: list[tuple[int, int]],
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._keypoints = list(keypoints_scene)   # [(x, y, v), ...]
        self._edges = list(skeleton_edges)
        self.label = label
        self._lod: float = 1.0

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        w, h = image_size
        self.prepareGeometryChange()
        self._keypoints = [(x * w, y * h, v) for x, y, v in data.get("keypoints", [])]
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        w, h = image_size
        return {"keypoints": [[x / w, y / h, v] for x, y, v in self._keypoints]}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        visible = [(x, y) for x, y, v in self._keypoints if v > 0]
        if not visible:
            return QRectF(0, 0, 1, 1)
        xs = [p[0] for p in visible]
        ys = [p[1] for p in visible]
        m = 30.0
        return QRectF(min(xs) - m, min(ys) - m,
                      max(xs) - min(xs) + 2 * m,
                      max(ys) - min(ys) + 2 * m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        for x, y, v in self._keypoints:
            if v > 0:
                path.addEllipse(QPointF(x, y), KP_HIT, KP_HIT)
        return path

    def paint(self, painter: QPainter, option, widget=None):
        self._lod = option.levelOfDetailFromTransform(painter.worldTransform())
        kp_r = KP_SCREEN_R / self._lod

        selected = self.isSelected()
        color = QColor(self.class_color)
        lw = self.line_width + (1.0 if selected else 0.0)

        # Skeleton edges (cosmetic — constant screen-pixel width)
        edge_pen = QPen(color, lw)
        edge_pen.setCosmetic(True)
        painter.setPen(edge_pen)
        for a, b in self._edges:
            if a < len(self._keypoints) and b < len(self._keypoints):
                xa, ya, va = self._keypoints[a]
                xb, yb, vb = self._keypoints[b]
                if va > 0 and vb > 0:
                    painter.drawLine(QPointF(xa, ya), QPointF(xb, yb))

        # Keypoints
        for i, (x, y, v) in enumerate(self._keypoints):
            if v == 0:
                continue
            dot_color = QColor(self.class_color)
            dot_color.setAlpha(230 if selected else 180)
            painter.setBrush(QBrush(dot_color))
            border_pen = QPen(Qt.GlobalColor.white, 1)
            border_pen.setCosmetic(True)
            painter.setPen(border_pen)
            painter.drawEllipse(QPointF(x, y), kp_r, kp_r)
            _draw_label(painter, QPointF(x + kp_r + 2, y + kp_r / 2), str(i), color)

        if self.label and self._keypoints:
            visible = [(x, y) for x, y, v in self._keypoints if v > 0]
            if visible:
                tx = min(p[0] for p in visible)
                ty = min(p[1] for p in visible) - 4
                _draw_label(painter, QPointF(tx, ty), self.label, color)
