"""SelectTool — click to select, drag vertex to move, Delete to remove."""
import copy

from PyQt6.QtCore import Qt, QPointF

from annotator.tools.base import BaseTool


class SelectTool(BaseTool):

    def __init__(self):
        self._scene = None
        self._ctrl = None
        self._drag_item = None    # BaseAnnotationItem currently being edited
        self._drag_handle = -1   # vertex/corner index
        self._drag_orig_data: dict | None = None  # snapshot before drag

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
            handle = selected.handle_at(pos)
            if handle >= 0:
                self._drag_item = selected
                self._drag_handle = handle
                if self._ctrl:
                    ann = self._ctrl.get_annotation(selected.annotation_id)
                    if ann:
                        self._drag_orig_data = copy.deepcopy(ann.data)
                return

        # 2 — try to pick an item
        if self._scene:
            item = self._scene.annotation_item_at(pos)
            if item:
                self._scene.select_item(item)
                if self._ctrl:
                    self._ctrl.select_annotation(item.annotation_id)
            else:
                self._scene.deselect_all()
                if self._ctrl:
                    self._ctrl.select_annotation("")

    def on_move(self, pos, modifiers):
        if self._drag_item is None or self._drag_handle < 0:
            return
        clamped = self._clamp(pos)
        # Dispatch to correct move method
        if hasattr(self._drag_item, 'move_handle'):      # BBoxAnnotationItem
            self._drag_item.move_handle(self._drag_handle, clamped)
        elif hasattr(self._drag_item, 'move_vertex'):    # PolygonAnnotationItem
            self._drag_item.move_vertex(self._drag_handle, clamped)

    def on_release(self, pos, modifiers, button):
        if self._drag_item is not None and self._drag_orig_data is not None:
            ann_id = self._drag_item.annotation_id
            new_data = self._drag_item.to_data(self._scene.image_size)
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

    def _reset_drag(self):
        self._drag_item = None
        self._drag_handle = -1
        self._drag_orig_data = None
