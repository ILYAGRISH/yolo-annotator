"""
Time events on video (phase 8-D): domain model, storage, EventManager
(E / Shift+E, edit, delete, undo / redo, types), export (CSV + ActivityNet),
main window (menu, timeline strip, Events tab, dialogs).
Run: .venv/Scripts/python test_events.py
"""
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import cv2
import numpy as np

_pass = _fail = 0

def check(name: str, ok: bool):
    global _pass, _fail
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    if ok:
        _pass += 1
    else:
        _fail += 1

def section(title: str):
    print(f"\n--- {title} ---")

def pump(ms=20):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()

W, H, FPS, N, STEP = 160, 120, 25, 50, 5

def make_video(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    for i in range(N):
        f = np.full((H, W, 3), (40, 90, 140), np.uint8)
        cv2.rectangle(f, (10 + 2 * i, 40), (40 + 2 * i, 80), (255, 255, 255), -1)
        w.write(f)
    w.release()

from annotator.domain.events import (EventType, VideoEvent, pack_lanes, seconds,
                                     sort_events, time_text)


# ═════════════════════════════════════════════════════════════════════════════
section("1. Domain model")
# ═════════════════════════════════════════════════════════════════════════════
e = VideoEvent.create(1, 30, 10, track_id=4, note="тест", author="Ilya")
check("create puts the bounds in order", (e.start, e.end) == (10, 30))
check("create stamps meta", e.meta.get("author") == "Ilya" and "created_at" in e.meta)
check("contains: inclusive bounds", e.contains(10) and e.contains(30) and not e.contains(31))
d = e.to_dict()
check("round trip", VideoEvent.from_dict(d) == e)
check("no track / note -> keys left out",
      set(VideoEvent.create(0, 1, 2).to_dict()) == {"id", "type_id", "start", "end", "meta"})
check("from_dict orders reversed bounds", VideoEvent.from_dict({"id": "x", "type_id": 0,
                                                                "start": 9, "end": 3}).start == 3)
e2 = e.edited(end=5)
check("edited swaps bounds when needed and keeps the id",
      (e2.start, e2.end, e2.id) == (5, 10, e.id) and (e.start, e.end) == (10, 30))
check("edited touches modified_at only on the copy",
      e2.meta["created_at"] == e.meta["created_at"])
a = VideoEvent.create(0, 0, 10)
b = VideoEvent.create(0, 5, 15)
c = VideoEvent.create(0, 11, 20)
z = VideoEvent.create(0, 16, 16)
lanes = pack_lanes([c, b, a, z])
check("pack_lanes: overlapping events in different rows, free row reused",
      lanes[a.id] == 0 and lanes[b.id] == 1 and lanes[c.id] == 0 and lanes[z.id] == 1)
check("sort_events by start", [x.id for x in sort_events([c, a, b])] == [a.id, b.id, c.id])
check("seconds and time text", seconds(50, 25) == 2.0 and seconds(5, 0) == 0.0
      and time_text(62.5) == "01:02.50")
check("event type round trip", EventType.from_dict(EventType(2, "гол", "#123456").to_dict())
      == EventType(2, "гол", "#123456"))


# ═════════════════════════════════════════════════════════════════════════════
section("2. Project and storage")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.controller.project_controller import ProjectController
from annotator.domain.project import DEFAULT_HOTKEYS, Project
from annotator.storage.project_store import ProjectStore
from annotator.video.extract import extract

check("hotkeys E / Shift+E", (DEFAULT_HOTKEYS["event_mark"], DEFAULT_HOTKEYS["event_cancel"])
      == ("E", "Shift+E"))
p = Project.create("x")
t0 = p.add_event_type("перестроение")
t1 = p.add_event_type("stop")
check("event type ids and colours", (t0.id, t1.id) == (0, 1) and t0.color != t1.color)
check("get_event_type", p.get_event_type(1).name == "stop" and p.get_event_type(9) is None)
p2 = Project.from_dict(json.loads(json.dumps(p.to_dict())))
check("event types saved in project.json", [t.name for t in p2.event_types] == ["перестроение", "stop"])
old = p.to_dict()
old.pop("event_types")
check("old project.json without event types opens", Project.from_dict(old).event_types == [])

ctrl = ProjectController()
proj = ctrl.create_project("ev", _TMP / "ev.annproj")
VIDEO = _TMP / "видео" / "улица.mp4"
make_video(VIDEO)
frames = extract(VIDEO, _TMP / "frames", "street", step=STEP)
info = {"path": str(VIDEO), "fps": FPS, "frame_count": N, "width": W, "height": H,
        "step": STEP, "folder": str(_TMP / "frames")}
ctrl.add_video_frames("street", info, frames)
paths = [p for _f, p in frames]
check("events file missing -> no events", ProjectStore.load_events(proj, "street") == [])
ProjectStore.save_events(proj, "street", [c, a])
f = proj.project_path / "events" / "street.json"
check("events/<video>.json written, sorted", f.exists()
      and [x["id"] for x in json.loads(f.read_text(encoding="utf-8"))] == [a.id, c.id])
check("load_events reads them back", ProjectStore.load_events(proj, "street") == [a, c])
ProjectStore.save_events(proj, "street", [])


# ═════════════════════════════════════════════════════════════════════════════
section("3. EventManager")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.video.events import EventManager
from annotator.video.manager import VideoManager

vm = VideoManager(ctrl)
em = EventManager(ctrl, vm)
ctrl.reviewer = lambda: "Ilya"
nav = []
vm.navigate.connect(lambda path: (nav.append(path), ctrl.set_image(path)))
statuses = []
em.status.connect(statuses.append)
changes = []
em.changed.connect(lambda: changes.append(1))

ctrl.set_image(paths[2])                     # frame 10
check("video frame shown -> events of that video loaded", em.vid == "street" and em.events == [])
check("start_here opens an event at the current frame",
      em.start_here() and em.is_open and em.open_start == 10 and statuses[-1] == "ev_started")
ctrl.set_image(paths[6])                     # frame 30
check("open event survives frame changes of the same video", em.open_start == 10)
check("finish without types -> asks for one", em.finish_here() is None
      and statuses[-1] == "ev_no_types" and em.is_open)
et = em.add_type("перестроение")
check("add_type saves the project and becomes current",
      em.current_type == et.id and
      ProjectStore.load(proj.project_path).event_types[0].name == "перестроение")
check("add_type with an existing name reuses it", em.add_type("перестроение").id == et.id
      and len(proj.event_types) == 1)
ev = em.finish_here()
check("finish_here adds the event 10..30 with author",
      ev is not None and (ev.start, ev.end, ev.type_id) == (10, 30, et.id)
      and ev.meta.get("author") == "Ilya" and not em.is_open)
check("added event is selected and saved",
      em.selected == ev.id and ProjectStore.load_events(proj, "street") == [ev])
check("one undo step", ctrl.undo_stack.count() == 1 and ctrl.undo_stack.canUndo())
ctrl.undo_stack.undo()
check("undo removes it (file too)", em.events == [] and ProjectStore.load_events(proj, "street") == []
      and em.selected is None)
ctrl.undo_stack.redo()
check("redo brings it back", [x.id for x in em.events] == [ev.id] and em.selected == ev.id)

em.start_here()                              # finished on an EARLIER frame
ctrl.set_image(paths[4])                     # frame 20
ev2 = em.finish_here()
check("finishing on an earlier frame orders the bounds", (ev2.start, ev2.end) == (20, 30))
check("events_at", {x.id for x in em.events_at(25)} == {ev.id, ev2.id}
      and [x.id for x in em.events_at(12)] == [ev.id])
em.start_here(track=7)
check("start with a track: status names it", statuses[-1] == "ev_started_track" and em.open_track == 7)
check("cancel drops the started event", em.cancel() and not em.is_open
      and statuses[-1] == "ev_cancelled" and not em.cancel())
ctrl.set_image(paths[0])
em.start_here(track=7)
ctrl.set_image(paths[1])
ev3 = em.finish_here()
check("event about an object track", ev3.track_id == 7 and (ev3.start, ev3.end) == (0, 5))

stop = em.add_type("stop")
upd = em.update(ev3.id, type_id=stop.id, note="резко", end=15)
check("update: type, note, bound",
      (upd.type_id, upd.note, upd.end, upd.id) == (stop.id, "резко", 15, ev3.id)
      and ProjectStore.load_events(proj, "street")[0].note == "резко")
n_undo = ctrl.undo_stack.count()
check("update with nothing new is not an undo step",
      em.update(ev3.id, note="резко") is not None and ctrl.undo_stack.count() == n_undo)
ctrl.undo_stack.undo()
check("undo of an edit", em.get(ev3.id).note == "" and em.get(ev3.id).end == 5)
ctrl.undo_stack.redo()
ctrl.set_image(paths[3])                     # frame 15
em.select(ev.id)
check("set_bound start := current frame", em.set_bound("start").start == 15)
ctrl.set_image(paths[8])                     # frame 40
check("set_bound end := current frame", em.set_bound("end").end == 40)
em.select(None)
check("set_bound without a selection -> status", em.set_bound("end") is None
      and statuses[-1] == "ev_select_first")
check("delete", em.delete(ev2.id) and em.get(ev2.id) is None
      and len(ProjectStore.load_events(proj, "street")) == 2)
ctrl.undo_stack.undo()
check("undo of delete restores and selects", em.get(ev2.id) is not None and em.selected == ev2.id)
check("select of an unknown id -> none", (em.select("nope"), em.selected)[1] is None)

nav.clear()
check("goto: first extracted frame inside the event", em.goto(ev2.id) and nav[-1] == paths[4])
check("goto end: last frame inside", em.goto(ev.id, "end") and nav[-1] == paths[8])
em.update(ev3.id, start=1, end=3)            # between extracted frames 0 and 5
check("goto with no frame inside -> nearest", em.goto(ev3.id) and nav[-1] == paths[0])
ctrl.set_image(paths[2])                     # frame 10
check("next event (by start)", em.goto_event(1) and em.selected == ev.id and nav[-1] == paths[3])
check("previous event", em.goto_event(-1) and em.selected == ev3.id)
check("no event before the first one", not em.goto_event(-1))

ctrl.undo_stack.clear()
ctrl.set_image(paths[5])
check("changing the image clears undo (like annotations)", not ctrl.undo_stack.canUndo())
check("counts per video", em.counts() == {"street": 3})
check("type usage", em.type_usage(et.id) == 2 and em.type_usage(stop.id) == 1)
em.edit_type(stop.id, name="остановка", color="#00ff00")
check("edit_type renames and recolours (saved)",
      ProjectStore.load(proj.project_path).get_event_type(stop.id).name == "остановка"
      and proj.get_event_type(stop.id).color == "#00ff00")
em.set_current_type(stop.id)
check("delete_type removes its events in all videos",
      em.delete_type(stop.id) == 1 and em.get(ev3.id) is None
      and len(ProjectStore.load_events(proj, "street")) == 2
      and proj.get_event_type(stop.id) is None and em.current_type is None)
check("current type falls back to the first", em.current_type_obj().id == et.id)

# a second video: events per video
frames2 = extract(VIDEO, _TMP / "frames2", "street_2", step=25)
ctrl.add_video_frames("street_2", dict(info, step=25), frames2)
ctrl.set_image(frames2[0][1])
check("another video: its own (empty) events", em.vid == "street_2" and em.events == [])
em.start_here()
ctrl.set_image(frames2[1][1])
em.finish_here()
check("events kept apart", len(ProjectStore.load_events(proj, "street_2")) == 1
      and len(ProjectStore.load_events(proj, "street")) == 2)
em.start_here()
plain = _TMP / "plain.jpg"
cv2.imwrite(str(plain), np.zeros((20, 20, 3), np.uint8))
ctrl.add_images_from_paths([str(plain)])
ctrl.set_image(str(plain))
check("plain image: no video, started event dropped", em.vid == "" and not em.is_open
      and not em.start_here() and statuses[-1] == "ev_not_video")
ctrl.set_image(paths[0])
check("back on the first video", em.vid == "street" and len(em.events) == 2)
ctrl.save_project()
ctrl2 = ProjectController()
ctrl2.open_project(proj.project_path)
vm2 = VideoManager(ctrl2)
em2 = EventManager(ctrl2, vm2)
ctrl2.set_image(paths[0])
check("reopened project: events and types", len(em2.events) == 2
      and [t.name for t in em2.types] == ["перестроение"])


# ═════════════════════════════════════════════════════════════════════════════
section("4. Export: CSV + ActivityNet JSON")
# ═════════════════════════════════════════════════════════════════════════════
for r in proj.images:
    if r.video == "street_2":
        r.split = "val"
ctrl.save_project()
out = _TMP / "export"
ctrl.export_dataset(out, "video_events")
rows = list(csv.DictReader(open(out / "events.csv", encoding="utf-8")))
check("events.csv: one row per event", len(rows) == 3)
r0 = next(r for r in rows if r["video"] == "street" and r["start_frame"] == "15")
check("csv row: frames, seconds, duration, type, file",
      (r0["end_frame"], r0["start_sec"], r0["end_sec"], r0["duration_sec"], r0["type"],
       r0["video_file"], r0["subset"]) == ("40", "0.6", "1.6", "1.0", "перестроение",
                                           "улица.mp4", "training"))
an = json.loads((out / "activitynet.json").read_text(encoding="utf-8"))
check("ActivityNet: version, taxonomy with root",
      an["version"] == "1.3" and an["taxonomy"][0]["nodeName"] == "Root"
      and an["taxonomy"][1]["nodeName"] == "перестроение")
db = an["database"]
check("ActivityNet: each video with subset, duration, annotations",
      set(db) == {"street", "street_2"} and db["street"]["duration"] == 2.0
      and db["street_2"]["subset"] == "validation" and len(db["street"]["annotations"]) == 2)
seg = next(x for x in db["street"]["annotations"] if x["frames"][0] == 15)
check("ActivityNet segment in seconds + frames", seg["segment"] == [0.6, 1.6]
      and seg["frames"] == [15, 40] and seg["label"] == "перестроение")
check("event_types.txt", (out / "event_types.txt").read_text(encoding="utf-8") == "перестроение\n")
check("copy on: source video copied into videos/", (out / "videos" / "улица.mp4").is_file()
      and (out / "videos" / "улица.mp4").stat().st_size == VIDEO.stat().st_size)
check("copy on: frames of each video into frames/<video>/",
      len(list((out / "frames" / "street").glob("*.jpg"))) == N // STEP
      and len(list((out / "frames" / "street_2").glob("*.jpg"))) == 2)
out2 = _TMP / "export_nocopy"
ctrl.export_dataset(out2, "video_events", copy_images=False)
check("copy off: tables only", (out2 / "events.csv").exists()
      and not (out2 / "videos").exists() and not (out2 / "frames").exists())
from annotator.ui.dialogs.export_dialog import _FORMATS, ExportDatasetDialog
check("Video Events in the export formats", "video_events" in [k for _, k in _FORMATS])
xd = ExportDatasetDialog(proj, {}, unreviewed=(5, 2))
xd._fmt_combo.setCurrentIndex([k for _, k in _FORMATS].index("video_events"))
check("export dialog: for events the copy option names videos and frames, no 'skip unreviewed'",
      "videos" in xd._copy_cb.text() and xd._reviewed_cb.isHidden()
      and not xd.reviewed_only)
xd._radio_multi.setChecked(True)
check("multi-task mode: copy images / skip unreviewed again",
      xd._copy_cb.text() == "Copy images to output folder" and not xd._reviewed_cb.isHidden())
xd._radio_single.setChecked(True)
xd._fmt_combo.setCurrentIndex(0)
check("other formats: unchanged", xd._copy_cb.text() == "Copy images to output folder"
      and not xd._reviewed_cb.isHidden())


# ═════════════════════════════════════════════════════════════════════════════
section("5. Main window")
# ═════════════════════════════════════════════════════════════════════════════
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QDialog, QInputDialog
import annotator.ui.main_window as mw
win = mw.MainWindow()
wc = win.controller
wc.open_project(proj.project_path)
pump()
check("Video menu: E / Shift+E", (win._act_event_mark.shortcut().toString(),
                                  win._act_event_cancel.shortcut().toString()) == ("E", "Shift+E"))
check("Events tab", win._right_tabs.indexOf(win._events_panel) == 2)
win._goto_image(paths[4])
pump()
check("Events tab lists the video's events", win._events_panel._tree.topLevelItemCount() == 2
      and "улица.mp4" in win._events_panel._head.text())
bold = [win._events_panel._tree.topLevelItem(i).font(0).bold() for i in range(2)]
check("events on the current frame in bold", bold == [True, True])
check("timeline: type combo with + new", win._timeline._type_combo.count() == 2
      and "перестроение" in win._timeline._type_combo.itemText(0))
check("timeline: events summary", "2" in win._timeline._ev_state.text())
win._timeline._ev_bar.resize(400, 30)
img = QImage(400, 40, QImage.Format.Format_ARGB32)
qp = QPainter(img)
win._timeline._ev_bar.render(qp)
qp.end()
check("event strip paints, hit areas known", len(win._timeline._ev_bar._rects) == 2)
r, eid = win._timeline._ev_bar._rects[0]
check("event at a point of its bar", win._timeline._ev_bar.event_at(r.center()) == eid)

wev = win._events
win._event_mark()
check("E starts an event", wev.is_open and wev.open_start == 20)
win._timeline.refresh()
check("timeline shows the started event", "20" in win._timeline._ev_state.text())
win._goto_image(paths[6])
pump()
win._event_mark()
pump()
check("second E finishes it", not wev.is_open and len(wev.events) == 3
      and win._events_panel._tree.topLevelItemCount() == 3)
win._ctrl.undo_stack.undo()
check("Ctrl+Z in the window undoes it", len(wev.events) == 2)
win._ctrl.undo_stack.redo()

# no types: E asks for a name
for t in list(wev.types):
    wev.delete_type(t.id)
_orig = QInputDialog.getText
QInputDialog.getText = staticmethod(lambda *a, **k: ("падение", True))
win._event_mark()
win._goto_image(paths[7])
pump()
win._event_mark()
QInputDialog.getText = _orig
check("E without types asks for one, then adds the event",
      [t.name for t in wev.types] == ["падение"] and len(wev.events) == 1)

from annotator.video.events_ui import EventDialog, EventTypesDialog
sel = wev.events[0]
dlg = EventDialog(wev, win._video, sel, win)
check("event dialog: frame range of the video", (dlg.start_spin.minimum(), dlg.end_spin.maximum())
      == (0, 45) and dlg.start_spin.value() == sel.start)
dlg.end_spin.setValue(45)
dlg.note_edit.setText("в конце")
ch = dlg.changes()
check("event dialog returns the changes", ch["end"] == 45 and ch["note"] == "в конце"
      and ch["track_id"] is None)
wev.update(sel.id, **ch)
check("applied", wev.get(sel.id).end == 45)
td = EventTypesDialog(wev, win)
check("types dialog lists the types", td._list.count() == 1)
wev.select(sel.id)
win._events_panel._tree.setFocus()
win._events_panel._tree.setCurrentItem(win._events_panel._tree.topLevelItem(0))
check("Delete in the Events list deletes the event (not an annotation)",
      win._events_panel.delete_selected() and wev.events == [])
win._goto_image(str(plain))
pump()
check("plain image: timeline hidden, Events tab says so", win._timeline.isHidden()
      and win._events_panel._tree.topLevelItemCount() == 0
      and not win._events_panel._btn_edit.isEnabled())
from annotator.ui.dialogs.project_settings_dialog import _HOTKEY_LABELS
check("event hotkeys in project settings", {"event_mark", "event_cancel"}
      <= {k for k, _ in _HOTKEY_LABELS})
wc.project.settings.hotkeys["event_mark"] = "Ctrl+Alt+E"
win._apply_hotkeys(wc.project.settings.hotkeys)
check("event key follows project hotkeys", win._act_event_mark.shortcut().toString() == "Ctrl+Alt+E")
from annotator.i18n import _EN, _RU
check("every event string translated", {k for k in _EN if k.startswith("ev_")}
      == {k for k in _RU if k.startswith("ev_")})
win._set_language("RU")
check("Events tab retranslated", win._right_tabs.tabText(2) == "События")
win._set_language("EN")

from PyQt6.QtWidgets import QApplication as _QApp
for _w in _QApp.topLevelWidgets():
    _w.close()

print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
