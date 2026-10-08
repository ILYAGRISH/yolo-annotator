"""Boxes -> outlines dialog: which boxes, into which class, which images, run."""
from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
                             QGroupBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                             QVBoxLayout)

from annotator.ml import config
from annotator.ml.client import MLBackend
from annotator.ml.prelabel import create_classes
from annotator.ml.sam_boxes import (SOURCE_TYPES, TARGET_TYPES, BoxSummary, SamBoxRunner)
from annotator.ml.strings import t

_OK, _BAD = "#3aa655", "#d9534f"
_SPLITS = ["train", "val", "test"]
_NEW = "__new__:"                      # target combo: "+ new class" entries carry "__new__:<type>"


class SamBoxesDialog(QDialog):

    def __init__(self, backend: MLBackend, runner: SamBoxRunner, ctrl, allowed_paths, parent=None):
        super().__init__(parent)
        self._backend, self._runner, self._ctrl = backend, runner, ctrl
        self._allowed_paths = allowed_paths            # callable -> [image paths]
        self._project = ctrl.project
        self._closed = False
        self.setWindowTitle(t("sb_title"))
        self.resize(620, 460)
        self._build()
        runner.progress.connect(self._on_progress)
        runner.finished.connect(self._on_finished)
        self._fill_classes()
        self._update_model()
        self._update_count()

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        intro = QLabel(t("sb_intro"))
        intro.setWordWrap(True)
        root.addWidget(intro)

        g = QGroupBox(t("sb_grp_classes"))
        form = QFormLayout(g)
        self._source = QComboBox()
        self._source.currentIndexChanged.connect(self._fill_targets)
        self._target = QComboBox()
        form.addRow(t("sb_source"), self._source)
        form.addRow(t("sb_target"), self._target)
        self._delete = QCheckBox(t("sb_delete"))
        form.addRow("", self._delete)
        root.addWidget(g)

        g = QGroupBox(t("sb_grp_model"))
        row = QHBoxLayout(g)
        self._model_lbl = QLabel()
        self._model_lbl.setWordWrap(True)
        row.addWidget(self._model_lbl, 1)
        pick = QPushButton(t("btn_browse"))
        pick.clicked.connect(self._pick_model)
        row.addWidget(pick)
        root.addWidget(g)

        g = QGroupBox(t("pl_grp_images"))
        row = QHBoxLayout(g)
        self._scope = QComboBox()
        self._scope.addItem(t("sb_scope_current"), "current")
        self._scope.addItem(t("pl_scope_all"), "all")
        for s in _SPLITS:
            self._scope.addItem(t("pl_scope_split", split=s), s)
        self._scope.currentIndexChanged.connect(self._update_count)
        row.addWidget(self._scope)
        self._count_lbl = QLabel()
        row.addWidget(self._count_lbl, 1)
        root.addWidget(g)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)
        self._result = QLabel()
        self._result.setWordWrap(True)
        self._result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._result)
        root.addStretch(1)

        row = QHBoxLayout()
        self._run_btn = QPushButton(t("sb_run"))
        self._run_btn.clicked.connect(self._run)
        self._stop_btn = QPushButton(t("pl_btn_stop"))
        self._stop_btn.clicked.connect(self._runner.cancel)
        self._stop_btn.setVisible(False)
        close = QPushButton(t("pl_btn_close"))
        close.clicked.connect(self.reject)
        row.addWidget(self._run_btn)
        row.addWidget(self._stop_btn)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)

    # ── classes ───────────────────────────────────────────────────────────────

    def _fill_classes(self):
        self._source.blockSignals(True)
        self._source.clear()
        for c in self._project.classes:
            if c.annotation_type in SOURCE_TYPES:
                self._source.addItem(_label(c), c.id)
        self._source.blockSignals(False)
        self._fill_targets()

    def _fill_targets(self):
        src = self._project.get_class(self._source.currentData()) if self._source.count() else None
        same_source = src is not None and src.id == getattr(self, "_filled_for", None)
        keep = self._target.currentData() if same_source else None   # new source: default again
        self._filled_for = src.id if src is not None else None
        self._target.clear()
        for c in self._project.classes:
            if c.annotation_type in TARGET_TYPES and (src is None or c.id != src.id):
                self._target.addItem(_label(c), c.id)
        if src is not None:
            for kind in ("polygon", "mask"):
                self._target.addItem(t("sb_new_class", name=f"{src.name}_{kind}", type=kind),
                                     _NEW + kind)
        idx = self._target.findData(keep) if keep is not None else -1
        if idx < 0 and src is not None:
            # never a random class: one named after the boxes (car -> car_poly), else a new one
            idx = next((i for i in range(self._target.count())
                        if isinstance(self._target.itemData(i), int)
                        and self._project.get_class(self._target.itemData(i)).name.lower()
                        .startswith(src.name.lower())), -1)
            if idx < 0:
                idx = self._target.findData(_NEW + "polygon")
        self._target.setCurrentIndex(max(0, idx))
        self._update_ready()

    def _resolve_target(self):
        """The target class; creates it for a "+ new class" entry."""
        data = self._target.currentData()
        if isinstance(data, str) and data.startswith(_NEW):
            kind = data[len(_NEW):]
            src = self._project.get_class(self._source.currentData())
            lc = create_classes(self._ctrl, [(f"{src.name}_{kind}", kind)])[0]
            keep_src = src.id
            self._fill_classes()
            self._source.setCurrentIndex(max(0, self._source.findData(keep_src)))
            self._target.setCurrentIndex(max(0, self._target.findData(lc.id)))
            return lc
        return self._project.get_class(data) if data is not None else None

    # ── model, images ─────────────────────────────────────────────────────────

    def _update_model(self):
        path = config.sam_model()
        ok = bool(path) and Path(path).is_file()
        self._model_lbl.setText(path if ok else t("sam_no_model"))
        self._model_lbl.setStyleSheet("" if ok else f"color:{_BAD};")
        self._update_ready()

    def _pick_model(self):
        start = config.sam_model() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, t("sam_pick"), start, "SAM (*.pt);;All files (*)")
        if path:
            config.set_sam_model(str(Path(path)))
            self._update_model()

    def _target_images(self) -> list[str]:
        scope = self._scope.currentData()
        allowed = self._allowed_paths()
        if scope == "current":
            cur = self._ctrl.current_image
            return [cur] if cur and cur in set(allowed) else []
        if scope == "all":
            return allowed
        split = {r.path: r.split for r in self._project.images}
        return [p for p in allowed if split.get(p) == scope]

    def _update_count(self):
        self._count_lbl.setText(t("pl_count", n=len(self._target_images())))

    def _update_ready(self):
        model = config.sam_model()
        ready = (self._source.count() > 0 and self._target.count() > 0
                 and bool(model) and Path(model).is_file() and not self._runner.running)
        self._run_btn.setEnabled(ready)
        if self._source.count() == 0:
            self._show_result(t("sb_no_source"), bad=True)

    # ── run ───────────────────────────────────────────────────────────────────

    def _run(self):
        images = self._target_images()
        if not images:
            self._show_result(t("pl_no_images"), bad=True)
            return
        source = self._project.get_class(self._source.currentData())
        target = self._resolve_target()
        if source is None or target is None:
            return
        self._set_running(True, len(images))
        self._runner.start(images, source, target, config.sam_model(),
                           delete_source=self._delete.isChecked())

    def _on_progress(self, done: int, total: int, name: str):
        if self._closed:
            return
        self._progress.setValue(done)
        self._progress.setFormat(f"{done} / {total} · {name}")

    def _on_finished(self, s: BoxSummary):
        if self._closed:
            return
        self._set_running(False, 0)
        text, bad = summary_text(s)
        self._show_result(text, bad)

    def _show_result(self, text: str, bad: bool = False):
        self._result.setText(text)
        self._result.setStyleSheet(f"color:{_BAD};" if bad else "")

    def _set_running(self, running: bool, total: int):
        self._progress.setVisible(running)
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(0)
        self._stop_btn.setVisible(running)
        self._run_btn.setVisible(not running)
        for w in (self._source, self._target, self._delete, self._scope):
            w.setEnabled(not running)

    def done(self, result: int):
        if self._runner.running:                     # closing stops the run
            self._runner.cancel()
            end = time.monotonic() + 15
            loop = QEventLoop()
            while self._runner.running and time.monotonic() < end:
                QTimer.singleShot(20, loop.quit)
                loop.exec()
        self._closed = True
        for sig, slot in ((self._runner.progress, self._on_progress),
                          (self._runner.finished, self._on_finished)):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
        super().done(result)


def summary_text(s: BoxSummary) -> tuple[str, bool]:
    """(text, is_error) for a finished run."""
    if s.fatal:
        return f"{t('error')}: {s.fatal}", True
    lines = [t("sb_done", sec=s.seconds, images=s.images, n=s.outlined)
             + (t("sb_removed", n=s.removed) if s.removed else "")]
    if s.empty:
        lines.append(t("sb_empty", n=s.empty))
    if s.images == 0 and not s.failed and not s.cancelled:
        lines.append(t("sb_nothing"))
    if s.failed:
        lines.append(t("pl_failed", n=s.failed) + ": " + "; ".join(s.errors))
    if s.cancelled:
        lines.append(t("pl_cancelled"))
    return "\n".join(lines), bool(s.failed)


def _label(c) -> str:
    return f"{c.id}: {c.name}  [{c.annotation_type}]"
