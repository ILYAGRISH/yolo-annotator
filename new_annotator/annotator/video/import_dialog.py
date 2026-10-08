"""
File › Import Video… (Phase 8-B): pick a video, a frame step and a time range;
frames are extracted in a background thread and added to the project.
"""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                             QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QProgressBar, QPushButton, QSpinBox, QVBoxLayout)

from annotator.i18n import tr
from annotator.video.extract import (VIDEO_EXTS, VideoInfo, extract, frames_to_extract,
                                     probe, video_id)


class _Worker(QObject):
    progress = pyqtSignal(int)
    done = pyqtSignal(list, str)               # frames, error text

    def __init__(self, args: dict):
        super().__init__()
        self._args = args
        self.stop = False

    def run(self):
        try:
            frames = extract(**self._args, progress=lambda n, _f: self.progress.emit(n),
                             cancelled=lambda: self.stop)
            self.done.emit(frames, "")
        except Exception as exc:              # unreadable file, disk full…
            self.done.emit([], str(exc))


class ImportVideoDialog(QDialog):

    def __init__(self, ctrl, parent=None, path: str = ""):
        super().__init__(parent)
        self._ctrl = ctrl
        self._info: VideoInfo | None = None
        self._thread: QThread | None = None
        self._worker: _Worker | None = None
        self.added = 0
        self.first_frame = ""
        self.setWindowTitle(tr("vid_title"))
        self.setMinimumWidth(560)
        self._build()
        if path:
            self._set_video(path)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        lay = QVBoxLayout(self)
        form = QFormLayout()
        row = QHBoxLayout()
        self._path = QLineEdit()
        self._path.setReadOnly(True)
        browse = QPushButton(tr("vid_browse"))
        browse.clicked.connect(self._browse)
        row.addWidget(self._path, 1)
        row.addWidget(browse)
        form.addRow(tr("vid_file"), row)
        self._about = QLabel("—")
        self._about.setStyleSheet("color:#999;")
        form.addRow("", self._about)

        self._step = QSpinBox()
        self._step.setRange(1, 10000)
        self._step.setValue(5)
        self._step.setSuffix(tr("vid_step_suffix"))
        self._step.valueChanged.connect(self._update_estimate)
        form.addRow(tr("vid_step"), self._step)

        rng = QHBoxLayout()
        self._start = QDoubleSpinBox()
        self._end = QDoubleSpinBox()
        for sb in (self._start, self._end):
            sb.setDecimals(1)
            sb.setSuffix(tr("vid_sec"))
            sb.setRange(0, 0)
            sb.valueChanged.connect(self._update_estimate)
            rng.addWidget(sb)
        rng.insertWidget(1, QLabel("—"))
        rng.addStretch(1)
        form.addRow(tr("vid_range"), rng)

        self._estimate = QLabel("")
        form.addRow("", self._estimate)

        orow = QHBoxLayout()
        self._out = QLineEdit()
        ob = QPushButton(tr("vid_browse"))
        ob.clicked.connect(self._browse_out)
        orow.addWidget(self._out, 1)
        orow.addWidget(ob)
        form.addRow(tr("vid_folder"), orow)
        lay.addLayout(form)

        hint = QLabel(tr("vid_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#999;font-size:11px;")
        lay.addWidget(hint)

        self._bar = QProgressBar()
        self._bar.setVisible(False)
        lay.addWidget(self._bar)

        self._buttons = QDialogButtonBox()
        self._run = self._buttons.addButton(tr("vid_import"), QDialogButtonBox.ButtonRole.AcceptRole)
        self._close = self._buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self._run.clicked.connect(self._start_extract)
        self._close.clicked.connect(self.reject)
        self._run.setEnabled(False)
        lay.addWidget(self._buttons)

    def _browse(self):
        exts = " ".join(f"*{e}" for e in sorted(VIDEO_EXTS))
        path, _ = QFileDialog.getOpenFileName(self, tr("vid_title"), "",
                                              f"{tr('vid_filter')} ({exts});;* (*)")
        if path:
            self._set_video(path)

    def _browse_out(self):
        folder = QFileDialog.getExistingDirectory(self, tr("vid_folder"), self._out.text())
        if folder:
            self._out.setText(folder)

    def _set_video(self, path: str):
        info = probe(path)
        if info is None:
            QMessageBox.warning(self, tr("vid_title"), tr("vid_cannot_open").format(path=path))
            return
        self._info = info
        self._path.setText(path)
        self._about.setText(tr("vid_about").format(
            w=info.width, h=info.height, fps=info.fps, n=info.frame_count,
            dur=info.duration))
        self._vid = video_id(path, set(self._ctrl.project.videos) if self._ctrl.project else set())
        self._step.setValue(max(1, round(info.fps / 5)))          # ~5 frames per second
        for sb in (self._start, self._end):
            sb.blockSignals(True)
            sb.setRange(0, round(info.duration, 1))
            sb.blockSignals(False)
        self._start.setValue(0)
        self._end.setValue(round(info.duration, 1))
        project = self._ctrl.project
        base = (project.project_path.parent if project and project.project_path
                else Path(path).parent)
        self._out.setText(str(base / f"{self._vid}_frames"))
        self._run.setEnabled(True)
        self._update_estimate()

    def _range(self) -> tuple[int, int | None]:
        info = self._info
        start = int(round(self._start.value() * info.fps))
        end_s = self._end.value()
        end = None if end_s >= round(info.duration, 1) else int(round(end_s * info.fps))
        return start, end

    def _update_estimate(self):
        if not self._info:
            return
        start, end = self._range()
        n = frames_to_extract(self._info.frame_count, self._step.value(), start, end)
        self._estimate.setText(tr("vid_estimate").format(
            n=n, fps=self._info.fps / self._step.value()))

    # ── extraction ────────────────────────────────────────────────────────────

    def _start_extract(self):
        if self._thread is not None:              # running → this is the Stop button
            self._worker.stop = True
            return
        info = self._info
        start, end = self._range()
        if end is not None and end <= start:
            return
        self._total = max(1, (end if end is not None else info.frame_count) - start)
        args = dict(path=info.path, folder=self._out.text(), vid=self._vid,
                    step=self._step.value(), start=start, end=end)
        self._meta = {"path": info.path, "fps": info.fps, "frame_count": info.frame_count,
                      "width": info.width, "height": info.height,
                      "step": self._step.value(), "folder": self._out.text()}
        self._bar.setRange(0, self._total)
        self._bar.setValue(0)
        self._bar.setVisible(True)
        self._run.setText(tr("vid_stop"))
        self._close.setEnabled(False)
        self._thread = QThread(self)
        self._worker = _Worker(args)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._bar.setValue)
        self._worker.done.connect(self._finished)
        self._thread.start()

    def _finished(self, frames: list, error: str):
        self._thread.quit()
        self._thread.wait()
        self._thread = self._worker = None
        self._run.setText(tr("vid_import"))
        self._close.setEnabled(True)
        self._bar.setVisible(False)
        if error:
            QMessageBox.warning(self, tr("vid_title"), error)
            return
        if not frames:
            QMessageBox.information(self, tr("vid_title"), tr("vid_no_frames"))
            return
        self.added = self._ctrl.add_video_frames(self._vid, self._meta, frames)
        self.first_frame = frames[0][1]
        self.accept()

    def reject(self):
        if self._thread is not None:              # closing while running: stop first
            self._worker.stop = True
            return
        super().reject()
