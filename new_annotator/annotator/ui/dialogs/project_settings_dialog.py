"""ProjectSettingsDialog — view and edit settings for the open project."""
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                              QGroupBox, QLabel, QLineEdit, QSpinBox, QVBoxLayout)

from annotator.domain.project import Project, ProjectSettings

_EXPORT_FORMATS = [
    ("Auto  (by class types)",  "auto"),
    ("YOLO Detect",             "yolo_detect"),
    ("YOLO Segment",            "yolo_seg"),
    ("YOLO OBB",                "yolo_obb"),
    ("YOLO Pose",               "yolo_pose"),
    ("YOLO Point",              "yolo_point"),
    ("YOLO Classify",           "yolo_classify"),
]


class ProjectSettingsDialog(QDialog):

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(440)
        self._project = project
        self._setup_ui()
        self._load(project)

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # Name
        top = QFormLayout()
        top.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self._name = QLineEdit()
        top.addRow("Name:", self._name)
        lay.addLayout(top)

        # Settings group
        sgrp = QGroupBox("Settings")
        sform = QFormLayout(sgrp)
        sform.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._fmt_combo = QComboBox()
        for label, _ in _EXPORT_FORMATS:
            self._fmt_combo.addItem(label)
        sform.addRow("Auto-export format:", self._fmt_combo)

        self._autosave = QSpinBox()
        self._autosave.setRange(10, 3600)
        self._autosave.setSingleStep(10)
        self._autosave.setSuffix(" sec")
        sform.addRow("Autosave interval:", self._autosave)

        lay.addWidget(sgrp)

        # Info group (read-only)
        igrp = QGroupBox("Info")
        iform = QFormLayout(igrp)

        self._lbl_created = QLabel()
        self._lbl_modified = QLabel()
        self._lbl_id = QLabel()
        self._lbl_id.setStyleSheet("color:#888; font-size:10px;")

        iform.addRow("Created:", self._lbl_created)
        iform.addRow("Modified:", self._lbl_modified)
        iform.addRow("ID:", self._lbl_id)
        lay.addWidget(igrp)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _load(self, project: Project):
        self._name.setText(project.name)

        fmt = project.settings.default_export_format
        for i, (_, key) in enumerate(_EXPORT_FORMATS):
            if key == fmt:
                self._fmt_combo.setCurrentIndex(i)
                break

        self._autosave.setValue(project.settings.autosave_interval_sec)

        self._lbl_created.setText(project.created_at[:19].replace("T", " "))
        self._lbl_modified.setText(project.modified_at[:19].replace("T", " "))
        self._lbl_id.setText(project.id)

    @property
    def project_name(self) -> str:
        return self._name.text().strip()

    @property
    def result_settings(self) -> ProjectSettings:
        return ProjectSettings(
            default_export_format=_EXPORT_FORMATS[self._fmt_combo.currentIndex()][1],
            autosave_interval_sec=self._autosave.value(),
            image_folder=self._project.settings.image_folder,  # preserve existing
        )
