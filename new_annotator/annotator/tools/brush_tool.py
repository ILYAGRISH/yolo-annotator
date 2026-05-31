"""
BrushTool — paint binary segmentation masks with a circular brush.

Workflow:
  - Left-click / drag → draw stroke (erase in Erase mode)
  - Enter / double-click → commit mask as new MASK annotation
  - Esc                  → discard all current strokes

ToolProps:
  brush_size  (int px)       — brush radius in image pixels
  mode        (draw | erase) — draw or erase mode

Primary storage: numpy uint8 array (_mask_bitmap), dtype uint8, shape (H, W).
  white (255) = object   black (0) = background
Painting uses cv2.circle() — fast filled circles, correct for both draw and erase.

Overlay: rebuilt from _mask_bitmap after every stroke via numpy → RGBA QImage.
The bytes object is stored as a named local variable ('raw') so it stays alive
through both QImage.__init__ and QPixmap.fromImage(), preventing use-after-free.
QImage.copy() additionally forces Qt to own the buffer independently.

Re-edit behaviour:
  • If a MASK annotation is selected when Brush activates → it is loaded
    immediately into the canvas (the annotation is removed from the controller
    so it will be replaced by a fresh commit).
  • If no selection and the user's first stroke is an Erase on an empty canvas
    → the last committed MASK of the current class is loaded automatically.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import QGraphicsPixmapItem

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.tools.base import BaseTool

_OVERLAY_ALPHA = 160   # semi-transparent overlay (0-255)


class BrushTool(BaseTool):

    _DEFAULT_PARAMS: dict = {"brush_size": 20, "mode": "draw"}

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._class_id: int = 0
        self._class_color: str = "#FF4444"
        self._params: dict = dict(self._DEFAULT_PARAMS)

        self._mask_bitmap: np.ndarray | None = None   # (H, W) uint8
        self._overlay_item: QGraphicsPixmapItem | None = None
        self._painting: bool = False
        self._last_pos: QPointF | None = None
        self._has_content: bool = False
        self._img_size: tuple[int, int] = (1, 1)      # (W, H)
        self._editing_ann = None                       # original Annotation being re-edited; restored on Esc

    # ── BaseTool interface ────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "brush"

    @property
    def cursor(self):
        return Qt.CursorShape.CrossCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller
        self._refresh_class_color()
        self._init_canvas()
        self._try_load_selected_mask()   # load selected MASK annotation if any

    def deactivate(self):
        if self._editing_ann is not None and self._ctrl is not None:
            self._ctrl.add_annotation(self._editing_ann)
            self._editing_ann = None
        self._remove_overlay()
        self._mask_bitmap = None
        self._has_content = False
        self._painting = False
        self._last_pos = None
        self._scene = None
        self._ctrl = None

    def set_class(self, class_id: int):
        self._class_id = class_id
        old = self._class_color
        self._refresh_class_color()
        if old != self._class_color and self._has_content:
            self._reset_canvas()

    def get_params_schema(self) -> dict:
        return {
            "brush_size": {
                "type": "int", "label": "Brush size (px)",
                "min": 1, "max": 300, "step": 1, "default": 20,
            },
            "mode": {
                "type": "select", "label": "Mode",
                "options": ["draw", "erase"], "default": "draw",
            },
        }

    def set_params(self, params: dict):
        self._params.update(params)

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if not self._scene or button != Qt.MouseButton.LeftButton:
            return
        self._painting = True
        clamped = self._clamp(pos)
        self._last_pos = clamped
        self._paint_stroke(clamped, clamped)

    def on_move(self, pos, modifiers):
        if not self._scene or not self._painting:
            return
        clamped = self._clamp(pos)
        if self._last_pos is not None:
            self._paint_stroke(self._last_pos, clamped)
        self._last_pos = clamped

    def on_release(self, pos, modifiers, button):
        if button != Qt.MouseButton.LeftButton:
            return
        if self._painting and self._last_pos is not None:
            self._paint_stroke(self._last_pos, self._clamp(pos))
        self._painting = False
        self._last_pos = None

    def on_double_click(self, pos, modifiers, button):
        if button == Qt.MouseButton.LeftButton:
            self._commit()

    def on_key_press(self, key, modifiers):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit()
        elif key == Qt.Key.Key_Escape:
            self._reset_canvas()

    # ── canvas setup ──────────────────────────────────────────────────────────

    def _init_canvas(self):
        if not self._scene:
            return
        w, h = self._scene.image_size
        self._img_size = (w, h)
        self._mask_bitmap = np.zeros((h, w), dtype=np.uint8)

        self._overlay_item = QGraphicsPixmapItem()
        self._overlay_item.setZValue(5)
        self._scene.addItem(self._overlay_item)
        self._flush_overlay()   # set initial transparent pixmap
        self._has_content = False

    def _remove_overlay(self):
        if self._overlay_item is not None and self._scene is not None:
            if self._overlay_item.scene() is self._scene:
                self._scene.removeItem(self._overlay_item)
        self._overlay_item = None

    def _reset_canvas(self):
        if self._editing_ann is not None and self._ctrl is not None:
            self._ctrl.add_annotation(self._editing_ann)
            self._editing_ann = None
        if self._mask_bitmap is not None:
            self._mask_bitmap[:] = 0
        self._flush_overlay()
        self._has_content = False
        self._painting = False
        self._last_pos = None

    # ── painting (cv2 + numpy) ────────────────────────────────────────────────

    def _paint_stroke(self, from_pos: QPointF, to_pos: QPointF):
        if self._mask_bitmap is None:
            return
        import cv2

        r = max(1, int(self._params.get("brush_size", 20)))
        erasing = self._params.get("mode", "draw") == "erase"
        fill_val = 0 if erasing else 255

        # First erase stroke on empty canvas → auto-load last mask of this class
        if erasing and not self._mask_bitmap.any():
            if not self._load_last_mask_for_reediting():
                return   # nothing to erase and no previous mask — skip

        for pt in self._stroke_steps(from_pos, to_pos, r):
            cv2.circle(self._mask_bitmap,
                       (int(pt.x()), int(pt.y())),
                       r, fill_val, -1)   # -1 = filled

        self._flush_overlay()
        self._has_content = bool(self._mask_bitmap.any())

    @staticmethod
    def _stroke_steps(from_pos: QPointF, to_pos: QPointF,
                      r: int) -> list[QPointF]:
        """Interpolate brush positions so circles overlap and no gaps appear."""
        dx = to_pos.x() - from_pos.x()
        dy = to_pos.y() - from_pos.y()
        dist = (dx * dx + dy * dy) ** 0.5
        n = max(1, int(dist / max(r * 0.5, 1.0)))
        return [QPointF(from_pos.x() + dx * i / n,
                        from_pos.y() + dy * i / n)
                for i in range(n + 1)]

    def _clamp(self, pos: QPointF) -> QPointF:
        if not self._scene:
            return pos
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(float(w - 1), pos.x())),
                       max(0.0, min(float(h - 1), pos.y())))

    # ── re-edit: load a mask annotation back into the canvas ──────────────────

    def _try_load_selected_mask(self):
        """If a MASK annotation is currently selected in the scene, load it."""
        if self._scene is None or self._ctrl is None:
            return

        selected_item = self._scene.get_selected_item()
        if selected_item is None:
            return

        ann_id = getattr(selected_item, "annotation_id", None)
        if ann_id is None:
            return

        ann = next(
            (a for a in self._ctrl.current_annotations
             if a.id == ann_id
             and a.ann_type == AnnotationType.MASK
             and a.data.get("mask_png_path")),
            None,
        )
        if ann is None:
            return

        self._load_mask_into_canvas(ann)
        self._scene.deselect_all()

    def _load_last_mask_for_reediting(self) -> bool:
        """Load the last committed MASK of the current class on first erase stroke."""
        if self._ctrl is None:
            return False

        candidates = [
            a for a in self._ctrl.current_annotations
            if a.ann_type == AnnotationType.MASK
            and a.class_id == self._class_id
            and a.data.get("mask_png_path")
        ]
        if not candidates:
            return False

        return self._load_mask_into_canvas(candidates[-1])

    def _load_mask_into_canvas(self, ann) -> bool:
        """
        Load a MASK annotation's PNG into the canvas bitmap.
        The original annotation is removed from the scene immediately (to avoid
        double-rendering) but saved in _editing_ann so Esc can restore it.
        On commit, _editing_ann is cleared (new annotation replaces it).
        Returns True on success.
        """
        if self._ctrl is None or self._mask_bitmap is None:
            return False

        project = self._ctrl.project
        if project is None or project.project_path is None:
            return False

        from annotator.storage.mask_storage import MaskStorage
        storage = MaskStorage(project.project_path)
        loaded = storage.load_mask(ann.data.get("mask_png_path", ""))
        if loaded is None:
            return False

        if loaded.shape != self._mask_bitmap.shape:
            return False   # image size mismatch — skip silently

        self._mask_bitmap[:] = loaded
        self._has_content = bool(self._mask_bitmap.any())
        self._editing_ann = ann              # save original — restored on Esc
        self._ctrl.delete_annotation(ann.id)
        self._flush_overlay()

        if hasattr(self._ctrl, "status_message"):
            self._ctrl.status_message.emit(
                "Маска загружена для редактирования  ·  Enter = сохранить  ·  Esc = отмена")

        return True

    # ── overlay: mask_bitmap → RGBA QImage → QPixmap ─────────────────────────

    def _flush_overlay(self):
        """Rebuild colored RGBA overlay from current mask_bitmap and set pixmap.

        IMPORTANT: 'raw' must be a named local variable (not a temporary).
        QImage does not own the bytes data; if tobytes() is passed inline as a
        temporary, it is freed after QImage.__init__ returns, leaving the QImage
        with a dangling pointer before fromImage() can copy the data.
        """
        if self._overlay_item is None:
            return

        if self._mask_bitmap is None:
            w, h = self._img_size
        else:
            h, w = self._mask_bitmap.shape

        if self._mask_bitmap is None or not self._mask_bitmap.any():
            # Fast path: fully transparent pixmap
            blank = QImage(w, h, QImage.Format.Format_RGBA8888)
            blank.fill(Qt.GlobalColor.transparent)
            self._overlay_item.setPixmap(QPixmap.fromImage(blank))
            return

        color = QColor(self._class_color)
        mask_on = self._mask_bitmap > 127

        # Build fresh RGBA8888 array — erased pixels stay at 0 (transparent)
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[mask_on, 0] = color.red()
        rgba[mask_on, 1] = color.green()
        rgba[mask_on, 2] = color.blue()
        rgba[mask_on, 3] = _OVERLAY_ALPHA

        # Named variable keeps raw bytes alive through QImage.__init__.
        # .copy() forces Qt to own the pixel buffer independently.
        raw = rgba.tobytes()
        img = QImage(raw, w, h, w * 4, QImage.Format.Format_RGBA8888).copy()
        self._overlay_item.setPixmap(QPixmap.fromImage(img))

    # ── commit ────────────────────────────────────────────────────────────────

    def _commit(self):
        if not self._has_content or not self._ctrl or not self._scene:
            return

        project = self._ctrl.project
        if project is None or project.project_path is None:
            return
        current_image = self._ctrl.current_image
        if current_image is None:
            return

        w, h = self._img_size
        image_stem = Path(current_image).stem

        from annotator.storage.mask_storage import MaskStorage
        storage = MaskStorage(project.project_path)

        ann = Annotation.new(self._class_id, AnnotationType.MASK, {}, tool=self.name)
        try:
            mask_path = storage.save_mask(ann.id, image_stem, self._mask_bitmap)
            polygon   = storage.mask_to_polygon(self._mask_bitmap, w, h)
            bbox      = storage.mask_to_bbox(self._mask_bitmap, w, h)
        except Exception as exc:
            print(f"[BrushTool] mask save error: {exc}")
            return

        ann.data = {
            "mask_png_path": mask_path,
            "polygon": polygon,
            "bbox": bbox,
        }

        self._ctrl.add_annotation(ann)
        self._editing_ann = None   # original already deleted; clear before _reset_canvas
        self._reset_canvas()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _refresh_class_color(self):
        if self._ctrl and self._ctrl.project:
            cls = self._ctrl.project.get_class(self._class_id)
            if cls:
                self._class_color = cls.color
                return
        self._class_color = "#FF4444"
