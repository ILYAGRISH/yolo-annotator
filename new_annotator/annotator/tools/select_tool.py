"""SelectTool — click to select, drag a vertex / corner to reshape, drag the
body to move the whole annotation, Delete to remove."""
import copy

from PyQt6.QtCore import Qt, QPointF

from annotator.domain.geometry import MOVABLE, clamp_shift, move_data
from annotator.tools.base import BaseTool

_MOVE_THRESHOLD_PX = 4      # screen pixels before a press on an annotation becomes a move

# Non-geometry fields of annotation.data that a vertex / handle drag must keep.
_KEEP_ON_EDIT = ("attributes", "subclass")


class SelectTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._drag_item = None    # BaseAnnotationItem currently being edited
        self._drag_handle = -1   # vertex/corner index
        self._drag_orig_data: dict | None = None  # snapshot before drag
        self._move_item = None    # item being moved as a whole
        self._move_ann = None     # its Annotation (type + data before the move)
        self._move_start: QPointF | None = None
        self._moving = False      # past the threshold

    @property
    def name(self) -> str:
        return "select"

    @property
    def cursor(self):
        return Qt.CursorShape.ArrowCursor

    def activate(self, scene, controller=None):
        self._scene = scene
        self._ctrl = controller

    def deactivate(self):
        self._reset_drag()
        self._scene = None
        self._ctrl = None

    # ── event handlers ────────────────────────────────────────────────────────

    def on_press(self, pos, modifiers, button):
        if button != Qt.MouseButton.LeftButton:
            return

        # 1 — check if we're on a handle of the already-selected item
        selected = self._scene.get_selected_item() if self._scene else None
        if selected is not None:
            # items without handles (e.g. from plugins) are selectable, not draggable
            handle_at = getattr(selected, "handle_at", None)
            handle = handle_at(pos) if handle_at else -1
            if handle >= 0:
                self._drag_item = selected
                self._drag_handle = handle
                if self._ctrl:
                    ann = self._ctrl.get_annotation(selected.annotation_id)
                    if ann:
                        self._drag_orig_data = copy.deepcopy(ann.data)
                return

        # 2 — try to pick an item (and get ready to move it as a whole)
        if self._scene:
            item = self._scene.annotation_item_at(pos)
            if item:
                self._scene.select_item(item)
                if self._ctrl:
                    self._ctrl.select_annotation(item.annotation_id)
                    ann = self._ctrl.get_annotation(item.annotation_id)
                    if ann is not None and ann.ann_type in MOVABLE:
                        self._move_item, self._move_ann = item, copy.deepcopy(ann)
                        self._move_start, self._moving = QPointF(pos), False
            else:
                self._scene.deselect_all()
                if self._ctrl:
                    self._ctrl.select_annotation("")

    def on_move(self, pos, modifiers):
        if self._move_item is not None:
            self._move_to(pos)
            return
        if self._drag_item is None or self._drag_handle < 0:
            return
        clamped = self._clamp(pos)
        # Dispatch to correct move method
        if hasattr(self._drag_item, 'move_handle'):      # BBoxAnnotationItem
            self._drag_item.move_handle(self._drag_handle, clamped)
        elif hasattr(self._drag_item, 'move_vertex'):    # PolygonAnnotationItem
            self._drag_item.move_vertex(self._drag_handle, clamped)

    def on_release(self, pos, modifiers, button):
        if self._move_item is not None:
            self._finish_move(pos)
            return
        if self._drag_item is not None and self._drag_orig_data is not None:
            ann_id = self._drag_item.annotation_id
            # to_data() returns geometry only — keep the user's metadata
            new_data = self._drag_item.to_data(self._scene.image_size)
            for key in _KEEP_ON_EDIT:
                if key in self._drag_orig_data:
                    new_data[key] = copy.deepcopy(self._drag_orig_data[key])
            if self._ctrl and new_data != self._drag_orig_data:
                self._ctrl.update_annotation_data(
                    ann_id, new_data, "Move vertex")
        self._reset_drag()

    def on_double_click(self, pos, modifiers, button): ...

    def on_key_press(self, key, modifiers):
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = self._scene.get_selected_item() if self._scene else None
            if selected and self._ctrl:
                self._ctrl.delete_annotation(selected.annotation_id)
        elif key == Qt.Key.Key_Escape:
            if self._scene:
                self._scene.deselect_all()
            if self._ctrl:
                self._ctrl.select_annotation("")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _clamp(self, pos: QPointF) -> QPointF:
        if not self._scene:
            return pos
        w, h = self._scene.image_size
        return QPointF(max(0.0, min(w, pos.x())), max(0.0, min(h, pos.y())))

    def _shift(self, pos) -> tuple[float, float]:
        """Normalized shift from the press point, kept inside the image."""
        w, h = self._scene.image_size
        if not w or not h:
            return 0.0, 0.0
        d = pos - self._move_start
        return clamp_shift(self._move_ann.ann_type, self._move_ann.data, d.x() / w, d.y() / h)

    def _view_scale(self) -> float:
        views = self._scene.views() if self._scene else []
        return views[0].transform().m11() if views else 1.0

    def _move_to(self, pos):
        if not self._moving:
            d = pos - self._move_start
            if max(abs(d.x()), abs(d.y())) * self._view_scale() < _MOVE_THRESHOLD_PX:
                return                       # a click, not a drag (yet)
            self._moving = True
        dx, dy = self._shift(pos)
        w, h = self._scene.image_size
        self._move_item.setPos(dx * w, dy * h)          # preview: shift the item

    def _finish_move(self, pos):
        item, ann, moving = self._move_item, self._move_ann, self._moving
        dx, dy = self._shift(pos) if moving else (0.0, 0.0)
        self._reset_drag()
        if not moving or (dx == 0 and dy == 0):
            item.setPos(0, 0)
            return
        if self._ctrl:
            self._ctrl.update_annotation_data(
                ann.id, move_data(ann.ann_type, ann.data, dx, dy), "Move annotation")

    def _reset_drag(self):
        self._drag_item = None
        self._drag_handle = -1
        self._drag_orig_data = None
        self._move_item = None
        self._move_ann = None
        self._move_start = None
        self._moving = False
