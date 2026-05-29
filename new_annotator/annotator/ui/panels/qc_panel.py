"""
QCPanel — validation results and dataset statistics sidebar.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from annotator.validation.base import ValidationReport


_SEV_ICON = {"error": "✖", "warning": "⚠", "info": "ℹ"}
_SEV_COLOR = {"error": "#FF4444", "warning": "#FFA500", "info": "#888888"}


class QCPanel(QWidget):
    """Shows dataset statistics and validation issues. Issues are clickable."""

    validate_requested = pyqtSignal()
    navigate_requested = pyqtSignal(str, str)   # image_path, ann_id (empty = image-level)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        self._btn_validate = QPushButton("▶  Validate")
        self._btn_validate.setEnabled(False)
        self._btn_validate.clicked.connect(self.validate_requested)
        lay.addWidget(self._btn_validate)

        # Statistics group
        stats_box = QGroupBox("Statistics")
        sl = QVBoxLayout(stats_box)
        sl.setSpacing(2)

        self._lbl_coverage  = QLabel("—")
        self._lbl_total     = QLabel("—")
        self._lbl_classes   = QLabel("—")
        self._lbl_classes.setWordWrap(True)
        self._lbl_types     = QLabel("—")
        self._lbl_types.setWordWrap(True)

        for caption, widget in [
            ("Coverage:",    self._lbl_coverage),
            ("Annotations:", self._lbl_total),
            ("By class:",    self._lbl_classes),
            ("By type:",     self._lbl_types),
        ]:
            row = QHBoxLayout()
            cap = QLabel(caption)
            cap.setFixedWidth(76)
            cap.setStyleSheet("color:#999;")
            row.addWidget(cap)
            row.addWidget(widget, stretch=1)
            sl.addLayout(row)

        lay.addWidget(stats_box)

        # Issues
        self._issues_header = QLabel("No validation data  —  press Validate")
        self._issues_header.setStyleSheet("color:#888;font-size:11px;")
        lay.addWidget(self._issues_header)

        self._issues_list = QListWidget()
        self._issues_list.setToolTip("Double-click to navigate to the image")
        self._issues_list.itemDoubleClicked.connect(self._on_item_dblclick)
        lay.addWidget(self._issues_list)

    # ── public API ────────────────────────────────────────────────────────────

    def set_project_loaded(self, loaded: bool):
        self._btn_validate.setEnabled(loaded)
        if not loaded:
            self._reset()

    def show_report(self, report: ValidationReport):
        s = report.stats
        self._lbl_coverage.setText(
            f"{s.get('annotated_images', 0)} / {s.get('total_images', 0)}"
            f"  ({s.get('coverage_pct', 0.0):.1f}%)"
        )
        self._lbl_total.setText(str(s.get("total_annotations", 0)))

        by_class = s.get("by_class", {})
        self._lbl_classes.setText(
            "  ".join(f"{k}: {v}" for k, v in by_class.items()) or "—"
        )
        by_type = s.get("by_type", {})
        self._lbl_types.setText(
            "  ".join(f"{k}: {v}" for k, v in by_type.items()) or "—"
        )

        self._issues_list.clear()
        n = len(report.issues)
        err = report.error_count
        warn = report.warning_count
        if n == 0:
            self._issues_header.setText("✔  No issues found")
            self._issues_header.setStyleSheet("color:#55CC55;font-size:11px;")
        else:
            self._issues_header.setText(
                f"{n} issue{'s' if n > 1 else ''}  "
                f"({err} error{'s' if err != 1 else ''}, "
                f"{warn} warning{'s' if warn != 1 else ''})"
            )
            self._issues_header.setStyleSheet("font-size:11px;")

        for issue in report.issues:
            icon = _SEV_ICON.get(issue.severity, "?")
            name = Path(issue.image_path).name
            text = f"{icon}  {name}  —  {issue.message}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, (issue.image_path, issue.ann_id))
            color = _SEV_COLOR.get(issue.severity, "#CCCCCC")
            item.setForeground(QColor(color))
            self._issues_list.addItem(item)

    # ── internals ─────────────────────────────────────────────────────────────

    def _reset(self):
        self._lbl_coverage.setText("—")
        self._lbl_total.setText("—")
        self._lbl_classes.setText("—")
        self._lbl_types.setText("—")
        self._issues_list.clear()
        self._issues_header.setText("No validation data  —  press Validate")
        self._issues_header.setStyleSheet("color:#888;font-size:11px;")

    def _on_item_dblclick(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            image_path, ann_id = data
            self.navigate_requested.emit(image_path, ann_id or "")
