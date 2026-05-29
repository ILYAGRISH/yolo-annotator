from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                              QPushButton, QVBoxLayout, QWidget)

from annotator.domain.annotation import Annotation
from annotator.domain.project import Project


def _icon(color: str) -> QIcon:
    px = QPixmap(12, 12)
    px.fill(QColor(color))
    return QIcon(px)


class AnnotationsPanel(QWidget):
    """Shows annotations for the currently selected image."""

    select_requested = pyqtSignal(str)   # annotation id
    delete_requested = pyqtSignal(str)   # annotation id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._annotations: list[Annotation] = []
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        self._header = QLabel("Annotations")
        lay.addWidget(self._header)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self._list)

        row = QHBoxLayout()
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete)
        row.addWidget(btn_del)
        lay.addLayout(row)

    def load_project(self, project: Project):
        self._project = project

    def refresh(self, annotations: list[Annotation]):
        self._annotations = list(annotations)
        self._list.blockSignals(True)
        self._list.clear()
        self._header.setText(f"Annotations ({len(annotations)})")
        for ann in annotations:
            color = "#888888"
            name = str(ann.class_id)
            if self._project:
                cls = self._project.get_class(ann.class_id)
                if cls:
                    color, name = cls.color, cls.name
            label = f"{name}  [{ann.ann_type.value}]  ({self._pts_count(ann)} pts)"
            self._list.addItem(QListWidgetItem(_icon(color), label))
        self._list.blockSignals(False)

    @staticmethod
    def _pts_count(ann: Annotation) -> int:
        pts = ann.data.get("points", [])
        return len(pts)

    def set_selected(self, annotation_id: str):
        self._list.blockSignals(True)
        for i, ann in enumerate(self._annotations):
            if ann.id == annotation_id:
                self._list.setCurrentRow(i)
                break
        self._list.blockSignals(False)

    def _on_row(self, row: int):
        if 0 <= row < len(self._annotations):
            self.select_requested.emit(self._annotations[row].id)

    def _delete(self):
        r = self._list.currentRow()
        if 0 <= r < len(self._annotations):
            self.delete_requested.emit(self._annotations[r].id)
