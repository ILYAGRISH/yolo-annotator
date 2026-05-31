from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QListWidget,
                              QListWidgetItem, QPushButton, QVBoxLayout, QWidget)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


class FilePanel(QWidget):
    image_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._folder: Path | None = None
        self._images: list[Path] = []
        self._label_folder: Path | None = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        btn = QPushButton("📁  Open folder…")
        btn.clicked.connect(self._open_folder)
        lay.addWidget(btn)

        self._lbl = QLabel("No folder selected")
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(self._lbl)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self._list)

        info = QLabel("🟢 = labeled   A/D = prev/next")
        info.setStyleSheet("color: #666; font-size: 10px;")
        lay.addWidget(info)

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select image folder")
        if folder:
            self.load_folder(Path(folder))

    def load_folder(self, folder: Path):
        self._folder = folder
        self._label_folder = folder.parent / "labels"
        self._images = sorted(p for p in folder.iterdir()
                              if p.suffix.lower() in IMAGE_EXTS)
        self._lbl.setText(str(folder))
        self._refresh_list()

    def _refresh_list(self):
        self._list.clear()
        for img in self._images:
            item = QListWidgetItem(img.name)
            if self._label_path(img).exists():
                item.setForeground(QColor("#55CC55"))
            self._list.addItem(item)

    def _label_path(self, img: Path) -> Path:
        base = self._label_folder or img.parent
        return base / (img.stem + ".txt")

    def _on_row(self, row: int):
        if 0 <= row < len(self._images):
            self.image_selected.emit(str(self._images[row]))

    def mark_labeled(self, image_path: str):
        p = Path(image_path)
        for i, img in enumerate(self._images):
            if img == p:
                self._list.item(i).setForeground(QColor("#55CC55"))
                break

    def select_next(self):
        r = self._list.currentRow()
        if r + 1 < self._list.count():
            self._list.setCurrentRow(r + 1)

    def select_prev(self):
        r = self._list.currentRow()
        if r > 0:
            self._list.setCurrentRow(r - 1)

    @property
    def label_folder(self) -> Path:
        return self._label_folder or Path("labels")

    @property
    def current_image(self) -> Path | None:
        r = self._list.currentRow()
        return self._images[r] if 0 <= r < len(self._images) else None
