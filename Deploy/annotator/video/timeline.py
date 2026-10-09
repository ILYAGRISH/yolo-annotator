"""
Frame strip under the canvas (Phase 8-B): shown only on video frames.

    [◀◆] [◀] [▶] [◆▶]  street.mp4 · frame 120 · 00:04.80 · 31 / 150   Track #3 car  ◆ 4
    ┃▁▁▁▁▁▁▁▁▁▁▁████████◆███████◆██████◆▁▁▁▁▁▁▁┃▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁

Grey ticks: frames with annotations; coloured band: frames of the active
track, ◆ its keyframes; white line: the current frame. Click or drag to go
to a frame.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from annotator.i18n import tr


class _Bar(QWidget):
    clicked = pyqtSignal(int)              # frame index

    def __init__(self, mgr, parent=None):
        super().__init__(parent)
        self._mgr = mgr
        self.setMinimumHeight(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("tl_bar_tip"))

    def _x(self, i: int, n: int) -> float:
        w = self.width() - 12
        return 6 + (w * (i + 0.5) / n if n else 0)

    def _index_at(self, x: float) -> int:
        n = len(self._mgr.frames)
        if not n:
            return -1
        w = self.width() - 12
        return min(max(int((x - 6) / w * n), 0), n - 1)

    def paintEvent(self, _event):
        mgr, p = self._mgr, QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(mgr.frames)
        h = self.height()
        p.fillRect(self.rect(), QColor(32, 32, 32))
        p.fillRect(QRectF(6, h / 2 - 3, self.width() - 12, 6), QColor(60, 60, 60))
        if not n:
            return
        tick_w = max(1.0, (self.width() - 12) / n - 1)
        for i, (path, _f) in enumerate(mgr.frames):
            if mgr.counts.get(path):
                x = self._x(i, n)
                p.fillRect(QRectF(x - tick_w / 2, h / 2 - 7, tick_w, 14), QColor(120, 120, 120))
        if mgr.active_track is not None:
            color = QColor(mgr.track_color or "#f0c040")
            idx = [i for i, (path, _f) in enumerate(mgr.frames)
                   if mgr.active_track in mgr.marks.get(path, {})]
            if idx:
                band = QColor(color)
                band.setAlpha(110)
                x0, x1 = self._x(idx[0], n), self._x(idx[-1], n)
                p.fillRect(QRectF(x0 - tick_w / 2, h / 2 - 5, x1 - x0 + tick_w, 10), band)
            p.setPen(QColor(20, 20, 20))
            p.setBrush(color)
            for i, (path, _f) in enumerate(mgr.frames):
                if mgr.marks.get(path, {}).get(mgr.active_track) is True:
                    x, y = self._x(i, n), h / 2
                    p.drawPolygon(QPolygonF([QPointF(x, y - 7), QPointF(x + 5, y),
                                             QPointF(x, y + 7), QPointF(x - 5, y)]))
        cur = mgr.current_index()
        if cur >= 0:
            x = self._x(cur, n)
            p.setPen(QColor(255, 255, 255))
            p.drawLine(QPointF(x, 1), QPointF(x, h - 1))

    def mousePressEvent(self, event):
        i = self._index_at(event.position().x())
        if i >= 0:
            self.clicked.emit(i)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            i = self._index_at(event.position().x())
            if i >= 0 and i != self._mgr.current_index():
                self.clicked.emit(i)


class Timeline(QWidget):
    """Frame strip; reads everything from VideoManager."""

    def __init__(self, mgr, parent=None):
        super().__init__(parent)
        self._mgr = mgr
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 3, 6, 3)
        lay.setSpacing(2)
        row = QHBoxLayout()
        row.setSpacing(3)

        def button(text, tip_key, slot):
            b = QToolButton()
            b.setText(text)
            b.setAutoRaise(True)
            b.clicked.connect(slot)
            b._tip_key = tip_key
            b.setToolTip(tr(tip_key))
            row.addWidget(b)
            return b

        self._buttons = [
            button("◀◆", "tl_prev_key", lambda: mgr.goto_keyframe(-1)),
            button("◀", "tl_prev", lambda: mgr.goto_frame_index(mgr.current_index() - 1)),
            button("▶", "tl_next", lambda: mgr.goto_frame_index(mgr.current_index() + 1)),
            button("◆▶", "tl_next_key", lambda: mgr.goto_keyframe(1)),
        ]
        self._info = QLabel()
        row.addWidget(self._info, stretch=1)
        self._track = QLabel()
        row.addWidget(self._track)
        lay.addLayout(row)
        self._bar = _Bar(mgr)
        self._bar.clicked.connect(mgr.goto_frame_index)
        lay.addWidget(self._bar)
        mgr.index_changed.connect(self.refresh)
        self.setVisible(False)

    def retranslate(self):
        for b in self._buttons:
            b.setToolTip(tr(b._tip_key))
        self._bar.setToolTip(tr("tl_bar_tip"))
        self.refresh()

    def refresh(self):
        mgr = self._mgr
        self.setVisible(bool(mgr.video))
        if not mgr.video:
            return
        i, n = mgr.current_index(), len(mgr.frames)
        parts = [f"🎞 {mgr.video_name()}",
                 tr("tl_frame").format(f=mgr.frame_number())]
        t = mgr.time_text()
        if t:
            parts.append(t)
        parts.append(f"{i + 1} / {n}")
        self._info.setText("  ·  ".join(parts))
        if mgr.active_track is None:
            self._track.setText(tr("tl_no_track"))
            self._track.setStyleSheet("color:#888;")
        else:
            cls = mgr.track_class()
            name = cls.name if cls else ""
            keys = len(mgr.keyframes())
            self._track.setText(tr("tl_track").format(id=mgr.active_track, cls=name, keys=keys))
            self._track.setStyleSheet(f"color:{mgr.track_color or '#f0c040'};font-weight:bold;")
        self._bar.update()
