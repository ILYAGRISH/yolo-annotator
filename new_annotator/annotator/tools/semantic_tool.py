"""
SemanticBrushTool — paint class regions directly (semantic segmentation mode).

The brush IS the class: every stroke of a class merges into that class's single
SEMANTIC layer on the current image — there are no per-stroke instances.

Workflow:
  - Left-click / drag → paint (or erase) a stroke; it is committed on release
  - Shift+click        → straight line from the end of the previous stroke
                         (a dashed guide shows it while Shift is held)
  - Esc while dragging → cancel the current stroke
  - Ctrl+Z             → undo the whole stroke (all touched layers at once)

ToolProps:
  brush_size  (int px)            — brush radius in image pixels
  mode        (draw | erase)      — erase unlabels pixels of EVERY semantic class
  overlap     (overwrite | keep)  — overwrite: take pixels from other classes
                                    keep: paint only into unlabeled pixels

Invariant: semantic layers of one image never overlap — each pixel belongs to
at most one semantic class. Instance annotations (MASK, SEGMENT, …) are a
separate layer and are never touched by this tool.

Storage: one AnnotationType.SEMANTIC annotation per (image, class); its PNG is
rewritten under a fresh name on every edit (see MaskStorage.save_semantic_mask),
so undo just restores the previous data dict and its still-existing file.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsPathItem

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool, BrushRing, ShiftLine

_PREVIEW_ALPHA = 140
_ERASE_PREVIEW = "#FFFFFF"


def compose_stroke(layers: dict[int, np.ndarray], stroke: np.ndarray,
                   class_id: int, mode: str = "draw",
                   overlap: str = "overwrite") -> dict[int, np.ndarray]:
    """
    Apply one stroke to the semantic layers of an image.

    layers  — {class_id: (H,W) uint8 bitmap, 0 / 255}
    stroke  — (H,W) bool, pixels covered by the brush
    Returns {class_id: new bitmap} for CHANGED layers only.
    A returned all-zero bitmap means the layer became empty.
    """
    changed: dict[int, np.ndarray] = {}
    stroke = np.asarray(stroke, dtype=bool)

    if mode == "erase":
        for cid, bmp in layers.items():
            hit = (bmp > 0) & stroke
            if hit.any():
                new = bmp.copy()
                new[hit] = 0
                changed[cid] = new
        return changed

    paint = stroke
    if overlap == "keep":
        occupied = np.zeros(stroke.shape, dtype=bool)
        for cid, bmp in layers.items():
            if cid != class_id:
                occupied |= bmp > 0
        paint = stroke & ~occupied
    if not paint.any():
        return changed

    own = layers.get(class_id)
    new_own = np.zeros(stroke.shape, dtype=np.uint8) if own is None else own.copy()
    new_own[paint] = 255
    if own is None or not np.array_equal(own, new_own):
        changed[class_id] = new_own

    if overlap != "keep":
        for cid, bmp in layers.items():
            if cid == class_id:
                continue
            hit = (bmp > 0) & paint
            if hit.any():
                new = bmp.copy()
                new[hit] = 0
                changed[cid] = new
    return changed


class SemanticBrushTool(BaseTool):

    _DEFAULT_PARAMS: dict = {"brush_size": 20, "mode": "draw", "overlap": "overwrite"}

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._class_color: str = "#FF4444"
        self._params: dict = dict(self._DEFAULT_PARAMS)

        self._stroke: np.ndarray | None = None        # (H, W) uint8, 255 = brushed
        self._preview: QGraphicsPathItem | None = None
        self._path: QPainterPath | None = None
        self._ring = BrushRing()
        self._shift = ShiftLine()                     # Shift+click straight lines
        self._last_pos: QPointF | None = None

    # ── BaseTool interface ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "semantic_brush"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller
        self._refresh_class_color()

    def deactivate(self):
        self._cancel_stroke()
        self._ring.remove()
        self._shift.reset()
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id
        self._refresh_class_color()

    def get_params_schema(self) -> dict:
        return {
            "brush_size": {
                "type": "int", "label": "Brush size (px)",
                "min": 1, "max": 500, "step": 1, "default": 20,
            },
            "mode": {
                "type": "select", "label": "Mode",
                "options": ["draw", "erase"], "default": "draw",
            },
            "overlap": {
                "type": "select", "label": "Other classes",
                "options": ["overwrite", "keep"], "default": "overwrite",
            },
        }

    def set_params(self, params: dict):
        self._params.update(params)

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene or button != Qt.MouseButton.LeftButton:
            return
        if not self._class_is_semantic():
            if self._ctrl:
                self._ctrl.status_message.emit(
                    "Semantic brush: select a class of type 'semantic'")
            return
        w, h = self._scene.image_size
        self._stroke = np.zeros((h, w), dtype=np.uint8)
        clamped = self._clamp(pos)
        start = self._shift.start_point(clamped, modifiers, self._image_key())
        self._shift.hide_guide()
        self._start_preview(start)
        self._paint_segment(start, clamped)
        self._last_pos = clamped

    def on_move(self, pos, modifiers):
        if not self._scene:
            return
        self._ring.update(self._scene, pos, self._radius())
        if self._stroke is None or self._last_pos is None:
            self._shift.update_guide(self._scene, self._clamp(pos), modifiers, self._image_key())
            return
        clamped = self._clamp(pos)
        self._paint_segment(self._last_pos, clamped)
        self._last_pos = clamped

    def on_release(self, pos, modifiers, button):
        if button != Qt.MouseButton.LeftButton or self._stroke is None:
            return
        clamped = self._clamp(pos)
        if self._last_pos is not None:
            self._paint_segment(self._last_pos, clamped)
        self._shift.set_anchor(clamped, self._image_key())
        stroke = self._stroke
        self._cancel_stroke()
        self._commit(stroke > 0)

    def on_key_press(self, key, modifiers):
        if key == Qt.Key.Key_Escape:
            self._cancel_stroke()

    # ── stroke painting ───────────────────────────────────────────────────────

    def _radius(self) -> int:
        return max(1, int(self._params.get("brush_size", 20)))

    def _paint_segment(self, a: QPointF, b: QPointF):
        import cv2

        r = self._radius()
        p0 = (int(round(a.x())), int(round(a.y())))
        p1 = (int(round(b.x())), int(round(b.y())))
        # thick cv2.line has rounded ends; the circles guarantee single clicks paint
        cv2.line(self._stroke, p0, p1, 255, thickness=2 * r + 1)
        cv2.circle(self._stroke, p0, r, 255, -1)
        cv2.circle(self._stroke, p1, r, 255, -1)
        if self._path is not None and self._preview is not None:
            self._path.lineTo(b)
            self._preview.setPath(self._path)

    def _start_preview(self, pos: QPointF):
        erasing = self._params.get("mode", "draw") == "erase"
        color = QColor(_ERASE_PREVIEW if erasing else self._class_color)
        color.setAlpha(_PREVIEW_ALPHA)
        pen = QPen(color, 2 * self._radius() + 1)     # image-pixel width, not cosmetic
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self._path = QPainterPath(pos)
        self._path.lineTo(pos + QPointF(0.01, 0))     # zero-length segment → dot
        self._preview = QGraphicsPathItem(self._path)
        self._preview.setPen(pen)
        self._preview.setZValue(5)
        self._scene.addItem(self._preview)

    def _cancel_stroke(self):
        if self._preview is not None and self._scene is not None:
            if self._preview.scene() is self._scene:
                self._scene.removeItem(self._preview)
        self._preview = None
        self._path = None
        self._stroke = None
        self._last_pos = None

    # ── commit ────────────────────────────────────────────────────────────────

    def _commit(self, stroke: np.ndarray):
        if not stroke.any() or not self._ctrl or not self._scene:
            return
        project = self._ctrl.project
        image = self._ctrl.current_image
        if project is None or project.project_path is None or image is None:
            return

        from annotator.storage.mask_storage import MaskStorage
        storage = MaskStorage(project.project_path)
        h, w = stroke.shape

        # Current layers; duplicates of one class (should not happen) are merged
        primary: dict[int, Annotation] = {}
        duplicates: list[Annotation] = []
        layers: dict[int, np.ndarray] = {}
        for ann in self._ctrl.current_annotations:
            if ann.ann_type != AnnotationType.SEMANTIC:
                continue
            bmp = self._load_layer(storage, ann, w, h)
            if ann.class_id in primary:
                duplicates.append(ann)
                layers[ann.class_id] = np.maximum(layers[ann.class_id], bmp)
            else:
                primary[ann.class_id] = ann
                layers[ann.class_id] = bmp

        changed = compose_stroke(
            layers, stroke, self._class_id,
            mode=self._params.get("mode", "draw"),
            overlap=self._params.get("overlap", "overwrite"))
        for dup in duplicates:
            changed.setdefault(dup.class_id, layers[dup.class_id])
        if not changed:
            return

        stem = Path(image).stem
        try:
            with self._ctrl.edit_group("Semantic stroke"):
                for dup in duplicates:
                    self._ctrl.delete_annotation(dup.id)
                for cid, bmp in changed.items():
                    ann = primary.get(cid)
                    if not bmp.any():
                        if ann is not None:
                            self._ctrl.delete_annotation(ann.id)
                        continue
                    geom = storage.semantic_data(stem, cid, bmp, w, h)
                    if ann is None:
                        self._ctrl.add_annotation(Annotation.new(
                            cid, AnnotationType.SEMANTIC, geom, tool=self.name))
                    else:
                        # keep attributes / subclass, replace geometry only
                        self._ctrl.update_annotation_data(
                            ann.id, {**ann.data, **geom}, "Semantic stroke")
        except Exception as exc:
            self._ctrl.status_message.emit(f"Semantic brush: save error: {exc}")

    @staticmethod
    def _load_layer(storage, ann: Annotation, w: int, h: int) -> np.ndarray:
        bmp = storage.load_mask_cached(ann.data.get("mask_png_path", ""))
        if bmp is None:
            return np.zeros((h, w), dtype=np.uint8)
        if bmp.shape != (h, w):
            import cv2
            bmp = cv2.resize(bmp, (w, h), interpolation=cv2.INTER_NEAREST)
        return bmp

    # ── helpers ───────────────────────────────────────────────────────────────

    def _image_key(self):
        return self._ctrl.current_image if self._ctrl else None

    def _class_is_semantic(self) -> bool:
        if not self._ctrl or not self._ctrl.project:
            return False
        cls = self._ctrl.project.get_class(self._class_id)
        return cls is not None and cls.annotation_type == "semantic"

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
