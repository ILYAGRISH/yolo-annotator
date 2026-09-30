"""SplitDatasetDialog — proportional train/val/test assignment for project images."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
                              QGroupBox, QLabel, QRadioButton, QSpinBox,
                              QVBoxLayout)

from annotator.domain.project import Project


class SplitDatasetDialog(QDialog):

    def __init__(self, project: Project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split Dataset")
        self.setMinimumWidth(430)
        self._project = project
        self._setup_ui()
        self._update_train_label()

    def _setup_ui(self):
        lay = QVBoxLayout(self)

        # ── Summary ──────────────────────────────────────────────────────────
        counts: dict[str, int] = {}
        for img in self._project.images:
            key = img.split if img.split in ("val", "test") else "train/unassigned"
            counts[key] = counts.get(key, 0) + 1
        total = len(self._project.images)
        parts = "  ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        summary = QLabel(f"Images: {total}  ({parts})")
        summary.setStyleSheet("color:#999; font-size:11px; padding:4px 0;")
        lay.addWidget(summary)

        # ── Mode ─────────────────────────────────────────────────────────────
        mode_box = QGroupBox("Images to split")
        mode_lay = QVBoxLayout(mode_box)
        self._radio_all = QRadioButton(
            "All images  (existing val/test splits will be overwritten)")
        self._radio_unassigned = QRadioButton(
            "Unassigned only  (keep existing val/test, split remaining)")
        self._radio_all.setChecked(True)
        mode_lay.addWidget(self._radio_all)
        mode_lay.addWidget(self._radio_unassigned)
        lay.addWidget(mode_box)

        # ── Proportions ───────────────────────────────────────────────────────
        prop_box = QGroupBox("Proportions")
        prop_lay = QFormLayout(prop_box)

        self._val_spin = QSpinBox()
        self._val_spin.setRange(0, 99)
        self._val_spin.setValue(15)
        self._val_spin.setSuffix(" %")
        self._val_spin.valueChanged.connect(self._update_train_label)

        self._test_spin = QSpinBox()
        self._test_spin.setRange(0, 99)
        self._test_spin.setValue(15)
        self._test_spin.setSuffix(" %")
        self._test_spin.valueChanged.connect(self._update_train_label)

        self._train_lbl = QLabel()
        self._train_lbl.setStyleSheet("font-weight: bold;")

        self._warn_lbl = QLabel()
        self._warn_lbl.setStyleSheet("color: #E05050; font-size: 11px;")
        self._warn_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        prop_lay.addRow("Val:", self._val_spin)
        prop_lay.addRow("Test:", self._test_spin)
        prop_lay.addRow("Train (auto):", self._train_lbl)
        prop_lay.addRow("", self._warn_lbl)
        lay.addWidget(prop_box)

        # ── Options ───────────────────────────────────────────────────────────
        self._shuffle_cb = QCheckBox("Shuffle images before splitting")
        self._shuffle_cb.setChecked(True)
        lay.addWidget(self._shuffle_cb)

        lay.addSpacing(8)

        # ── Buttons ───────────────────────────────────────────────────────────
        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel)
        self._ok_btn = self._btns.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_btn.setText("Split")
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)
        lay.addWidget(self._btns)

    def _update_train_label(self):
        other = self._val_spin.value() + self._test_spin.value()
        train = 100 - other
        if other > 100:
            self._train_lbl.setText("—")
            self._warn_lbl.setText(
                f"Val + Test = {other}% — must not exceed 100%")
            self._ok_btn.setEnabled(False)
        else:
            self._train_lbl.setText(f"{train} %")
            self._warn_lbl.setText("")
            self._ok_btn.setEnabled(True)

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def val_pct(self) -> int:
        return self._val_spin.value()

    @property
    def test_pct(self) -> int:
        return self._test_spin.value()

    @property
    def mode(self) -> str:
        return "all" if self._radio_all.isChecked() else "unassigned"

    @property
    def shuffle(self) -> bool:
        return self._shuffle_cb.isChecked()
