"""
Review of model annotations (phase 8-A): status in meta, controller, canvas,
panels, QC, export, main-window keys, ML re-run keeps accepted annotations.
Run: .venv/Scripts/python test_review.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QEventLoop, Qt, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from PIL import Image

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

def pump(ms=30):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()

from annotator.controller.project_controller import ProjectController
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.review import (count_unreviewed, count_unreviewed_in_file,
                                     drop_unreviewed, is_model, is_reviewed,
                                     is_unreviewed, reviewed_meta)

def box(cid, x=0.1, model=False, reviewed=False, conf=0.9):
    a = Annotation.new(cid, AnnotationType.BBOX, {"x": x, "y": 0.1, "w": 0.2, "h": 0.2})
    if model:
        a.meta.update(source="model", model="det.pt", confidence=conf)
        if reviewed:
            a.meta.update(reviewed_meta(a.meta, True, "Bob"))
    return a

def make_images(folder: Path, n: int) -> list[str]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(n):
        p = folder / f"img{i}.png"
        Image.new("RGB", (64, 48), (40 * i % 255, 80, 120)).save(p)
        out.append(str(p))
    return out


# ═════════════════════════════════════════════════════════════════════════════
section("1. Review status in meta")
# ═════════════════════════════════════════════════════════════════════════════
man, mod, acc = box(0), box(0, model=True), box(0, model=True, reviewed=True)
check("manual annotation is never unreviewed", not is_model(man) and not is_unreviewed(man))
check("fresh model annotation is unreviewed", is_model(mod) and is_unreviewed(mod))
check("accepted model annotation is reviewed", is_reviewed(acc) and not is_unreviewed(acc))
check("reviewed_meta records time and reviewer",
      acc.meta.get("reviewed_by") == "Bob" and "reviewed_at" in acc.meta)
check("reviewed_meta keeps the rest of meta",
      acc.meta["source"] == "model" and acc.meta["confidence"] == 0.9)
cleared = reviewed_meta(acc.meta, False)
check("clearing removes every review key",
      not any(k in cleared for k in ("reviewed", "reviewed_at", "reviewed_by"))
      and cleared["source"] == "model")
check("no reviewer -> no reviewed_by", "reviewed_by" not in reviewed_meta(mod.meta, True, ""))
check("count_unreviewed", count_unreviewed([man, mod, acc, box(1, model=True)]) == 2)
d = drop_unreviewed({"a": [man, mod, acc], "b": [mod]})
check("drop_unreviewed keeps manual and accepted",
      [x.id for x in d["a"]] == [man.id, acc.id] and d["b"] == [])
f1 = _TMP / "plain.json"
f1.write_text(json.dumps([man.to_dict()]), encoding="utf-8")
f2 = _TMP / "mixed.json"
f2.write_text(json.dumps([man.to_dict(), mod.to_dict(), acc.to_dict(), box(2, model=True).to_dict()]),
              encoding="utf-8")
check("file count: no model annotations -> 0", count_unreviewed_in_file(f1) == 0)
check("file count: unreviewed ones only", count_unreviewed_in_file(f2) == 2)
check("file count: missing file -> 0", count_unreviewed_in_file(_TMP / "nope.json") == 0)
check("old annotation from dict (no review keys) loads unreviewed",
      is_unreviewed(Annotation.from_dict(mod.to_dict())))


# ═════════════════════════════════════════════════════════════════════════════
section("2. Controller: accept, edit, undo")
# ═════════════════════════════════════════════════════════════════════════════
ctrl = ProjectController()
proj = ctrl.create_project("rv", _TMP / "rv.annproj")
paths = make_images(_TMP / "imgs", 4)
ctrl.add_images_from_paths([Path(p) for p in paths])
ctrl.reviewer = lambda: "Alice"
ctrl.set_image(paths[0])
m1, m2, h1 = box(0, model=True), box(0, 0.5, model=True), box(0, 0.7)
for a in (m1, m2, h1):
    ctrl.add_annotation(a)
before = ctrl.undo_stack.count()
n = ctrl.set_reviewed([m1.id, h1.id])
check("accept selected: only the model annotation counts", n == 1)
check("accepted annotation carries the reviewer",
      ctrl.get_annotation(m1.id).meta.get("reviewed_by") == "Alice")
check("manual annotation got no review keys", "reviewed" not in ctrl.get_annotation(h1.id).meta)
check("accept is one undo step", ctrl.undo_stack.count() == before + 1)
check("accepting again changes nothing", ctrl.set_reviewed([m1.id]) == 0
      and ctrl.undo_stack.count() == before + 1)
ctrl.undo_stack.undo()
check("undo makes it unreviewed again", is_unreviewed(ctrl.get_annotation(m1.id)))
ctrl.undo_stack.redo()
n = ctrl.set_reviewed(None)
check("accept all on the image", n == 1 and count_unreviewed(ctrl.current_annotations) == 0)
ctrl.undo_stack.undo()
check("undo of accept-all", count_unreviewed(ctrl.current_annotations) == 1)
n = ctrl.set_reviewed([m1.id], False)
check("mark unreviewed", n == 1 and is_unreviewed(ctrl.get_annotation(m1.id)))

new_data = dict(ctrl.get_annotation(m2.id).data, x=0.55)
ctrl.update_annotation_data(m2.id, new_data)
a2 = ctrl.get_annotation(m2.id)
check("editing a model annotation accepts it", is_reviewed(a2) and a2.data["x"] == 0.55)
ctrl.undo_stack.undo()
a2 = ctrl.get_annotation(m2.id)
check("undo of the edit restores geometry and status",
      a2.data["x"] == 0.5 and is_unreviewed(a2))
ctrl.update_annotation_data(m2.id, dict(ctrl.get_annotation(m2.id).data))
check("an 'edit' that changes nothing does not accept", is_unreviewed(ctrl.get_annotation(m2.id)))
ctrl.undo_stack.undo()
ctrl.update_annotation_data(h1.id, dict(h1.data, x=0.72))
check("editing a manual annotation adds no review keys",
      "reviewed" not in ctrl.get_annotation(h1.id).meta)
ctrl.set_reviewed([m1.id])
ctrl.set_image(paths[1])                        # flush to disk
ctrl.set_image(paths[0])
check("review status survives save / reload",
      is_reviewed(ctrl.get_annotation(m1.id)) and is_unreviewed(ctrl.get_annotation(m2.id)))
ctrl.apply_annotation_changes(paths[2], [box(0, model=True), box(0, 0.4, model=True)], [])
check("unreviewed_counts across the project (memory + disk)", ctrl.unreviewed_counts() == (3, 2))
ctrl.reviewer = None
ctrl.set_reviewed(None)
check("no reviewer callable -> accepted without a name",
      "reviewed_by" not in ctrl.get_annotation(m2.id).meta and is_reviewed(ctrl.get_annotation(m2.id)))
ctrl.undo_stack.undo()


# ═════════════════════════════════════════════════════════════════════════════
section("3. Export: only reviewed")
# ═════════════════════════════════════════════════════════════════════════════
def label_lines(out: Path) -> int:
    stems = {Path(p).stem for p in paths}
    return sum(len([l for l in f.read_text().splitlines() if l.strip()])
               for f in out.rglob("*.txt") if f.stem in stems)

out_all, out_rev = _TMP / "exp_all", _TMP / "exp_rev"
ctrl.export_dataset(out_all, "yolo_detect", copy_images=False)
ctrl.export_dataset(out_rev, "yolo_detect", copy_images=False, reviewed_only=True)
check("export keeps everything by default", label_lines(out_all) == 5)
check("reviewed_only drops the 3 unreviewed", label_lines(out_rev) == 2)
check("reviewed_only does not change the project", ctrl.unreviewed_counts() == (3, 2))
from annotator.exporters.export_job import ExportJob
out_mt = _TMP / "exp_mt"
ctrl.export_multitask(out_mt, [ExportJob("yolo_detect", geometry_policy="skip")],
                      copy_images=False, reviewed_only=True)
check("multi-task export honours reviewed_only", label_lines(out_mt) == 2)


# ═════════════════════════════════════════════════════════════════════════════
section("4. QC: rule and statistics")
# ═════════════════════════════════════════════════════════════════════════════
ctrl.run_validation()
from annotator.storage.project_store import ProjectStore
from annotator.validation.validator import Validator
all_anns = ProjectStore.load_all_annotations(proj)
all_anns[ctrl.current_image] = ctrl.current_annotations
rep = Validator().run(proj, all_anns)
issues = [i for i in rep.issues if i.rule_name == "Unreviewed"]
check("one info issue per image with unreviewed annotations",
      len(issues) == 2 and all(i.severity == "info" for i in issues))
check("issue points at an unreviewed annotation (double-click navigates)",
      issues[0].ann_id in {a.id for a in all_anns[issues[0].image_path] if is_unreviewed(a)})
check("stats: model / unreviewed / images",
      (rep.stats["model_annotations"], rep.stats["unreviewed_annotations"],
       rep.stats["unreviewed_images"]) == (4, 3, 2))
from annotator.ui.panels.qc_panel import QCPanel
qc = QCPanel()
qc.show_report(rep)
check("QC panel shows reviewed / total", qc._lbl_review.text().startswith("1 / 4"))


# ═════════════════════════════════════════════════════════════════════════════
section("5. Canvas")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.ui.canvas.scene import AnnotationScene
scene = AnnotationScene()
scene.load_image(paths[0])
scene.rebuild_annotations(ctrl.current_annotations, proj)
it_unrev = scene._ann_items[m2.id]
it_acc = scene._ann_items[m1.id]
it_man = scene._ann_items[h1.id]
check("unreviewed item is dashed", it_unrev.unreviewed
      and it_unrev.outline_style == Qt.PenStyle.DashLine)
check("accepted and manual items are solid",
      it_acc.outline_style == Qt.PenStyle.SolidLine and it_man.outline_style == Qt.PenStyle.SolidLine)
check("unreviewed label carries the robot", it_unrev.label.endswith("🤖") and "🤖" not in it_acc.label)
check("unreviewed fill is paler", abs(it_unrev.fill_opacity - it_acc.fill_opacity / 2) < 1e-9)
from PyQt6.QtGui import QImage, QPainter
img = QImage(64, 48, QImage.Format.Format_ARGB32)
p = QPainter(img)
scene.render(p)
p.end()
check("scene with dashed items renders", True)
# every item kind paints with the dashed style without errors
kinds = [
    Annotation.new(0, AnnotationType.SEGMENT, {"points": [[.1, .1], [.5, .1], [.3, .5]]}),
    Annotation.new(0, AnnotationType.POLYLINE, {"points": [[.1, .1], [.5, .5]]}),
    Annotation.new(0, AnnotationType.OBB, {"cx": .5, "cy": .5, "w": .2, "h": .1, "angle_deg": 30}),
    Annotation.new(0, AnnotationType.POINT, {"x": .5, "y": .5}),
    Annotation.new(0, AnnotationType.MASK, {"mask_png_path": "", "polygon": [[.1, .1], [.4, .1], [.4, .4]],
                                            "bbox": [.25, .25, .3, .3]}),
    Annotation.new(0, AnnotationType.POSE, {"keypoints": [[.1, .1, 2], [.3, .3, 2]]}),
]
for a in kinds:
    a.meta.update(source="model")
scene.rebuild_annotations(kinds, proj)
p = QPainter(img)
scene.render(p)
p.end()
check("all item kinds draw dashed", all(scene._ann_items[a.id].unreviewed for a in kinds))


# ═════════════════════════════════════════════════════════════════════════════
section("6. Panels")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.ui.panels.annotations_panel import AnnotationsPanel
panel = AnnotationsPanel()
panel.load_project(proj)
panel.refresh([ctrl.get_annotation(m1.id), ctrl.get_annotation(m2.id), ctrl.get_annotation(h1.id)])
check("accepted: tick+robot with confidence", "✓🤖 0.90" in panel._list.item(0).text())
check("unreviewed: robot without the tick",
      "🤖 0.90" in panel._list.item(1).text() and "✓" not in panel._list.item(1).text())
check("manual: no marker", "🤖" not in panel._list.item(2).text())
check("header counts unreviewed", "1" in panel._header.text() and "🤖" in panel._header.text())
check("tooltip says who reviewed", "Alice" in panel._list.item(0).toolTip())
panel._list.setCurrentRow(1)
check("selected_annotation_id", panel.selected_annotation_id() == m2.id)

from annotator.ui.panels.images_panel import ImagesPanel
ctrl.save_project()
ctrl.set_image(paths[1])                                  # flush the current image
ip = ImagesPanel()
ip.load_project(proj)
check("scan finds unreviewed per image", ip.unreviewed_count(paths[0]) == 1
      and ip.unreviewed_count(paths[2]) == 2 and ip.unreviewed_count(paths[1]) == 0)
check("list item shows the count", "🤖2" in ip._list.item(2).text())
ip._status_filter.setCurrentIndex(3)
check("filter 'unreviewed' lists only those images",
      [r.path for r in ip._displayed] == [paths[0], paths[2]])
ip._status_filter.setCurrentIndex(0)
ip.select_by_path(paths[1])
check("next unreviewed from img1 -> img2", ip.select_next_unreviewed()
      and ip._list.currentRow() == 2)
check("wraps around to img0", ip.select_next_unreviewed() and ip._list.currentRow() == 0)
ip.set_unreviewed(paths[0], 0)
ip.set_unreviewed(paths[2], 0)
check("none left -> False", not ip.select_next_unreviewed())


# ═════════════════════════════════════════════════════════════════════════════
section("7. Main window: R / Shift+R / U, export dialog")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.app_settings import app_settings
app_settings().setValue("user_name", "Carol")
import annotator.ui.main_window as mw
win = mw.MainWindow()
wc = win.controller
wc.open_project(proj.project_path)
pump()
ipw = win._images_panel
check("default shortcuts", (win._act_review_accept.shortcut().toString(),
                            win._act_review_all.shortcut().toString(),
                            win._act_review_next.shortcut().toString()) == ("R", "Shift+R", "U"))
ipw.select_by_path(paths[1])
pump()
win._act_review_next.trigger()
pump()
check("U jumps to the next image to review", wc.current_image == paths[2])
win._scene.deselect_all()
win._annotations_panel._list.setCurrentRow(-1)
win._act_review_accept.trigger()
check("R without a selection explains", "Shift+R" in win.statusBar().currentMessage())
target = next(a for a in wc.current_annotations if is_unreviewed(a))
win._scene.select_by_id(target.id)
win._act_review_accept.trigger()
check("R accepts the selected annotation, reviewer from the user name",
      is_reviewed(wc.get_annotation(target.id))
      and wc.get_annotation(target.id).meta.get("reviewed_by") == "Carol")
other = next(a for a in wc.current_annotations if is_unreviewed(a))
ap = win._annotations_panel
check("after R the next unreviewed annotation is selected (list and canvas)",
      ap.selected_annotation_id() == other.id
      and win._scene.get_selected_item().annotation_id == other.id)
ap.refresh(wc.current_annotations)
check("panel rebuild keeps the selected row", ap.selected_annotation_id() == other.id)
check("images panel count follows the current image", ipw.unreviewed_count(paths[2]) == 1)
win._act_review_all.trigger()
pump()
check("Shift+R accepts the rest and moves to the next image to review",
      wc.current_image == paths[0] and ipw.unreviewed_count(paths[2]) == 0)
win._act_review_all.trigger()
pump()
check("last one accepted -> stays, says nothing left",
      ipw.unreviewed_count(paths[0]) == 0 and wc.current_image == paths[0]
      and win.statusBar().currentMessage() != "")
target = next(a for a in wc.current_annotations if is_model(a))
win._scene.select_by_id(target.id)
win._review_unmark_selected()
check("unmark returns it to unreviewed", is_unreviewed(wc.get_annotation(target.id))
      and ipw.unreviewed_count(paths[0]) == 1)
proj.settings.hotkeys["review_accept"] = "Ctrl+Alt+R"
win._apply_hotkeys(proj.settings.hotkeys)
check("review keys follow project hotkeys", win._act_review_accept.shortcut().toString() == "Ctrl+Alt+R")
del proj.settings.hotkeys["review_accept"]

from annotator.ui.dialogs.export_dialog import ExportDatasetDialog
dlg = ExportDatasetDialog(wc.project, {}, win, unreviewed=wc.unreviewed_counts())
check("export dialog offers 'skip unreviewed' when there are some",
      not dlg._reviewed_cb.isHidden() and "1 on 1 image" in dlg._reviewed_cb.text())
check("unchecked by default", not dlg.reviewed_only)
dlg._reviewed_cb.setChecked(True)
check("checked -> reviewed_only", dlg.reviewed_only)
dlg2 = ExportDatasetDialog(wc.project, {}, win)
check("hidden when nothing to review", dlg2._reviewed_cb.isHidden() and not dlg2.reviewed_only)
from annotator.ui.dialogs.project_settings_dialog import _HOTKEY_LABELS
check("hotkeys listed in project settings",
      {"review_accept", "review_accept_all", "review_next"} <= {k for k, _ in _HOTKEY_LABELS})


# ═════════════════════════════════════════════════════════════════════════════
section("8. ML: accepted annotations are kept")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.ml.convert import is_unaccepted_model_annotation
check("ML sees accepted model annotations as kept",
      is_unaccepted_model_annotation(mod) and not is_unaccepted_model_annotation(acc)
      and not is_unaccepted_model_annotation(man))
from PyQt6.QtWidgets import QMessageBox
class _AutoBox(QMessageBox):
    def exec(self):
        for b in self.buttons():
            if self.buttonRole(b) == QMessageBox.ButtonRole.DestructiveRole:
                self._clicked = b
        return 0
    def clickedButton(self):
        return getattr(self, "_clicked", None)
import annotator.ml.extension as ext
_orig = ext.QMessageBox
ext.QMessageBox = _AutoBox
try:
    win._ml.remove_model_annotations()
finally:
    ext.QMessageBox = _orig
left = wc.current_annotations
check("'Remove model annotations' takes only unreviewed ones",
      count_unreviewed(left) == 0 and sum(is_model(a) for a in left) >= 1)


# close every window: one left open is destroyed during interpreter shutdown,
# its app-wide key filter then crashes the process (random exit code 139)
from PyQt6.QtWidgets import QApplication as _QApp
for _w in _QApp.topLevelWidgets():
    _w.close()

print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
