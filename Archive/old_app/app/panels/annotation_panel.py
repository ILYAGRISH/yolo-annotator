from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                              QPushButton, QVBoxLayout, QWidget)


def _icon(hex_color: str) -> QIcon:
    px = QPixmap(12, 12)
    px.fill(QColor(hex_color))
    return QIcon(px)


class AnnotationPanel(QWidget):
    select_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.addWidget(QLabel("Annotations"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(
            lambda r: self.select_requested.emit(r) if r >= 0 else None)
        lay.addWidget(self._list)

        row = QHBoxLayout()
        btn_del = QPushButton("Delete selected")
        btn_del.clicked.connect(self._delete)
        row.addWidget(btn_del)
        lay.addLayout(row)

    def refresh(self, annotations: list, classes: list):
        self._list.blockSignals(True)
        self._list.clear()
        for i, ann in enumerate(annotations):
            name, color = str(ann.class_id), "#888888"
            for cls in classes:
                if cls.id == ann.class_id:
                    name, color = cls.name, cls.color
                    break
            item = QListWidgetItem(_icon(color),
                                   f"#{i}  {name}  ({len(ann.points)} pts)")
            self._list.addItem(item)
        self._list.blockSignals(False)

    def set_selected(self, index: int):
        self._list.blockSignals(True)
        self._list.setCurrentRow(index)
        self._list.blockSignals(False)

    def _delete(self):
        r = self._list.currentRow()
        if r >= 0:
            self.delete_requested.emit(r)
