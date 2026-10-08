"""Pre-label dialog: model, class mapping, parameters, which images, run."""
from __future__ import annotations

import time
from pathlib import Path

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDialog,
                             QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
                             QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                             QMessageBox, QProgressBar, QPushButton, QRadioButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout)

from annotator.ml.client import MLBackend, Reply
from annotator.ml.convert import compatible, default_class_type
from annotator.ml.prelabel import (PrelabelRunner, PrelabelSummary, create_classes,
                                   unused_placeholder)
from annotator.ml.prelabel_settings import (EXISTING_ADD, EXISTING_REPLACE,
                                            EXISTING_SKIP, PrelabelSettings)
from annotator.ml.strings import reason, t

_OK, _BAD = "#3aa655", "#d9534f"
_CREATE = "__create__"
_HEADER = "__header__"
_IMGSZ = [0, 320, 480, 640, 800, 960, 1024, 1280, 1536]
_SPLITS = ["train", "val", "test"]


class PrelabelDialog(QDialog):

    def __init__(self, backend: MLBackend, runner: PrelabelRunner, ctrl,
                 allowed_paths, parent=None):
        super().__init__(parent)
        self._backend, self._runner, self._ctrl = backend, runner, ctrl
        self._allowed_paths = allowed_paths            # callable -> [image paths]
        self._project = ctrl.project
        self._settings = PrelabelSettings.load(self._project.project_path)
        self._info: dict | None = None                 # yolo.load_model result
        self._closed = False
        self.setWindowTitle(t("pl_title"))
        self.resize(760, 780)
        self._build()
        self._load_settings_into_ui()
        runner.progress.connect(self._on_progress)
        runner.finished.connect(self._on_finished)
        if self._settings.model and Path(self._settings.model).is_file():
            QTimer.singleShot(0, self._load_model)

    # ── layout ────────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)

        g = QGroupBox(t("pl_grp_model"))
        gv = QVBoxLayout(g)
        row = QHBoxLayout()
        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText(t("model_placeholder"))
        row.addWidget(self._model_edit, 1)
        b = QPushButton(t("btn_browse"))
        b.clicked.connect(self._browse_model)
        row.addWidget(b)
        self._load_btn = QPushButton(t("btn_load"))
        self._load_btn.clicked.connect(self._load_model)
        row.addWidget(self._load_btn)
        gv.addLayout(row)
        self._model_status = QLabel()
        self._model_status.setWordWrap(True)
        gv.addWidget(self._model_status)
        root.addWidget(g)

        g = QGroupBox(t("pl_grp_mapping"))
        gv = QVBoxLayout(g)
        self._filter = QLineEdit()
        self._filter.setPlaceholderText(t("pl_filter"))
        self._filter.setClearButtonEnabled(True)
        self._filter.textChanged.connect(self._apply_filter)
        gv.addWidget(self._filter)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels([t("pl_col_model"), t("pl_col_project")])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        gv.addWidget(self._table, 1)
        row = QHBoxLayout()
        self._mapped_lbl = QLabel()
        row.addWidget(self._mapped_lbl, 1)
        self._create_sel_btn = QPushButton(t("pl_btn_create_sel"))
        self._create_sel_btn.setToolTip(t("pl_create_sel_tip"))
        self._create_sel_btn.clicked.connect(self._create_selected)
        row.addWidget(self._create_sel_btn)
        self._create_btn = QPushButton(t("pl_btn_create"))
        self._create_btn.setToolTip(t("pl_create_tip"))
        self._create_btn.clicked.connect(self._create_missing)
        row.addWidget(self._create_btn)
        gv.addLayout(row)
        root.addWidget(g, 1)

        g = QGroupBox(t("pl_grp_params"))
        form = QFormLayout(g)
        self._conf = _spin(0.01, 0.99, 0.05, 2)
        self._iou = _spin(0.10, 0.95, 0.05, 2)
        self._imgsz = QComboBox()
        for v in _IMGSZ:
            self._imgsz.addItem(t("pl_auto") if v == 0 else str(v), v)
        self._simplify = _spin(0.0, 10.0, 0.5, 1)
        form.addRow(t("pl_conf"), self._conf)
        form.addRow(t("pl_iou"), self._iou)
        form.addRow(t("pl_imgsz"), self._imgsz)
        form.addRow(t("pl_simplify"), self._simplify)
        root.addWidget(g)

        g = QGroupBox(t("pl_grp_images"))
        gv = QVBoxLayout(g)
        row = QHBoxLayout()
        self._scope = QComboBox()
        self._scope.addItem(t("pl_scope_all"), "all")
        for s in _SPLITS:
            self._scope.addItem(t("pl_scope_split", split=s), s)
        self._scope.currentIndexChanged.connect(self._update_count)
        row.addWidget(self._scope)
        self._count_lbl = QLabel()
        row.addWidget(self._count_lbl, 1)
        gv.addLayout(row)
        gv.addWidget(QLabel(t("pl_existing")))
        self._existing = QButtonGroup(self)
        for key, text in ((EXISTING_SKIP, t("pl_ex_skip")),
                          (EXISTING_REPLACE, t("pl_ex_replace")),
                          (EXISTING_ADD, t("pl_ex_add"))):
            rb = QRadioButton(text)
            rb.setProperty("key", key)
            self._existing.addButton(rb)
            gv.addWidget(rb)
        root.addWidget(g)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root.addWidget(self._progress)
        self._result = QLabel()
        self._result.setWordWrap(True)
        self._result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self._result)

        row = QHBoxLayout()
        self._cur_btn = QPushButton(t("pl_btn_current"))
        self._cur_btn.clicked.connect(self._run_current)
        self._run_btn = QPushButton()
        self._run_btn.clicked.connect(self._run_dataset)
        self._stop_btn = QPushButton(t("pl_btn_stop"))
        self._stop_btn.clicked.connect(self._runner.cancel)
        self._stop_btn.setVisible(False)
        close = QPushButton(t("pl_btn_close"))
        close.clicked.connect(self.reject)
        row.addWidget(self._cur_btn)
        row.addWidget(self._run_btn)
        row.addWidget(self._stop_btn)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self._set_ready(False)

    # ── settings <-> UI ───────────────────────────────────────────────────────

    def _load_settings_into_ui(self):
        s = self._settings
        self._model_edit.setText(s.model)
        self._conf.setValue(s.conf)
        self._iou.setValue(s.iou)
        self._imgsz.setCurrentIndex(max(0, self._imgsz.findData(s.imgsz)))
        self._simplify.setValue(s.simplify_px)
        self._scope.setCurrentIndex(max(0, self._scope.findData(s.scope)))
        for b in self._existing.buttons():
            b.setChecked(b.property("key") == s.existing)
        self._update_count()

    def _read_ui_into_settings(self):
        s = self._settings
        s.model = self._model_edit.text().strip().strip('"')
        s.conf = round(self._conf.value(), 2)
        s.iou = round(self._iou.value(), 2)
        s.imgsz = int(self._imgsz.currentData())
        s.simplify_px = self._simplify.value()
        s.scope = self._scope.currentData()
        checked = self._existing.checkedButton()
        s.existing = checked.property("key") if checked else EXISTING_SKIP
        if self._info:
            s.set_mapping(s.model, self._mapping_ids())

    def _save(self):
        self._read_ui_into_settings()
        try:
            self._settings.save(self._project.project_path)
        except OSError:
            pass

    # ── model ─────────────────────────────────────────────────────────────────

    def _browse_model(self):
        start = self._model_edit.text().strip() or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self, t("pick_model"), start,
            "YOLO (*.pt *.onnx *.engine *.torchscript);;All files (*)")
        if path:
            self._model_edit.setText(str(Path(path)))
            self._load_model()

    def _load_model(self):
        path = self._model_edit.text().strip().strip('"')
        if not path:
            return
        self._info = None
        self._table.setRowCount(0)
        self._set_ready(False)
        self._load_btn.setEnabled(False)
        self._model_status.setStyleSheet("")
        self._model_status.setText(t("loading"))
        self._backend.request("yolo.load_model", {"path": path}, on_done=self._on_model)

    def _on_model(self, r: Reply):
        if self._closed:
            return
        self._load_btn.setEnabled(True)
        if not r.ok:
            self._model_status.setText(f"{t('error')} ({r.error_type}): {r.message}")
            self._model_status.setStyleSheet(f"color:{_BAD};")
            return
        self._info = r.result
        res = r.result
        self._model_status.setText(t("model_ok", task=res["task"], n=len(res["classes"]),
                                     device=res["device"], sec=res["load_seconds"],
                                     cached=t("model_cached") if res["cached"] else ""))
        self._model_status.setStyleSheet(f"color:{_OK};")
        self._fill_table()
        self._set_ready(True)

    # ── class mapping ─────────────────────────────────────────────────────────

    def _fill_table(self, choices: dict | None = None):
        """(Re)build the mapping table. `choices` {model id: class id | None |
        _CREATE} keeps the current state; otherwise the saved mapping / same name."""
        info = self._info
        task = info["task"]
        saved = choices if choices is not None else \
            self._settings.mapping_for(self._model_edit.text().strip()) or {}
        classes = [c for c in self._project.classes if compatible(task, c.annotation_type)]
        state = []
        for mc in info["classes"]:
            if mc["id"] in saved:                            # remembered choice, if still valid
                choice = saved[mc["id"]]
                if choice != _CREATE and not any(c.id == choice for c in classes):
                    choice = None
            else:                                            # same name, compatible type
                choice = next((c.id for c in classes if c.name.lower() == mc["name"].lower()), None)
            state.append(choice)
        self._table.setRowCount(len(info["classes"]))
        for row, mc in enumerate(info["classes"]):
            self._table.setItem(row, 0, QTableWidgetItem(f"{mc['id']}: {mc['name']}"))
            combo = QComboBox()
            combo.currentIndexChanged.connect(lambda _i, r=row: self._on_choice(r))
            self._table.setCellWidget(row, 1, combo)
        self._populate_combos(state)
        self._apply_filter()
        self._update_mapped()

    def _populate_combos(self, state: list, skip_row: int | None = None):
        """Fill every row's list: skip, free project classes, "+ new class",
        then (under a header) the classes other rows already use — they stay
        selectable (car + truck -> vehicle) but don't clutter the list."""
        info = self._info
        task = info["task"]
        classes = [c for c in self._project.classes if compatible(task, c.annotation_type)]
        for row, mc in enumerate(info["classes"]):
            if row == skip_row:                              # its own list doesn't depend on it
                continue
            choice = state[row]
            used = {v for r, v in enumerate(state) if r != row and isinstance(v, int)}
            combo = self._combo(row)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(t("pl_skip"), None)
            for c in classes:
                if c.id not in used or c.id == choice:
                    combo.addItem(_class_label(c), c.id)
            combo.addItem(t("pl_create", name=mc["name"], type=default_class_type(task)), _CREATE)
            taken = [c for c in classes if c.id in used and c.id != choice]
            if taken:
                combo.insertSeparator(combo.count())
                combo.addItem(t("pl_taken"), _HEADER)
                combo.model().item(combo.count() - 1).setEnabled(False)
                for c in taken:
                    combo.addItem(_class_label(c), c.id)
            combo.setCurrentIndex(0 if choice is None else max(0, combo.findData(choice)))
            combo.blockSignals(False)

    def _state(self) -> list:
        return [self._combo(r).currentData() for r in range(self._table.rowCount())]

    def _on_choice(self, row: int):
        self._populate_combos(self._state(), skip_row=row)   # other rows' lists depend on it
        self._update_mapped()

    def _apply_filter(self):
        text = self._filter.text().strip().lower()
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            self._table.setRowHidden(row, bool(text) and text not in item.text().lower())

    def _combo(self, row: int) -> QComboBox:
        return self._table.cellWidget(row, 1)

    def _mapping_ids(self) -> dict[int, int | None]:
        out = {}
        for row, mc in enumerate((self._info or {}).get("classes", [])):
            data = self._combo(row).currentData()
            out[mc["id"]] = data if isinstance(data, int) else None
        return out

    # ── creating classes ──────────────────────────────────────────────────────

    def _visible_rows(self) -> list[int]:
        return [r for r in range(self._table.rowCount()) if not self._table.isRowHidden(r)]

    def _marked_rows(self) -> list[int]:
        return [r for r in range(self._table.rowCount()) if self._combo(r).currentData() == _CREATE]

    def _create_selected(self):
        """Create the classes marked "+ new class" in their rows."""
        rows = self._marked_rows()
        if not rows:
            self._show_result(t("pl_mark_first"))
            return
        self._create_rows(rows)

    def _create_missing(self):
        """Every row in the list (with a search: the rows found) that is
        "skip" or marked "+ new class"."""
        rows = [r for r in self._visible_rows() if self._combo(r).currentData() in (None, _CREATE)]
        if not rows:
            self._show_result(t("pl_nothing_missing"))
            return
        if len(rows) > 10 and QMessageBox.question(
                self, t("pl_title"), t("pl_confirm_create", n=len(rows))) \
                != QMessageBox.StandardButton.Yes:
            return
        self._create_rows(rows)

    def _create_rows(self, rows: list[int]):
        """Create a project class for each of these model classes, map them,
        rebuild the table keeping every other choice."""
        info = self._info
        if not info or self._runner.running or not rows:
            return
        choices = {mc["id"]: v for mc, v in zip(info["classes"], self._state())}
        placeholder = unused_placeholder(
            self._ctrl, keep_ids={v for v in choices.values() if isinstance(v, int)})
        kpt = (info.get("kpt_shape") or [None])[0]
        model_classes = [info["classes"][r] for r in rows]
        created = create_classes(self._ctrl,
                                 [(mc["name"], default_class_type(info["task"])) for mc in model_classes],
                                 kpt_count=kpt, replace=placeholder)
        for mc, lc in zip(model_classes, created):
            choices[mc["id"]] = lc.id
        self._settings.set_mapping(self._model_edit.text().strip(),
                                   {k: (v if isinstance(v, int) else None) for k, v in choices.items()})
        self._fill_table(choices)
        msg = t("pl_created", n=len(created))
        if placeholder is not None:
            msg += t("pl_placeholder", name=placeholder.name)
        self._show_result(msg)

    def _update_mapped(self):
        if not self._info:
            self._mapped_lbl.setText("")
            return
        state = self._state()
        text = t("pl_mapped", n=sum(1 for v in state if isinstance(v, int)), total=len(state))
        marked = state.count(_CREATE)
        if marked:
            text += t("pl_marked", n=marked)
        self._mapped_lbl.setText(text)

    def _resolve_mapping(self) -> dict:
        """Create the classes still marked "+ new class", then
        {model id: LabelClass | None}."""
        self._create_rows(self._marked_rows())
        return {mid: (self._project.get_class(cid) if cid is not None else None)
                for mid, cid in self._mapping_ids().items()}

    # ── images ────────────────────────────────────────────────────────────────

    def _target_images(self) -> list[str]:
        scope = self._scope.currentData()
        allowed = self._allowed_paths()
        if scope == "all":
            return allowed
        split = {r.path: r.split for r in self._project.images}
        return [p for p in allowed if split.get(p) == scope]

    def _update_count(self):
        n = len(self._target_images())
        self._count_lbl.setText(t("pl_count", n=n))
        self._run_btn.setText(t("pl_btn_run", n=n))

    # ── run ───────────────────────────────────────────────────────────────────

    def _run_current(self):
        path = self._ctrl.current_image
        if not path:
            self._show_result(t("pl_no_image"), bad=True)
            return
        if path not in set(self._allowed_paths()):
            self._show_result(t("pl_not_allowed"), bad=True)
            return
        self._start([path], current=True)

    def _run_dataset(self):
        images = self._target_images()
        if not images:
            self._show_result(t("pl_no_images"), bad=True)
            return
        self._start(images, current=False)

    def _start(self, images: list[str], current: bool):
        if not self._info:
            self._show_result(t("pl_load_first"), bad=True)
            return
        mapping = self._resolve_mapping()
        self._save()
        existing = self._settings.existing
        if current and existing == EXISTING_SKIP:          # an explicit click must do something
            existing = EXISTING_REPLACE
        self._set_running(True, len(images))
        self._runner.start(images, self._settings, mapping, existing)

    def _on_progress(self, done: int, total: int, name: str):
        if self._closed:
            return
        self._progress.setMaximum(total)
        self._progress.setValue(done)
        self._result.setStyleSheet("")
        self._result.setText(t("pl_running", done=done, total=total, name=name))

    def _on_finished(self, s: PrelabelSummary):
        if self._closed:
            return
        self._set_running(False, 0)
        self._update_count()
        self._show_result(*summary_text(s))

    # ── helpers ───────────────────────────────────────────────────────────────

    def _show_result(self, text: str, bad: bool = False):
        self._result.setText(text)
        self._result.setStyleSheet(f"color:{_BAD if bad else _OK};")

    def _set_ready(self, ready: bool):
        for w in (self._cur_btn, self._run_btn, self._create_btn, self._create_sel_btn):
            w.setEnabled(ready)

    def _set_running(self, running: bool, total: int):
        self._progress.setVisible(running)
        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(0)
        self._stop_btn.setVisible(running)
        self._cur_btn.setVisible(not running)
        self._run_btn.setVisible(not running)
        for w in (self._model_edit, self._load_btn, self._table, self._filter,
                  self._create_btn, self._create_sel_btn,
                  self._conf, self._iou, self._imgsz, self._simplify, self._scope):
            w.setEnabled(not running)
        for b in self._existing.buttons():
            b.setEnabled(not running)

    def done(self, result: int):
        if self._runner.running:                   # closing stops the run (results so far stay)
            self._runner.cancel()
            end = time.monotonic() + 15
            loop = QEventLoop()
            while self._runner.running and time.monotonic() < end:
                QTimer.singleShot(20, loop.quit)
                loop.exec()
        self._closed = True
        self._save()
        for sig, slot in ((self._runner.progress, self._on_progress),
                          (self._runner.finished, self._on_finished)):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
        super().done(result)


def summary_text(s: PrelabelSummary) -> tuple[str, bool]:
    """(text, is_error) for a finished run."""
    if s.fatal:
        return f"{t('error')}: {s.fatal}", True
    lines = [t("pl_done", sec=s.seconds, processed=s.processed, added=s.added)
             + (t("pl_replaced", n=s.replaced) if s.replaced else "")]
    if s.skipped_existing:
        lines.append(t("pl_skipped_existing", n=s.skipped_existing))
    if s.skip_reasons:
        reasons = ", ".join(f"{reason(k)} — {v}" for k, v in s.skip_reasons.items())
        lines.append(t("pl_not_counted", reasons=reasons))
    if s.failed:
        lines.append(t("pl_failed", n=s.failed) + ": " + "; ".join(s.errors))
    if s.cancelled:
        lines.append(t("pl_cancelled"))
    return "\n".join(lines), bool(s.failed)


def _class_label(c) -> str:
    return f"{c.id}: {c.name}  [{c.annotation_type}]"


def _spin(lo: float, hi: float, step: float, decimals: int) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setSingleStep(step)
    sp.setDecimals(decimals)
    return sp
