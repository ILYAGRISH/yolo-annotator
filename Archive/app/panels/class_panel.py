from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (QColorDialog, QDialog, QDialogButtonBox,
                              QHBoxLayout, QLabel, QLineEdit, QListWidget,
                              QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

from app.models.annotation import LabelClass

_PALETTE = [
    "#FF4444", "#44DD44", "#4488FF", "#FFDD00",
    "#FF44FF", "#00DDDD", "#FF8800", "#8844FF",
    "#44FF99", "#FF4499", "#99FF44", "#4499FF",
]


def _color_icon(hex_color: str) -> QIcon:
    px = QPixmap(14, 14)
    px.fill(QColor(hex_color))
    return QIcon(px)


class ClassPanel(QWidget):
    class_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._classes: list[LabelClass] = []
        self._next_id = 0
        self._setup_ui()
        self._add("object", _PALETTE[0])

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)
        lay.addWidget(QLabel("Classes  (double-click to edit)"))

        self._list = QListWidget()
        self._list.currentRowChanged.connect(
            lambda r: self.class_selected.emit(self._classes[r].id) if 0 <= r < len(self._classes) else None)
        self._list.itemDoubleClicked.connect(self._edit)
        lay.addWidget(self._list)

        row = QHBoxLayout()
        b_add = QPushButton("+")
        b_add.setFixedWidth(28)
        b_add.clicked.connect(self._prompt_add)
        b_rm = QPushButton("−")
        b_rm.setFixedWidth(28)
        b_rm.clicked.connect(self._remove)
        row.addWidget(b_add)
        row.addWidget(b_rm)
        row.addStretch()
        lay.addLayout(row)

    # ── public ───────────────────────────────────────────────────────────────

    @property
    def classes(self) -> list:
        return self._classes

    @property
    def current_class(self) -> LabelClass | None:
        r = self._list.currentRow()
        return self._classes[r] if 0 <= r < len(self._classes) else None

    def get_by_id(self, class_id: int) -> LabelClass | None:
        return next((c for c in self._classes if c.id == class_id), None)

    # ── internal ─────────────────────────────────────────────────────────────

    def _add(self, name: str, color: str):
        cls = LabelClass(id=self._next_id, name=name, color=color)
        self._next_id += 1
        self._classes.append(cls)
        item = QListWidgetItem(_color_icon(color), f"{cls.id}: {name}")
        self._list.addItem(item)
        if self._list.count() == 1:
            self._list.setCurrentRow(0)

    def _prompt_add(self):
        dlg = _ClassDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            color = _PALETTE[self._next_id % len(_PALETTE)]
            if dlg.color:
                color = dlg.color
            self._add(dlg.name, color)

    def _remove(self):
        r = self._list.currentRow()
        if r < 0 or len(self._classes) <= 1:
            return
        self._classes.pop(r)
        self._list.takeItem(r)

    def _edit(self, item: QListWidgetItem):
        r = self._list.row(item)
        cls = self._classes[r]
        dlg = _ClassDialog(self, cls.name, cls.color)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            cls.name = dlg.name
            if dlg.color:
                cls.color = dlg.color
            item.setText(f"{cls.id}: {cls.name}")
            item.setIcon(_color_icon(cls.color))


class _ClassDialog(QDialog):

    def __init__(self, parent=None, name: str = "", color: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Class")
        self.setFixedWidth(280)
        self.name = name
        self.color = color or _PALETTE[0]

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Name:"))
        self._name = QLineEdit(name)
        lay.addWidget(self._name)

        row = QHBoxLayout()
        row.addWidget(QLabel("Color:"))
        self._btn = QPushButton()
        self._btn.setFixedSize(40, 24)
        self._refresh_btn()
        self._btn.clicked.connect(self._pick)
        row.addWidget(self._btn)
        row.addStretch()
        lay.addLayout(row)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self)
        if c.isValid():
            self.color = c.name()
            self._refresh_btn()

    def _refresh_btn(self):
        self._btn.setStyleSheet(f"background-color:{self.color};border:1px solid #555;")

    def _ok(self):
        n = self._name.text().strip()
        if n:
            self.name = n
            self.accept()
