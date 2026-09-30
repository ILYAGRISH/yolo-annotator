"""
QUndoCommand subclasses for all annotation mutations.
All state changes go through these commands so Ctrl+Z / Ctrl+Y work correctly.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

try:
    from PyQt6.QtGui import QUndoCommand
except ImportError:
    from PyQt6.QtWidgets import QUndoCommand  # type: ignore[no-redef]

from annotator.domain.annotation import Annotation

if TYPE_CHECKING:
    from annotator.controller.project_controller import ProjectController


class AddAnnotationCmd(QUndoCommand):
    def __init__(self, ctrl: "ProjectController", annotation: Annotation):
        super().__init__(f"Add {annotation.ann_type.value}")
        self._ctrl = ctrl
        self._ann = annotation

    def redo(self): self._ctrl._raw_add(self._ann)
    def undo(self): self._ctrl._raw_delete(self._ann.id)


class DeleteAnnotationCmd(QUndoCommand):
    def __init__(self, ctrl: "ProjectController", annotation: Annotation):
        super().__init__(f"Delete {annotation.ann_type.value}")
        self._ctrl = ctrl
        self._ann = annotation

    def redo(self): self._ctrl._raw_delete(self._ann.id)
    def undo(self): self._ctrl._raw_add(self._ann)


class UpdateAnnotationCmd(QUndoCommand):
    def __init__(self, ctrl: "ProjectController", ann_id: str,
                 old_data: dict, new_data: dict, text: str = "Edit annotation"):
        super().__init__(text)
        self._ctrl = ctrl
        self._ann_id = ann_id
        self._old = copy.deepcopy(old_data)
        self._new = copy.deepcopy(new_data)

    def redo(self): self._ctrl._raw_update(self._ann_id, self._new)
    def undo(self): self._ctrl._raw_update(self._ann_id, self._old)
