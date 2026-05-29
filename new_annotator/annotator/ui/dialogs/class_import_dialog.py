"""
ClassImportDialog — conflict resolution when importing a class_schema.json.

For each incoming class the dialog shows the conflict type and lets the user
choose: Skip / Merge (replace existing) / Add as new (auto-remap ID).
ID conflicts are resolved by auto-remapping; the user just confirms.
"""
from __future__ import annotations
import copy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QScrollArea, QVBoxLayout, QWidget,
)

from annotator.domain.label_class import LabelClass


_ACTION_SKIP = "Skip"
_ACTION_MERGE = "Replace existing"
_ACTION_ADD = "Add as new (remap ID)"


class ClassImportDialog(QDialog):
    """
    Shows each incoming class and its conflict. User resolves per-class.

    Accepted result:
      .resolved_classes  → list[LabelClass] to add/replace
      .remap             → dict[old_id → new_id]   (for ID remaps)
    """

    def __init__(self, report: list[dict],
                 existing_classes: list[LabelClass], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import class schema — resolve conflicts")
        self.setModal(True)
        self.resize(640, 480)

        self.resolved_classes: list[LabelClass] = []
        self.remap: dict[int, int] = {}

        self._report = report
        self._existing = existing_classes
        self._max_id = max((c.id for c in existing_classes), default=-1)
        self._combos: list[QComboBox] = []

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        root.addWidget(QLabel(
            f"Importing {len(self._report)} class(es). "
            "Choose an action for each conflict:"
        ))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_l = QVBoxLayout(inner)
        inner_l.setSpacing(6)

        for entry in self._report:
            inc: LabelClass = entry["incoming"]
            conflict: str | None = entry["conflict_type"]
            existing: LabelClass | None = entry["existing"]

            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 2, 4, 2)

            # Description
            if conflict is None:
                desc = f"<b>{inc.name}</b> (ID {inc.id}) — no conflict"
            elif conflict == "name":
                desc = (f"<b>{inc.name}</b> (ID {inc.id}) — "
                        f"<span style='color:#e67e22'>name conflict</span> "
                        f"with existing ID {existing.id if existing else '?'}")
            else:  # id conflict
                desc = (f"<b>{inc.name}</b> (ID {inc.id}) — "
                        f"<span style='color:#c0392b'>ID conflict</span> "
                        f"with existing '{existing.name if existing else '?'}'")

            lbl = QLabel(desc)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            lbl.setWordWrap(True)
            rl.addWidget(lbl, stretch=1)

            combo = QComboBox()
            if conflict is None:
                combo.addItem("Add")
                combo.setEnabled(False)
            else:
                combo.addItems([_ACTION_SKIP, _ACTION_MERGE, _ACTION_ADD])
                if conflict == "id":
                    combo.setCurrentText(_ACTION_ADD)
            rl.addWidget(combo)
            self._combos.append(combo)

            inner_l.addWidget(row)

        inner_l.addStretch()
        scroll.setWidget(inner)
        root.addWidget(scroll)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _next_free_id(self) -> int:
        self._max_id += 1
        return self._max_id

    def _accept(self):
        resolved: list[LabelClass] = []
        remap: dict[int, int] = {}

        for entry, combo in zip(self._report, self._combos):
            inc: LabelClass = entry["incoming"]
            conflict: str | None = entry["conflict_type"]
            action = combo.currentText()

            if conflict is None or action == "Add":
                # Direct add — no conflict or no-conflict row
                resolved.append(copy.deepcopy(inc))

            elif action == _ACTION_SKIP:
                continue  # drop this class

            elif action == _ACTION_MERGE:
                # Replace existing with incoming (keep incoming's ID)
                resolved.append(copy.deepcopy(inc))

            elif action == _ACTION_ADD:
                # Auto-remap: assign a fresh ID
                new_id = self._next_free_id()
                lc = copy.deepcopy(inc)
                remap[inc.id] = new_id
                lc.id = new_id
                resolved.append(lc)

        self.resolved_classes = resolved
        self.remap = remap
        self.accept()
