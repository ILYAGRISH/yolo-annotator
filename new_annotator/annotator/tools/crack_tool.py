"""
CrackTool — draws a polyline and converts it to a buffered polygon (SEGMENT).

Workflow:
  1. Click to add polyline points.
  2. Preview shows: dashed orange polyline + semi-transparent buffered polygon.
  3. Double-click or Enter to commit.
  4. RMB removes the last point.  Escape cancels.

Result annotation:
  ann_type = SEGMENT
  data = {
    "points": [[x,y], ...],          # buffered polygon (normalized)
    "source_geometry": {              # original polyline (for re-editing)
        "type": "polyline",
        "points": [[x,y], ...]
    },
    "tool_params": {                  # buffer parameters used
        "buffer_width": 0.008,
        "cap_style": "round",
        "join_style": "round",
        "simplify": 0.001,
    }
  }
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPen, QBrush, QColor, QPolygonF

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool

MIN_PTS = 2  # minimum polyline points to commit


def _buffer_polyline(norm_pts: list, params: dict, image_size: tuple) -> list:
    """
    Buffer a normalized polyline with shapely and return normalized polygon points.
    Returns [] on failure or degenerate geometry.
    """
    try:
        from shapely.geometry import LineString
    except ImportError:
        return []

    w, h = image_size
    pts_px = [(x * w, y * h) for x, y in norm_pts]
    if len(pts_px) < 2:
        return []

    line = LineString(pts_px)
    buf_px = params.get("buffer_width", 0.008) * min(w, h)
    cap_map = {"round": 1, "flat": 2, "square": 3}
    join_map = {"round": 1, "mitre": 2, "bevel": 3}

    try:
        poly = line.buffer(
            buf_px,
            cap_style=cap_map.get(params.get("cap_style", "round"), 1),
            join_style=join_map.get(params.get("join_style", "round"), 1),
        )
        tol = params.get("simplify", 0.001)
        if tol > 0:
            poly = poly.simplify(tol * min(w, h), preserve_topology=True)
    except Exception:
        return []

    if poly is None or poly.is_empty:
        return []

    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda p: p.area)
    if poly.geom_type != "Polygon":
        return []

    return [[x / w, y / h] for x, y in poly.exterior.coords]


class CrackTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id = 0
        self._points: list[QPointF] = []
        self._cursor_pos: QPointF | None = None
        self._temp_items: list = []
        self._params: dict = {
            "buffer_width": 0.008,
            "cap_style": "round",
            "join_style": "round",
            "simplify": 0.001,
        }
        self._edit_ann = None   # Annotation being edited (None = create mode)

    @property
    def name(self) -> str:
        return "crack_tool"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def get_params_schema(self) -> dict:
        return {
            "buffer_width": {
                "type": "float", "min": 0.001, "max": 0.10,
                "step": 0.001, "decimals": 3,
                "default": 0.008, "label": "Buffer width",
            },
            "cap_style": {
                "type": "select",
                "options": ["round", "flat", "square"],
                "default": "round", "label": "Cap style",
            },
            "join_style": {
                "type": "select",
                "options": ["round", "mitre", "bevel"],
                "default": "round", "label": "Join style",
            },
            "simplify": {
                "type": "float", "min": 0.0, "max": 0.01,
                "step": 0.0005, "decimals": 4,
                "default": 0.001, "label": "Simplify",
            },
        }

    def set_params(self, params: dict) -> None:
        self._params.update(params)
        self._refresh_preview(self._cursor_pos)

    # ── BaseTool lifecycle ────────────────────────────────────────────────────

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._cancel()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id

    @property
    def is_editing(self) -> bool:
        """True when editing an existing annotation's source polyline."""
        return self._edit_ann is not None

    def start_edit(self, ann) -> None:
        """
        Load an existing crack annotation for source-line editing.
        Must be called after activate(). The user edits the source polyline
        in place; Enter/double-click recomputes the buffer and updates the
        annotation via update_annotation_data (undo-able).
        """
        if not self._scene:
            return
        src = ann.data.get("source_geometry", {})
        norm_pts = src.get("points", [])
        if not norm_pts:
            return
        w, h = self._scene.image_size
        self._edit_ann = ann
        self._points = [QPointF(x * w, y * h) for x, y in norm_pts]
        # Restore tool params from the annotation so preview matches original
        stored = ann.data.get("tool_params", {})
        if stored:
            self._params.update(stored)
        self._refresh_preview(None)

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene:
            return
        pos = self._clamp(pos)
        if button == Qt.MouseButton.LeftButton:
            self._points.append(pos)
            self._refresh_preview(pos)
        elif button == Qt.MouseButton.RightButton:
            if self._points:
                self._points.pop()
                self._refresh_preview(self._cursor_pos)

    def on_move(self, pos, modifiers):
        if not self._scene:
            return
        self._cursor_pos = self._clamp(pos)
        if self._points:
            self._refresh_preview(self._cursor_pos)

    def on_release(self, pos, modifiers, button): ...

    def on_double_click(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton:
            # The single-click of the double-click already added a point — remove it
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
        self._cursor_pos = None
        self._edit_ann = None
        self._clear_preview()

    def _commit(self):
        if len(self._points) < MIN_PTS or not self._ctrl or not self._scene:
            self._cancel()
            return

        w, h = self._scene.image_size
        norm_src = [[p.x() / w, p.y() / h] for p in self._points]
        poly_pts = _buffer_polyline(norm_src, self._params, (w, h))

        if not poly_pts:
            self._cancel()
            return

        if self._edit_ann is not None:
            # Update existing annotation (undo-able)
            new_data = {
                **self._edit_ann.data,
                "points": poly_pts,
                "source_geometry": {"type": "polyline", "points": norm_src},
                "tool_params": dict(self._params),
            }
            edit_id = self._edit_ann.id
            self._cancel()
            self._ctrl.update_annotation_data(
                edit_id, new_data, "Edit crack source")
        else:
            ann = Annotation.new(
                self._class_id,
                AnnotationType.SEGMENT,
                {
                    "points": poly_pts,
                    "source_geometry": {"type": "polyline", "points": norm_src},
                    "tool_params": dict(self._params),
                },
                tool="crack_tool",
            )
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
        if not pts:
            return

        orange_dash = QPen(QColor("#FFAA00"), 1.5, Qt.PenStyle.DashLine)
        orange_solid = QPen(QColor("#FFAA00"), 1.5)
        dot_r = 3

        # Draw committed segments
        for i in range(len(pts) - 1):
            ln = self._scene.addLine(
                pts[i].x(), pts[i].y(), pts[i+1].x(), pts[i+1].y(), orange_dash)
            ln.setZValue(20)
            self._temp_items.append(ln)

        # Rubber-band line to cursor
        if cursor is not None:
            cl = self._scene.addLine(
                pts[-1].x(), pts[-1].y(), cursor.x(), cursor.y(),
                QPen(QColor(255, 170, 0, 120), 1, Qt.PenStyle.DashLine))
            cl.setZValue(20)
            self._temp_items.append(cl)

        # Vertex dots
        for pt in pts:
            dot = self._scene.addEllipse(
                pt.x() - dot_r, pt.y() - dot_r, dot_r*2, dot_r*2,
                orange_solid, QBrush(QColor("#FFAA00")))
            dot.setZValue(21)
            self._temp_items.append(dot)

        # Buffered polygon preview (only when >= 2 pts)
        if len(pts) >= MIN_PTS:
            src = pts + ([cursor] if cursor is not None else [])
            w, h = self._scene.image_size
            norm_src = [[p.x() / w, p.y() / h] for p in src]
            poly_pts = _buffer_polyline(norm_src, self._params, (w, h))
            if poly_pts:
                qpoly = QPolygonF([QPointF(x * w, y * h) for x, y in poly_pts])
                filled = self._scene.addPolygon(
                    qpoly,
                    QPen(QColor("#FFAA00"), 1),
                    QBrush(QColor(255, 170, 0, 55)),
                )
                filled.setZValue(19)
                self._temp_items.append(filled)
