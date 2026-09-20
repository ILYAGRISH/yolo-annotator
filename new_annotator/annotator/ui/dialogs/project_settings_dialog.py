"""ProjectSettingsDialog — view and edit settings for the open project."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                              QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                              QScrollArea, QSpinBox, QVBoxLayout, QWidget)

from annotator.domain.project import DEFAULT_HOTKEYS, Project, ProjectSettings

_EXPORT_FORMATS = [
    ("Auto  (by class types)",  "auto"),
    ("YOLO Detect",             "yolo_detect"),
    ("YOLO Segment",            "yolo_seg"),
    ("YOLO OBB",                "yolo_obb"),
    ("YOLO Pose",               "yolo_pose"),
    ("YOLO Point",              "yolo_point"),
    ("YOLO Classify",           "yolo_classify"),
]

# Human-readable labels for each hotkey action
_HOTKEY_LABELS: list[tuple[str, str]] = [
    ("navigate_next",  "Next image"),
    ("navigate_prev",  "Prev image"),
    ("view_fit",       "Fit view"),
    ("tool_select",    "Tool: Select"),
    ("tool_polygon",   "Tool: Polygon"),
    ("tool_polyline",  "Tool: Polyline"),
    ("tool_bbox",      "Tool: BBox"),
    ("tool_obb",       "Tool: OBB"),
    ("tool_crack",     "Tool: Crack"),
    ("tool_pose",      "Tool: Pose"),
    ("tool_point",     "Tool: Point"),
    ("tool_brush",     "Tool: Brush"),
]


class KeyCaptureEdit(QLineEdit):
    """Read-only key capture field. Click to focus, then press the desired key."""

    def __init__(self, key_str: str, parent=None):
        super().__init__(parent)
        self._original = key_str
        self.setText(key_str)
        self.setMaximumWidth(72)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setReadOnly(True)
        self.setPlaceholderText("—")
        self.setToolTip("Click then press a key to assign. Esc = cancel, Backspace = clear.")

    def mousePressEvent(self, event):
        self.setReadOnly(False)
        self.selectAll()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        key = event.key()

        # Modifier-only: ignore
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift,
                   Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return

        # Escape: cancel, restore original
        if key == Qt.Key.Key_Escape:
            self.setText(self._original)
            self.setReadOnly(True)
            self.clearFocus()
            return

        # Backspace/Delete: clear (disable)
        if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.setText("")
            self.setReadOnly(True)
            self.clearFocus()
            return

        # Single key (no modifiers): capture
        seq = QKeySequence(int(key))
        text = seq.toString()
        if not text:
            text = event.text()
        self.setText(text)
        self.setReadOnly(True)
        self.clearFocus()

    def focusOutEvent(self, event):
        self.setReadOnly(True)
        super().focusOutEvent(event)


class ProjectSettingsDialog(QDialog):

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Settings")
        self.setMinimumWidth(460)
        self._project = project
        self._hk_edits: dict[str, KeyCaptureEdit] = {}
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

        # Hotkeys group
        hk_grp = QGroupBox("Hotkeys  (click a field, then press the desired key)")
        hk_outer = QVBoxLayout(hk_grp)
        hk_outer.setContentsMargins(4, 4, 4, 4)

        hint = QLabel("Esc = cancel  ·  Backspace = clear (disable)")
        hint.setStyleSheet("color:#888; font-size:10px;")
        hk_outer.addWidget(hint)

        # Two-column layout: Navigation (left) | Tools (right)
        cols = QHBoxLayout()
        cols.setSpacing(16)

        nav_form = QFormLayout()
        nav_form.setHorizontalSpacing(8)
        tools_form = QFormLayout()
        tools_form.setHorizontalSpacing(8)

        for i, (key_id, label) in enumerate(_HOTKEY_LABELS):
            edit = KeyCaptureEdit("", self)
            self._hk_edits[key_id] = edit
            if i < 3:
                nav_form.addRow(label + ":", edit)
            else:
                tools_form.addRow(label + ":", edit)

        nav_box = QWidget()
        nav_box.setLayout(nav_form)
        tools_box = QWidget()
        tools_box.setLayout(tools_form)
        cols.addWidget(nav_box)
        cols.addWidget(tools_box)
        hk_outer.addLayout(cols)
        lay.addWidget(hk_grp)

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

        hk = {**DEFAULT_HOTKEYS, **project.settings.hotkeys}
        for key_id, edit in self._hk_edits.items():
            edit.setText(hk.get(key_id, ""))
            edit._original = hk.get(key_id, "")

        self._lbl_created.setText(project.created_at[:19].replace("T", " "))
        self._lbl_modified.setText(project.modified_at[:19].replace("T", " "))
        self._lbl_id.setText(project.id)

    @property
    def project_name(self) -> str:
        return self._name.text().strip()

    @property
    def result_hotkeys(self) -> dict[str, str]:
        return {k: edit.text().strip() for k, edit in self._hk_edits.items()}

    @property
    def result_settings(self) -> ProjectSettings:
        return ProjectSettings(
            default_export_format=_EXPORT_FORMATS[self._fmt_combo.currentIndex()][1],
            autosave_interval_sec=self._autosave.value(),
            image_folder=self._project.settings.image_folder,
            hotkeys=self.result_hotkeys,
        )
