"""ML Settings dialog: choose the interpreter, check it, test-load a model.

Works on the shared MLBackend. "Check" restarts the backend with the
interpreter typed in the field; on close the backend is switched back to the
saved choice (and stopped if it was running another interpreter — it starts
again lazily on the next request)."""
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

from annotator.ml import config
from annotator.ml.client import MLBackend, Reply, format_info
from annotator.ml.strings import t

_OK, _BAD = "#3aa655", "#d9534f"


def _same_file(a, b) -> bool:
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except (OSError, ValueError):
        return False


class MLSettingsDialog(QDialog):

    def __init__(self, backend: MLBackend, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._busy = False
        self._closed = False             # late replies after close are ignored
        self.setWindowTitle(t("dlg_title"))
        self.resize(720, 760)
        self._build()
        self._python_edit.setText(config.saved_python())
        self._model_edit.setText(config.test_model())
        self._sam_edit.setText(config.sam_model())
        self._autostart.setChecked(config.autostart())
        self._update_env_hint()
        for line in backend.log_tail:
            self._log.appendPlainText(line)
        backend.log_line.connect(self._log.appendPlainText)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)

        env = QGroupBox(t("grp_env"))
        ev = QVBoxLayout(env)
        intro = QLabel(t("env_intro"))
        intro.setWordWrap(True)
        ev.addWidget(intro)
        row = QHBoxLayout()
        self._python_edit = QLineEdit()
        self._python_edit.setPlaceholderText(t("env_placeholder", default=config.default_python()))
        self._python_edit.textChanged.connect(self._update_env_hint)
        row.addWidget(self._python_edit, 1)
        browse = QPushButton(t("btn_browse"))
        browse.clicked.connect(self._browse_python)
        row.addWidget(browse)
        self._check_btn = QPushButton(t("btn_check"))
        self._check_btn.clicked.connect(self._check)
        row.addWidget(self._check_btn)
        ev.addLayout(row)
        self._env_hint = QLabel()
        self._env_hint.setWordWrap(True)
        ev.addWidget(self._env_hint)
        self._info_grid = QGridLayout()
        self._info_grid.setColumnStretch(2, 1)
        ev.addLayout(self._info_grid)
        self._check_status = QLabel()
        self._check_status.setWordWrap(True)
        ev.addWidget(self._check_status)
        self._autostart = QCheckBox(t("chk_autostart"))
        ev.addWidget(self._autostart)
        root.addWidget(env)

        model = QGroupBox(t("grp_model"))
        mv = QVBoxLayout(model)
        row = QHBoxLayout()
        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText(t("model_placeholder"))
        row.addWidget(self._model_edit, 1)
        mbrowse = QPushButton(t("btn_browse"))
        mbrowse.clicked.connect(self._browse_model)
        row.addWidget(mbrowse)
        self._load_btn = QPushButton(t("btn_load"))
        self._load_btn.clicked.connect(self._load_model)
        row.addWidget(self._load_btn)
        mv.addLayout(row)
        self._model_status = QLabel()
        self._model_status.setWordWrap(True)
        self._model_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        mv.addWidget(self._model_status)
        root.addWidget(model)

        sam = QGroupBox(t("sam_grp"))
        sv = QVBoxLayout(sam)
        intro = QLabel(t("sam_intro"))
        intro.setWordWrap(True)
        intro.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        sv.addWidget(intro)
        row = QHBoxLayout()
        self._sam_edit = QLineEdit()
        self._sam_edit.setPlaceholderText(t("sam_placeholder"))
        row.addWidget(self._sam_edit, 1)
        sbrowse = QPushButton(t("btn_browse"))
        sbrowse.clicked.connect(self._browse_sam)
        row.addWidget(sbrowse)
        self._sam_btn = QPushButton(t("btn_load"))
        self._sam_btn.clicked.connect(self._load_sam)
        row.addWidget(self._sam_btn)
        sv.addLayout(row)
        self._sam_status = QLabel()
        self._sam_status.setWordWrap(True)
        sv.addWidget(self._sam_status)
        root.addWidget(sam)

        logbox = QGroupBox(t("grp_log"))
        lv = QVBoxLayout(logbox)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(500)
        self._log.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        lv.addWidget(self._log)
        root.addWidget(logbox, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ── environment ───────────────────────────────────────────────────────────

    def _typed_python(self) -> str:
        return self._python_edit.text().strip().strip('"')

    def _update_env_hint(self):
        typed = self._typed_python()
        found = config.resolve_python(typed)
        if found is None:
            self._env_hint.setText(t("env_missing"))
            self._env_hint.setStyleSheet(f"color:{_BAD};")
        else:
            self._env_hint.setText(f"Python: {found}")
            self._env_hint.setStyleSheet("color:gray;")

    def _browse_python(self):
        start = self._typed_python() or str(config.app_dir())
        flt = "Python (python.exe)" if os.name == "nt" else "Python (python python3)"
        path, _ = QFileDialog.getOpenFileName(self, t("pick_python"), start, flt)
        if path:
            self._python_edit.setText(str(Path(path)))

    def _check(self):
        self._clear_info()
        self._set_busy(True)
        self._check_status.setStyleSheet("")
        self._check_status.setText(t("checking"))
        self._backend.set_python(self._typed_python())
        self._backend.stop()
        self._backend.request("system.info", on_done=self._on_info)

    def _on_info(self, r: Reply):
        if self._closed:
            return
        self._set_busy(False)
        if not r.ok:
            self._show_error(self._check_status, r)
            return
        all_ok = True
        for row, (label, value, ok) in enumerate(format_info(r.result)):
            mark = QLabel("✓" if ok else "✗")    # not ✔/✖: those render as colour emoji
            mark.setStyleSheet(f"color:{_OK if ok else _BAD}; font-weight:bold;")
            val = QLabel(value)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._info_grid.addWidget(mark, row, 0)
            self._info_grid.addWidget(QLabel(f"<b>{label}</b>"), row, 1)
            self._info_grid.addWidget(val, row, 2)
            all_ok = all_ok and ok
        self._check_status.setText(t("check_ok") if all_ok else t("check_warn"))
        self._check_status.setStyleSheet(f"color:{_OK if all_ok else _BAD};")

    def _clear_info(self):
        while self._info_grid.count():
            w = self._info_grid.takeAt(0).widget()
            if w:
                w.deleteLater()

    # ── model ─────────────────────────────────────────────────────────────────

    def _browse_model(self):
        start = self._model_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, t("pick_model"), start,
            "YOLO (*.pt *.onnx *.engine *.torchscript);;All files (*)")
        if path:
            self._model_edit.setText(str(Path(path)))

    def _load_model(self):
        path = self._model_edit.text().strip().strip('"')
        if not path:
            return
        self._set_busy(True)
        self._model_status.setStyleSheet("")
        self._model_status.setText(t("loading"))
        self._backend.set_python(self._typed_python())
        self._backend.request("yolo.load_model", {"path": path}, on_done=self._on_model)

    def _on_model(self, r: Reply):
        if self._closed:
            return
        self._set_busy(False)
        if not r.ok:
            self._show_error(self._model_status, r)
            return
        res = r.result
        names = ", ".join(f"{c['id']}: {c['name']}" for c in res["classes"][:40])
        if len(res["classes"]) > 40:
            names += ", …"
        head = t("model_ok", task=res["task"], n=len(res["classes"]), device=res["device"],
                 sec=res["load_seconds"], cached=t("model_cached") if res["cached"] else "")
        self._model_status.setText(f"{head}\n{names}")
        self._model_status.setStyleSheet(f"color:{_OK};")

    # ── SAM ───────────────────────────────────────────────────────────────────

    def _browse_sam(self):
        start = self._sam_edit.text().strip() or self._model_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, t("sam_pick"), start, "SAM (*.pt);;All files (*)")
        if path:
            self._sam_edit.setText(str(Path(path)))
            self._load_sam()

    def _load_sam(self):
        path = self._sam_edit.text().strip().strip('"')
        if not path:
            return
        self._set_busy(True)
        self._sam_status.setStyleSheet("")
        self._sam_status.setText(t("loading"))
        self._backend.set_python(self._typed_python())
        self._backend.request("sam.load_model", {"path": path}, on_done=self._on_sam)

    def _on_sam(self, r: Reply):
        if self._closed:
            return
        self._set_busy(False)
        if not r.ok:
            self._show_error(self._sam_status, r)
            return
        res = r.result
        self._sam_status.setText(t("sam_load_ok", device=res["device"], sec=res["load_seconds"],
                                   cached=t("model_cached") if res["cached"] else ""))
        self._sam_status.setStyleSheet(f"color:{_OK};")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _show_error(self, label: QLabel, r: Reply):
        label.setText(f"{t('error')} ({r.error_type}): {r.message}")
        label.setStyleSheet(f"color:{_BAD};")

    def _set_busy(self, busy: bool):
        self._busy = busy
        self._check_btn.setEnabled(not busy)
        self._load_btn.setEnabled(not busy)
        self._sam_btn.setEnabled(not busy)

    def done(self, result: int):
        self._closed = True
        if result == QDialog.DialogCode.Accepted:
            config.set_saved_python(self._typed_python())
            config.set_autostart(self._autostart.isChecked())
            config.set_test_model(self._model_edit.text().strip())
            config.set_sam_model(self._sam_edit.text().strip().strip('"'))
        # back to the saved interpreter; drop a process that runs another one
        # (it starts again, with the right one, on the next request)
        self._backend.set_python(None)
        running = self._backend.ready_info.get("executable", "")
        wanted = config.resolve_python()
        if self._backend.running and (wanted is None or not _same_file(running, wanted)):
            self._backend.stop()
        try:
            self._backend.log_line.disconnect(self._log.appendPlainText)
        except TypeError:
            pass
        super().done(result)
