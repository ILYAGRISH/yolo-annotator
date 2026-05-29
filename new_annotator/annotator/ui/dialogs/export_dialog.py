"""ExportDatasetDialog — choose format, output folder, and copy-images option."""
from pathlib import Path

from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                              QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                              QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from annotator.domain.project import Project

_FORMATS = [
    ("YOLO Detect  (bbox → cx cy w h)",          "yolo_detect"),
    ("YOLO Segment  (polygon / polyline)",         "yolo_seg"),
    ("YOLO OBB  (oriented bbox → 4 corners)",      "yolo_obb"),
    ("COCO Instances  (JSON with attributes)",     "coco"),
]


class ExportDatasetDialog(QDialog):

    def __init__(self, project: Project, ann_counts: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Dataset")
        self.setMinimumWidth(500)
        self._project = project
        self._ann_counts = ann_counts   # {type_str: count}
        self._out_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Format
        self._fmt_combo = QComboBox()
        for label, _ in _FORMATS:
            self._fmt_combo.addItem(label)
        form.addRow("Format:", self._fmt_combo)

        # Output folder
        row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select output folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self._folder_edit)
        row.addWidget(browse_btn)
        form.addRow("Output folder:", row)

        # Copy images
        self._copy_cb = QCheckBox("Copy images to output folder")
        self._copy_cb.setChecked(True)
        form.addRow("", self._copy_cb)

        lay.addLayout(form)

        # Summary
        lay.addSpacing(8)
        lay.addWidget(QLabel("<b>Project summary</b>"))
        self._summary = QLabel(self._build_summary())
        self._summary.setStyleSheet("color:#999; font-size:11px; padding-left:4px;")
        self._summary.setWordWrap(True)
        lay.addWidget(self._summary)
        lay.addSpacing(8)

        # OK / Cancel
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── public properties ─────────────────────────────────────────────────────

    @property
    def format_name(self) -> str:
        return _FORMATS[self._fmt_combo.currentIndex()][1]

    @property
    def output_dir(self) -> str:
        return self._out_dir

    @property
    def copy_images(self) -> bool:
        return self._copy_cb.isChecked()

    # ── internal ──────────────────────────────────────────────────────────────

    def _build_summary(self) -> str:
        imgs = len(self._project.images)
        splits: dict[str, int] = {}
        for r in self._project.images:
            s = r.split or "train"
            splits[s] = splits.get(s, 0) + 1
        split_str = "  ".join(f"{s}: {n}" for s, n in sorted(splits.items()))
        total = sum(self._ann_counts.values())
        count_str = "  ".join(
            f"{t}: {n}" for t, n in sorted(self._ann_counts.items()))
        return (f"Images: {imgs}  ({split_str})\n"
                f"Annotations: {total}  ({count_str})")

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if folder:
            self._out_dir = folder
            self._folder_edit.setText(folder)

    def _on_accept(self):
        folder = self._folder_edit.text().strip()
        if not folder:
            QMessageBox.warning(self, "No output folder",
                                "Please select an output folder.")
            return
        self._out_dir = folder
        if any(cls.attributes for cls in self._project.classes):
            if self.format_name != "coco":
                QMessageBox.information(
                    self, "Attributes not exported",
                    "Class attributes will not be included in the YOLO export.\n"
                    "They are preserved in the project file (.annproj).")
        self.accept()
