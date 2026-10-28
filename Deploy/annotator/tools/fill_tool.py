"""
FillTool — draw a contour, the whole enclosed area is filled ("lasso" fill).

Workflow:
  - Left-click / drag → draw a contour; a dashed line shows how it will be
                         closed. On release the end is joined to the start
                         with a straight line and everything inside is filled
                         (erased in Erase mode).
  - Esc while dragging → cancel the current contour

Every contour is saved on release — one undo step, no Enter needed.
Works with two class types (one toolbar button, the class decides):
  mask      → a new MASK annotation per contour; with a mask of this class
              selected the contour is added to it (erase: cut from it).
              Erase without a selection cuts from every mask of the class.
  semantic  → the contour goes into the class layer (see SemanticBrushTool)

ToolProps:
  brush_size  (int px)            — contour line radius in image pixels
  mode        (draw | erase)
  overlap     (overwrite | keep)  — semantic classes only

Shift+click straight lines of the brushes are not used here: a single
straight line encloses nothing.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPathItem

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool, BrushRing
from annotator.tools.semantic_tool import SemanticBrushTool

_PREVIEW_ALPHA = 140
_ERASE_PREVIEW = "#FFFFFF"


def _mask_data(storage, ann_id: str, stem: str, bitmap: np.ndarray, w: int, h: int,
               revision: bool = False) -> dict:
    """MASK annotation geometry — the same keys BrushTool writes."""
    return {"mask_png_path": storage.save_mask(ann_id, stem, bitmap, revision=revision),
            "polygon": storage.mask_to_polygon(bitmap, w, h),
            "bbox": storage.mask_to_bbox(bitmap, w, h)}


def fill_enclosed(contour: np.ndarray) -> np.ndarray:
    """
    contour — (H,W) uint8, 255 = drawn line.
    Returns (H,W) bool: the line plus every pixel it encloses, i.e. every pixel
    that can't be reached from outside the image without crossing the line.
    """
    import cv2

    h, w = contour.shape
    padded = np.zeros((h + 2, w + 2), dtype=np.uint8)   # 1-px frame: "outside"
    padded[1:-1, 1:-1] = (contour > 0) * 255
    flood_mask = np.zeros((h + 4, w + 4), dtype=np.uint8)
    cv2.floodFill(padded, flood_mask, (0, 0), 128)       # 4-connected → thin lines hold
    return padded[1:-1, 1:-1] != 128


class _Contour:
    """A contour being drawn: brushed pixels + preview path + closing guide."""

    def __init__(self, scene, start: QPointF, radius: int, color: str):
        w, h = scene.image_size
        self._scene = scene
        self._r = radius
        self.start = QPointF(start)
        self.last = QPointF(start)
        self.moved = False                               # a bare click encloses nothing
        self.bitmap = np.zeros((h, w), dtype=np.uint8)

        c = QColor(color)
        c.setAlpha(_PREVIEW_ALPHA)
        pen = QPen(c, 2 * radius + 1)                    # image-pixel width, not cosmetic
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._path = QPainterPath(self.start)
        self._path.lineTo(self.start + QPointF(0.01, 0))  # zero-length segment → dot
        self._item = QGraphicsPathItem(self._path)
        self._item.setPen(pen)
        self._item.setZValue(5)
        scene.addItem(self._item)

        self._guide = QGraphicsLineItem()
        self._guide.setPen(BaseTool._cosmetic_pen("#FFFFFF", 1.0, Qt.PenStyle.DashLine))
        self._guide.setZValue(6)
        scene.addItem(self._guide)
        self._paint(self.start, self.start)

    def add(self, pos: QPointF):
        self._paint(self.last, pos)
        self._path.lineTo(pos)
        self._item.setPath(self._path)
        self._guide.setLine(pos.x(), pos.y(), self.start.x(), self.start.y())
        self.last = QPointF(pos)
        d = pos - self.start
        self.moved = self.moved or abs(d.x()) + abs(d.y()) > max(3, self._r)

    def finish(self) -> np.ndarray:
        """Close the contour, remove the preview; returns the filled area (bool)."""
        self._paint(self.last, self.start)
        self.remove()
        return fill_enclosed(self.bitmap)

    def remove(self):
        for item in (self._item, self._guide):
            if item is not None and item.scene() is self._scene:
                self._scene.removeItem(item)
        self._item = self._guide = None

    def _paint(self, a: QPointF, b: QPointF):
        import cv2

        p0 = (int(round(a.x())), int(round(a.y())))
        p1 = (int(round(b.x())), int(round(b.y())))
        # thick cv2.line has rounded ends; the circles guarantee a single click paints
        cv2.line(self.bitmap, p0, p1, 255, thickness=2 * self._r + 1)
        cv2.circle(self.bitmap, p0, self._r, 255, -1)
        cv2.circle(self.bitmap, p1, self._r, 255, -1)


class _ContourMixin:
    """Mouse handling shared by both fills; subclasses implement _apply_fill()."""

    _contour: _Contour | None = None

    def _radius(self) -> int:
        return max(1, int(self._params.get("brush_size", 3)))

    def _preview_color(self) -> str:
        erasing = self._params.get("mode", "draw") == "erase"
        return _ERASE_PREVIEW if erasing else self._class_color

    def _can_start(self) -> bool:
        return True

    def on_press(self, pos, modifiers, button):
        if not self._scene or button != Qt.MouseButton.LeftButton:
            return
        if not self._can_start():
            return
        self._cancel_contour()
        self._contour = _Contour(self._scene, self._clamp(pos),
                                 self._radius(), self._preview_color())

    def on_move(self, pos, modifiers):
        if not self._scene:
            return
        self._ring.update(self._scene, pos, self._radius())
        if self._contour is not None:
            self._contour.add(self._clamp(pos))

    def on_release(self, pos, modifiers, button):
        if button != Qt.MouseButton.LeftButton or self._contour is None:
            return
        self._contour.add(self._clamp(pos))
        if not self._contour.moved:              # click / double click: nothing to save
            self._cancel_contour()
            return
        filled = self._contour.finish()
        self._contour = None
        self._apply_fill(filled)

    def _cancel_contour(self):
        if self._contour is not None:
            self._contour.remove()
            self._contour = None

    def _apply_fill(self, filled: np.ndarray): ...


class _MaskFill(_ContourMixin, BaseTool):
    """Fill for 'mask' classes: every contour is saved at once as MASK data."""

    _DEFAULT_PARAMS: dict = {"brush_size": 3, "mode": "draw"}

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._class_color: str = "#FF4444"
        self._params: dict = dict(self._DEFAULT_PARAMS)
        self._ring = BrushRing()

    @property
    def name(self) -> str:
        return "fill"

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller
        self._refresh_class_color()

    def deactivate(self):
        self._cancel_contour()
        self._ring.remove()
        self._scene = None
        self._ctrl = None

    def leave_image(self):
        self._cancel_contour()

    def set_class(self, class_id: int):
        self._class_id = class_id
        self._refresh_class_color()

    def set_params(self, params: dict):
        self._params.update(params)

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._cancel_contour()

    def _apply_fill(self, filled: np.ndarray):
        ctrl = self._ctrl
        if ctrl is None or ctrl.project is None or ctrl.project.project_path is None:
            return
        image = ctrl.current_image
        if image is None:
            return
        from annotator.storage.mask_storage import MaskStorage
        storage = MaskStorage(ctrl.project.project_path)
        h, w = filled.shape
        stem = Path(image).stem

        masks = [a for a in ctrl.current_annotations
                 if a.ann_type == AnnotationType.MASK and a.class_id == self._class_id
                 and a.data.get("mask_png_path")]
        selected = self._selected(masks)
        erase = self._params.get("mode", "draw") == "erase"

        new_mask = None                                   # bitmap of a new annotation
        edits: list[tuple[Annotation, np.ndarray]] = []   # (ann, new bitmap); empty → delete
        if erase:
            for ann in ([selected] if selected else masks):
                bmp = self._load(storage, ann, w, h)
                hit = (bmp > 0) & filled
                if hit.any():
                    bmp = bmp.copy()
                    bmp[hit] = 0
                    edits.append((ann, bmp))
        elif selected is not None:
            bmp = self._load(storage, selected, w, h)
            if (filled & (bmp == 0)).any():
                bmp = bmp.copy()
                bmp[filled] = 255
                edits.append((selected, bmp))
        elif filled.any():
            new_mask = filled.astype(np.uint8) * 255
        if new_mask is None and not edits:
            return

        try:
            with ctrl.edit_group("Fill"):
                for ann, bmp in edits:
                    if bmp.any():
                        geom = _mask_data(storage, ann.id, stem, bmp, w, h, revision=True)
                        ctrl.update_annotation_data(ann.id, {**ann.data, **geom}, "Fill")
                    else:
                        ctrl.delete_annotation(ann.id)
                if new_mask is not None:
                    ann = Annotation.new(self._class_id, AnnotationType.MASK, {}, tool=self.name)
                    ann.data = _mask_data(storage, ann.id, stem, new_mask, w, h)
                    ctrl.add_annotation(ann)
        except Exception as exc:
            ctrl.status_message.emit(f"Fill: save error: {exc}")

    def _selected(self, masks: list[Annotation]) -> Annotation | None:
        item = self._scene.get_selected_item() if self._scene else None
        ann_id = getattr(item, "annotation_id", None)
        return next((a for a in masks if a.id == ann_id), None)

    @staticmethod
    def _load(storage, ann: Annotation, w: int, h: int) -> np.ndarray:
        bmp = storage.load_mask(ann.data.get("mask_png_path", ""))
        if bmp is None:
            return np.zeros((h, w), dtype=np.uint8)
        if bmp.shape != (h, w):
            import cv2
            bmp = cv2.resize(bmp, (w, h), interpolation=cv2.INTER_NEAREST)
        return bmp

    def _refresh_class_color(self):
        if self._ctrl and self._ctrl.project:
            cls = self._ctrl.project.get_class(self._class_id)
            if cls:
                self._class_color = cls.color
                return
        self._class_color = "#FF4444"

    def _clamp(self, pos: QPointF) -> QPointF:
        if not self._scene:
            return pos
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(float(w - 1), pos.x())),
                       max(0.0, min(float(h - 1), pos.y())))


class _SemanticFill(_ContourMixin, SemanticBrushTool):
    """Fill for 'semantic' classes: each contour is committed to the class layer."""

    _DEFAULT_PARAMS: dict = {"brush_size": 3, "mode": "draw", "overlap": "overwrite"}

    @property
    def name(self) -> str:
        return "fill"

    def deactivate(self):
        self._cancel_contour()
        super().deactivate()

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._cancel_contour()

    def leave_image(self):
        self._cancel_contour()

    def _can_start(self) -> bool:
        if self._class_is_semantic():
            return True
        if self._ctrl:
            self._ctrl.status_message.emit("Fill: select a class of type 'mask' or 'semantic'")
        return False

    def _apply_fill(self, filled: np.ndarray):
        self._commit(filled)


class FillTool(BaseTool):
    """One toolbar tool; forwards everything to the fill matching the class type."""

    _DEFAULT_PARAMS: dict = {"brush_size": 3, "mode": "draw", "overlap": "overwrite"}

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._params: dict = dict(self._DEFAULT_PARAMS)
        self._mask = _MaskFill()
        self._semantic = _SemanticFill()
        self._active: _MaskFill | _SemanticFill | None = None

    # ── BaseTool interface ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "fill"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        # The fill is picked in set_class(), which follows activate() — the class
        # stored here may be stale.
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._switch_to(None)
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id
        if self._scene is not None:
            self._switch_to(self._delegate_for(class_id))
        if self._active is not None:
            self._active.set_class(class_id)

    def get_params_schema(self) -> dict:
        return {
            "brush_size": {
                "type": "int", "label": "Contour width (px)",
                "min": 1, "max": 100, "step": 1, "default": 3,
            },
            "mode": {
                "type": "select", "label": "Mode",
                "options": ["draw", "erase"], "default": "draw",
            },
            "overlap": {
                "type": "select", "label": "Other classes (semantic)",
                "options": ["overwrite", "keep"], "default": "overwrite",
            },
        }

    def set_params(self, params: dict):
        self._params.update(params)
        self._mask.set_params(params)
        self._semantic.set_params(params)

    # ── events → active fill ──────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if self._current() is not None:
            self._active.on_press(pos, modifiers, button)

    def on_move(self, pos, modifiers):
        if self._current() is not None:
            self._active.on_move(pos, modifiers)

    def on_release(self, pos, modifiers, button):
        if self._current() is not None:
            self._active.on_release(pos, modifiers, button)

    def on_double_click(self, pos, modifiers, button):
        if self._current() is not None:
            self._active.on_double_click(pos, modifiers, button)

    def on_key_press(self, key, modifiers):
        if self._current() is not None:
            self._active.on_key_press(key, modifiers)

    def leave_image(self):
        if self._active is not None:
            self._active.leave_image()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _current(self):
        """Active fill; picked on first use when set_class() was never called."""
        if self._active is None and self._scene is not None:
            self._switch_to(self._delegate_for(self._class_id))
        return self._active

    def _delegate_for(self, class_id: int):
        cls = None
        if self._ctrl and self._ctrl.project:
            cls = self._ctrl.project.get_class(class_id)
        semantic = cls is not None and cls.annotation_type == "semantic"
        return self._semantic if semantic else self._mask

    def _switch_to(self, delegate):
        if delegate is self._active:
            return
        if self._active is not None:
            self._active.deactivate()
        self._active = delegate
        if delegate is not None:
            delegate.set_class(self._class_id)
            delegate.activate(self._scene, self._ctrl)
