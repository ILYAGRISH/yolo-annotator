"""
PoseTool — click to place keypoints, Enter/dbl-click to commit, Esc to cancel.

Workflow:
  - Left-click  → place next keypoint (v=2, visible)
  - Right-click → undo last keypoint
  - Enter / double-click → commit annotation
  - Escape → cancel

If the selected class has a skeleton defined:
  - Tool shows "Placing: <name> (N/M)" in preview label
  - Auto-commits when all N keypoints are placed

Annotation data: {"keypoints": [[x, y, v], ...]}  (normalized 0-1; v ∈ {0, 2})
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool


class PoseTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._points: list[QPointF] = []      # pixel coords, placed keypoints
        self._skeleton_names: list[str] = []  # keypoint names from class skeleton
        self._skeleton_edges: list[tuple[int, int]] = []  # (a, b) pairs, a < b
        self._temp_items: list = []

    @property
    def name(self) -> str:
        return "pose"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller
        self._load_skeleton()

    def deactivate(self):
        self._cancel()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id
        self._load_skeleton()

    # ── skeleton helpers ──────────────────────────────────────────────────────

    def _load_skeleton(self):
        self._skeleton_names = []
        self._skeleton_edges = []
        if not (self._ctrl and self._ctrl.project):
            return
        cls = self._ctrl.project.get_class(self._class_id)
        if cls is None or not cls.skeleton:
            return
        self._skeleton_names = [kp.name for kp in cls.skeleton]
        edge_set: set[tuple[int, int]] = set()
        for i, kp in enumerate(cls.skeleton):
            for j in kp.edges:
                if 0 <= j < len(cls.skeleton) and i != j:
                    edge_set.add((min(i, j), max(i, j)))
        self._skeleton_edges = sorted(edge_set)

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene:
            return
        pos = self._clamp(pos)
        if button == Qt.MouseButton.LeftButton:
            self._points.append(pos)
            # Auto-commit when all skeleton keypoints are placed
            n = len(self._skeleton_names)
            if n > 0 and len(self._points) >= n:
                self._refresh_preview()
                self._commit()
            else:
                self._refresh_preview(pos)
        elif button == Qt.MouseButton.RightButton:
            if self._points:
                self._points.pop()
                self._refresh_preview()

    def on_move(self, pos, modifiers):
        if self._scene:
            self._refresh_preview(self._clamp(pos))

    def on_release(self, pos, modifiers, button): ...

    def on_double_click(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton:
            # First press of double-click already added a point — remove it
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

    def _cancel(self):
        self._points.clear()
        self._clear_preview()

    def _commit(self):
        if not self._points or not self._ctrl or not self._scene:
            self._cancel()
            return
        w, h = self._scene.image_size
        keypoints = [[p.x() / w, p.y() / h, 2] for p in self._points]

        n = len(self._skeleton_names)
        if n > 0:
            keypoints = keypoints[:n]               # trim excess
            while len(keypoints) < n:
                keypoints.append([0.0, 0.0, 0])    # invisible placeholder

        ann = Annotation.new(
            self._class_id, AnnotationType.POSE,
            {"keypoints": keypoints}, tool=self.name)
        self._cancel()
        self._ctrl.add_annotation(ann)

    def _clear_preview(self):
        if not self._scene:
            return
        for item in self._temp_items:
            if item.scene():
                self._scene.removeItem(item)
        self._temp_items.clear()

    def _refresh_preview(self, cursor: QPointF | None = None):
        self._clear_preview()
        pts = self._points
        color = QColor("#00FF88")
        r = 5

        # Skeleton edges between already-placed keypoints
        edge_pen = QPen(color, 1.5)
        for a, b in self._skeleton_edges:
            if a < len(pts) and b < len(pts):
                ln = self._scene.addLine(
                    pts[a].x(), pts[a].y(), pts[b].x(), pts[b].y(), edge_pen)
                ln.setZValue(20)
                self._temp_items.append(ln)

        # Placed keypoints
        dot_pen = QPen(Qt.GlobalColor.white, 1)
        dot_brush = QBrush(color)
        for i, pt in enumerate(pts):
            dot = self._scene.addEllipse(
                pt.x() - r, pt.y() - r, r * 2, r * 2, dot_pen, dot_brush)
            dot.setZValue(21)
            self._temp_items.append(dot)

            short = self._skeleton_names[i][:10] if i < len(self._skeleton_names) else str(i)
            txt = self._scene.addSimpleText(short)
            txt.setPos(pt.x() + r + 2, pt.y() - r)
            txt.setBrush(QBrush(color))
            txt.setZValue(22)
            self._temp_items.append(txt)

        # Ghost indicator for next keypoint
        if cursor is not None:
            idx = len(pts)
            c_dot = self._scene.addEllipse(
                cursor.x() - r, cursor.y() - r, r * 2, r * 2,
                QPen(color, 1, Qt.PenStyle.DashLine),
                QBrush(QColor(0, 255, 136, 60)))
            c_dot.setZValue(20)
            self._temp_items.append(c_dot)

            # Ghost edge from last placed point to cursor
            if pts and self._skeleton_edges:
                last_idx = len(pts) - 1
                connects = [b for a, b in self._skeleton_edges if a == last_idx] + \
                           [a for a, b in self._skeleton_edges if b == last_idx]
                if idx in connects:
                    gl = self._scene.addLine(
                        pts[-1].x(), pts[-1].y(), cursor.x(), cursor.y(),
                        QPen(QColor(0, 255, 136, 100), 1, Qt.PenStyle.DashLine))
                    gl.setZValue(19)
                    self._temp_items.append(gl)
