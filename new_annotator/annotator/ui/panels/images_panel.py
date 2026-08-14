from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QLabel, QListWidget, QListWidgetItem, QMenu,
                              QVBoxLayout, QWidget)

from annotator.domain.project import ImageRecord, Project

_SPLIT_COLORS = {
    "train": None,          # default text color
    "val":   "#55AAFF",
    "test":  "#FF9944",
}
_ASSIGN_COLOR = "#BB99FF"  # light purple for assignee tag (leader view)


class ImagesPanel(QWidget):
    """Shows the image inventory of the current project."""

    image_selected = pyqtSignal(str)   # absolute image path
    split_changed  = pyqtSignal()      # any ImageRecord.split was modified

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._annotated: set[str] = set()
        self._user_filter: set[str] | None = None  # None = no filter (leader)
        self._displayed: list[ImageRecord] = []     # currently visible records
        self._stem_assignee: dict[str, str] = {}    # stem → username (leader view)
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        self._header = QLabel("Images")
        lay.addWidget(self._header)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        lay.addWidget(self._list)

        hint = QLabel("A / D — prev / next   RMB — set split")
        hint.setStyleSheet("color:#666;font-size:10px;")
        lay.addWidget(hint)

    # ── public API ────────────────────────────────────────────────────────────

    def load_project(self, project: Project | None):
        self._project = project
        self._annotated = self._scan_annotated(project) if project else set()
        self._refresh()

    def set_user_filter(self, allowed_stems: set[str] | None):
        """None = leader (no filter). A set of stems = client sees only those."""
        self._user_filter = allowed_stems
        self._refresh()

    def set_assignments(self, data: dict | None):
        """Update stem→assignee map shown in leader view. Pass None to clear."""
        if data is None:
            self._stem_assignee = {}
        else:
            mapping: dict[str, str] = {}
            for name, stems in data.get("users", {}).items():
                for stem in stems:
                    mapping[stem] = name
            self._stem_assignee = mapping
        self._refresh()

    def set_annotated(self, image_path: str, has_annotations: bool):
        if has_annotations:
            self._annotated.add(image_path)
        else:
            self._annotated.discard(image_path)
        if not self._project:
            return
        for i, rec in enumerate(self._displayed):
            if rec.path == image_path:
                self._refresh_item(i)
                break

    def select_next(self):
        r = self._list.currentRow()
        if r + 1 < self._list.count():
            self._list.setCurrentRow(r + 1)

    def select_prev(self):
        r = self._list.currentRow()
        if r > 0:
            self._list.setCurrentRow(r - 1)

    def select_by_path(self, image_path: str):
        for i, rec in enumerate(self._displayed):
            if rec.path == image_path:
                self._list.setCurrentRow(i)
                return

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _scan_annotated(project: Project) -> set[str]:
        annotated: set[str] = set()
        if project is None or project.project_path is None:
            return annotated
        ann_dir = project.project_path / "annotations"
        if not ann_dir.exists():
            return annotated
        stem_to_path = {Path(rec.path).stem: rec.path for rec in project.images}
        for ann_file in ann_dir.glob("*.json"):
            if ann_file.stat().st_size > 5:  # non-empty: more than just "[]"
                img_path = stem_to_path.get(ann_file.stem)
                if img_path:
                    annotated.add(img_path)
        return annotated

    def _refresh(self):
        self._list.clear()
        if not self._project:
            self._displayed = []
            self._header.setText("Images")
            return

        if self._user_filter is None:
            self._displayed = list(self._project.images)
            label = f"Images ({len(self._displayed)})"
        else:
            self._displayed = [
                r for r in self._project.images
                if Path(r.path).stem in self._user_filter
            ]
            label = f"My Images ({len(self._displayed)})"

        self._header.setText(label)
        for rec in self._displayed:
            self._list.addItem(self._make_item(rec))

    def _make_item(self, rec: ImageRecord) -> QListWidgetItem:
        split = rec.split or "train"
        split_tag = f" [{split}]" if split != "train" else ""
        check = " ✓" if rec.path in self._annotated else ""

        stem = Path(rec.path).stem
        assignee = self._stem_assignee.get(stem, "") if self._user_filter is None else ""
        assign_tag = f" ▸{assignee}" if assignee else ""

        item = QListWidgetItem(Path(rec.path).name + split_tag + assign_tag + check)
        tooltip = f"{rec.path}\nSplit: {split}"
        if assignee:
            tooltip += f"\nAssigned to: {assignee}"
        item.setToolTip(tooltip)

        color = _SPLIT_COLORS.get(split)
        if assign_tag and not color:
            color = _ASSIGN_COLOR
        if color:
            item.setForeground(QColor(color))
        return item

    def _refresh_item(self, row: int):
        if row >= len(self._displayed):
            return
        new_item = self._make_item(self._displayed[row])
        old = self._list.item(row)
        if old:
            old.setText(new_item.text())
            old.setToolTip(new_item.toolTip())
            old.setForeground(new_item.foreground())

    def _on_row(self, row: int):
        if 0 <= row < len(self._displayed):
            self.image_selected.emit(self._displayed[row].path)

    # ── context menu (split assignment) ───────────────────────────────────────

    def _on_context_menu(self, pos):
        item = self._list.itemAt(pos)
        if item is None or not self._project:
            return
        row = self._list.row(item)
        if row < 0 or row >= len(self._displayed):
            return
        rec = self._displayed[row]

        menu = QMenu(self)
        menu.addAction("Set split:").setEnabled(False)
        for split in ("train", "val", "test"):
            act = menu.addAction(f"  {split}")
            act.setCheckable(True)
            act.setChecked((rec.split or "train") == split)
            act.triggered.connect(
                lambda _checked, r=row, s=split: self._set_split(r, s))
        menu.exec(self._list.viewport().mapToGlobal(pos))

    def _set_split(self, row: int, split: str):
        if row >= len(self._displayed):
            return
        self._displayed[row].split = split
        self._refresh_item(row)
        self.split_changed.emit()
