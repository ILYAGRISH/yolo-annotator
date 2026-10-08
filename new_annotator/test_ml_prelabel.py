"""
Pre-labelling tests (phase 7-B): conversion, controller batch API, runner.
Run: .venv/Scripts/python test_ml_prelabel.py

No GPU needed — the runner is driven by a fake backend. Optional real run
(skipped unless both are set):
    ML_TEST_PYTHON=C:/miniconda3/envs/yolo_hard/python.exe
    ML_TEST_SEG_MODEL=<path to yolo11n-seg.pt>
"""
import math
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import numpy as np
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

def wait(pred, timeout=20.0) -> bool:
    end = time.monotonic() + timeout
    loop = QEventLoop()
    while not pred():
        if time.monotonic() > end:
            return False
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    return True

def close(a, b, eps=1e-6):
    return abs(a - b) < eps

from annotator.controller.project_controller import ProjectController
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import LabelClass, SkeletonKeypoint
from annotator.ml.client import BACKEND_EXITED, Reply
from annotator.ml.convert import (ConvertOptions, ConvertReport, compatible, convert,
                                  default_class_type, is_model_annotation)
from annotator.ml.prelabel import (PrelabelRunner, PrelabelSummary, create_classes,
                                   make_skeleton, unused_placeholder)
from annotator.ml.prelabel_settings import (EXISTING_ADD, EXISTING_REPLACE, EXISTING_SKIP,
                                            PrelabelSettings)
from ml_backend import protocol

W, H = 200, 100

def lc(cid, kind, name=None, skeleton=None):
    c = LabelClass(id=cid, name=name or f"c{cid}", color="#ff0000", annotation_type=kind)
    if skeleton:
        c.skeleton = skeleton
    return c

def det(cls=0, conf=0.9, box=(20, 10, 60, 50), **kw):
    return {"cls": cls, "conf": conf, "box": list(box), **kw}

def res(task, dets=(), classification=()):
    return {"width": W, "height": H, "task": task,
            "detections": list(dets), "classification": list(classification)}

OPTS = ConvertOptions(model_name="m.pt")


# ═════════════════════════════════════════════════════════════════════════════
section("1. Conversion: boxes, points, OBB")
# ═════════════════════════════════════════════════════════════════════════════
a = convert(res("detect", [det()]), {0: lc(5, "bbox")}, OPTS)[0]
check("detect -> bbox, normalised top-left + size",
      a.ann_type == AnnotationType.BBOX and a.class_id == 5
      and (a.data["x"], a.data["y"], a.data["w"], a.data["h"]) == (0.1, 0.1, 0.2, 0.4))
check("meta: source=model, confidence, model name",
      a.meta["source"] == "model" and a.meta["confidence"] == 0.9 and a.meta["model"] == "m.pt"
      and a.meta["tool"] == "yolo" and is_model_annotation(a))
a = convert(res("detect", [det(box=(-15, -5, 250, 130))]), {0: lc(1, "bbox")}, OPTS)[0]
check("box outside the image is clamped to it",
      (a.data["x"], a.data["y"], a.data["w"], a.data["h"]) == (0.0, 0.0, 1.0, 1.0))
rep = ConvertReport()
out = convert(res("detect", [det(box=(50, 50, 50.4, 80))]), {0: lc(1, "bbox")}, OPTS, report=rep)
check("degenerate box skipped and counted", out == [] and rep.skipped == {"empty geometry": 1})
a = convert(res("detect", [det()]), {0: lc(1, "point")}, OPTS)[0]
check("detect -> point at the box centre",
      a.ann_type == AnnotationType.POINT and (a.data["x"], a.data["y"]) == (0.2, 0.3))
a = convert(res("detect", [det()]), {0: lc(1, "obb")}, OPTS)[0]
check("detect -> obb with angle 0",
      a.data == {"cx": 0.2, "cy": 0.3, "w": 0.2, "h": 0.4, "angle_deg": 0.0})
a = convert(res("detect", [det()]), {0: lc(1, "polygon")}, OPTS)[0]
check("detect -> polygon = the 4 box corners", len(a.data["points"]) == 4)

o = det(box=(70, 20, 130, 80), obb=[100.0, 50.0, 60.0, 20.0, math.radians(30)])
a = convert(res("obb", [o]), {0: lc(1, "obb")}, OPTS)[0]
check("obb -> obb: centre / size normalised per axis, radians -> degrees",
      close(a.data["cx"], 0.5) and close(a.data["cy"], 0.5) and close(a.data["w"], 0.3)
      and close(a.data["h"], 0.2) and close(a.data["angle_deg"], 30.0))
a = convert(res("obb", [o]), {0: lc(1, "polygon")}, OPTS)[0]
# canvas convention: corner (-w/2, -h/2) rotated clockwise (y down) by the angle, in pixels
c30, s30 = math.cos(math.radians(30)), math.sin(math.radians(30))
x0, y0 = 100 + c30 * -30 - s30 * -10, 50 + s30 * -30 + c30 * -10
check("obb -> polygon: corners follow the canvas rotation",
      close(a.data["points"][0][0], x0 / W, 1e-4) and close(a.data["points"][0][1], y0 / H, 1e-4))
a = convert(res("obb", [o]), {0: lc(1, "bbox")}, OPTS)[0]
check("obb -> bbox uses the enclosing box", close(a.data["x"], 0.35) and close(a.data["w"], 0.3))


# ═════════════════════════════════════════════════════════════════════════════
section("2. Conversion: polygons and masks")
# ═════════════════════════════════════════════════════════════════════════════
circle = [[100 + 30 * math.cos(t / 60 * 2 * math.pi), 50 + 30 * math.sin(t / 60 * 2 * math.pi)]
          for t in range(60)]
square = [[10, 10], [30, 10], [30, 30], [10, 30]]
seg = det(box=(70, 20, 130, 80), polygons=[circle, square])
a = convert(res("segment", [seg]), {0: lc(1, "polygon")}, ConvertOptions(simplify_px=2.0))[0]
pts = a.data["points"]
check("segment -> polygon: the largest part, simplified", 6 <= len(pts) < 60)
check("polygon points normalised into [0, 1]", all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts))
a0 = convert(res("segment", [seg]), {0: lc(1, "polygon")}, ConvertOptions(simplify_px=0))[0]
check("simplify 0 keeps every point", len(a0.data["points"]) == 60)

proj_dir = _TMP / "maskproj"
proj_dir.mkdir()
mopts = ConvertOptions(project_path=proj_dir, image_stem="img")
a = convert(res("segment", [seg]), {0: lc(2, "mask")}, mopts)[0]
png = proj_dir / a.data["mask_png_path"]
arr = np.array(Image.open(png))
check("segment -> mask: brush-style data", a.ann_type == AnnotationType.MASK
      and set(a.data) == {"mask_png_path", "polygon", "bbox"} and png.is_file())
check("mask PNG has the image size", arr.shape == (H, W))
check("mask keeps EVERY part (circle and square)", arr[50, 100] == 255 and arr[20, 20] == 255)
check("mask outside the parts is empty", arr[90, 190] == 0)
check("mask bbox covers both parts", a.data["bbox"][0] < 0.5 and a.data["bbox"][2] > 0.5)
rep = ConvertReport()
convert(res("segment", [seg]), {0: lc(2, "mask")}, ConvertOptions(), report=rep)
check("mask without a project folder is skipped", rep.skipped == {"no project folder for masks": 1})
a = convert(res("detect", [det()]), {0: lc(2, "mask")}, mopts)[0]
check("detect -> mask fills the box", np.array(Image.open(proj_dir / a.data["mask_png_path"]))[30, 40] == 255)


# ═════════════════════════════════════════════════════════════════════════════
section("3. Conversion: pose, classification, mapping")
# ═════════════════════════════════════════════════════════════════════════════
skel3 = [SkeletonKeypoint("a"), SkeletonKeypoint("b"), SkeletonKeypoint("c")]
pose = det(keypoints=[[20, 10, 0.9], [40, 20, 0.3], [60, 30, 0.8]])
a = convert(res("pose", [pose]), {0: lc(3, "keypoints", skeleton=skel3)}, OPTS)[0]
check("pose -> keypoints: confident visible (2), weak not labelled (0)",
      a.data["keypoints"] == [[0.1, 0.1, 2], [0.0, 0.0, 0], [0.3, 0.3, 2]])
rep = ConvertReport()
convert(res("pose", [pose]), {0: lc(3, "keypoints", skeleton=skel3[:2])}, OPTS, report=rep)
check("keypoint count != skeleton -> skipped with a reason",
      rep.skipped == {"keypoint count differs from the class skeleton": 1})
rep = ConvertReport()
convert(res("pose", [det(keypoints=[[1, 1, 0.1]] * 3)]),
        {0: lc(3, "keypoints", skeleton=skel3)}, OPTS, report=rep)
check("no visible keypoint -> skipped", rep.skipped == {"no visible keypoints": 1})

cl = res("classify", classification=[{"cls": 7, "conf": 0.8}, {"cls": 2, "conf": 0.1}])
out = convert(cl, {7: lc(9, "classification"), 2: lc(4, "classification")}, OPTS)
check("classify -> one image label for the top-1 class",
      len(out) == 1 and out[0].ann_type == AnnotationType.CLASSIFY and out[0].class_id == 9)
rep = ConvertReport()
convert(cl, {7: lc(9, "classification")}, OPTS, existing=[out[0]], report=rep)
check("same image label already there -> not duplicated", rep.skipped == {"already labelled": 1})
rep = ConvertReport()
out = convert(cl, {7: lc(9, "classification")}, ConvertOptions(min_conf=0.9), report=rep)
check("classify: top-1 below the confidence threshold -> no label",
      out == [] and rep.skipped == {"below confidence": 1})

rep = ConvertReport()
out = convert(res("detect", [det(cls=0), det(cls=1), det(cls=2)]),
              {0: lc(1, "bbox"), 1: None, 2: lc(2, "keypoints")}, OPTS, report=rep)
check("unmapped and incompatible detections are skipped and counted",
      len(out) == 1 and rep.skipped == {"class not mapped": 1, "incompatible class type": 1}
      and rep.added == 1)
check("compatibility table", compatible("segment", "mask") and not compatible("detect", "keypoints")
      and not compatible("classify", "bbox"))
check("natural class type per task", [default_class_type(t) for t in
      ("detect", "segment", "obb", "pose", "classify")] ==
      ["bbox", "polygon", "obb", "keypoints", "classification"])


# ═════════════════════════════════════════════════════════════════════════════
section("4. Controller: changes on any image")
# ═════════════════════════════════════════════════════════════════════════════
imgs = []
for i in range(4):
    p = _TMP / f"img{i}.png"
    Image.new("RGB", (W, H), (60, 60, 60)).save(p)
    imgs.append(str(p))
ctrl = ProjectController()
proj = ctrl.create_project("pl", _TMP / "pl.annproj")
car = proj.classes[0]
car.name, car.annotation_type = "car", "bbox"
ctrl.add_images_from_paths(imgs)
paths = [r.path for r in proj.images]
ctrl.set_image(paths[0])

manual = Annotation.new(car.id, AnnotationType.BBOX, {"x": 0, "y": 0, "w": 0.1, "h": 0.1})
ctrl.add_annotation(manual)
check("annotations_for(current) = memory", [a.id for a in ctrl.annotations_for(paths[0])] == [manual.id])
new = convert(res("detect", [det(), det(box=(100, 10, 150, 60))]), {0: car}, OPTS)
depth = ctrl.undo_stack.count()
ctrl.apply_annotation_changes(paths[0], new, [manual.id], text="Pre-label")
check("current image: changes applied in memory",
      {a.id for a in ctrl.current_annotations} == {a.id for a in new})
check("current image: ONE undo step", ctrl.undo_stack.count() == depth + 1)
ctrl.undo_stack.undo()
check("undo restores the manual annotation, drops the model ones",
      [a.id for a in ctrl.current_annotations] == [manual.id])
ctrl.undo_stack.redo()

other = convert(res("detect", [det()]), {0: car}, OPTS)
ctrl.apply_annotation_changes(paths[1], other)
check("other image: written to disk", [a.id for a in ctrl.annotations_for(paths[1])] == [other[0].id])
labels = Path(paths[1]).parent / "labels" / (Path(paths[1]).stem + ".txt")
check("other image: YOLO label file refreshed", labels.is_file() and labels.read_text().startswith("0 "))
ctrl.apply_annotation_changes(paths[1], [], [other[0].id])
check("other image: removal written to disk", ctrl.annotations_for(paths[1]) == [])
ctrl.apply_annotation_changes(paths[1], [], [])
check("empty change is a no-op", ctrl.undo_stack.count() == depth + 1)


# ═════════════════════════════════════════════════════════════════════════════
section("5. Runner (fake backend)")
# ═════════════════════════════════════════════════════════════════════════════
class FakeBackend:
    """request() answers asynchronously from a per-image script."""
    def __init__(self, script):
        self.script, self.requests, self.cancelled, self._n = script, [], [], 0
    def request(self, method, params=None, on_done=None, on_progress=None):
        self._n += 1
        rid = self._n
        self.requests.append(params)
        answer = self.script(params["image"])
        QTimer.singleShot(5, lambda: on_done(Reply(rid, *answer)))
        return rid
    def cancel(self, rid):
        self.cancelled.append(rid)

def one_box(image):
    return (res("detect", [det()]), None)

def run(runner, images, settings, mapping, existing=None, timeout=20):
    done = []
    runner.finished.connect(done.append)
    runner.start(images, settings, mapping, existing)
    wait(lambda: done, timeout)
    runner.finished.disconnect(done.append)
    return done[0] if done else None

st = PrelabelSettings(model="m.pt")
fake = FakeBackend(one_box)
runner = PrelabelRunner(fake, ctrl)
progress = []
runner.progress.connect(lambda d, t, n: progress.append((d, t)))
changed = []
ctrl.project_changed.connect(lambda p: changed.append(p))
s = run(runner, paths, st, {0: car})        # img0 (current) has annotations -> skipped
check("skip mode: annotated image left alone, others processed",
      s.skipped_existing == 1 and s.processed == 3 and s.added == 3)
check("only mapped model classes are requested", fake.requests[0]["classes"] == [0])
check("progress reaches total", progress[-1] == (4, 4))
check("other images changed -> project_changed refreshes the marks", len(changed) >= 1)
check("results are on disk", all(len(ctrl.annotations_for(p)) == 1 for p in paths[1:]))

manual2 = Annotation.new(car.id, AnnotationType.BBOX, {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1})
ctrl.apply_annotation_changes(paths[2], [manual2])
s = run(runner, paths[1:3], st, {0: car}, existing=EXISTING_REPLACE)
anns2 = ctrl.annotations_for(paths[2])
check("replace mode: earlier model annotations replaced", s.replaced == 2 and s.added == 2)
check("replace mode: manual annotations kept",
      manual2.id in [a.id for a in anns2] and sum(is_model_annotation(a) for a in anns2) == 1)
s = run(runner, [paths[3]], st, {0: car}, existing=EXISTING_ADD)
check("add mode: added on top", len(ctrl.annotations_for(paths[3])) == 2)

bad = FakeBackend(lambda img: (None, {"type": protocol.BAD_REQUEST, "message": "cannot read image"})
                  if img == paths[2] else one_box(img))
s = run(PrelabelRunner(bad, ctrl), paths[1:4], st, {0: car}, existing=EXISTING_ADD)
check("a bad image is counted, the run goes on",
      s.failed == 1 and s.processed == 2 and "cannot read image" in s.errors[0])
dead = FakeBackend(lambda img: (None, {"type": BACKEND_EXITED, "message": "ML backend exited"}))
s = run(PrelabelRunner(dead, ctrl), paths[1:4], st, {0: car}, existing=EXISTING_ADD)
check("backend gone -> the run stops with the reason",
      s.fatal == "ML backend exited" and s.processed == 0 and len(dead.requests) == 1)
s = run(PrelabelRunner(fake, ctrl), paths, st, {0: None})
check("nothing mapped -> clear message, no requests", "No model class" in s.fatal)

slow = FakeBackend(one_box)
r_slow = PrelabelRunner(slow, ctrl)
done = []
r_slow.finished.connect(done.append)
r_slow.progress.connect(lambda d, t, n: r_slow.cancel() if d == 1 else None)
r_slow.start(paths[1:4], st, {0: car}, EXISTING_ADD)
wait(lambda: done)
check("cancel stops after the current image, keeps its result",
      done[0].cancelled and done[0].processed == 1 and len(slow.requests) == 1)

before = ctrl.undo_stack.count()
s = run(runner, [paths[0]], st, {0: car}, existing=EXISTING_REPLACE)
check("current image via the runner is one undo step", ctrl.undo_stack.count() == before + 1)


# ═════════════════════════════════════════════════════════════════════════════
section("6. Creating classes from a model")
# ═════════════════════════════════════════════════════════════════════════════
changed.clear()
n0 = len(proj.classes)
created = create_classes(ctrl, [("person", "keypoints"), ("dog", "bbox"), ("cat", "bbox")], kpt_count=17)
check("classes added with their types",
      len(proj.classes) == n0 + 3 and [c.annotation_type for c in created] == ["keypoints", "bbox", "bbox"])
check("one project_changed for the whole batch", len(changed) == 1)
check("pose class from a 17-point model gets the COCO skeleton",
      [k.name for k in created[0].skeleton][:3] == ["nose", "left_eye", "right_eye"]
      and 1 in created[0].skeleton[0].edges)
check("other point counts get kp0..kpN", [k.name for k in make_skeleton(4)] == ["kp0", "kp1", "kp2", "kp3"])
reopened = ProjectController()
reopened.open_project(proj.project_path)
check("new classes saved with the project",
      [c.name for c in reopened.project.classes][-3:] == ["person", "dog", "cat"])

pctrl = ProjectController()
pproj = pctrl.create_project("ph", _TMP / "ph.annproj")
ph = unused_placeholder(pctrl)
check("a new project's empty 'object' class is a placeholder", ph is not None and ph.name == "object")
check("not a placeholder when a model class is mapped to it", unused_placeholder(pctrl, {ph.id}) is None)
created = create_classes(pctrl, [("person", "polygon"), ("car", "polygon")], replace=ph)
check("placeholder replaced, new ids start from 0 (YOLO class ids)",
      [(c.id, c.name) for c in pproj.classes] == [(0, "person"), (1, "car")])
check("no placeholder once the project has real classes", unused_placeholder(pctrl) is None)
qctrl = ProjectController()
qproj = qctrl.create_project("ph2", _TMP / "ph2.annproj")
qp = _TMP / "ph2.png"
Image.new("RGB", (W, H)).save(qp)
qctrl.add_images_from_paths([str(qp)])
qctrl.set_image(qproj.images[0].path)
qctrl.add_annotation(Annotation.new(qproj.classes[0].id, AnnotationType.BBOX,
                                    {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}))
check("'object' with annotations is kept", unused_placeholder(qctrl) is None)
rctrl = ProjectController()
rproj = rctrl.create_project("ph3", _TMP / "ph3.annproj")
rproj.classes[0].name = "tree"
check("a renamed only class is kept", unused_placeholder(rctrl) is None)


# ═════════════════════════════════════════════════════════════════════════════
section("7. Settings persistence")
# ═════════════════════════════════════════════════════════════════════════════
st = PrelabelSettings(model=str(_TMP / "m.pt"), conf=0.4, existing=EXISTING_REPLACE, scope="val")
st.set_mapping(st.model, {0: 3, 1: None})
st.save(proj.project_path)
back = PrelabelSettings.load(proj.project_path)
check("settings round-trip", back.conf == 0.4 and back.existing == EXISTING_REPLACE and back.scope == "val")
check("mapping round-trip with None", back.mapping_for(str(_TMP / "m.pt")) == {0: 3, 1: None})
check("unknown model -> no mapping", back.mapping_for(str(_TMP / "other.pt")) is None)
(proj.project_path / "ml_prelabel.json").write_text("{broken", encoding="utf-8")
check("broken file -> defaults", PrelabelSettings.load(proj.project_path).conf == 0.25)
check("no project -> defaults", PrelabelSettings.load(None).existing == EXISTING_SKIP)


# ═════════════════════════════════════════════════════════════════════════════
section("8. UI: dialog, Ctrl+L, remove, panel marker")
# ═════════════════════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import QDialog, QMessageBox
from annotator.ml.prelabel_dialog import PrelabelDialog, summary_text

class FakeModelBackend(FakeBackend):
    """Also answers yolo.load_model: a detector with car / person / truck."""
    def request(self, method, params=None, on_done=None, on_progress=None):
        if method == "yolo.load_model":
            self._n += 1
            rid = self._n
            info = {"path": params["path"], "task": "detect", "kpt_shape": None, "cached": False,
                    "load_seconds": 0.1, "device": "cpu",
                    "classes": [{"id": 0, "name": "car"}, {"id": 1, "name": "Person"},
                                {"id": 2, "name": "truck"}]}
            QTimer.singleShot(5, lambda: on_done(Reply(rid, info)))
            return rid
        return super().request(method, params, on_done, on_progress)

def three_boxes(image):
    return (res("detect", [det(cls=0), det(cls=1, box=(100, 10, 140, 90)),
                           det(cls=2, box=(150, 20, 190, 60))]), None)

uctrl = ProjectController()
uproj = uctrl.create_project("ui", _TMP / "ui.annproj")
ucar = uproj.classes[0]
ucar.name, ucar.annotation_type = "car", "bbox"
upaths = []
for i in range(3):
    p = _TMP / f"ui{i}.png"
    Image.new("RGB", (W, H)).save(p)
    upaths.append(str(p))
uctrl.add_images_from_paths(upaths)
upaths = [r.path for r in uproj.images]
uproj.images[2].split = "val"
uctrl.set_image(upaths[0])
model_file = _TMP / "det.pt"
model_file.write_bytes(b"x")

fake_ui = FakeModelBackend(three_boxes)
urunner = PrelabelRunner(fake_ui, uctrl)
dlg = PrelabelDialog(fake_ui, urunner, uctrl, lambda: list(upaths))
dlg._model_edit.setText(str(model_file))
dlg._load_model()
check("model loads into the mapping table", wait(lambda: dlg._table.rowCount() == 3, 5))
combo = lambda r: dlg._table.cellWidget(r, 1)
check("same name is mapped automatically", combo(0).currentData() == ucar.id)
check("other classes start as skip", combo(1).currentData() is None and combo(2).currentData() is None)
check("mapped counter", "1" in dlg._mapped_lbl.text() and "3" in dlg._mapped_lbl.text())
check("count of images in scope", "3" in dlg._count_lbl.text())
dlg._scope.setCurrentIndex(dlg._scope.findData("val"))
check("split scope narrows the images", dlg._target_images() == [upaths[2]])
dlg._scope.setCurrentIndex(0)
dlg._filter.setText("TRU")
check("search hides the other model classes",
      [dlg._table.isRowHidden(r) for r in range(3)] == [True, True, False])
n_classes = len(uproj.classes)
dlg._create_selected()
check("'create selected' with nothing marked only explains",
      "+" in dlg._result.text() and len(uproj.classes) == n_classes)
combo(2).setCurrentIndex(combo(2).findData("__create__"))   # the user picks "+ new class"
check("'+ new class' only marks the row", len(uproj.classes) == n_classes
      and "1" in dlg._mapped_lbl.text().split("·")[-1])
check("a class mapped in one row moves under 'already chosen' in the others",
      [combo(1).itemData(i) for i in range(combo(1).count())].index(ucar.id)
      > [combo(1).itemData(i) for i in range(combo(1).count())].index("__header__"))
check("... but stays first-level in its own row",
      "__header__" not in [combo(0).itemData(i) for i in range(combo(0).count())])
dlg._create_selected()
check("'create selected' creates the marked classes",
      [c.name for c in uproj.classes][n_classes:] == ["truck"])
check("created class is mapped at once, filter kept",
      uproj.get_class(combo(2).currentData()).name == "truck" and dlg._table.isRowHidden(0))
dlg._filter.clear()
dlg._create_missing()
names = [c.name for c in uproj.classes]
check("'create missing' creates the rest right away",
      names.count("Person") == 1 and names.count("truck") == 1
      and all(combo(r).currentData() is not None for r in range(3)))
check("missing classes created with the natural type",
      all(c.annotation_type == "bbox" for c in uproj.classes))
dlg._create_missing()
check("nothing left to create -> no new classes", len(uproj.classes) == len(names))
dlg._run_dataset()                                   # existing = skip; all images are empty
check("dataset run finishes", wait(lambda: not urunner.running and dlg._stop_btn.isHidden(), 10))
check("every image got 3 boxes", all(len(uctrl.annotations_for(p)) == 3 for p in upaths))
check("result line shows the summary", "3" in dlg._result.text() and "9" in dlg._result.text())
saved = PrelabelSettings.load(uproj.project_path).mapping_for(str(model_file))
check("mapping saved with the new class ids", saved and None not in saved.values())
n_before = len(uctrl.current_annotations)
dlg._run_current()                                   # skip would do nothing -> replace
wait(lambda: not urunner.running and dlg._stop_btn.isHidden(), 10)
check("'Current image' replaces this image's model annotations", len(uctrl.current_annotations) == n_before)
slow_ui = FakeModelBackend(three_boxes)
r2 = PrelabelRunner(slow_ui, uctrl)
dlg2 = PrelabelDialog(slow_ui, r2, uctrl, lambda: list(upaths))
dlg2._model_edit.setText(str(model_file))
dlg2._load_model()
wait(lambda: dlg2._table.rowCount() == 3, 5)
dlg2._existing.buttons()[2].setChecked(True)          # add
dlg2._run_dataset()
dlg2.done(QDialog.DialogCode.Rejected)               # close while running
check("closing the dialog stops the run", not r2.running and r2.summary.cancelled)
dlg.done(QDialog.DialogCode.Rejected)

nctrl = ProjectController()
nproj = nctrl.create_project("fresh", _TMP / "fresh.annproj")   # only the default "object"
dlg3 = PrelabelDialog(fake_ui, PrelabelRunner(fake_ui, nctrl), nctrl, lambda: [])
dlg3._model_edit.setText(str(model_file))
dlg3._load_model()
wait(lambda: dlg3._table.rowCount() == 3, 5)
for r in (1, 2):                                     # mark Person and truck
    c3 = dlg3._table.cellWidget(r, 1)
    c3.setCurrentIndex(c3.findData("__create__"))
check("marked rows are not created yet", [c.name for c in nproj.classes] == ["object"])
dlg3._create_selected()
check("marked classes replace the empty default class, ids from 0",
      [(c.id, c.name) for c in nproj.classes] == [(0, "Person"), (1, "truck")]
      and dlg3._table.cellWidget(1, 1).currentData() == 0 and "object" in dlg3._result.text())
dlg3.done(QDialog.DialogCode.Rejected)

mctrl = ProjectController()
mproj = mctrl.create_project("marked", _TMP / "marked.annproj")
mp = _TMP / "marked.png"
Image.new("RGB", (W, H)).save(mp)
mctrl.add_images_from_paths([str(mp)])
dlg4 = PrelabelDialog(fake_ui, PrelabelRunner(fake_ui, mctrl), mctrl, lambda: [mproj.images[0].path])
dlg4._model_edit.setText(str(model_file))
dlg4._load_model()
wait(lambda: dlg4._table.rowCount() == 3, 5)
c4 = dlg4._table.cellWidget(0, 1)
c4.setCurrentIndex(c4.findData("__create__"))
dlg4._run_dataset()                                  # marked but never created -> created on run
wait(lambda: not dlg4._runner.running and dlg4._stop_btn.isHidden(), 10)
check("classes still marked are created when the run starts",
      [c.name for c in mproj.classes] == ["car"]
      and len(mctrl.annotations_for(mproj.images[0].path)) == 1)
dlg4.done(QDialog.DialogCode.Rejected)

text, bad = summary_text(PrelabelSummary(fatal="boom"))
check("summary of a failed run is an error", bad and "boom" in text)

# annotations panel marker (generic: shows meta.source == "model")
from annotator.ui.panels.annotations_panel import AnnotationsPanel
panel = AnnotationsPanel()
panel.load_project(uproj)
model_ann = next(a for a in uctrl.current_annotations if is_model_annotation(a))
manual3 = Annotation.new(ucar.id, AnnotationType.BBOX, {"x": 0, "y": 0, "w": 0.1, "h": 0.1})
panel.refresh([model_ann, manual3])
check("panel marks model annotations with confidence", "🤖 0.90" in panel._list.item(0).text())
check("panel tooltip names the model", "det.pt" in panel._list.item(0).toolTip()
      or "m.pt" in panel._list.item(0).toolTip() or "model:" in panel._list.item(0).toolTip())
check("manual annotations have no marker", "🤖" not in panel._list.item(1).text())

# main window: Ctrl+L and Remove model annotations
from annotator.app_settings import app_settings
app_settings().setValue("user_name", "Tester")
import annotator.ml.extension as ext
import annotator.ui.main_window as mw
win = mw.MainWindow()
win.controller.open_project(uproj.project_path)
wctrl = win.controller
wctrl.set_image(upaths[1])
fake_w = FakeModelBackend(one_box)
win._ml.runner = PrelabelRunner(fake_w, wctrl, win._ml)
win._ml.runner.finished.connect(win._ml._on_quick_finished)
check("window exposes the allowed images", win.allowed_image_paths() == upaths)
before = len(wctrl.current_annotations)
win._ml._act_image.trigger()                          # Ctrl+L
check("Ctrl+L pre-labels the current image",
      wait(lambda: "+" in win.statusBar().currentMessage(), 10))
check("Ctrl+L replaced earlier model annotations",
      sum(is_model_annotation(a) for a in wctrl.current_annotations) == 1
      and len(wctrl.current_annotations) <= before)
check("Ctrl+L is one undo step", wctrl.undo_stack.canUndo())
check("Ctrl+L shortcut is set", win._ml._act_image.shortcut().toString() == "Ctrl+L")

class _Btn:
    def setEnabled(self, v):
        pass

class _Box:
    Icon, ButtonRole, StandardButton = QMessageBox.Icon, QMessageBox.ButtonRole, QMessageBox.StandardButton
    choice = 1
    def __init__(self, *a, **k):
        self._b = []
    def addButton(self, *a):
        self._b.append(_Btn())
        return self._b[-1]
    def exec(self):
        return 0
    def clickedButton(self):
        return self._b[_Box.choice]
    @staticmethod
    def information(*a):
        pass

_orig_box = ext.QMessageBox
ext.QMessageBox = _Box
_Box.choice = 0                                      # this image
manual4 = Annotation.new(ucar.id, AnnotationType.BBOX, {"x": 0, "y": 0, "w": 0.1, "h": 0.1})
wctrl.add_annotation(manual4)
win._ml.remove_model_annotations()
check("remove (this image): only model annotations go",
      [a.id for a in wctrl.current_annotations if not is_model_annotation(a)]
      == [a.id for a in wctrl.current_annotations] and manual4.id in [a.id for a in wctrl.current_annotations])
_Box.choice = 1                                      # all images
win._ml.remove_model_annotations()
check("remove (all images): none left anywhere",
      not any(is_model_annotation(a) for p in upaths for a in wctrl.annotations_for(p)))
ext.QMessageBox = _orig_box
win.close()


# ═════════════════════════════════════════════════════════════════════════════
section("9. Real model (optional)")
# ═════════════════════════════════════════════════════════════════════════════
ml_py, seg_model = os.environ.get("ML_TEST_PYTHON"), os.environ.get("ML_TEST_SEG_MODEL")
if ml_py and seg_model:
    from annotator.ml.client import MLBackend
    bus = Path(ml_py).parent / "Lib" / "site-packages" / "ultralytics" / "assets" / "bus.jpg"
    rctrl = ProjectController()
    rproj = rctrl.create_project("real", _TMP / "real.annproj")
    person = rproj.classes[0]
    person.name, person.annotation_type = "person", "polygon"
    busc = rproj.add_class("bus")
    busc.annotation_type = "mask"
    rctrl.add_images_from_paths([str(bus)])
    be = MLBackend(python=ml_py)
    s = run(PrelabelRunner(be, rctrl), [rproj.images[0].path],
            PrelabelSettings(model=seg_model), {0: person, 5: busc}, timeout=180)
    anns = rctrl.annotations_for(rproj.images[0].path)
    kinds = {a.ann_type for a in anns}
    check("real seg model: people as polygons, the bus as a mask",
          AnnotationType.SEGMENT in kinds and AnnotationType.MASK in kinds)
    print(f"      {s.added} annotations in {s.seconds} s; skipped: {s.skip_reasons}")
    be.stop()
else:
    print("  (skipped: set ML_TEST_PYTHON and ML_TEST_SEG_MODEL)")


print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
