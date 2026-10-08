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
    """Geometry / attribute edit. `old_meta`/`new_meta` (optional) change meta
    in the same step — an edit marks a model annotation reviewed."""
    def __init__(self, ctrl: "ProjectController", ann_id: str,
                 old_data: dict, new_data: dict, text: str = "Edit annotation",
                 old_meta: dict | None = None, new_meta: dict | None = None):
        super().__init__(text)
        self._ctrl = ctrl
        self._ann_id = ann_id
        self._old = copy.deepcopy(old_data)
        self._new = copy.deepcopy(new_data)
        self._old_meta = copy.deepcopy(old_meta)
        self._new_meta = copy.deepcopy(new_meta)

    def redo(self): self._ctrl._raw_update(self._ann_id, self._new, self._new_meta)
    def undo(self): self._ctrl._raw_update(self._ann_id, self._old, self._old_meta)


class SetMetaCmd(QUndoCommand):
    """Replace the meta of several annotations at once (review status)."""
    def __init__(self, ctrl: "ProjectController", old: dict, new: dict,
                 text: str = "Change annotation status"):
        super().__init__(text)
        self._ctrl = ctrl
        self._old = copy.deepcopy(old)        # {ann_id: meta}
        self._new = copy.deepcopy(new)

    def redo(self): self._ctrl._raw_set_meta(self._new)
    def undo(self): self._ctrl._raw_set_meta(self._old)
