"""BBoxAnnotationItem — renders BBOX annotations with 4 corner resize handles."""
from PyQt6.QtCore import QRectF, QPointF, Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPainterPath

from annotator.ui.canvas.items.base_item import BaseAnnotationItem

HANDLE_R = 5.0
HANDLE_HIT = 9.0


class BBoxAnnotationItem(BaseAnnotationItem):
    # Corner order: TL, TR, BR, BL
    def __init__(self, annotation_id: str, rect_scene: tuple,
                 class_color: str, label: str = "", parent=None):
        super().__init__(annotation_id, class_color, parent)
        self._x, self._y, self._w, self._h = rect_scene
        self.label = label
        self._hover_handle = -1
        self.setAcceptHoverEvents(True)

    # ── geometry accessors ────────────────────────────────────────────────────

    @property
    def rect(self) -> tuple:
        return (self._x, self._y, self._w, self._h)

    def _corners(self) -> list[QPointF]:
        x, y, w, h = self._x, self._y, self._w, self._h
        return [QPointF(x, y), QPointF(x+w, y),
                QPointF(x+w, y+h), QPointF(x, y+h)]

    def handle_at(self, pos: QPointF) -> int:
        for i, pt in enumerate(self._corners()):
            if (pt - pos).manhattanLength() <= HANDLE_HIT:
                return i
        return -1

    def move_handle(self, index: int, new_pos: QPointF):
        self.prepareGeometryChange()
        x, y, w, h = self._x, self._y, self._w, self._h
        if index == 0:    # TL → adjust x,y,w,h
            self._w = (x + w) - new_pos.x()
            self._h = (y + h) - new_pos.y()
            self._x = new_pos.x()
            self._y = new_pos.y()
        elif index == 1:  # TR
            self._w = new_pos.x() - x
            self._h = (y + h) - new_pos.y()
            self._y = new_pos.y()
        elif index == 2:  # BR
            self._w = new_pos.x() - x
            self._h = new_pos.y() - y
        elif index == 3:  # BL
            self._w = (x + w) - new_pos.x()
            self._h = new_pos.y() - y
            self._x = new_pos.x()
        self.update()

    # ── BaseAnnotationItem interface ──────────────────────────────────────────

    def update_from_data(self, data: dict, image_size: tuple[int, int]):
        iw, ih = image_size
        self.prepareGeometryChange()
        self._x = data["x"] * iw
        self._y = data["y"] * ih
        self._w = data["w"] * iw
        self._h = data["h"] * ih
        self.update()

    def to_data(self, image_size: tuple[int, int]) -> dict:
        iw, ih = image_size
        return {"x": self._x / iw, "y": self._y / ih,
                "w": self._w / iw, "h": self._h / ih}

    # ── QGraphicsItem overrides ───────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        m = HANDLE_R + 2
        return QRectF(self._x - m, self._y - m,
                      self._w + 2 * m, self._h + 2 * m)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self._x, self._y, self._w, self._h)
        return path

    def paint(self, painter: QPainter, option, widget=None):
        selected = self.isSelected()
        color = QColor(self.class_color)

        fill = QColor(color)
        fill.setAlpha(40 if not selected else 70)
        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(color, 1.5 if not selected else 2.5))
        painter.drawRect(QRectF(self._x, self._y, self._w, self._h))

        if selected:
            for i, pt in enumerate(self._corners()):
                if i == self._hover_handle:
                    painter.setBrush(QBrush(QColor(255, 220, 0)))
                    painter.setPen(QPen(Qt.GlobalColor.black, 1))
                else:
                    painter.setBrush(QBrush(Qt.GlobalColor.white))
                    painter.setPen(QPen(color, 1.5))
                painter.drawEllipse(pt, HANDLE_R, HANDLE_R)

        if self.label:
            painter.setPen(QPen(color))
            painter.drawText(QPointF(self._x + 4, self._y - 4), self.label)

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
