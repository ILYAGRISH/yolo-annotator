"""
ClassSchemaEditorDialog — full editor for the class schema.

Layout:
  Left list  │  Right form (name, color, annotation_type, allowed_tools,
             │              subclasses, attributes, display_style)
"""
from __future__ import annotations
import copy
import uuid

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QComboBox, QVBoxLayout, QWidget,
)

from annotator.domain.label_class import (
    ANNOTATION_TYPES, ClassAttribute, DisplayStyle,
    LabelClass, SkeletonKeypoint,
)


def _color_icon(color: str) -> QIcon:
    px = QPixmap(14, 14)
    px.fill(QColor(color))
    return QIcon(px)


# All drawing tools — "select" excluded (it is a navigation tool, not an annotation tool)

class ClassSchemaEditorDialog(QDialog):
    """
    Edit the full list of classes. Returns the modified list via .result_classes
    if accepted.
    """

    def __init__(self, classes: list[LabelClass], parent=None, count_fn=None):
        super().__init__(parent)
        self.setWindowTitle("Class Schema Editor")
        self.resize(820, 580)
        self.setModal(True)

        # Deep-copy so Cancel discards all changes
        self._classes: list[LabelClass] = copy.deepcopy(classes)
        self._selected_idx: int = -1
        # IDs created during this editor session — annotation_type stays editable for them
        self._new_class_ids: set[int] = set()
        self.result_classes: list[LabelClass] = []
        # count_fn(class_id) -> int  — provided by main_window
        self._count_fn = count_fn
        # (class_id, reassign_to | None) — applied by main_window after accept
        self._pending_deletions: list[tuple[int, int | None]] = []

        self._build_ui()
        self._refresh_list()
        if self._classes:
            self._class_list.setCurrentRow(0)

    @property
    def pending_deletions(self) -> list[tuple[int, int | None]]:
        return list(self._pending_deletions)

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── left: class list ──────────────────────────────────────────────────
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Classes"))
        self._class_list = QListWidget()
        self._class_list.currentRowChanged.connect(self._on_class_selected)
        ll.addWidget(self._class_list)

        btn_row = QHBoxLayout()
        for label, slot in [("+ Add", self._add_class),
                             ("↑", self._move_up),
                             ("↓", self._move_down)]:
            b = QPushButton(label)
            b.setFixedHeight(24)
            b.clicked.connect(slot)
            btn_row.addWidget(b)
        b_del = QPushButton("− Delete")
        b_del.setFixedHeight(24)
        b_del.setStyleSheet("color:#c0392b;")
        b_del.clicked.connect(self._delete_class)
        btn_row.addWidget(b_del)
        btn_row.addStretch()
        ll.addLayout(btn_row)
        left.setMaximumWidth(220)
        splitter.addWidget(left)

        # ── right: class form ─────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 0, 0, 0)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._name_edit = QLineEdit()
        self._name_edit.editingFinished.connect(self._sync_name)
        form.addRow("Name:", self._name_edit)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(40, 24)
        self._color_btn.clicked.connect(self._pick_color)
        self._color_label = QLabel()
        color_row.addWidget(self._color_btn)
        color_row.addWidget(self._color_label)
        color_row.addStretch()
        form.addRow("Color:", color_row)

        # annotation_type: editable combo for new classes; plain label for existing
        type_container = QWidget()
        type_row = QHBoxLayout(type_container)
        type_row.setContentsMargins(0, 0, 0, 0)
        self._type_combo = QComboBox()
        self._type_combo.addItems(ANNOTATION_TYPES)
        self._type_combo.currentTextChanged.connect(self._sync_type)
        self._type_label = QLabel()
        self._type_label.setStyleSheet("font-weight: bold; padding: 2px 0;")
        type_row.addWidget(self._type_combo)
        type_row.addWidget(self._type_label)
        type_row.addStretch()
        form.addRow("Annotation type:", type_container)

        rl.addLayout(form)

        # Subclasses
        sub_box = QGroupBox("Subclasses")
        sl = QVBoxLayout(sub_box)
        self._sub_list = QListWidget()
        self._sub_list.setMaximumHeight(90)
        sl.addWidget(self._sub_list)
        sub_btns = QHBoxLayout()
        b_sub_add = QPushButton("+ Add")
        b_sub_add.setFixedHeight(22)
        b_sub_add.clicked.connect(self._add_subclass)
        b_sub_rm = QPushButton("− Remove")
        b_sub_rm.setFixedHeight(22)
        b_sub_rm.clicked.connect(self._remove_subclass)
        sub_btns.addWidget(b_sub_add)
        sub_btns.addWidget(b_sub_rm)
        sub_btns.addStretch()
        sl.addLayout(sub_btns)
        rl.addWidget(sub_box)

        # Attributes
        attr_box = QGroupBox("Attributes")
        al = QVBoxLayout(attr_box)
        self._attr_table = QTableWidget(0, 3)
        self._attr_table.setHorizontalHeaderLabels(["Name", "Type", "Options / default"])
        self._attr_table.horizontalHeader().setStretchLastSection(True)
        self._attr_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self._attr_table.setMaximumHeight(130)
        al.addWidget(self._attr_table)
        self._attr_table.cellDoubleClicked.connect(self._edit_attribute)
        attr_btns = QHBoxLayout()
        b_attr_add = QPushButton("+ Add attribute")
        b_attr_add.setFixedHeight(22)
        b_attr_add.clicked.connect(self._add_attribute)
        b_attr_rm = QPushButton("− Remove")
        b_attr_rm.setFixedHeight(22)
        b_attr_rm.clicked.connect(self._remove_attribute)
        attr_btns.addWidget(b_attr_add)
        attr_btns.addWidget(b_attr_rm)
        attr_btns.addStretch()
        al.addLayout(attr_btns)
        rl.addWidget(attr_box)

        # Skeleton (keypoints type only)
        self._skel_box = QGroupBox("Skeleton  (keypoints order)")
        skel_l = QVBoxLayout(self._skel_box)
        self._kp_list = QListWidget()
        self._kp_list.setMaximumHeight(100)
        skel_l.addWidget(self._kp_list)
        kp_btns = QHBoxLayout()
        b_kp_add = QPushButton("+ Add keypoint")
        b_kp_add.setFixedHeight(22)
        b_kp_add.clicked.connect(self._add_keypoint)
        b_kp_rm = QPushButton("− Remove last")
        b_kp_rm.setFixedHeight(22)
        b_kp_rm.clicked.connect(self._remove_keypoint)
        kp_btns.addWidget(b_kp_add)
        kp_btns.addWidget(b_kp_rm)
        kp_btns.addStretch()
        skel_l.addLayout(kp_btns)
        edges_form = QFormLayout()
        self._edges_edit = QLineEdit()
        self._edges_edit.setPlaceholderText('e.g. "0-1, 1-2, 1-5"')
        self._edges_edit.editingFinished.connect(self._sync_skeleton)
        edges_form.addRow("Edges (i-j pairs):", self._edges_edit)
        skel_l.addLayout(edges_form)
        rl.addWidget(self._skel_box)

        # Display style
        style_box = QGroupBox("Display style")
        sty_l = QFormLayout(style_box)
        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setRange(0.0, 1.0)
        self._opacity_spin.setSingleStep(0.05)
        self._opacity_spin.setDecimals(2)
        self._opacity_spin.valueChanged.connect(self._sync_style)
        sty_l.addRow("Opacity:", self._opacity_spin)
        self._lw_spin = QSpinBox()
        self._lw_spin.setRange(1, 20)
        self._lw_spin.valueChanged.connect(self._sync_style)
        sty_l.addRow("Line width:", self._lw_spin)
        rl.addWidget(style_box)

        rl.addStretch()
        splitter.addWidget(right)
        splitter.setSizes([200, 600])

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._skel_box.setVisible(False)
        self._set_form_enabled(False)

    # ── list management ───────────────────────────────────────────────────────

    def _refresh_list(self):
        self._class_list.blockSignals(True)
        self._class_list.clear()
        for c in self._classes:
            item = QListWidgetItem(_color_icon(c.color), f"{c.id}: {c.name}")
            self._class_list.addItem(item)
        self._class_list.blockSignals(False)

    def _on_class_selected(self, row: int):
        if row < 0 or row >= len(self._classes):
            self._selected_idx = -1
            self._set_form_enabled(False)
            return
        self._selected_idx = row
        self._set_form_enabled(True)
        self._load_class(self._classes[row])

    def _add_class(self):
        dlg = _NewClassDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        next_id = max((c.id for c in self._classes), default=-1) + 1
        color = LabelClass.default_color(next_id)
        new_cls = LabelClass(
            id=next_id, name=dlg.class_name, color=color,
            annotation_type=dlg.annotation_type,
        )
        self._new_class_ids.add(next_id)
        self._classes.append(new_cls)
        self._refresh_list()
        self._class_list.setCurrentRow(len(self._classes) - 1)

    def _move_up(self):
        r = self._class_list.currentRow()
        if r <= 0:
            return
        self._classes[r - 1], self._classes[r] = self._classes[r], self._classes[r - 1]
        self._refresh_list()
        self._class_list.setCurrentRow(r - 1)

    def _move_down(self):
        r = self._class_list.currentRow()
        if r < 0 or r >= len(self._classes) - 1:
            return
        self._classes[r], self._classes[r + 1] = self._classes[r + 1], self._classes[r]
        self._refresh_list()
        self._class_list.setCurrentRow(r + 1)

    def _delete_class(self):
        r = self._class_list.currentRow()
        if r < 0 or r >= len(self._classes):
            return
        if len(self._classes) == 1:
            QMessageBox.warning(self, "Cannot delete",
                                "At least one class must remain in the schema.")
            return
        target = self._classes[r]

        if target.id in self._new_class_ids:
            # Never saved — remove silently, no annotation impact
            self._classes.pop(r)
            self._new_class_ids.discard(target.id)
        else:
            count = self._count_fn(target.id) if self._count_fn else 0
            others = [c for c in self._classes if c.id != target.id]
            from annotator.ui.dialogs.class_delete_dialog import ClassDeleteDialog
            dlg = ClassDeleteDialog(target, count, others, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            reassign_to = dlg.reassign_to if dlg.action == "reassign" else None
            self._pending_deletions.append((target.id, reassign_to))
            self._classes.pop(r)

        self._refresh_list()
        new_row = min(r, len(self._classes) - 1)
        if new_row >= 0:
            self._class_list.setCurrentRow(new_row)
        else:
            self._set_form_enabled(False)

    # ── form ──────────────────────────────────────────────────────────────────

    def _set_form_enabled(self, enabled: bool):
        for w in [self._name_edit, self._color_btn,
                  self._sub_list, self._attr_table,
                  self._opacity_spin, self._lw_spin,
                  self._kp_list, self._edges_edit]:
            w.setEnabled(enabled)
        self._type_combo.setEnabled(enabled)
        self._type_label.setEnabled(enabled)

    def _load_class(self, c: LabelClass):
        self._name_edit.blockSignals(True)
        self._name_edit.setText(c.name)
        self._name_edit.blockSignals(False)

        self._color_label.setText(c.color)
        self._color_btn.setStyleSheet(
            f"background-color:{c.color};border:1px solid #555;")

        # annotation_type: combo only for classes created in this session
        is_new = c.id in self._new_class_ids
        self._type_combo.setVisible(is_new)
        self._type_label.setVisible(not is_new)
        if is_new:
            idx = ANNOTATION_TYPES.index(c.annotation_type) if c.annotation_type in ANNOTATION_TYPES else 0
            self._type_combo.blockSignals(True)
            self._type_combo.setCurrentIndex(idx)
            self._type_combo.blockSignals(False)
        else:
            self._type_label.setText(c.annotation_type)

        self._update_type_ui(c.annotation_type)

        self._sub_list.clear()
        for s in c.subclasses:
            self._sub_list.addItem(s)

        self._attr_table.setRowCount(0)
        for attr in c.attributes:
            self._append_attr_row(attr)

        self._opacity_spin.blockSignals(True)
        self._opacity_spin.setValue(c.display_style.opacity)
        self._opacity_spin.blockSignals(False)

        self._lw_spin.blockSignals(True)
        self._lw_spin.setValue(c.display_style.line_width)
        self._lw_spin.blockSignals(False)

        self._load_skeleton_ui(c)

    def _update_type_ui(self, annotation_type: str):
        self._skel_box.setVisible(annotation_type == "keypoints")

    def _current_class(self) -> LabelClass | None:
        if self._selected_idx < 0:
            return None
        return self._classes[self._selected_idx]

    def _sync_name(self):
        c = self._current_class()
        if c is None:
            return
        c.name = self._name_edit.text().strip() or c.name
        item = self._class_list.item(self._selected_idx)
        if item:
            item.setText(f"{c.id}: {c.name}")

    def _pick_color(self):
        c = self._current_class()
        if c is None:
            return
        col = QColorDialog.getColor(QColor(c.color), self)
        if col.isValid():
            c.color = col.name()
            self._color_label.setText(c.color)
            self._color_btn.setStyleSheet(
                f"background-color:{c.color};border:1px solid #555;")
            item = self._class_list.item(self._selected_idx)
            if item:
                item.setIcon(_color_icon(c.color))

    def _sync_type(self, text: str):
        c = self._current_class()
        if c is None:
            return
        c.annotation_type = text
        self._update_type_ui(text)

    def _sync_style(self):
        c = self._current_class()
        if c is None:
            return
        c.display_style.opacity = self._opacity_spin.value()
        c.display_style.line_width = self._lw_spin.value()

    # ── skeleton ──────────────────────────────────────────────────────────────

    def _load_skeleton_ui(self, c: LabelClass):
        """Populate skeleton list + edges field from class.skeleton."""
        self._kp_list.clear()
        for i, kp in enumerate(c.skeleton):
            self._kp_list.addItem(f"{i}: {kp.name}")
        edges = self._collect_edges(c.skeleton)
        self._edges_edit.blockSignals(True)
        self._edges_edit.setText(", ".join(f"{a}-{b}" for a, b in edges))
        self._edges_edit.blockSignals(False)

    @staticmethod
    def _collect_edges(skeleton: list) -> list[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        for i, kp in enumerate(skeleton):
            for j in kp.edges:
                if 0 <= j < len(skeleton) and i != j:
                    pairs.add((min(i, j), max(i, j)))
        return sorted(pairs)

    def _sync_skeleton(self):
        c = self._current_class()
        if c is None:
            return
        n = len(c.skeleton)
        pairs = self._parse_edges(self._edges_edit.text(), n)
        # Reset all edges, then apply parsed pairs
        for kp in c.skeleton:
            kp.edges = []
        for a, b in pairs:
            if a < n:
                c.skeleton[a].edges.append(b)
            if b < n:
                c.skeleton[b].edges.append(a)

    @staticmethod
    def _parse_edges(text: str, n_kp: int) -> list[tuple[int, int]]:
        pairs: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                a_s, b_s = part.split("-")
                a, b = int(a_s.strip()), int(b_s.strip())
                if 0 <= a < n_kp and 0 <= b < n_kp and a != b:
                    p = (min(a, b), max(a, b))
                    if p not in seen:
                        seen.add(p)
                        pairs.append(p)
            except (ValueError, AttributeError):
                pass
        return pairs

    def _add_keypoint(self):
        c = self._current_class()
        if c is None:
            return
        name, ok = QInputDialog.getText(
            self, "Add keypoint", f"Name for keypoint {len(c.skeleton)}:")
        if ok and name.strip():
            kp = SkeletonKeypoint(name=name.strip())
            c.skeleton.append(kp)
            self._kp_list.addItem(f"{len(c.skeleton)-1}: {kp.name}")

    def _remove_keypoint(self):
        c = self._current_class()
        if c is None or not c.skeleton:
            return
        last_idx = len(c.skeleton) - 1
        c.skeleton.pop()
        # Remove any edges referencing the removed index
        for kp in c.skeleton:
            kp.edges = [e for e in kp.edges if e != last_idx]
        self._load_skeleton_ui(c)

    # ── subclasses ────────────────────────────────────────────────────────────

    def _add_subclass(self):
        c = self._current_class()
        if c is None:
            return
        name, ok = QInputDialog.getText(self, "Add subclass", "Subclass label:")
        if ok and name.strip():
            c.subclasses.append(name.strip())
            self._sub_list.addItem(name.strip())

    def _remove_subclass(self):
        c = self._current_class()
        if c is None:
            return
        r = self._sub_list.currentRow()
        if r >= 0:
            c.subclasses.pop(r)
            self._sub_list.takeItem(r)

    # ── attributes ────────────────────────────────────────────────────────────

    def _append_attr_row(self, attr: ClassAttribute):
        row = self._attr_table.rowCount()
        self._attr_table.insertRow(row)
        self._attr_table.setItem(row, 0, QTableWidgetItem(attr.name))
        self._attr_table.setItem(row, 1, QTableWidgetItem(attr.attr_type))
        opts = (", ".join(attr.options) if attr.options
                else (str(attr.default_value) if attr.default_value is not None else ""))
        self._attr_table.setItem(row, 2, QTableWidgetItem(opts))
        self._attr_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, attr.id)

    def _add_attribute(self):
        c = self._current_class()
        if c is None:
            return
        dlg = _AttributeDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            attr = ClassAttribute(
                id=str(uuid.uuid4()),
                name=dlg.attr_name,
                attr_type=dlg.attr_type,
                options=dlg.options,
                default_value=dlg.default_value,
            )
            c.attributes.append(attr)
            self._append_attr_row(attr)

    def _edit_attribute(self, row: int, col: int):
        c = self._current_class()
        if c is None or row < 0 or row >= len(c.attributes):
            return
        attr = c.attributes[row]
        dlg = _AttributeDialog(self, attr=attr)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            attr.name = dlg.attr_name
            attr.attr_type = dlg.attr_type
            attr.options = dlg.options
            attr.default_value = dlg.default_value
            self._attr_table.item(row, 0).setText(attr.name)
            self._attr_table.item(row, 1).setText(attr.attr_type)
            opts = (", ".join(attr.options) if attr.options
                    else (str(attr.default_value) if attr.default_value is not None else ""))
            self._attr_table.item(row, 2).setText(opts)

    def _remove_attribute(self):
        c = self._current_class()
        if c is None:
            return
        row = self._attr_table.currentRow()
        if row < 0:
            return
        attr_id = self._attr_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        c.attributes = [a for a in c.attributes if a.id != attr_id]
        self._attr_table.removeRow(row)

    # ── accept / reject ───────────────────────────────────────────────────────

    def _accept(self):
        if not self._classes:
            QMessageBox.warning(self, "Empty schema",
                                "At least one class is required.")
            return
        self.result_classes = self._classes
        self.accept()


# ── New class creation dialog ─────────────────────────────────────────────────

class _NewClassDialog(QDialog):
    """Name + annotation_type selection at class creation time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add class")
        self.setFixedWidth(300)
        self.class_name = ""
        self.annotation_type = "bbox"

        lay = QFormLayout(self)

        self._name = QLineEdit()
        lay.addRow("Name:", self._name)

        self._type = QComboBox()
        self._type.addItems(ANNOTATION_TYPES)
        lay.addRow("Annotation type:", self._type)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

    def _ok(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        self.class_name = name
        self.annotation_type = self._type.currentText()
        self.accept()


# ── Attribute dialog ──────────────────────────────────────────────────────────

class _AttributeDialog(QDialog):
    _TYPES = ["text", "number", "bool", "select"]

    def __init__(self, parent=None, attr: "ClassAttribute | None" = None):
        super().__init__(parent)
        self.setWindowTitle("Edit attribute" if attr else "Add attribute")
        self.setFixedWidth(320)
        self.attr_name = ""
        self.attr_type = "text"
        self.options: list[str] = []
        self.default_value = None

        lay = QFormLayout(self)

        self._name = QLineEdit()
        lay.addRow("Name:", self._name)

        self._type = QComboBox()
        self._type.addItems(self._TYPES)
        self._type.currentTextChanged.connect(self._on_type)
        lay.addRow("Type:", self._type)

        self._opts_label = QLabel("Options (comma-separated):")
        self._opts_edit = QLineEdit()
        self._opts_label.setVisible(False)
        self._opts_edit.setVisible(False)
        lay.addRow(self._opts_label, self._opts_edit)

        self._default_edit = QLineEdit()
        lay.addRow("Default:", self._default_edit)

        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addRow(bb)

        if attr is not None:
            self._name.setText(attr.name)
            idx = self._TYPES.index(attr.attr_type) if attr.attr_type in self._TYPES else 0
            self._type.setCurrentIndex(idx)
            self._on_type(attr.attr_type)
            if attr.options:
                self._opts_edit.setText(", ".join(attr.options))
            if attr.default_value is not None:
                self._default_edit.setText(str(attr.default_value))

    def _on_type(self, t: str):
        show_opts = t == "select"
        self._opts_label.setVisible(show_opts)
        self._opts_edit.setVisible(show_opts)

    def _ok(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Name is required.")
            return
        self.attr_name = name
        self.attr_type = self._type.currentText()
        if self.attr_type == "select":
            self.options = [o.strip() for o in self._opts_edit.text().split(",") if o.strip()]
        self.default_value = self._default_edit.text().strip() or None
        self.accept()
