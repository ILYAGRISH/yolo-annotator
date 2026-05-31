from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                              QPushButton, QVBoxLayout, QWidget)

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project


def _icon(color: str) -> QIcon:
    px = QPixmap(12, 12)
    px.fill(QColor(color))
    return QIcon(px)


class AnnotationsPanel(QWidget):
    """Shows annotations for the currently selected image."""

    select_requested = pyqtSignal(str)          # annotation id
    delete_requested = pyqtSignal(str)          # annotation id
    edit_source_requested = pyqtSignal(str)     # annotation id (crack source edit)
    classify_image_requested = pyqtSignal(int)  # class_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._annotations: list[Annotation] = []
        self._active_class_id: int | None = None
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

        self._btn_classify = QPushButton("+ Classify image")
        self._btn_classify.setVisible(False)
        self._btn_classify.clicked.connect(self._classify_image)
        lay.addWidget(self._btn_classify)

        row = QHBoxLayout()
        self._btn_edit_src = QPushButton("Edit source")
        self._btn_edit_src.setEnabled(False)
        self._btn_edit_src.setToolTip(
            "Edit the source polyline of a crack annotation")
        self._btn_edit_src.clicked.connect(self._edit_source)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete)
        row.addWidget(self._btn_edit_src)
        row.addWidget(btn_del)
        lay.addLayout(row)

    def load_project(self, project: Project):
        self._project = project

    def set_active_class(self, cls) -> None:
        """Called by main_window when the selected class changes."""
        self._active_class_id = cls.id if cls else None
        is_classify = cls is not None and cls.annotation_type == "classification"
        self._btn_classify.setVisible(is_classify)
        if is_classify:
            self._btn_classify.setText(f'+ Classify as "{cls.name}"')

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
            if ann.ann_type == AnnotationType.CLASSIFY:
                label = f"{name}  [IMAGE LABEL]"
            else:
                label = f"{name}  [{ann.ann_type.value}]  ({self._pts_count(ann)} pts)"
            self._list.addItem(QListWidgetItem(_icon(color), label))
        self._list.blockSignals(False)

    @staticmethod
    def _pts_count(ann: Annotation) -> int:
        pts = ann.data.get("points", [])
        return len(pts)

    def set_selected(self, annotation_id: str):
        self._list.blockSignals(True)
        found: Annotation | None = None
        for i, ann in enumerate(self._annotations):
            if ann.id == annotation_id:
                self._list.setCurrentRow(i)
                found = ann
                break
        self._list.blockSignals(False)
        self._btn_edit_src.setEnabled(
            found is not None and "source_geometry" in found.data)

    def _on_row(self, row: int):
        if 0 <= row < len(self._annotations):
            ann = self._annotations[row]
            self.select_requested.emit(ann.id)
            self._btn_edit_src.setEnabled("source_geometry" in ann.data)
        else:
            self._btn_edit_src.setEnabled(False)

    def _classify_image(self):
        if self._active_class_id is not None:
            self.classify_image_requested.emit(self._active_class_id)

    def _edit_source(self):
        r = self._list.currentRow()
        if 0 <= r < len(self._annotations):
            self.edit_source_requested.emit(self._annotations[r].id)

    def _delete(self):
        r = self._list.currentRow()
        if 0 <= r < len(self._annotations):
            self.delete_requested.emit(self._annotations[r].id)
