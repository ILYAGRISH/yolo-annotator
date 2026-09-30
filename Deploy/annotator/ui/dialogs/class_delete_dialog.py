"""
ClassDeleteDialog — safety warning before deleting a class.

Shows the number of affected annotations and offers:
  - Reassign to another class
  - Delete all affected annotations
  - Cancel
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from annotator.domain.label_class import LabelClass


class ClassDeleteDialog(QDialog):
    """
    Result is stored in:
      .action  → "reassign" | "delete_all" | None (cancelled)
      .reassign_to  → int class_id  (only when action == "reassign")
    """

    def __init__(self, target: LabelClass, count: int,
                 other_classes: list[LabelClass], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete class")
        self.setModal(True)
        self.setMinimumWidth(380)

        self.action: str | None = None
        self.reassign_to: int | None = None

        lay = QVBoxLayout(self)

        # Warning message
        warn = QLabel(
            f"<b>Delete class '{target.name}' (ID {target.id})?</b><br><br>"
            f"<b>{count}</b> annotation(s) reference this class."
        )
        warn.setWordWrap(True)
        lay.addWidget(warn)

        # Radio: reassign
        self._radio_reassign = QRadioButton("Reassign annotations to:")
        self._radio_reassign.setChecked(bool(other_classes))
        self._radio_reassign.toggled.connect(self._on_radio)
        lay.addWidget(self._radio_reassign)

        reassign_row = QWidget()
        rrl = QHBoxLayout(reassign_row)
        rrl.setContentsMargins(20, 0, 0, 0)
        self._combo = QComboBox()
        for c in other_classes:
            self._combo.addItem(f"{c.id}: {c.name}", c.id)
        self._combo.setEnabled(bool(other_classes))
        rrl.addWidget(self._combo)
        rrl.addStretch()
        lay.addWidget(reassign_row)

        # Radio: delete all
        self._radio_delete = QRadioButton("Delete all affected annotations")
        if not other_classes:
            self._radio_delete.setChecked(True)
        lay.addWidget(self._radio_delete)

        # Buttons
        btn_row = QHBoxLayout()
        b_ok = QPushButton("Delete class")
        b_ok.setStyleSheet("background-color:#c0392b;color:white;")
        b_ok.clicked.connect(self._confirm)
        b_cancel = QPushButton("Cancel")
        b_cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_ok)
        lay.addLayout(btn_row)

    def _on_radio(self, checked: bool):
        self._combo.setEnabled(checked and self._combo.count() > 0)

    def _confirm(self):
        if self._radio_reassign.isChecked() and self._combo.count() > 0:
            self.action = "reassign"
            self.reassign_to = self._combo.currentData()
        else:
            self.action = "delete_all"
            self.reassign_to = None
        self.accept()
