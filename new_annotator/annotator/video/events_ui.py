"""
Time events UI (Phase 8-D): the Events tab, the event editor and the event
types editor. All of them work through EventManager (video/events.py).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (QAbstractItemView, QColorDialog, QComboBox, QDialog,
                             QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QSpinBox, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from annotator.domain.events import seconds, time_text
from annotator.i18n import tr


def _time(mgr, frame: int) -> str:
    fps = mgr.fps()
    return time_text(seconds(frame, fps)) if fps > 0 else ""


# ── Events tab ────────────────────────────────────────────────────────────────

class EventsPanel(QWidget):
    edit_requested = pyqtSignal(str)        # event id
    types_requested = pyqtSignal()

    COLS = ("ev_col_type", "ev_col_frames", "ev_col_time", "ev_col_track", "ev_col_note")

    def __init__(self, events, video, parent=None):
        super().__init__(parent)
        self._ev, self._video = events, video
        self._filling = False
        self._key = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self._head = QLabel()
        self._head.setWordWrap(True)
        lay.addWidget(self._head)
        self._tree = QTreeWidget()
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemSelectionChanged.connect(self._on_selection)
        self._tree.itemDoubleClicked.connect(lambda it, _c: self._ev.goto(it.data(0, Qt.ItemDataRole.UserRole)))
        lay.addWidget(self._tree, stretch=1)

        row1, row2 = QHBoxLayout(), QHBoxLayout()
        self._btn_edit = QPushButton()
        self._btn_edit.clicked.connect(self._edit)
        self._btn_del = QPushButton()
        self._btn_del.clicked.connect(self.delete_selected)
        self._btn_start = QPushButton()
        self._btn_start.clicked.connect(lambda: self._ev.set_bound("start"))
        self._btn_end = QPushButton()
        self._btn_end.clicked.connect(lambda: self._ev.set_bound("end"))
        self._btn_types = QPushButton()
        self._btn_types.clicked.connect(self.types_requested)
        for b in (self._btn_start, self._btn_end):
            row1.addWidget(b)
        for b in (self._btn_edit, self._btn_del, self._btn_types):
            row2.addWidget(b)
        lay.addLayout(row1)
        lay.addLayout(row2)
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color:#888;font-size:11px;")
        lay.addWidget(self._hint)

        events.changed.connect(self.refresh)
        video.index_changed.connect(self._mark_current)
        self.retranslate()

    def retranslate(self):
        self._tree.setHeaderLabels([tr(k) for k in self.COLS])
        self._btn_edit.setText(tr("ev_btn_edit"))
        self._btn_del.setText(tr("ev_btn_delete"))
        self._btn_start.setText(tr("ev_btn_start"))
        self._btn_end.setText(tr("ev_btn_end"))
        self._btn_types.setText(tr("ev_btn_types"))
        self._btn_start.setToolTip(tr("ev_btn_start_tip"))
        self._btn_end.setToolTip(tr("ev_btn_end_tip"))
        self._hint.setText(tr("ev_hint"))
        self._key = None                     # rebuild: the header is translated too
        self.refresh()

    def has_focus(self) -> bool:
        return self._tree.hasFocus()

    def refresh(self):
        ev = self._ev
        key = (ev.vid, tuple((e.id, e.type_id, e.start, e.end, e.track_id, e.note) for e in ev.events),
               tuple((t.id, t.name, t.color) for t in ev.types))
        if key == self._key:                 # only the selection changed
            self._sync_selection()
            return
        self._key = key
        self._filling = True
        self._tree.clear()
        for e in ev.events:
            et = ev.type_of(e)
            fps = ev.fps()
            it = QTreeWidgetItem([
                f"■ {et.name}" if et else "?",
                f"{e.start}–{e.end}",
                f"{seconds(e.start, fps):.1f}–{seconds(e.end, fps):.1f}{tr('vid_sec')}" if fps > 0 else "",
                f"#{e.track_id}" if e.track_id is not None else "",
                e.note,
            ])
            it.setData(0, Qt.ItemDataRole.UserRole, e.id)
            if et:
                it.setForeground(0, QColor(et.color))
            self._tree.addTopLevelItem(it)
        for c in range(4):
            self._tree.resizeColumnToContents(c)
        self._filling = False
        if not ev.vid:
            self._head.setText(tr("ev_no_video"))
        else:
            self._head.setText(tr("ev_head").format(video=self._video.video_name(), n=len(ev.events)))
        self._sync_selection()
        self._mark_current()

    def _sync_selection(self):
        ev = self._ev
        self._filling = True
        for i in range(self._tree.topLevelItemCount()):
            it = self._tree.topLevelItem(i)
            sel = it.data(0, Qt.ItemDataRole.UserRole) == ev.selected
            it.setSelected(sel)
            if sel:
                self._tree.setCurrentItem(it)
                self._tree.scrollToItem(it)
        if ev.selected is None:
            self._tree.clearSelection()
        self._filling = False
        on = bool(ev.vid)
        has_sel = ev.selected_event() is not None
        for b in (self._btn_edit, self._btn_del, self._btn_start, self._btn_end):
            b.setEnabled(on and has_sel)
        self._btn_types.setEnabled(ev.project is not None)

    def _mark_current(self):
        here = self._video.frame_number()
        for i in range(self._tree.topLevelItemCount()):
            it = self._tree.topLevelItem(i)
            e = self._ev.get(it.data(0, Qt.ItemDataRole.UserRole))
            f = QFont(self._tree.font())
            f.setBold(bool(e and e.contains(here)))
            for c in range(len(self.COLS)):
                it.setFont(c, f)

    def _on_selection(self):
        if self._filling:
            return
        items = self._tree.selectedItems()
        self._ev.select(items[0].data(0, Qt.ItemDataRole.UserRole) if items else None)

    def _edit(self):
        if self._ev.selected:
            self.edit_requested.emit(self._ev.selected)

    def delete_selected(self) -> bool:
        return bool(self._ev.selected) and self._ev.delete(self._ev.selected)


# ── one event ─────────────────────────────────────────────────────────────────

class EventDialog(QDialog):
    """Type, first / last frame, object track and note of an event."""

    def __init__(self, events, video, event, parent=None):
        super().__init__(parent)
        self._ev, self._video, self.event = events, video, event
        self.setWindowTitle(tr("ev_dlg_title"))
        self.setMinimumWidth(420)
        form = QFormLayout(self)

        self.type_combo = QComboBox()
        for et in events.types:
            self.type_combo.addItem(f"■ {et.name}", et.id)
            self.type_combo.setItemData(self.type_combo.count() - 1, QColor(et.color),
                                        Qt.ItemDataRole.ForegroundRole)
        self.type_combo.setCurrentIndex(max(self.type_combo.findData(event.type_id), 0))
        form.addRow(tr("ev_col_type") + ":", self.type_combo)

        frames = [f for _p, f in video.frames] or [event.start, event.end]
        lo, hi = min(frames + [event.start]), max(frames + [event.end])
        self.start_spin, self._start_t = self._frame_row(form, tr("ev_first"), event.start, lo, hi)
        self.end_spin, self._end_t = self._frame_row(form, tr("ev_last"), event.end, lo, hi)

        self.track_combo = QComboBox()
        self.track_combo.addItem(tr("ev_no_track"), None)
        tids = sorted({t for m in video.marks.values() for t in m} |
                      ({event.track_id} if event.track_id is not None else set()))
        for t in tids:
            cls = video.track_class(t)
            self.track_combo.addItem(f"#{t}  {cls.name if cls else ''}".rstrip(), t)
        self.track_combo.setCurrentIndex(max(self.track_combo.findData(event.track_id), 0)
                                         if event.track_id is not None else 0)
        form.addRow(tr("ev_col_track") + ":", self.track_combo)

        self.note_edit = QLineEdit(event.note)
        form.addRow(tr("ev_col_note") + ":", self.note_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def _frame_row(self, form, label, value, lo, hi):
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(value)
        t = QLabel()
        t.setStyleSheet("color:#888;")
        here = QPushButton(tr("ev_here_btn"))
        here.setToolTip(tr("ev_here_btn_tip"))
        here.clicked.connect(lambda: spin.setValue(max(self._video.frame_number(), lo)))
        spin.valueChanged.connect(lambda v: t.setText(_time(self._ev, v)))
        t.setText(_time(self._ev, value))
        row = QHBoxLayout()
        row.addWidget(spin, stretch=1)
        row.addWidget(t)
        row.addWidget(here)
        form.addRow(label, row)
        return spin, t

    def changes(self) -> dict:
        return {"type_id": self.type_combo.currentData(),
                "start": self.start_spin.value(), "end": self.end_spin.value(),
                "track_id": self.track_combo.currentData(),
                "note": self.note_edit.text().strip()}


# ── event types ───────────────────────────────────────────────────────────────

def ask_new_type(events, parent) -> bool:
    name, ok = QInputDialog.getText(parent, tr("ev_new_type_title"), tr("ev_new_type_prompt"))
    return bool(ok and name.strip() and events.add_type(name))


class EventTypesDialog(QDialog):
    """Add, rename, recolour and delete event types (changes apply at once)."""

    def __init__(self, events, parent=None):
        super().__init__(parent)
        self._ev = events
        self.setWindowTitle(tr("ev_types_title"))
        self.setMinimumWidth(360)
        lay = QVBoxLayout(self)
        hint = QLabel(tr("ev_types_hint"))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888;")
        lay.addWidget(hint)
        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(lambda _it: self._rename())
        lay.addWidget(self._list, stretch=1)
        row = QHBoxLayout()
        for key, slot in (("ev_types_add", self._add), ("ev_types_rename", self._rename),
                          ("ev_types_color", self._color), ("ev_types_delete", self._delete)):
            b = QPushButton(tr(key))
            b.clicked.connect(slot)
            row.addWidget(b)
        lay.addLayout(row)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.accept)
        lay.addWidget(btns)
        self._fill()

    def _fill(self, select_id=None):
        self._list.clear()
        for et in self._ev.types:
            it = QListWidgetItem(f"■  {et.name}")
            it.setForeground(QColor(et.color))
            it.setData(Qt.ItemDataRole.UserRole, et.id)
            self._list.addItem(it)
            if et.id == select_id:
                self._list.setCurrentItem(it)
        if self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)

    def _current(self):
        it = self._list.currentItem()
        return self._ev.project.get_event_type(it.data(Qt.ItemDataRole.UserRole)) if it else None

    def _add(self):
        if ask_new_type(self._ev, self):
            self._fill(self._ev.current_type)

    def _rename(self):
        et = self._current()
        if et is None:
            return
        name, ok = QInputDialog.getText(self, tr("ev_types_rename"), tr("ev_new_type_prompt"),
                                        text=et.name)
        if ok and name.strip():
            self._ev.edit_type(et.id, name=name)
            self._fill(et.id)

    def _color(self):
        et = self._current()
        if et is None:
            return
        c = QColorDialog.getColor(QColor(et.color), self)
        if c.isValid():
            self._ev.edit_type(et.id, color=c.name())
            self._fill(et.id)

    def _delete(self):
        et = self._current()
        if et is None:
            return
        n = self._ev.type_usage(et.id)
        q = tr("ev_types_delete_q").format(name=et.name, n=n) if n else \
            tr("ev_types_delete_q0").format(name=et.name)
        if QMessageBox.question(self, tr("ev_types_delete"), q) == QMessageBox.StandardButton.Yes:
            self._ev.delete_type(et.id)
            self._fill()
