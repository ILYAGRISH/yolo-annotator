"""
SAM tool (7-C): click an object -> SAM mask preview -> Enter -> an annotation
of the current class.

    left click            point "this is the object"
    right click           point "this is not the object"
    left drag             box around the object (replaces the previous box)
    Enter                 accept: the mask becomes a polygon / mask / box / OBB /
                          point, by the class type (annotator.ml.convert)
    Backspace             undo the last click / box
    Esc                   clear

Requests go to the ML backend (ml_backend/handlers/sam.py). Only one is in
flight at a time: clicks made meanwhile are merged into the next request, so
fast clicking never queues stale work. The image is encoded once, when it is
opened with the tool active (sam.set_image), so the first click is fast too.
Results are written as manual annotations (tool "sam"): a person chose them.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPainterPath
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem

from annotator.ml.client import MLBackend, Reply
from annotator.ml.convert import ConvertOptions, ConvertReport, compatible, convert
from annotator.ml.strings import t
from annotator.tools.base import BaseTool

TASK = "segment"                 # a SAM mask fills the classes a segmentation model fills
_DRAG_PX = 5                     # screen pixels before a press becomes a box
_POINT_PX = 5                    # radius of a click marker on screen
_POS, _NEG = "#3aa655", "#d9534f"


class SamTool(BaseTool):

    def __init__(self, backend: MLBackend, model_path: Callable[[], str],
                 ask_model: Callable[[], str]):
        self._backend = backend
        self._model_path = model_path        # -> saved SAM weights ("" if none)
        self._ask_model = ask_model          # -> file dialog, "" if cancelled
        self._scene = None
        self._ctrl = None
        self._class_id: int | None = None
        self._params = {"simplify_px": 2.0}
        self._image: str | None = None       # image the prompts belong to
        self._points: list[tuple[float, float, int]] = []
        self._box: tuple[float, float, float, float] | None = None
        self._history: list[tuple] = []      # ("point",) | ("box", previous box)
        self._press: tuple[QPointF, object] | None = None
        self._result: dict | None = None     # sam.predict for the current prompts
        self._pending: int | None = None     # request id in flight
        self._dirty = False                  # prompts changed while a request was in flight
        self._items: list[QGraphicsItem] = []
        self._drag_item = None

    # ── BaseTool ──────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "sam"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene, self._ctrl = scene, controller
        if controller is not None:
            controller.image_changed.connect(self._on_image_changed)
            self._image = controller.current_image
        self._status(t("sam_hint"))
        self._warm()

    def deactivate(self):
        self._clear()
        if self._ctrl is not None:
            try:
                self._ctrl.image_changed.disconnect(self._on_image_changed)
            except TypeError:
                pass
        self._scene = self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id
        self._draw()                                  # preview in the new class colour

    def get_params_schema(self) -> dict:
        return {"simplify_px": {"type": "float", "min": 0.0, "max": 10.0, "step": 0.5,
                                "decimals": 1, "default": 2.0,
                                "label": "Simplify polygon, px"}}

    def set_params(self, params: dict) -> None:
        self._params.update(params)

    def on_press(self, pos, modifiers, button):
        if self._image_ok(pos):
            self._press = (QPointF(pos), button)

    def on_double_click(self, pos, modifiers, button):
        self.on_press(pos, modifiers, button)         # Qt sends no press for the 2nd click

    def on_move(self, pos, modifiers):
        if self._press is None or self._press[1] != Qt.MouseButton.LeftButton:
            return
        start = self._press[0]
        if self._dragged(start, pos):
            self._show_drag(QRectF(start, self._clamp(pos)).normalized())

    def on_release(self, pos, modifiers, button):
        if self._press is None:
            return
        start, pressed = self._press
        self._press = None
        self._hide_drag()
        if pressed != button or not self._class_ok():
            return
        if button == Qt.MouseButton.LeftButton and self._dragged(start, pos):
            r = QRectF(start, self._clamp(pos)).normalized()
            if r.width() < 2 or r.height() < 2:
                return
            self._history.append(("box", self._box))
            self._box = (r.left(), r.top(), r.right(), r.bottom())
        elif button in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            label = 1 if button == Qt.MouseButton.LeftButton else 0
            self._points.append((start.x(), start.y(), label))
            self._history.append(("point",))
        else:
            return
        self._draw()
        self._request()

    def on_key_press(self, key, modifiers):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
        elif key == Qt.Key.Key_Escape:
            self._clear()
            self._status(t("sam_hint"))
        elif key == Qt.Key.Key_Backspace:
            self.undo_prompt()

    # ── public (also used by tests) ───────────────────────────────────────────

    def undo_prompt(self) -> None:
        if not self._history:
            return
        last = self._history.pop()
        if last[0] == "point":
            self._points.pop()
        else:
            self._box = last[1]
        self._result = None if not (self._points or self._box) else self._result
        self._draw()
        self._request()

    def accept(self) -> None:
        """The current mask -> an annotation of the current class (one undo step)."""
        if self._ctrl is None:
            return
        if self._pending is not None or self._dirty:
            self._status(t("sam_wait"))
            return
        res = self._result
        if not res or not res.get("polygons"):
            self._status(t("sam_nothing"))
            return
        lc = self._current_class()
        if lc is None or not compatible(TASK, lc.annotation_type):
            self._class_ok()                          # explains why
            return
        det = {"cls": 0, "conf": res["score"], "box": res["box"], "polygons": res["polygons"]}
        if lc.annotation_type == "obb":
            det["obb"] = _min_area_rect(res["polygons"][0])
        project = self._ctrl.project
        opts = ConvertOptions(model_name=Path(self._model_path()).name,
                              simplify_px=float(self._params.get("simplify_px", 2.0)),
                              project_path=project.project_path,
                              image_stem=Path(self._image).stem, tool="sam", source="manual")
        report = ConvertReport()
        anns = convert({"width": res["width"], "height": res["height"], "task": TASK,
                        "detections": [det]}, {0: lc}, opts, report=report)
        for ann in anns:
            self._ctrl.add_annotation(ann)
        self._clear()
        if anns:
            self._status(t("sam_added", name=lc.name))
        else:
            self._status(t("sam_empty"))

    @property
    def prompts(self) -> dict:
        return {"points": list(self._points), "box": self._box}

    # ── backend ───────────────────────────────────────────────────────────────

    def _warm(self) -> None:
        """Encode the open image now, so the first click is fast."""
        model = self._model_path()
        if not self._image or not model or not Path(model).is_file():
            return
        self._status(t("sam_preparing"))
        image = self._image
        self._backend.request("sam.set_image", {"model": model, "image": image},
                              on_done=lambda r, img=image: self._on_warm(r, img))

    def _on_warm(self, r: Reply, image: str) -> None:
        if self._scene is None or image != self._image or self._points or self._box:
            return
        self._status(t("sam_ready") if r.ok else t("sam_error", kind=r.error_type, message=r.message))

    def _model(self) -> str:
        model = self._model_path()
        if model and Path(model).is_file():
            return model
        model = self._ask_model()
        if not model:
            self._status(t("sam_no_model"))
        return model

    def _request(self) -> None:
        if not (self._box or any(label for _, _, label in self._points)):
            # right clicks only refine a mask: without a left click or a box there
            # is no object yet (SAM would guess one) — wait for one
            self._result = None
            self._draw()
            if self._points:
                self._status(t("sam_need_positive"))
            return
        if self._pending is not None:
            self._dirty = True                        # sent when the current one answers
            return
        model = self._model()
        if not model:
            return
        self._dirty = False
        image = self._image
        params = {"model": model, "image": image,
                  "points": [[x, y] for x, y, _ in self._points],
                  "labels": [v for _, _, v in self._points],
                  "box": list(self._box) if self._box else None}
        self._status(t("sam_busy"))
        self._pending = self._backend.request(
            "sam.predict", params, on_done=lambda r, img=image: self._on_result(r, img))

    def _on_result(self, r: Reply, image: str) -> None:
        self._pending = None
        if self._scene is None or image != self._image:
            return                                    # tool switched off / another image
        if self._dirty:
            self._request()                           # newer prompts are waiting
            return
        if not r.ok:
            self._result = None
            self._status(t("sam_error", kind=r.error_type, message=r.message))
        else:
            self._result = r.result
            self._status(t("sam_result", score=r.result["score"], ms=r.result["ms"])
                         if r.result["polygons"] else t("sam_empty"))
        self._draw()

    # ── state ─────────────────────────────────────────────────────────────────

    def _on_image_changed(self, path: str, _anns) -> None:
        self._clear()
        self._image = path
        self._warm()

    def _clear(self) -> None:
        self._points, self._box, self._history = [], None, []
        self._result, self._press, self._dirty = None, None, False
        self._hide_drag()
        self._remove_items()

    def _current_class(self):
        if self._ctrl is None or self._ctrl.project is None or self._class_id is None:
            return None
        return self._ctrl.project.get_class(self._class_id)

    def _class_ok(self) -> bool:
        lc = self._current_class()
        if lc is None:
            self._status(t("sam_no_class"))
            return False
        if not compatible(TASK, lc.annotation_type):
            self._status(t("sam_bad_class", type=lc.annotation_type))
            return False
        return True

    def _image_ok(self, pos) -> bool:
        if self._scene is None or not self._image:
            self._status(t("sam_no_image"))
            return False
        w, h = self._scene.image_size
        return 0 <= pos.x() <= w and 0 <= pos.y() <= h

    def _clamp(self, pos) -> QPointF:
        w, h = self._scene.image_size
        return QPointF(min(max(pos.x(), 0.0), w), min(max(pos.y(), 0.0), h))

    def _dragged(self, start, pos) -> bool:
        lod = self._view_lod() or 1.0
        return max(abs(pos.x() - start.x()), abs(pos.y() - start.y())) * lod > _DRAG_PX

    def _status(self, text: str) -> None:
        if self._ctrl is not None:
            self._ctrl.status_message.emit(text)

    # ── preview ───────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        self._remove_items()
        if self._scene is None:
            return
        lc = self._current_class()
        color = QColor(lc.color if lc else "#FFD400")
        res = self._result
        if res and res.get("polygons"):
            path = QPainterPath()
            path.setFillRule(Qt.FillRule.OddEvenFill)
            for poly in res["polygons"]:
                path.moveTo(*poly[0])
                for x, y in poly[1:]:
                    path.lineTo(x, y)
                path.closeSubpath()
            fill = QColor(color)
            fill.setAlpha(90)
            self._add(self._scene.addPath(path, self._cosmetic_pen(color, 2.0), QBrush(fill)))
        if self._box:
            x1, y1, x2, y2 = self._box
            self._add(self._scene.addRect(QRectF(x1, y1, x2 - x1, y2 - y1),
                                          self._cosmetic_pen("#FFFFFF", 1.5, Qt.PenStyle.DashLine)))
        for x, y, label in self._points:
            dot = QGraphicsEllipseItem(-_POINT_PX, -_POINT_PX, 2 * _POINT_PX, 2 * _POINT_PX)
            dot.setPos(x, y)
            dot.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            dot.setBrush(QBrush(QColor(_POS if label else _NEG)))
            dot.setPen(self._cosmetic_pen("#FFFFFF", 1.5))
            self._scene.addItem(dot)
            self._add(dot)

    def _add(self, item) -> None:
        item.setZValue(30)
        self._items.append(item)

    def _remove_items(self) -> None:
        for item in self._items:
            if item.scene() is not None:
                item.scene().removeItem(item)
        self._items = []

    def _show_drag(self, rect: QRectF) -> None:
        if self._drag_item is None or self._drag_item.scene() is None:
            self._drag_item = self._scene.addRect(
                rect, self._cosmetic_pen("#FFFFFF", 1.5, Qt.PenStyle.DashLine))
            self._drag_item.setZValue(31)
        else:
            self._drag_item.setRect(rect)

    def _hide_drag(self) -> None:
        if self._drag_item is not None and self._drag_item.scene() is not None:
            self._drag_item.scene().removeItem(self._drag_item)
        self._drag_item = None


def _min_area_rect(poly) -> list[float]:
    """Tightest rotated box around a mask outline: [cx, cy, w, h, angle_rad]
    (pixels, y down — the convention of yolo.predict's "obb")."""
    import cv2
    import numpy as np
    (cx, cy), (w, h), angle = cv2.minAreaRect(np.asarray(poly, dtype=np.float32))
    return [float(cx), float(cy), float(w), float(h), math.radians(angle)]
