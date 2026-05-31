"""
AnnotationScene — QGraphicsScene that:
  1. Displays one image + annotation items.
  2. Delegates all mouse/key events to the active BaseTool.
  3. Rebuilds annotation items on demand from domain data.

The scene knows nothing about save/load/undo — that's the controller's job.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsPixmapItem, QGraphicsTextItem

from annotator.tools.base import BaseTool
from annotator.tools.select_tool import SelectTool


class AnnotationScene(QGraphicsScene):
    annotations_changed = pyqtSignal()   # reserved for future direct-scene edits

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_item: QGraphicsPixmapItem | None = None
        self._image_size: tuple[int, int] = (1, 1)
        self._active_tool: BaseTool = SelectTool()
        # ann_id → BaseAnnotationItem
        self._ann_items: dict[str, object] = {}
        self._selected_item = None
        self._placeholder: QGraphicsTextItem | None = None
        self._project = None
        self._show_placeholder()

    # ── public read-only properties ───────────────────────────────────────────

    @property
    def active_tool(self) -> BaseTool:
        return self._active_tool

    @property
    def image_size(self) -> tuple[int, int]:
        return self._image_size

    # ── tool management ───────────────────────────────────────────────────────

    def set_tool(self, tool: BaseTool, controller=None):
        self._active_tool.deactivate()
        self._active_tool = tool
        self._active_tool.activate(self, controller)

    # ── image management ──────────────────────────────────────────────────────

    def load_image(self, path: str) -> bool:
        self._remove_placeholder()
        if self._image_item:
            self.removeItem(self._image_item)
            self._image_item = None

        pix = QPixmap(path)
        if pix.isNull():
            self._show_placeholder(f"Cannot load:\n{path}")
            return False

        self._image_size = (pix.width(), pix.height())
        self._image_item = QGraphicsPixmapItem(pix)
        self._image_item.setZValue(-1)
        self.addItem(self._image_item)
        self.setSceneRect(0, 0, pix.width(), pix.height())
        return True

    def clear_image(self):
        if self._image_item:
            self.removeItem(self._image_item)
            self._image_item = None
        self._clear_ann_items()
        self._show_placeholder()

    # ── annotation items ──────────────────────────────────────────────────────

    def rebuild_annotations(self, annotations: list, project):
        """
        Rebuild all annotation graphics items from domain Annotation objects.
        Called by the main window whenever the controller emits annotations_changed.
        """
        self._project = project
        # Remember selected id across rebuild
        prev_selected_id = (self._selected_item.annotation_id
                            if self._selected_item else None)
        self._clear_ann_items()

        for ann in annotations:
            item = self._make_item(ann, project)
            if item is None:
                continue
            item.setZValue(1)
            self.addItem(item)
            self._ann_items[ann.id] = item
            if ann.id == prev_selected_id:
                item.setSelected(True)
                self._selected_item = item

    def _make_item(self, ann, project):
        from annotator.domain.annotation import AnnotationType
        from annotator.ui.canvas.items.bbox_item import BBoxAnnotationItem
        from annotator.ui.canvas.items.obb_item import OBBAnnotationItem
        from annotator.ui.canvas.items.point_item import PointAnnotationItem
        from annotator.ui.canvas.items.polygon_item import PolygonAnnotationItem
        from annotator.ui.canvas.items.pose_item import PoseAnnotationItem

        color, label = "#AAAAAA", str(ann.class_id)
        cls = None
        if project:
            cls = project.get_class(ann.class_id)
            if cls:
                color, label = cls.color, cls.name

        w, h = self._image_size
        item = None

        if ann.ann_type == AnnotationType.SEGMENT:
            pts = [(x * w, y * h) for x, y in ann.data.get("points", [])]
            item = PolygonAnnotationItem(ann.id, pts, color, label, closed=True)

        elif ann.ann_type == AnnotationType.POLYLINE:
            pts = [(x * w, y * h) for x, y in ann.data.get("points", [])]
            item = PolygonAnnotationItem(ann.id, pts, color, label, closed=False)

        elif ann.ann_type == AnnotationType.BBOX:
            d = ann.data
            rect = (d["x"]*w, d["y"]*h, d["w"]*w, d["h"]*h)
            item = BBoxAnnotationItem(ann.id, rect, color, label)

        elif ann.ann_type == AnnotationType.OBB:
            d = ann.data
            item = OBBAnnotationItem(
                ann.id,
                d["cx"] * w, d["cy"] * h,
                d["w"] * w,  d["h"] * h,
                d.get("angle_deg", 0.0),
                color, label,
            )

        elif ann.ann_type == AnnotationType.POSE:
            kps = [(x * w, y * h, v) for x, y, v in ann.data.get("keypoints", [])]
            edges: list[tuple[int, int]] = []
            if cls and cls.skeleton:
                edge_set: set[tuple[int, int]] = set()
                for i, kp in enumerate(cls.skeleton):
                    for j in kp.edges:
                        if 0 <= j < len(cls.skeleton) and i != j:
                            edge_set.add((min(i, j), max(i, j)))
                edges = sorted(edge_set)
            item = PoseAnnotationItem(ann.id, kps, edges, color, label)

        elif ann.ann_type == AnnotationType.POINT:
            d = ann.data
            item = PointAnnotationItem(ann.id, (d["x"] * w, d["y"] * h), color, label)

        elif ann.ann_type == AnnotationType.MASK:
            from annotator.ui.canvas.items.mask_item import MaskAnnotationItem
            pts = [(x * w, y * h) for x, y in ann.data.get("polygon", [])]
            item = MaskAnnotationItem(ann.id, pts, color, label)

        if item is not None and cls is not None:
            item.line_width = float(cls.display_style.line_width)
            item.fill_opacity = float(cls.display_style.opacity)

        return item  # None for unsupported types

    def _clear_ann_items(self):
        for item in self._ann_items.values():
            if item.scene() is self:
                self.removeItem(item)
        self._ann_items.clear()
        self._selected_item = None

    # ── selection API (used by SelectTool) ────────────────────────────────────

    def get_selected_item(self):
        return self._selected_item

    def select_item(self, item):
        self.deselect_all()
        item.setSelected(True)
        self._selected_item = item

    def deselect_all(self):
        for item in self._ann_items.values():
            item.setSelected(False)
        self._selected_item = None

    def annotation_item_at(self, pos):
        """Return the topmost annotation item at scene pos, or None."""
        for gitem in self.items(pos):
            if gitem in self._ann_items.values():
                return gitem
        return None

    def select_by_id(self, ann_id: str):
        """Select the item for a given annotation id (called from outside)."""
        self.deselect_all()
        item = self._ann_items.get(ann_id)
        if item:
            item.setSelected(True)
            self._selected_item = item

    # ── placeholder ────────────────────────────────────────────────────────────

    def _show_placeholder(self, text: str =
                          "No image loaded\n\nOpen or create a project\nto get started"):
        self._remove_placeholder()
        self.setSceneRect(0, 0, 600, 400)
        item = QGraphicsTextItem(text)
        item.setDefaultTextColor(Qt.GlobalColor.gray)
        r = item.boundingRect()
        item.setPos((600 - r.width()) / 2, (400 - r.height()) / 2)
        self.addItem(item)
        self._placeholder = item

    def _remove_placeholder(self):
        if self._placeholder:
            self.removeItem(self._placeholder)
            self._placeholder = None

    # ── event dispatch to active tool ──────────────────────────────────────────

    def mousePressEvent(self, event):
        self._active_tool.on_press(
            event.scenePos(), event.modifiers(), event.button())

    def mouseMoveEvent(self, event):
        self._active_tool.on_move(event.scenePos(), event.modifiers())

    def mouseReleaseEvent(self, event):
        self._active_tool.on_release(
            event.scenePos(), event.modifiers(), event.button())

    def mouseDoubleClickEvent(self, event):
        self._active_tool.on_double_click(
            event.scenePos(), event.modifiers(), event.button())

    def keyPressEvent(self, event):
        self._active_tool.on_key_press(event.key(), event.modifiers())
