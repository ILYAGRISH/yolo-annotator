from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from annotator.domain.label_class import LabelClass
from annotator.i18n import tr
from annotator.domain.project import Project


def _icon(color: str) -> QIcon:
    px = QPixmap(14, 14)
    px.fill(QColor(color))
    return QIcon(px)


class ClassesPanel(QWidget):
    """Displays project classes and opens the schema editor."""

    class_selected = pyqtSignal(int)    # class id
    classes_changed = pyqtSignal()
    open_schema_editor = pyqtSignal()   # MainWindow handles this

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        header = QHBoxLayout()
        self._header_lbl = QLabel(tr("classes"))
        header.addWidget(self._header_lbl)
        header.addStretch()
        self._btn_schema = QPushButton(tr("btn_schema"))
        self._btn_schema.setFixedHeight(22)
        self._btn_schema.setToolTip("Open full class schema editor")
        self._btn_schema.clicked.connect(self.open_schema_editor)
        header.addWidget(self._btn_schema)
        lay.addLayout(header)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self._list)

    def load_project(self, project: Project):
        self._project = project
        self._refresh()

    def retranslate(self):
        self._header_lbl.setText(tr("classes"))
        self._btn_schema.setText(tr("btn_schema"))

    def _refresh(self):
        self._list.clear()
        if not self._project:
            return
        for cls in self._project.classes:
            self._list.addItem(
                QListWidgetItem(_icon(cls.color),
                                f"{cls.id}: {cls.name}  [{cls.annotation_type}]"))
        if self._list.count():
            self._list.setCurrentRow(0)

    def _on_row(self, row: int):
        if self._project and 0 <= row < len(self._project.classes):
            self.class_selected.emit(self._project.classes[row].id)

    def select_class_by_id(self, class_id: int) -> bool:
        """Select the row whose class.id == class_id. Returns True if found."""
        if not self._project:
            return False
        for i, cls in enumerate(self._project.classes):
            if cls.id == class_id:
                self._list.setCurrentRow(i)
                return True
        return False

    @property
    def current_class_id(self) -> int | None:
        if not self._project:
            return None
        r = self._list.currentRow()
        if 0 <= r < len(self._project.classes):
            return self._project.classes[r].id
        return None
