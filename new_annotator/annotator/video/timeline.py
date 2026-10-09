"""
Frame strip under the canvas (Phase 8-B): shown only on video frames.

    [◀◆] [◀] [▶] [◆▶]  street.mp4 · frame 120 · 00:04.80 · 31 / 150   Track #3 car  ◆ 4
    ┃▁▁▁▁▁▁▁▁▁▁▁████████◆███████◆██████◆▁▁▁▁▁▁▁┃▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁
    Event: [■ lane change ▾]   3 events · here: lane change
         [ lane change ]        [ stop       ]          ← events (Phase 8-D)
                   [ overtake         ]

Grey ticks: frames with annotations; coloured band: frames of the active
track, ◆ its keyframes; white line: the current frame. Click or drag to go
to a frame. Under it the time events of the video, overlapping ones in
separate rows; a click selects an event, a double click edits it.
"""
from __future__ import annotations

import bisect

from PyQt6.QtCore import QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QToolButton, QToolTip,
                             QVBoxLayout, QWidget)

from annotator.domain.events import pack_lanes, seconds, time_text
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


class _EventBar(QWidget):
    """Time events of the current video, one row per overlap level."""
    clicked = pyqtSignal(int)              # frame index
    edit_requested = pyqtSignal(str)       # event id

    LANE_H = 13

    def __init__(self, mgr, events, parent=None):
        super().__init__(parent)
        self._mgr, self._ev = mgr, events
        self._rects: list[tuple[QRectF, str]] = []
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh()

    def refresh(self):
        lanes = pack_lanes(self._ev.events)
        rows = max(lanes.values(), default=-1) + 1 + (1 if self._ev.is_open else 0)
        self.setFixedHeight(max(rows, 1) * self.LANE_H + 4)
        self.update()

    def _span(self, a: int, b: int) -> tuple[float, float]:
        """Frame numbers a..b → x range, in step with the frame bar above."""
        frames = [f for _p, f in self._mgr.frames]
        n = len(frames)
        w = self.width() - 12
        i0 = min(bisect.bisect_left(frames, a), n - 1)
        i1 = max(bisect.bisect_right(frames, b) - 1, 0)
        if i1 < i0:                        # no extracted frame inside: a thin mark
            i0 = i1 = min(i0, n - 1)
        return 6 + w * i0 / n, 6 + w * (i1 + 1) / n

    def paintEvent(self, _event):
        ev, p = self._ev, QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(32, 32, 32))
        self._rects = []
        if not self._mgr.frames:
            return
        lanes = pack_lanes(ev.events)
        fm = p.fontMetrics()
        for e in ev.events:
            et = ev.type_of(e)
            color = QColor(et.color if et else "#999999")
            x0, x1 = self._span(e.start, e.end)
            r = QRectF(x0, 2 + lanes[e.id] * self.LANE_H, max(x1 - x0, 3), self.LANE_H - 2)
            self._rects.append((r, e.id))
            fill = QColor(color)
            fill.setAlpha(170)
            sel = e.id == ev.selected
            p.setPen(QPen(QColor(255, 255, 255), 2) if sel else QPen(color.darker(160), 1))
            p.setBrush(fill)
            p.drawRoundedRect(r, 3, 3)
            label = (et.name if et else "?") + (f" #{e.track_id}" if e.track_id is not None else "")
            if fm.horizontalAdvance(label) + 6 < r.width():
                p.setPen(QColor(15, 15, 15))
                p.drawText(r.adjusted(3, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, label)
        if ev.is_open:                     # started, not finished: up to the current frame
            here = self._mgr.frame_number()
            lane = max(lanes.values(), default=-1) + 1
            et = ev.current_type_obj()
            color = QColor(et.color if et else "#f0c040")
            x0, x1 = self._span(min(ev.open_start, here), max(ev.open_start, here))
            r = QRectF(x0, 2 + lane * self.LANE_H, max(x1 - x0, 3), self.LANE_H - 2)
            p.setPen(QPen(color, 1, Qt.PenStyle.DashLine))
            p.setBrush(QBrush(color, Qt.BrushStyle.BDiagPattern))
            p.drawRoundedRect(r, 3, 3)
        cur = self._mgr.current_index()
        if cur >= 0:
            n = len(self._mgr.frames)
            x = 6 + (self.width() - 12) * (cur + 0.5) / n
            p.setPen(QColor(255, 255, 255, 140))
            p.drawLine(QPointF(x, 0), QPointF(x, self.height()))

    def event_at(self, pos) -> str | None:
        for r, eid in reversed(self._rects):
            if r.adjusted(-2, -1, 2, 1).contains(pos):
                return eid
        return None

    def _index_at(self, x: float) -> int:
        n = len(self._mgr.frames)
        if not n:
            return -1
        return min(max(int((x - 6) / (self.width() - 12) * n), 0), n - 1)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._ev.select(self.event_at(event.position()))
        i = self._index_at(event.position().x())
        if i >= 0 and i != self._mgr.current_index():
            self.clicked.emit(i)

    def mouseDoubleClickEvent(self, event):
        eid = self.event_at(event.position())
        if eid:
            self.edit_requested.emit(eid)

    def event(self, e):
        if e.type() == QEvent.Type.ToolTip:
            ev = self._ev.get(self.event_at(QPointF(e.pos())))
            QToolTip.showText(e.globalPos(),
                              event_text(self._ev, ev) if ev else tr("ev_bar_tip"), self)
            return True
        return super().event(e)


def event_text(mgr, ev) -> str:
    """One line about an event: type, frames, time, track, note."""
    et = mgr.type_of(ev)
    fps = mgr.fps()
    parts = [et.name if et else "?", tr("ev_frames").format(a=ev.start, b=ev.end)]
    if fps > 0:
        a, b = seconds(ev.start, fps), seconds(ev.end, fps)
        parts.append(f"{time_text(a)}–{time_text(b)} ({b - a:.1f} s)")
    if ev.track_id is not None:
        parts.append(f"#{ev.track_id}")
    if ev.note:
        parts.append(ev.note)
    return "  ·  ".join(parts)


class Timeline(QWidget):
    """Frame strip; reads everything from VideoManager (and the time events
    from EventManager)."""
    edit_event = pyqtSignal(str)           # event id — double click on the event strip
    new_type_requested = pyqtSignal()      # "+ New event type…" in the combo

    def __init__(self, mgr, events=None, parent=None):
        super().__init__(parent)
        self._mgr = mgr
        self._ev = events
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
        self._ev_bar = None
        if events is not None:
            ev_row = QHBoxLayout()
            ev_row.setSpacing(6)
            self._ev_caption = QLabel(tr("ev_type"))
            ev_row.addWidget(self._ev_caption)
            self._type_combo = QComboBox()
            self._type_combo.setMinimumWidth(150)
            self._type_combo.setToolTip(tr("ev_type_tip"))
            self._type_combo.activated.connect(self._on_type_chosen)
            ev_row.addWidget(self._type_combo)
            self._ev_state = QLabel()
            ev_row.addWidget(self._ev_state, stretch=1)
            lay.addLayout(ev_row)
            self._ev_bar = _EventBar(mgr, events)
            self._ev_bar.clicked.connect(mgr.goto_frame_index)
            self._ev_bar.edit_requested.connect(self.edit_event)
            lay.addWidget(self._ev_bar)
            events.changed.connect(self.refresh)
        mgr.index_changed.connect(self.refresh)
        self.setVisible(False)

    def _fill_types(self):
        ev, combo = self._ev, self._type_combo
        combo.blockSignals(True)
        combo.clear()
        for et in ev.types:
            combo.addItem(f"■ {et.name}", et.id)
            combo.setItemData(combo.count() - 1, QColor(et.color), Qt.ItemDataRole.ForegroundRole)
        combo.addItem(tr("ev_new_type"), None)
        cur = ev.current_type_obj()
        i = combo.findData(cur.id) if cur is not None else -1
        combo.setCurrentIndex(i if i >= 0 else 0)
        combo.blockSignals(False)

    def _on_type_chosen(self, index: int):
        tid = self._type_combo.itemData(index)
        if tid is None:
            self.new_type_requested.emit()
            self._fill_types()
        else:
            self._ev.set_current_type(tid)

    def retranslate(self):
        for b in self._buttons:
            b.setToolTip(tr(b._tip_key))
        self._bar.setToolTip(tr("tl_bar_tip"))
        if self._ev_bar is not None:
            self._ev_caption.setText(tr("ev_type"))
            self._type_combo.setToolTip(tr("ev_type_tip"))
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
        if self._ev_bar is not None:
            self._refresh_events()

    def _refresh_events(self):
        ev = self._ev
        self._fill_types()
        if ev.is_open:
            self._ev_state.setText(tr("ev_open").format(f=ev.open_start))
            self._ev_state.setStyleSheet("color:#ff6060;font-weight:bold;")
        else:
            here = ev.events_at(self._mgr.frame_number())
            names = ", ".join(sorted({ev.type_of(e).name if ev.type_of(e) else "?" for e in here}))
            text = tr("ev_summary").format(n=len(ev.events))
            if names:
                text += "  ·  " + tr("ev_here").format(names=names)
            self._ev_state.setText(text)
            self._ev_state.setStyleSheet("color:#aaa;")
        self._ev_bar.refresh()
