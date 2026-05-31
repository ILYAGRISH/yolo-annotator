from PyQt6.QtWidgets import QGraphicsItem
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF, QPainterPath

HANDLE_R = 5.0
HANDLE_HIT = 9.0


class PolygonAnnotationItem(QGraphicsItem):

    def __init__(self, points_scene, class_id: int, color: str, label: str = "", parent=None):
        super().__init__(parent)
        self._points = [QPointF(x, y) for x, y in points_scene]
        self.class_id = class_id
        self.color = QColor(color)
        self.label = label
        self._hover_handle = -1
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

    # ── public ──────────────────────────────────────────────────────────────

    @property
    def points(self) -> list:
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

    def update_color(self, color: str):
        self.color = QColor(color)
        self.update()

    # ── QGraphicsItem overrides ──────────────────────────────────────────────

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
            path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        if len(self._points) < 2:
            return

        selected = self.isSelected()
        poly = QPolygonF(self._points)

        fill = QColor(self.color)
        fill.setAlpha(55 if not selected else 90)
        painter.setBrush(QBrush(fill))

        pen = QPen(self.color, 1.5 if not selected else 2.5)
        painter.setPen(pen)
        painter.drawPolygon(poly)

        if selected:
            for i, pt in enumerate(self._points):
                if i == self._hover_handle:
                    painter.setBrush(QBrush(QColor(255, 220, 0)))
                    painter.setPen(QPen(Qt.GlobalColor.black, 1))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(self.color, 1.5))
                painter.drawEllipse(pt, HANDLE_R, HANDLE_R)

        if self.label and self._points:
            cx = sum(p.x() for p in self._points) / len(self._points)
            cy = sum(p.y() for p in self._points) / len(self._points)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(QPointF(cx + 1, cy + 1), self.label)
            painter.setPen(QPen(self.color))
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
