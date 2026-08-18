"""ExportDatasetDialog — single-format or multi-task (detect + segment) export."""
from pathlib import Path

from PyQt6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog,
                              QDialogButtonBox, QFileDialog, QFormLayout,
                              QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                              QMessageBox, QPushButton, QRadioButton,
                              QVBoxLayout)

from annotator.domain.project import Project
from annotator.exporters.export_job import ExportJob

_FORMATS = [
    ("YOLO Detect  (bbox → cx cy w h)",              "yolo_detect"),
    ("YOLO Segment  (polygon / polyline / mask)",     "yolo_seg"),
    ("YOLO OBB  (oriented bbox → 4 corners)",         "yolo_obb"),
    ("YOLO Pose  (keypoints → bbox + kpoints)",       "yolo_pose"),
    ("YOLO Point  (single point → 1-kpt pose)",       "yolo_point"),
    ("YOLO Classify  (image-level classification)",   "yolo_classify"),
    ("COCO Instances  (JSON with attributes)",        "coco"),
    ("COCO Keypoints  (JSON keypoints format)",       "coco_keypoints"),
]

_POLICIES = [
    ("Skip incompatible types  (safe default)",  "skip"),
    ("Convert to compatible format  (bbox↔poly)", "convert"),
]


class ExportDatasetDialog(QDialog):

    def __init__(self, project: Project, ann_counts: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Dataset")
        self.setMinimumWidth(520)
        self._project = project
        self._ann_counts = ann_counts
        self._out_dir = ""
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # ── Mode selector ──────────────────────────────────────────────────────
        mode_box = QGroupBox("Export mode")
        mode_lay = QVBoxLayout(mode_box)
        self._radio_single = QRadioButton("Single format")
        self._radio_multi  = QRadioButton("Multi-task  (Detect + Segment, shared images/)")
        self._radio_single.setChecked(True)
        self._radio_single.toggled.connect(self._on_mode_changed)
        mode_lay.addWidget(self._radio_single)
        mode_lay.addWidget(self._radio_multi)
        lay.addWidget(mode_box)

        # ── Single-format section ──────────────────────────────────────────────
        self._single_group = QGroupBox("Format")
        single_lay = QFormLayout(self._single_group)
        self._fmt_combo = QComboBox()
        for label, _ in _FORMATS:
            self._fmt_combo.addItem(label)
        single_lay.addRow("Format:", self._fmt_combo)
        lay.addWidget(self._single_group)

        # ── Multi-task section ─────────────────────────────────────────────────
        self._multi_group = QGroupBox("Tasks")
        multi_lay = QFormLayout(self._multi_group)
        self._chk_detect   = QCheckBox("YOLO Detect  (bbox labels)")
        self._chk_segment  = QCheckBox("YOLO Segment  (polygon / mask labels)")
        self._chk_obb      = QCheckBox("YOLO OBB  (oriented bbox labels)")
        self._chk_pose     = QCheckBox("YOLO Pose  (keypoints labels)")
        self._chk_classify = QCheckBox("YOLO Classify  (image folders → classify/)")
        self._chk_detect.setChecked(True)
        self._chk_segment.setChecked(True)
        self._policy_combo = QComboBox()
        for label, _ in _POLICIES:
            self._policy_combo.addItem(label)
        multi_lay.addRow("", self._chk_detect)
        multi_lay.addRow("", self._chk_segment)
        multi_lay.addRow("", self._chk_obb)
        multi_lay.addRow("", self._chk_pose)
        multi_lay.addRow("", self._chk_classify)
        multi_lay.addRow("Incompatible types:", self._policy_combo)
        self._multi_group.setVisible(False)
        lay.addWidget(self._multi_group)

        # ── Output folder ──────────────────────────────────────────────────────
        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        row = QHBoxLayout()
        self._folder_edit = QLineEdit()
        self._folder_edit.setPlaceholderText("Select output folder…")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        row.addWidget(self._folder_edit)
        row.addWidget(browse_btn)
        form.addRow("Output folder:", row)
        self._copy_cb = QCheckBox("Copy images to output folder")
        self._copy_cb.setChecked(True)
        form.addRow("", self._copy_cb)
        lay.addLayout(form)

        # ── Summary ────────────────────────────────────────────────────────────
        lay.addSpacing(8)
        lay.addWidget(QLabel("<b>Project summary</b>"))
        summary = QLabel(self._build_summary())
        summary.setStyleSheet("color:#999; font-size:11px; padding-left:4px;")
        summary.setWordWrap(True)
        lay.addWidget(summary)
        lay.addSpacing(8)

        # ── Buttons ────────────────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── public properties ─────────────────────────────────────────────────────

    @property
    def is_multitask(self) -> bool:
        return self._radio_multi.isChecked()

    @property
    def format_name(self) -> str:
        return _FORMATS[self._fmt_combo.currentIndex()][1]

    @property
    def export_jobs(self) -> list[ExportJob]:
        policy = _POLICIES[self._policy_combo.currentIndex()][1]
        jobs = []
        if self._chk_detect.isChecked():
            jobs.append(ExportJob("yolo_detect", geometry_policy=policy))
        if self._chk_segment.isChecked():
            jobs.append(ExportJob("yolo_seg", geometry_policy=policy))
        if self._chk_obb.isChecked():
            jobs.append(ExportJob("yolo_obb", geometry_policy=policy))
        if self._chk_pose.isChecked():
            jobs.append(ExportJob("yolo_pose", geometry_policy=policy))
        if self._chk_classify.isChecked():
            jobs.append(ExportJob("yolo_classify", geometry_policy=policy))
        return jobs

    @property
    def output_dir(self) -> str:
        return self._out_dir

    @property
    def copy_images(self) -> bool:
        return self._copy_cb.isChecked()

    # ── internal ──────────────────────────────────────────────────────────────

    def _on_mode_changed(self, single_checked: bool):
        self._single_group.setVisible(single_checked)
        self._multi_group.setVisible(not single_checked)

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

        if self.is_multitask and not self.export_jobs:
            QMessageBox.warning(self, "No tasks selected",
                                "Select at least one task (Detect or Segment).")
            return

        if not self.is_multitask:
            if any(cls.attributes for cls in self._project.classes):
                if self.format_name != "coco":
                    QMessageBox.information(
                        self, "Attributes not exported",
                        "Class attributes will not be included in the YOLO export.\n"
                        "They are preserved in the project file (.annproj).")
        self.accept()
