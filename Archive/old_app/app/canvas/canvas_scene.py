from enum import Enum

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPen, QBrush, QColor, QPolygonF
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem

from app.canvas.items.polygon_item import PolygonAnnotationItem
from app.models.annotation import SegmentAnnotation

_PALETTE = [
    "#FF4444", "#44DD44", "#4488FF", "#FFDD00",
    "#FF44FF", "#00DDDD", "#FF8800", "#8844FF",
    "#44FF99", "#FF4499", "#99FF44", "#4499FF",
]

CLOSE_THRESHOLD = 12  # scene pixels to snap-close polygon


class ToolMode(Enum):
    SELECT = "select"
    POLYGON = "polygon"


class AnnotationScene(QGraphicsScene):
    annotation_added = pyqtSignal(object)   # SegmentAnnotation
    annotation_deleted = pyqtSignal()
    annotation_selected = pyqtSignal(int)   # index in _items, -1 = none
    annotations_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = ToolMode.SELECT
        self._current_class_id = 0
        self._classes = []
        self._image_item: QGraphicsPixmapItem | None = None
        self._image_size = (1, 1)
        self._annotations: list[SegmentAnnotation] = []
        self._items: list[PolygonAnnotationItem] = []

        # Drawing state
        self._draw_pts: list[QPointF] = []
        self._prev_lines = []
        self._prev_dots = []
        self._prev_cursor = None

        # Vertex drag state
        self._drag_item: PolygonAnnotationItem | None = None
        self._drag_handle = -1

    # ── public API ───────────────────────────────────────────────────────────

    @property
    def mode(self) -> ToolMode:
        return self._mode

    @property
    def annotations(self) -> list:
        return self._annotations

    def set_mode(self, mode: ToolMode):
        self._cancel_draw()
        self._mode = mode

    def set_classes(self, classes: list):
        self._classes = classes
        # Refresh colors on existing items
        for i, item in enumerate(self._items):
            if i < len(self._annotations):
                item.color = QColor(self._color_for(self._annotations[i].class_id))
                item.label = self._label_for(self._annotations[i].class_id)
                item.update()

    def set_current_class(self, class_id: int):
        self._current_class_id = class_id

    def load_image(self, path: str) -> bool:
        self.clear()
        self._image_item = None
        self._items = []
        self._annotations = []
        self._draw_pts = []
        self._prev_lines = []
        self._prev_dots = []
        self._prev_cursor = None
        self._drag_item = None

        pix = QPixmap(path)
        if pix.isNull():
            return False
        self._image_size = (pix.width(), pix.height())
        self._image_item = QGraphicsPixmapItem(pix)
        self._image_item.setZValue(-1)
        self.addItem(self._image_item)
        self.setSceneRect(0, 0, pix.width(), pix.height())
        return True

    def load_annotations(self, annotations: list):
        for item in self._items:
            self.removeItem(item)
        self._items = []
        self._annotations = list(annotations)
        for ann in self._annotations:
            item = self._make_item(ann)
            self.addItem(item)
            self._items.append(item)

    def save_annotations(self) -> list:
        return list(self._annotations)

    def delete_selected(self):
        changed = False
        for item in list(self.selectedItems()):
            if item in self._items:
                idx = self._items.index(item)
                self._items.pop(idx)
                self._annotations.pop(idx)
                self.removeItem(item)
                changed = True
        if changed:
            self.annotation_deleted.emit()
            self.annotations_changed.emit()

    def cancel_current_polygon(self):
        self._cancel_draw()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _color_for(self, class_id: int) -> str:
        for cls in self._classes:
            if cls.id == class_id:
                return cls.color
        return _PALETTE[class_id % len(_PALETTE)]

    def _label_for(self, class_id: int) -> str:
        for cls in self._classes:
            if cls.id == class_id:
                return cls.name
        return str(class_id)

    def _make_item(self, ann: SegmentAnnotation) -> PolygonAnnotationItem:
        w, h = self._image_size
        pts = [(x * w, y * h) for x, y in ann.points]
        return PolygonAnnotationItem(pts, ann.class_id,
                                     self._color_for(ann.class_id),
                                     self._label_for(ann.class_id))

    def _clamp(self, pos: QPointF) -> QPointF:
        w, h = self._image_size
        return QPointF(max(0.0, min(w, pos.x())), max(0.0, min(h, pos.y())))

    def _norm(self, pos: QPointF):
        w, h = self._image_size
        return (max(0.0, min(1.0, pos.x() / w)), max(0.0, min(1.0, pos.y() / h)))

    def _near_first(self, pos: QPointF) -> bool:
        if not self._draw_pts:
            return False
        return (self._draw_pts[0] - pos).manhattanLength() <= CLOSE_THRESHOLD

    # ── drawing preview ───────────────────────────────────────────────────────

    def _clear_preview(self):
        for it in self._prev_lines + self._prev_dots:
            if it.scene() is self:
                self.removeItem(it)
        self._prev_lines = []
        self._prev_dots = []
        if self._prev_cursor and self._prev_cursor.scene() is self:
            self.removeItem(self._prev_cursor)
        self._prev_cursor = None

    def _update_preview(self, cursor: QPointF | None = None):
        self._clear_preview()
        pts = self._draw_pts
        if not pts:
            return

        dash = QPen(QColor("#FFFF00"), 1.5, Qt.PenStyle.DashLine)
        solid = QPen(QColor("#FFFF00"), 1.5)
        white = QBrush(QColor("white"))
        yellow = QBrush(QColor("#FFFF00"))
        r = 4

        for i in range(len(pts) - 1):
            ln = self.addLine(pts[i].x(), pts[i].y(), pts[i+1].x(), pts[i+1].y(), dash)
            ln.setZValue(20)
            self._prev_lines.append(ln)

        if cursor is not None:
            last = pts[-1]
            cl = self.addLine(last.x(), last.y(), cursor.x(), cursor.y(),
                              QPen(QColor(255, 255, 0, 120), 1, Qt.PenStyle.DashLine))
            cl.setZValue(20)
            self._prev_cursor = cl

        for i, pt in enumerate(pts):
            dot = self.addEllipse(pt.x() - r, pt.y() - r, r * 2, r * 2,
                                  solid, yellow if i == 0 else white)
            dot.setZValue(21)
            self._prev_dots.append(dot)

    def _cancel_draw(self):
        self._draw_pts.clear()
        self._clear_preview()

    def _close_polygon(self):
        if len(self._draw_pts) < 3:
            return
        pts_norm = [self._norm(p) for p in self._draw_pts]
        ann = SegmentAnnotation(class_id=self._current_class_id, points=pts_norm)
        self._cancel_draw()
        self._annotations.append(ann)
        item = self._make_item(ann)
        self.addItem(item)
        self._items.append(item)
        self.annotation_added.emit(ann)
        self.annotations_changed.emit()

    # ── mouse events ─────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        pos = self._clamp(event.scenePos())

        if self._mode == ToolMode.POLYGON:
            if event.button() == Qt.MouseButton.LeftButton:
                if len(self._draw_pts) >= 3 and self._near_first(pos):
                    self._close_polygon()
                else:
                    self._draw_pts.append(pos)
                    self._update_preview(pos)
            elif event.button() == Qt.MouseButton.RightButton:
                if self._draw_pts:
                    self._draw_pts.pop()
                    self._update_preview()
            return

        if self._mode == ToolMode.SELECT:
            if event.button() == Qt.MouseButton.LeftButton:
                for item in self._items:
                    if item.isSelected():
                        h = item.handle_at(pos)
                        if h >= 0:
                            self._drag_item = item
                            self._drag_handle = h
                            return
                super().mousePressEvent(event)
                sel = self.selectedItems()
                if sel and sel[0] in self._items:
                    self.annotation_selected.emit(self._items.index(sel[0]))
                else:
                    self.annotation_selected.emit(-1)
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = self._clamp(event.scenePos())

        if self._mode == ToolMode.POLYGON:
            if self._draw_pts:
                self._update_preview(pos)
            return

        if self._mode == ToolMode.SELECT and self._drag_item is not None:
            self._drag_item.move_vertex(self._drag_handle, pos)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mode == ToolMode.SELECT and self._drag_item is not None:
            item = self._drag_item
            idx = self._items.index(item)
            w, h = self._image_size
            new_pts = [(p.x() / w, p.y() / h) for p in item.points]
            self._annotations[idx] = SegmentAnnotation(
                class_id=self._annotations[idx].class_id,
                points=new_pts,
            )
            self._drag_item = None
            self._drag_handle = -1
            self.annotations_changed.emit()
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._mode == ToolMode.POLYGON and event.button() == Qt.MouseButton.LeftButton:
            # Second press of double-click already added a duplicate point; remove it
            if self._draw_pts:
                self._draw_pts.pop()
            self._close_polygon()
            return
        super().mouseDoubleClickEvent(event)
