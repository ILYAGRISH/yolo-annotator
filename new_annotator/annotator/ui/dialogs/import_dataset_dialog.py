"""ImportDatasetDialog — choose a YOLO dataset folder and import settings."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QVBoxLayout,
)

from annotator.importers.yolo_importer import auto_find_class_file, parse_class_names


_ANN_TYPES = [
    ("Detect  (bbox: class cx cy w h)",              "detect"),
    ("OBB  (class x1 y1 x2 y2 x3 y3 x4 y4)",        "obb"),
    ("Segment  (class x1 y1 x2 y2 …)",               "segment"),
    ("Point  (1-keypoint: class cx cy w h x y v)",    "point"),
    ("Classify  (split/class_name/image.jpg)",        "classify"),
]

_CONFLICT_MODES = [
    ("Skip  — keep existing annotations",             "skip"),
    ("Replace  — overwrite existing annotations",     "replace"),
    ("Merge  — add on top of existing annotations",   "merge"),
]


class ImportDatasetDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import YOLO Dataset")
        self.setMinimumWidth(540)
        self._class_file: Path | None = None
        self._class_names: list[str] = []
        self._setup_ui()

    # ── setup ─────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # Dataset folder
        folder_grp = QGroupBox("Dataset folder")
        folder_lay = QHBoxLayout(folder_grp)
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select the folder that contains images/ and labels/")
        self._folder_edit.setReadOnly(True)
        btn_folder = QPushButton("Browse…")
        btn_folder.clicked.connect(self._browse_folder)
        folder_lay.addWidget(self._folder_edit)
        folder_lay.addWidget(btn_folder)
        lay.addWidget(folder_grp)

        # Class file
        cls_grp = QGroupBox("Class definitions  (data.yaml or classes.txt)")
        cls_lay = QVBoxLayout(cls_grp)
        cls_path_row = QHBoxLayout()
        self._cls_edit = QLineEdit()
        self._cls_edit.setReadOnly(True)
        self._cls_edit.setPlaceholderText("Auto-detected when you select a folder")
        btn_cls = QPushButton("Browse…")
        btn_cls.clicked.connect(self._browse_class_file)
        cls_path_row.addWidget(self._cls_edit)
        cls_path_row.addWidget(btn_cls)
        cls_lay.addLayout(cls_path_row)
        self._cls_preview = QLabel()
        self._cls_preview.setStyleSheet("color:#888; font-size:10px;")
        self._cls_preview.setWordWrap(True)
        cls_lay.addWidget(self._cls_preview)
        lay.addWidget(cls_grp)

        # Import options
        opt_grp = QGroupBox("Import options")
        opt_form = QFormLayout(opt_grp)
        opt_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._type_combo = QComboBox()
        for label, _ in _ANN_TYPES:
            self._type_combo.addItem(label)
        opt_form.addRow("Annotation type:", self._type_combo)

        self._conflict_combo = QComboBox()
        for label, _ in _CONFLICT_MODES:
            self._conflict_combo.addItem(label)
        opt_form.addRow("On conflict:", self._conflict_combo)

        lay.addWidget(opt_grp)

        # Status / preview
        self._status_lbl = QLabel("Select a dataset folder to begin.")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px; padding:4px;")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        self._ok_btn = bb.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Import")
        self._ok_btn.setEnabled(False)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    # ── slots ─────────────────────────────────────────────────────────────────

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Dataset Folder")
        if not path:
            return
        self._folder_edit.setText(path)
        # Auto-detect class file
        found = auto_find_class_file(Path(path))
        if found:
            self._set_class_file(found)
        else:
            self._class_file = None
            self._cls_edit.clear()
            self._cls_preview.setText("No data.yaml or classes.txt found — browse manually.")
        self._update_status()

    def _browse_class_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Class File",
            self._folder_edit.text() or "",
            "Class files (*.yaml *.yml classes.txt *.names);;All files (*)"
        )
        if path:
            self._set_class_file(Path(path))
            self._update_status()

    def _set_class_file(self, path: Path):
        self._class_file = path
        self._cls_edit.setText(str(path))
        try:
            self._class_names = parse_class_names(path)
            n = len(self._class_names)
            preview = ", ".join(self._class_names[:8])
            if n > 8:
                preview += f"  … (+{n - 8} more)"
            self._cls_preview.setText(f"{n} class{'es' if n != 1 else ''}: {preview}")
        except Exception as exc:
            self._class_names = []
            self._cls_preview.setText(f"Error reading file: {exc}")

    def _update_status(self):
        folder = self._folder_edit.text()
        if not folder or not self._class_names:
            self._status_lbl.setText(
                "Select a dataset folder and a class file." if not folder
                else "Select or browse a class definitions file."
            )
            self._ok_btn.setEnabled(False)
            return

        self._ok_btn.setEnabled(True)
        from annotator.importers.yolo_importer import find_images_with_split, find_label_file
        root = Path(folder)
        images = find_images_with_split(root)
        n_img = len(images)
        ann_type = _ANN_TYPES[self._type_combo.currentIndex()][1]
        if ann_type == "classify":
            self._status_lbl.setStyleSheet("color:#4488FF; font-size:11px; padding:4px;")
            self._status_lbl.setText(
                f"Ready: {n_img} image(s) found, {len(self._class_names)} classes. "
                "Classify mode — folder structure determines labels."
            )
        else:
            n_lbl = sum(1 for p, _ in images if find_label_file(p, root) is not None)
            self._status_lbl.setStyleSheet("color:#4488FF; font-size:11px; padding:4px;")
            self._status_lbl.setText(
                f"Ready: {n_img} image(s), {n_lbl} label file(s), "
                f"{len(self._class_names)} class(es)."
            )

    # ── public accessors ──────────────────────────────────────────────────────

    @property
    def dataset_folder(self) -> Path | None:
        t = self._folder_edit.text().strip()
        return Path(t) if t else None

    @property
    def class_names(self) -> list[str]:
        return list(self._class_names)

    @property
    def ann_type(self) -> str:
        return _ANN_TYPES[self._type_combo.currentIndex()][1]

    @property
    def conflict_mode(self) -> str:
        return _CONFLICT_MODES[self._conflict_combo.currentIndex()][1]
