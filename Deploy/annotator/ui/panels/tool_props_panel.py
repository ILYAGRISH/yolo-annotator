"""
ToolPropsPanel — contextual strip shown below the toolbar when a
parameterized tool is active.

Controls are built dynamically from the tool's get_params_schema() dict.

Schema entry types:
  float  → QDoubleSpinBox
  select → QComboBox

Emits params_changed(dict) whenever any control changes.
"""
from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout,
                              QLabel, QSizePolicy, QSpinBox, QWidget)


class ToolPropsPanel(QFrame):

    params_changed = pyqtSignal(dict)
    commit_requested = pyqtSignal()   # Enter pressed while a param widget has focus

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "ToolPropsPanel { background:#2a2a2a; border-bottom:1px solid #444; }"
            "QLabel { color:#ccc; font-size:11px; }"
        )
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(36)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(8, 4, 8, 4)
        self._layout.setSpacing(12)

        self._controls: dict[str, QWidget] = {}   # param_key → widget
        self._schema: dict = {}
        self.hide()

    # ── public API ────────────────────────────────────────────────────────────

    def load_tool(self, tool) -> None:
        """Show panel with controls built from tool.get_params_schema()."""
        self._clear_controls()
        if not hasattr(tool, "get_params_schema"):
            self.hide()
            return

        schema = tool.get_params_schema()
        if not schema:
            self.hide()
            return

        self._schema = schema
        current_params = getattr(tool, "_params", {})

        for key, spec in schema.items():
            label = QLabel(spec.get("label", key) + ":")
            self._layout.addWidget(label)

            if spec["type"] == "float":
                w = QDoubleSpinBox()
                w.setMinimum(spec.get("min", 0.0))
                w.setMaximum(spec.get("max", 1.0))
                w.setSingleStep(spec.get("step", 0.001))
                w.setDecimals(spec.get("decimals", 3))
                w.setValue(current_params.get(key, spec.get("default", 0.0)))
                w.setFixedWidth(80)
                w.valueChanged.connect(self._emit_params)
                w.installEventFilter(self)
                self._layout.addWidget(w)
                self._controls[key] = w

            elif spec["type"] == "int":
                w = QSpinBox()
                w.setMinimum(spec.get("min", 1))
                w.setMaximum(spec.get("max", 9999))
                w.setSingleStep(spec.get("step", 1))
                w.setValue(int(current_params.get(key, spec.get("default", 1))))
                w.setFixedWidth(70)
                w.valueChanged.connect(self._emit_params)
                w.installEventFilter(self)
                self._layout.addWidget(w)
                self._controls[key] = w

            elif spec["type"] == "select":
                w = QComboBox()
                for opt in spec.get("options", []):
                    w.addItem(opt)
                default = current_params.get(key, spec.get("default", ""))
                idx = w.findText(default)
                if idx >= 0:
                    w.setCurrentIndex(idx)
                w.currentTextChanged.connect(self._emit_params)
                w.installEventFilter(self)
                self._layout.addWidget(w)
                self._controls[key] = w

        self._layout.addStretch()
        self.show()

    def clear_tool(self) -> None:
        self._clear_controls()
        self.hide()

    # ── event filter — forward Enter to active tool ───────────────────────────

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.KeyPress and
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            self.commit_requested.emit()
            return True   # consume — don't let combo/spinbox reopen on Enter
        return False

    # ── internal ─────────────────────────────────────────────────────────────

    def _clear_controls(self):
        self._controls.clear()
        self._schema.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _emit_params(self, _=None):
        params = {}
        for key, widget in self._controls.items():
            if isinstance(widget, QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QComboBox):
                params[key] = widget.currentText()
        self.params_changed.emit(params)
