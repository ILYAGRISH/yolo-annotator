"""
PolygonTool — click to add vertices, close by clicking first point or double-click.
PolylineTool — same mechanics but produces an open POLYLINE annotation.
"""
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool

CLOSE_THRESHOLD_SCREEN = 15  # screen pixels (dynamically converted to scene units)


class PolygonTool(BaseTool):

    _ANN_TYPE = AnnotationType.SEGMENT
    _MIN_PTS = 3

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id = 0
        self._points: list[QPointF] = []
        self._temp_items: list = []
        self._cursor_line = None

    @property
    def name(self) -> str:
        return "polygon"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._cancel()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene:
            return
        pos = self._clamp(pos)
        if button == Qt.MouseButton.LeftButton:
            if len(self._points) >= self._MIN_PTS and self._near_first(pos):
                self._commit()
            else:
                self._points.append(pos)
                self._refresh_preview(pos)
        elif button == Qt.MouseButton.RightButton:
            if self._points:
                self._points.pop()
                self._refresh_preview()

    def on_move(self, pos, modifiers):
        if self._points and self._scene:
            self._refresh_preview(self._clamp(pos))

    def on_release(self, pos, modifiers, button): ...

    def on_double_click(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton:
            # First press of double-click already added a duplicate — remove it
            if self._points:
                self._points.pop()
            self._commit()

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._cancel()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit()

    # ── internal ──────────────────────────────────────────────────────────────

    def _clamp(self, pos: QPointF) -> QPointF:
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(w, pos.x())), max(0.0, min(h, pos.y())))

    def _near_first(self, pos: QPointF) -> bool:
        lod = self._view_lod()
        threshold = max(8.0, min(60.0, CLOSE_THRESHOLD_SCREEN / max(lod, 0.05)))
        return (self._points[0] - pos).manhattanLength() <= threshold

    def _cancel(self):
        self._points.clear()
        self._clear_preview()

    def _commit(self):
        if len(self._points) < self._MIN_PTS:
            self._cancel()
            return
        if not self._ctrl or not self._scene:
            self._cancel()
            return
        w, h = self._scene.image_size
        pts = [[p.x() / w, p.y() / h] for p in self._points]
        ann = Annotation.new(self._class_id, self._ANN_TYPE,
                             {"points": pts}, tool=self.name)
        self._cancel()
        self._ctrl.add_annotation(ann)

    def _clear_preview(self):
        if not self._scene:
            return
        for item in self._temp_items:
            if item.scene():
                self._scene.removeItem(item)
        self._temp_items.clear()
        if self._cursor_line and self._cursor_line.scene():
            self._scene.removeItem(self._cursor_line)
        self._cursor_line = None

    def _refresh_preview(self, cursor: QPointF | None = None):
        self._clear_preview()
        pts = self._points
        if not pts:
            return

        lod = self._view_lod()
        dot_r = 5.0 / max(lod, 0.05)       # 5 screen-pixel dot
        snap_r = 11.0 / max(lod, 0.05)     # 11 screen-pixel snap ring

        dash = self._cosmetic_pen("#FFFF00", 1.5, Qt.PenStyle.DashLine)
        solid = self._cosmetic_pen("#FFFF00", 1.5)

        for i in range(len(pts) - 1):
            ln = self._scene.addLine(
                pts[i].x(), pts[i].y(), pts[i+1].x(), pts[i+1].y(), dash)
            ln.setZValue(20)
            self._temp_items.append(ln)

        if cursor is not None:
            cursor_pen = self._cosmetic_pen("#FFFF00", 1.0, Qt.PenStyle.DashLine)
            cursor_pen.setColor(QColor(255, 255, 0, 120))
            cl = self._scene.addLine(
                pts[-1].x(), pts[-1].y(), cursor.x(), cursor.y(), cursor_pen)
            cl.setZValue(20)
            self._cursor_line = cl

            # Snap indicator: bright ring around first point
            if len(pts) >= self._MIN_PTS and self._near_first(cursor):
                snap_pen = self._cosmetic_pen("#FFFF00", 2.5)
                snap = self._scene.addEllipse(
                    pts[0].x() - snap_r, pts[0].y() - snap_r,
                    snap_r * 2, snap_r * 2,
                    snap_pen,
                    QBrush(QColor(255, 255, 0, 70)))
                snap.setZValue(22)
                self._temp_items.append(snap)

        yellow = QBrush(QColor("#FFFF00"))
        white = QBrush(QColor("white"))
        for i, pt in enumerate(pts):
            dot = self._scene.addEllipse(
                pt.x() - dot_r, pt.y() - dot_r, dot_r * 2, dot_r * 2,
                solid,
                yellow if i == 0 else white)
            dot.setZValue(21)
            self._temp_items.append(dot)


class PolylineTool(PolygonTool):
    """Same as PolygonTool but creates an open POLYLINE annotation."""

    _ANN_TYPE = AnnotationType.POLYLINE
    _MIN_PTS = 2

    @property
    def name(self) -> str:
        return "polyline"

    def on_press(self, pos, modifiers, button):
        # No snap-to-first for polylines — press Enter or double-click to finish
        if not self._scene:
            return
        pos = self._clamp(pos)
        if button == Qt.MouseButton.LeftButton:
            self._points.append(pos)
            self._refresh_preview(pos)
        elif button == Qt.MouseButton.RightButton:
            if self._points:
                self._points.pop()
                self._refresh_preview()
