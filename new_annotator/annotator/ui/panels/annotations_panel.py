from __future__ import annotations

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.i18n import tr


def _icon(color: str) -> QIcon:
    px = QPixmap(12, 12)
    px.fill(QColor(color))
    return QIcon(px)


class AnnotationsPanel(QWidget):
    """Shows annotations for the currently selected image."""

    select_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    edit_source_requested = pyqtSignal(str)
    classify_image_requested = pyqtSignal(int)
    attribute_changed = pyqtSignal(str, dict)   # ann_id, new_data

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: Project | None = None
        self._annotations: list[Annotation] = []
        self._active_class_id: int | None = None
        self._selected_ann_id: str | None = None
        self._attr_widgets: list[tuple] = []    # [(ClassAttribute, QWidget), ...]
        self._rebuilding: bool = False          # guard against signals during form rebuild
        self._commit_pending: bool = False      # deferred commit already scheduled
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(4)

        self._header = QLabel(tr("annotations"))
        lay.addWidget(self._header)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row)
        lay.addWidget(self._list)

        # ── Attribute form ────────────────────────────────────────────────
        self._attr_frame = QFrame()
        self._attr_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._attr_frame.setVisible(False)
        af = QVBoxLayout(self._attr_frame)
        af.setContentsMargins(4, 4, 4, 2)
        af.setSpacing(3)

        lbl = QLabel("Attributes")
        lbl.setStyleSheet("font-size:11px; color:#aaa;")
        af.addWidget(lbl)

        self._attr_form = QWidget()
        self._attr_layout = QFormLayout(self._attr_form)
        self._attr_layout.setContentsMargins(0, 0, 0, 0)
        self._attr_layout.setSpacing(4)
        af.addWidget(self._attr_form)

        # ── Subclass selector ─────────────────────────────────────────────
        self._sub_frame = QFrame()
        self._sub_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._sub_frame.setVisible(False)
        sf = QHBoxLayout(self._sub_frame)
        sf.setContentsMargins(4, 3, 4, 3)
        sf.setSpacing(6)
        self._sub_lbl = QLabel(tr("subclass_lbl"))
        self._sub_lbl.setStyleSheet("font-size:11px;")
        sf.addWidget(self._sub_lbl)
        self._sub_combo = QComboBox()
        self._sub_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._sub_combo.currentIndexChanged.connect(self._commit_attrs)
        sf.addWidget(self._sub_combo)
        lay.addWidget(self._sub_frame)

        lay.addWidget(self._attr_frame)

        # ── Bottom buttons ────────────────────────────────────────────────
        self._btn_classify = QPushButton(tr("btn_classify_img"))
        self._btn_classify.setVisible(False)
        self._btn_classify.clicked.connect(self._classify_image)
        lay.addWidget(self._btn_classify)

        row = QHBoxLayout()
        self._btn_edit_src = QPushButton(tr("btn_edit_src"))
        self._btn_edit_src.setEnabled(False)
        self._btn_edit_src.setToolTip(
            "Edit the source polyline of a crack annotation")
        self._btn_edit_src.clicked.connect(self._edit_source)
        self._btn_del = QPushButton(tr("btn_delete"))
        self._btn_del.clicked.connect(self._delete)
        row.addWidget(self._btn_edit_src)
        row.addWidget(self._btn_del)
        lay.addLayout(row)

    # ── public API ────────────────────────────────────────────────────────

    def retranslate(self):
        self._sub_lbl.setText(tr("subclass_lbl"))
        self._btn_edit_src.setText(tr("btn_edit_src"))
        self._btn_del.setText(tr("btn_delete"))
        self.refresh(self._annotations)

    def load_project(self, project: Project):
        self._project = project

    def set_active_class(self, cls) -> None:
        self._active_class_id = cls.id if cls else None
        is_classify = cls is not None and cls.annotation_type == "classification"
        self._btn_classify.setVisible(is_classify)
        if is_classify:
            self._btn_classify.setText(f'+ Classify as "{cls.name}"')

    def refresh(self, annotations: list[Annotation]):
        self._annotations = list(annotations)
        self._list.blockSignals(True)
        self._list.clear()
        self._header.setText(f"{tr('annotations')} ({len(annotations)})")
        for ann in annotations:
            color, name = "#888888", str(ann.class_id)
            if self._project:
                cls = self._project.get_class(ann.class_id)
                if cls:
                    color, name = cls.color, cls.name
            if ann.ann_type == AnnotationType.CLASSIFY:
                label = f"{name}  [IMAGE LABEL]"
            else:
                sub = ann.data.get("subclass", "")
                sub_str = f"  · {sub}" if sub else f"  ({self._pts_count(ann)} pts)"
                label = f"{name}  [{ann.ann_type.value}]{sub_str}"
            self._list.addItem(QListWidgetItem(_icon(color), label))
        self._list.blockSignals(False)
        self._rebuild_attr_form()

    def set_selected(self, annotation_id: str):
        self._selected_ann_id = annotation_id
        self._list.blockSignals(True)
        found: Annotation | None = None
        for i, ann in enumerate(self._annotations):
            if ann.id == annotation_id:
                self._list.setCurrentRow(i)
                found = ann
                break
        self._list.blockSignals(False)
        self._btn_edit_src.setEnabled(
            found is not None and "source_geometry" in found.data)
        self._rebuild_attr_form()

    # ── attribute form ────────────────────────────────────────────────────

    def _rebuild_attr_form(self):
        self._rebuilding = True
        self._commit_pending = False   # cancel any pending commit for old widgets
        try:
            for _, w in self._attr_widgets:
                w.blockSignals(True)
            self._attr_widgets.clear()
            while self._attr_layout.rowCount():
                self._attr_layout.removeRow(0)

            if not self._selected_ann_id or not self._project:
                self._sub_frame.setVisible(False)
                self._attr_frame.setVisible(False)
                return

            ann = next((a for a in self._annotations
                        if a.id == self._selected_ann_id), None)
            if ann is None:
                self._sub_frame.setVisible(False)
                self._attr_frame.setVisible(False)
                return

            cls = self._project.get_class(ann.class_id)
            if cls is None:
                self._sub_frame.setVisible(False)
                self._attr_frame.setVisible(False)
                return

            # ── subclass combobox ─────────────────────────────────────────
            self._sub_combo.blockSignals(True)
            self._sub_combo.clear()
            if cls.subclasses:
                self._sub_combo.addItem("— (none) —")
                for s in cls.subclasses:
                    self._sub_combo.addItem(s)
                current_sub = ann.data.get("subclass", "")
                if current_sub in cls.subclasses:
                    self._sub_combo.setCurrentText(current_sub)
                else:
                    self._sub_combo.setCurrentIndex(0)
            self._sub_combo.blockSignals(False)
            self._sub_frame.setVisible(bool(cls.subclasses))

            if not cls.attributes:
                self._attr_frame.setVisible(False)
                return

            saved = ann.data.get("attributes", {})
            for attr in cls.attributes:
                val = saved.get(attr.name, attr.default_value)
                w = self._make_widget(attr, val)
                self._attr_layout.addRow(f"{attr.name}:", w)
                self._attr_widgets.append((attr, w))

            self._attr_frame.setVisible(True)
        finally:
            self._rebuilding = False

    def _make_widget(self, attr, value) -> QWidget:
        if attr.attr_type == "bool":
            w = QCheckBox()
            w.setChecked(bool(value) if value is not None else False)
            w.stateChanged.connect(self._commit_attrs)
            return w

        if attr.attr_type == "number":
            w = QDoubleSpinBox()
            w.setRange(-1e9, 1e9)
            w.setDecimals(4)
            w.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
            try:
                w.setValue(float(value) if value is not None else 0.0)
            except (TypeError, ValueError):
                w.setValue(0.0)
            w.editingFinished.connect(self._commit_attrs)
            return w

        if attr.attr_type == "select":
            w = QComboBox()
            for opt in attr.options:
                w.addItem(opt)
            if value in attr.options:
                w.setCurrentText(str(value))
            w.currentIndexChanged.connect(self._commit_attrs)
            return w

        # text (default)
        w = QLineEdit()
        w.setText(str(value) if value is not None else "")
        w.editingFinished.connect(self._commit_attrs)
        return w

    def _collect_attrs(self) -> dict:
        out = {}
        for attr, w in self._attr_widgets:
            if attr.attr_type == "bool":
                out[attr.name] = w.isChecked()
            elif attr.attr_type == "number":
                out[attr.name] = w.value()
            elif attr.attr_type == "select":
                out[attr.name] = w.currentText()
            else:
                out[attr.name] = w.text()
        return out

    def _commit_attrs(self):
        # Schedule a deferred commit so the widget's signal handler can return
        # before refresh() destroys the widget. Multiple rapid changes collapse
        # into one commit via _commit_pending guard.
        if self._rebuilding or not self._selected_ann_id or self._commit_pending:
            return
        self._commit_pending = True
        QTimer.singleShot(0, self._do_commit)

    def _do_commit(self):
        self._commit_pending = False
        if self._rebuilding or not self._selected_ann_id or not self._attr_widgets:
            return
        ann = next((a for a in self._annotations
                    if a.id == self._selected_ann_id), None)
        if ann is None:
            return
        new_data = {**ann.data, "attributes": self._collect_attrs()}
        if self._sub_frame.isVisible():
            idx = self._sub_combo.currentIndex()
            new_data["subclass"] = self._sub_combo.currentText() if idx > 0 else ""
        self.attribute_changed.emit(self._selected_ann_id, new_data)

    # ── internal slots ────────────────────────────────────────────────────

    @staticmethod
    def _pts_count(ann: Annotation) -> int:
        return len(ann.data.get("points", []))

    def _on_row(self, row: int):
        if 0 <= row < len(self._annotations):
            ann = self._annotations[row]
            self._selected_ann_id = ann.id
            self.select_requested.emit(ann.id)
            self._btn_edit_src.setEnabled("source_geometry" in ann.data)
        else:
            self._selected_ann_id = None
            self._btn_edit_src.setEnabled(False)
        self._rebuild_attr_form()

    def _classify_image(self):
        if self._active_class_id is not None:
            self.classify_image_requested.emit(self._active_class_id)

    def _edit_source(self):
        r = self._list.currentRow()
        if 0 <= r < len(self._annotations):
            self.edit_source_requested.emit(self._annotations[r].id)

    def _delete(self):
        r = self._list.currentRow()
        if 0 <= r < len(self._annotations):
            self.delete_requested.emit(self._annotations[r].id)
