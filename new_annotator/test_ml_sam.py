"""
SAM tool tests (phase 7-C): tool registration, prompts, request merging,
preview, accept into every class type, errors.
Run: .venv/Scripts/python test_ml_sam.py

No GPU needed — the tool talks to a fake backend. Optional real run
(skipped unless both are set):
    ML_TEST_PYTHON=C:/miniconda3/envs/yolo_hard/python.exe
    ML_TEST_SAM_MODEL=<path to sam2.1_b.pt>
"""
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")

from PyQt6.QtCore import QEventLoop, QPointF, Qt, QTimer
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


def wait(pred, timeout=10.0) -> bool:
    end = time.monotonic() + timeout
    loop = QEventLoop()
    while not pred():
        if time.monotonic() > end:
            return False
        QTimer.singleShot(10, loop.quit)
        loop.exec()
    return True


from annotator.app_settings import app_settings
app_settings().setValue("user_name", "Tester")

from annotator.domain.annotation import AnnotationType
from annotator.exporters.yolo_obb import _format_obb
from annotator.ml import config
from annotator.ml.client import Reply
import annotator.ui.main_window as mw
from annotator.controller.project_controller import ProjectController

W, H = 200, 100
LEFT, RIGHT = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
NOMOD = Qt.KeyboardModifier.NoModifier


def rotated_rect(cx, cy, w, h, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [[cx + c * dx - s * dy, cy + s * dx + c * dy]
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


SHAPE = rotated_rect(100, 50, 60, 20, 30)


class FakeSam:
    """Answers sam.* like the real backend, after `delay` ms."""
    def __init__(self, delay=30):
        self.requests, self._n, self.delay, self.fail = [], 0, delay, None

    def request(self, method, params=None, on_done=None, on_progress=None):
        self._n += 1
        rid = self._n
        self.requests.append((method, params))
        if self.fail:
            answer = (None, {"type": "exception", "message": self.fail})
        elif method == "sam.set_image":
            answer = ({"width": W, "height": H, "embed_ms": 1.0}, None)
        else:
            xs = [x for x, _ in SHAPE]
            ys = [y for _, y in SHAPE]
            answer = ({"width": W, "height": H, "ms": 3.0, "embed_ms": 0.0, "score": 0.93,
                       "box": [min(xs), min(ys), max(xs), max(ys)], "polygons": [SHAPE]}, None)
        QTimer.singleShot(self.delay, lambda: on_done and on_done(Reply(rid, *answer)))
        return rid

    def predicts(self):
        return [p for m, p in self.requests if m == "sam.predict"]


# ── project: one non-square image, a class of every type ─────────────────────
img = _TMP / "wide.png"
Image.new("RGB", (W, H), (40, 40, 40)).save(img)
model_file = _TMP / "sam2.1_b.pt"
model_file.write_bytes(b"x")
config.set_sam_model(str(model_file))

win = mw.MainWindow()
ctrl = win.controller
proj = ctrl.create_project("sam", _TMP / "sam.annproj")
kinds = ["polygon", "mask", "bbox", "obb", "point", "keypoints", "semantic"]
proj.classes[0].name, proj.classes[0].annotation_type = "polygon", "polygon"
for k in kinds[1:]:
    ctrl.add_class(k).annotation_type = k
ctrl.save_project()
ctrl.project_changed.emit(proj)
cls = {c.annotation_type: c for c in proj.classes}
ctrl.add_images_from_paths([str(img)])
ctrl.set_image(proj.images[0].path)
tool = win._ml.sam_tool
fake = FakeSam()
tool._backend = fake

# ═════════════════════════════════════════════════════════════════════════════
section("1. Registration")
# ═════════════════════════════════════════════════════════════════════════════
act = win._tool_act_map.get("sam")
check("SAM tool registered in the window", win._tools.get("sam") is tool)
check("toolbar button with shortcut I", act is not None and act.shortcut().toString() == "I"
      and win._toolbar.widgetForAction(act) is not None)
check("Tools menu entry", "sam" in win._menu_tool_acts)
check("register_tool refuses a taken name", win.register_tool(tool, "again") is None)
check("ML menu has the SAM entry", win._ml._act_sam.text() != "")

win._ml.activate_sam()
check("ML menu entry activates the tool", win._scene.active_tool is tool and act.isChecked())
check("image is encoded ahead of the first click",
      wait(lambda: any(m == "sam.set_image" for m, _ in fake.requests))
      and fake.requests[0][1] == {"model": str(model_file), "image": proj.images[0].path})
win._classes_panel.select_class_by_id(cls["mask"].id)
check("choosing a class does not switch away from SAM", win._scene.active_tool is tool)

# ═════════════════════════════════════════════════════════════════════════════
section("2. Prompts and request merging")
# ═════════════════════════════════════════════════════════════════════════════
win._classes_panel.select_class_by_id(cls["polygon"].id)


def click(x, y, button=LEFT):
    tool.on_press(QPointF(x, y), NOMOD, button)
    tool.on_release(QPointF(x, y), NOMOD, button)


def drag(x1, y1, x2, y2):
    tool.on_press(QPointF(x1, y1), NOMOD, LEFT)
    tool.on_move(QPointF(x2, y2), NOMOD)
    tool.on_release(QPointF(x2, y2), NOMOD, LEFT)


fake.requests.clear()
click(20, 20, RIGHT)                                  # right click first: no object yet
check("right click alone sends nothing and explains",
      not fake.predicts() and tool.prompts["points"] == [(20.0, 20.0, 0)]
      and "left" in win.statusBar().currentMessage())
tool.on_key_press(Qt.Key.Key_Return, NOMOD)
check("... and Enter accepts nothing", not ctrl.current_annotations)
tool.on_key_press(Qt.Key.Key_Escape, NOMOD)
click(100, 50)
click(20, 20, RIGHT)                                  # while the first is in flight
drag(60, 20, 140, 80)
check("one request in flight; later clicks wait", len(fake.predicts()) == 1)
check("first request: one positive point",
      fake.predicts()[0]["points"] == [[100.0, 50.0]] and fake.predicts()[0]["labels"] == [1])
check("then ONE merged request with everything", wait(lambda: len(fake.predicts()) == 2)
      and fake.predicts()[1]["labels"] == [1, 0] and fake.predicts()[1]["box"] == [60.0, 20.0, 140.0, 80.0])
wait(lambda: tool._result is not None and tool._pending is None)
check("mask preview + 2 point markers + box drawn", len(tool._items) == 4)
check("status shows the score", "0.93" in win.statusBar().currentMessage())
click(500, 500)
check("click outside the image is ignored", len(tool.prompts["points"]) == 2)

tool.undo_prompt()                                    # the box
check("Backspace undoes the box", tool.prompts["box"] is None and len(tool.prompts["points"]) == 2)
tool.on_key_press(Qt.Key.Key_Backspace, NOMOD)
check("... then the last point", tool.prompts["points"] == [(100.0, 50.0, 1)])
wait(lambda: tool._pending is None and not tool._dirty)
tool.on_key_press(Qt.Key.Key_Escape, NOMOD)
check("Esc clears prompts and preview", tool.prompts == {"points": [], "box": None}
      and not tool._items and tool._result is None)

# ═════════════════════════════════════════════════════════════════════════════
section("3. Accept into each class type")
# ═════════════════════════════════════════════════════════════════════════════


def label_as(kind):
    win._classes_panel.select_class_by_id(cls[kind].id)
    click(100, 50)
    wait(lambda: tool._result is not None and tool._pending is None)
    n = len(ctrl.current_annotations)
    tool.on_key_press(Qt.Key.Key_Return, NOMOD)
    new = ctrl.current_annotations[n:]
    return new[0] if len(new) == 1 else None


a = label_as("polygon")
check("polygon class -> polygon of the mask outline",
      a is not None and a.ann_type == AnnotationType.SEGMENT and len(a.data["points"]) == 4)
check("written as a manual annotation by the SAM tool (no robot mark, no confidence)",
      a.meta["source"] == "manual" and a.meta["tool"] == "sam" and "confidence" not in a.meta)
check("accept clears the prompts", tool.prompts["points"] == [] and not tool._items)
check("status names the class", "polygon" in win.statusBar().currentMessage())
n = len(ctrl.current_annotations)
ctrl.undo_stack.undo()
check("one Ctrl+Z removes it", len(ctrl.current_annotations) == n - 1)

a = label_as("mask")
check("mask class -> brush mask with a PNG",
      a is not None and a.ann_type == AnnotationType.MASK
      and (proj.project_path / a.data["mask_png_path"]).is_file())
a = label_as("bbox")
xs, ys = [p[0] for p in SHAPE], [p[1] for p in SHAPE]
check("bbox class -> box around the mask",
      a is not None and a.ann_type == AnnotationType.BBOX
      and abs(a.data["x"] * W - min(xs)) < 1 and abs((a.data["x"] + a.data["w"]) * W - max(xs)) < 1)
a = label_as("obb")
corners = [] if a is None else _format_obb(a, (W, H)).split()[1:]
px = [(float(corners[i]) * W, float(corners[i + 1]) * H) for i in range(0, len(corners), 2)]
check("obb class -> the tight ROTATED box (corners match the shape)",
      a is not None and a.ann_type == AnnotationType.OBB and len(px) == 4
      and all(min(math.dist(p, q) for q in SHAPE) < 1.0 for p in px))
a = label_as("point")
check("point class -> centre of the mask box",
      a is not None and a.ann_type == AnnotationType.POINT and abs(a.data["x"] * W - 100) < 1)

for kind in ("keypoints", "semantic"):
    win._classes_panel.select_class_by_id(cls[kind].id)
    fake.requests.clear()
    click(100, 50)
    check(f"{kind} class: no request, the status explains",
          not fake.predicts() and kind in win.statusBar().currentMessage())

# ═════════════════════════════════════════════════════════════════════════════
section("4. Images, errors, no model")
# ═════════════════════════════════════════════════════════════════════════════
win._classes_panel.select_class_by_id(cls["polygon"].id)
click(100, 50)
img2 = _TMP / "second.png"
Image.new("RGB", (W, H)).save(img2)
ctrl.add_images_from_paths([str(img2)])
fake.requests.clear()
second = next(r.path for r in proj.images if r.path.endswith("second.png"))
ctrl.set_image(second)
check("another image: prompts cleared, the new image encoded",
      tool.prompts["points"] == [] and wait(lambda: any(
          m == "sam.set_image" and p["image"] == second for m, p in fake.requests)))
wait(lambda: tool._pending is None)
check("a late answer for the old image draws nothing", tool._result is None and not tool._items)

tool.on_key_press(Qt.Key.Key_Return, NOMOD)
check("Enter with nothing to accept only explains", "SAM" in win.statusBar().currentMessage())

fake.fail = "CUDA out of memory"
click(100, 50)
check("backend error -> shown in the status bar, nothing to accept",
      wait(lambda: "CUDA out of memory" in win.statusBar().currentMessage())
      and tool._result is None)
fake.fail = None
tool.on_key_press(Qt.Key.Key_Escape, NOMOD)

config.set_sam_model("")
asked = []
tool._ask_model = lambda: asked.append(1) or ""
fake.requests.clear()
click(100, 50)
check("no SAM model: asks for the file, sends nothing",
      asked == [1] and not fake.predicts() and "ML" in win.statusBar().currentMessage())
tool._ask_model = lambda: str(model_file)
tool.on_key_press(Qt.Key.Key_Escape, NOMOD)
click(100, 50)
check("model chosen in the dialog -> the request goes out", wait(lambda: len(fake.predicts()) == 1))
wait(lambda: tool._pending is None)

tool.on_key_press(Qt.Key.Key_Return, NOMOD)
n = len(ctrl.current_annotations)
win._annotations_panel._list.setCurrentRow(n - 1)              # the user picks it in the panel
win._on_delete_key()                                  # Delete with SAM (not Select) active
check("Delete removes the annotation selected in the panel with any tool",
      len(ctrl.current_annotations) == n - 1)

win._activate_tool("select")
check("switching tools removes the preview", not tool._items and tool._scene is None)

# ═════════════════════════════════════════════════════════════════════════════
section("5. Real SAM model (optional)")
# ═════════════════════════════════════════════════════════════════════════════
ml_py, sam_model = os.environ.get("ML_TEST_PYTHON"), os.environ.get("ML_TEST_SAM_MODEL")
if ml_py and sam_model:
    from annotator.ml.client import MLBackend
    bus = _TMP / "bus.jpg"
    shutil.copy(Path(ml_py).parent / "Lib" / "site-packages" / "ultralytics" / "assets" / "bus.jpg", bus)
    be = MLBackend(python=ml_py)
    out = {}
    be.request("sam.predict", {"model": sam_model, "image": str(bus),
                               "points": [[400, 500]], "labels": [1]},
               on_done=lambda r: out.setdefault("first", r))
    wait(lambda: "first" in out, 180)
    be.request("sam.predict", {"model": sam_model, "image": str(bus), "box": [50, 230, 800, 750]},
               on_done=lambda r: out.setdefault("box", r))
    wait(lambda: "box" in out, 60)
    r1, r2 = out.get("first"), out.get("box")
    check("real SAM: a click on the bus gives one big mask",
          r1 is not None and r1.ok and r1.result["score"] > 0.5 and r1.result["polygons"]
          and (r1.result["box"][2] - r1.result["box"][0]) > 500)
    check("real SAM: the same image is not encoded again",
          r2 is not None and r2.ok and r2.result["embed_ms"] == 0.0)
    if r1 is not None and r1.ok:
        print(f"      first click {r1.result['ms']} ms (+{r1.result['embed_ms']} ms encode), "
              f"box {r2.result['ms'] if r2 and r2.ok else '?'} ms")
    be.stop()
else:
    print("  (skipped: set ML_TEST_PYTHON and ML_TEST_SAM_MODEL)")

# ═════════════════════════════════════════════════════════════════════════════
section("6. Boxes -> outlines: helpers")
# ═════════════════════════════════════════════════════════════════════════════
from annotator.domain.annotation import Annotation
from annotator.ml.convert import is_model_annotation
from annotator.ml.prelabel import PrelabelRunner
from annotator.ml.prelabel_settings import EXISTING_ADD, PrelabelSettings
from annotator.ml.sam_boxes import FROM_BOX, SamBoxRunner, boxes_to_outline, pixel_box
from annotator.ml.sam_boxes_dialog import SamBoxesDialog, summary_text as box_summary

bx = Annotation.new(0, AnnotationType.BBOX, {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4})
check("bbox -> pixel box", [round(v, 3) for v in pixel_box(bx, W, H)] == [20.0, 20.0, 80.0, 60.0])
ob = Annotation.new(0, AnnotationType.OBB, {"cx": 0.5, "cy": 0.5, "w": 0.2, "h": 0.2, "angle_deg": 90})
check("rotated OBB -> box around its corners (pixels)",
      [round(v, 3) for v in pixel_box(ob, W, H)] == [90.0, 30.0, 110.0, 70.0])
done = Annotation.new(1, AnnotationType.SEGMENT, {"points": [[0, 0], [1, 0], [1, 1]]})
done.meta[FROM_BOX] = bx.id
other = Annotation.new(0, AnnotationType.BBOX, {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1})
check("boxes already outlined into the target class are skipped",
      boxes_to_outline([bx, done, other, ob], 0, 1) == [other, ob])
check("... but not for another target class", boxes_to_outline([bx, done, other, ob], 0, 2) == [bx, other, ob])


class FakeBoxes(FakeSam):
    """sam.boxes: a polygon inside every box (none for boxes narrower than 5 px);
    yolo.predict: a detector with two boxes (class 0 and 1)."""
    def request(self, method, params=None, on_done=None, on_progress=None):
        if method == "sam.boxes":
            self._n += 1
            rid = self._n
            self.requests.append((method, params))
            res = []
            for x1, y1, x2, y2 in params["boxes"]:
                if x2 - x1 < 5:
                    res.append({"score": 0.0, "box": None, "polygons": []})
                    continue
                poly = [[x1 + 8, y1], [x2, y1 + 10], [x2 - 8, y2], [x1 + 8, y2],
                        [x1, (y1 + y2) / 2]]                      # a pentagon
                res.append({"score": 0.88, "box": [x1, y1, x2, y2], "polygons": [poly]})
            answer = ({"width": W, "height": H, "ms": 5.0, "embed_ms": 0.0, "results": res}, None)
            QTimer.singleShot(self.delay, lambda: on_done(Reply(rid, *answer)))
            return rid
        if method == "yolo.predict":
            self._n += 1
            rid = self._n
            self.requests.append((method, params))
            answer = ({"width": W, "height": H, "task": "detect", "ms": 1.0, "classification": [],
                       "detections": [{"cls": 0, "conf": 0.9, "box": [20, 20, 80, 60]},
                                      {"cls": 1, "conf": 0.8, "box": [120, 10, 180, 90]}]}, None)
            QTimer.singleShot(self.delay, lambda: on_done(Reply(rid, *answer)))
            return rid
        return super().request(method, params, on_done, on_progress)


bctrl = ProjectController()
bproj = bctrl.create_project("boxes", _TMP / "boxes.annproj")
car = bproj.classes[0]
car.name, car.annotation_type = "car", "bbox"
car_poly = bctrl.add_class("car_poly")
car_poly.annotation_type = "polygon"
car_rot = bctrl.add_class("car_rot")
car_rot.annotation_type = "obb"
bpaths = []
for i in range(2):
    p = _TMP / f"b{i}.png"
    Image.new("RGB", (W, H)).save(p)
    bpaths.append(str(p))
bctrl.add_images_from_paths(bpaths)
bpaths = [r.path for r in bproj.images]
bctrl.set_image(bpaths[0])
bctrl.add_annotation(Annotation.new(car.id, AnnotationType.BBOX, {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}))
bctrl.add_annotation(Annotation.new(car.id, AnnotationType.BBOX, {"x": 0.6, "y": 0.1, "w": 0.01, "h": 0.5}))
bctrl.apply_annotation_changes(bpaths[1], [Annotation.new(car.id, AnnotationType.BBOX,
                                                         {"x": 0.5, "y": 0.5, "w": 0.3, "h": 0.3})], [])

# ═════════════════════════════════════════════════════════════════════════════
section("7. Boxes -> outlines: runner")
# ═════════════════════════════════════════════════════════════════════════════
fb = FakeBoxes(delay=5)
brun = SamBoxRunner(fb, bctrl)
got = []
brun.finished.connect(got.append)


def run_boxes(target, delete=False, images=None):
    got.clear()
    brun.start(bpaths if images is None else images, car, target, str(model_file), delete_source=delete)
    wait(lambda: got)
    return got[0] if got else None


undo_before = bctrl.undo_stack.count()
s = run_boxes(car_poly)
new0 = [a for a in bctrl.current_annotations if a.class_id == car_poly.id]
check("every box outlined into the polygon class (the thin one: SAM found nothing)",
      s is not None and s.images == 2 and s.outlined == 2 and s.empty == 1)
check("outlines are model annotations that remember their box",
      len(new0) == 1 and is_model_annotation(new0[0]) and new0[0].meta["confidence"] == 0.88
      and new0[0].meta[FROM_BOX] in {a.id for a in bctrl.current_annotations if a.class_id == car.id}
      and new0[0].meta["tool"] == "sam")
check("the other image changed on disk", len([a for a in bctrl.annotations_for(bpaths[1])
                                              if a.class_id == car_poly.id]) == 1)
check("current image: one undo step", bctrl.undo_stack.count() == undo_before + 1)
s = run_boxes(car_poly)
check("second run: boxes already outlined are skipped", s.outlined == 0 and s.images == 1 and s.empty == 1)
s = run_boxes(car_rot, delete=True, images=[bpaths[1]])
rot = [a for a in bctrl.annotations_for(bpaths[1]) if a.class_id == car_rot.id]
check("OBB target: a rotated box; the outlined boxes deleted on request",
      s.outlined == 1 and s.removed == 1 and len(rot) == 1 and rot[0].ann_type == AnnotationType.OBB
      and not [a for a in bctrl.annotations_for(bpaths[1]) if a.class_id == car.id])
text, bad = box_summary(s)
check("summary text", not bad and "1" in text)
s = run_boxes(car_poly, images=[])
check("no images -> nothing to do", s.images == 0 and "" != box_summary(s)[0])
got.clear()
brun.start(bpaths, car, car_poly, str(_TMP / "missing.pt"))
wait(lambda: got)
check("no SAM model -> clear error", got and got[0].fatal and box_summary(got[0])[1])

# ═════════════════════════════════════════════════════════════════════════════
section("8. Boxes -> outlines: dialog and menu")
# ═════════════════════════════════════════════════════════════════════════════
config.set_sam_model(str(model_file))
dlg = SamBoxesDialog(fb, SamBoxRunner(fb, bctrl), bctrl, lambda: list(bpaths))
srcs = [dlg._source.itemData(i) for i in range(dlg._source.count())]
tgts = [dlg._target.itemData(i) for i in range(dlg._target.count())]
check("source list: bbox / obb classes", srcs == [car.id, car_rot.id])
check("target list: polygon / mask / obb classes + two '+ new class' entries",
      tgts[:2] == [car_poly.id, car_rot.id] and tgts[2:] == ["__new__:polygon", "__new__:mask"])
check("scope 'current image' counts one image", "1" in dlg._count_lbl.text())
check("default target: the class named after the boxes (car -> car_poly)",
      dlg._target.currentData() == car_poly.id)
dlg._source.setCurrentIndex(dlg._source.findData(car_rot.id))
check("... else '+ new class', never an unrelated class",
      dlg._target.currentData() == "__new__:polygon")
dlg._source.setCurrentIndex(dlg._source.findData(car.id))
dlg._target.setCurrentIndex(dlg._target.findData("__new__:mask"))
n_cls = len(bproj.classes)
dlg._run()
check("'+ new class' creates the target class and runs",
      wait(lambda: not dlg._runner.running and dlg._stop_btn.isHidden())
      and len(bproj.classes) == n_cls + 1 and bproj.classes[-1].name == "car_mask"
      and bproj.classes[-1].annotation_type == "mask")
check("masks added on the current image",
      any(a.ann_type == AnnotationType.MASK for a in bctrl.current_annotations)
      and "1" in dlg._result.text())
dlg.done(0)
check("ML menu has the command", win._ml._act_sam_boxes.text() != "")

# ═════════════════════════════════════════════════════════════════════════════
section("9. Pre-labelling: outlines via SAM")
# ═════════════════════════════════════════════════════════════════════════════
pctrl = ProjectController()
pproj = pctrl.create_project("refine", _TMP / "refine.annproj")
person = pproj.classes[0]
person.name, person.annotation_type = "person", "polygon"
truck = pctrl.add_class("truck")
truck.annotation_type = "bbox"
pimg = _TMP / "refine.png"
Image.new("RGB", (W, H)).save(pimg)
pctrl.add_images_from_paths([str(pimg)])
ppath = pproj.images[0].path
fr = FakeBoxes(delay=5)
prun = PrelabelRunner(fr, pctrl)
pdone = []
prun.finished.connect(pdone.append)
st = PrelabelSettings(model=str(model_file), sam_refine=True)
prun.start([ppath], st, {0: person, 1: truck}, EXISTING_ADD, sam_model=str(model_file))
wait(lambda: pdone)
anns = pctrl.annotations_for(ppath)
poly = next((a for a in anns if a.class_id == person.id), None)
check("detector box into a polygon class -> SAM outline (not a 4-point rectangle)",
      poly is not None and len(poly.data["points"]) == 5)
check("box class stays a plain box; only polygon/mask/obb boxes go to SAM",
      any(a.class_id == truck.id and a.ann_type == AnnotationType.BBOX for a in anns)
      and [p["boxes"] for m, p in fr.requests if m == "sam.boxes"] == [[[20.0, 20.0, 80.0, 60.0]]])
check("summary counts the SAM outlines", pdone and pdone[0].sam_outlined == 1)
pdone.clear()
prun.start([ppath], PrelabelSettings(model=str(model_file), sam_refine=True), {0: person},
           EXISTING_ADD, sam_model="")
wait(lambda: pdone)
check("outlines on but no SAM model -> clear error", pdone and "SAM" in pdone[0].fatal)
pdone.clear()
fr.requests.clear()
prun.start([ppath], PrelabelSettings(model=str(model_file)), {0: person}, EXISTING_ADD)
wait(lambda: pdone)
check("outlines off -> no SAM request", not [m for m, _ in fr.requests if m == "sam.boxes"])

# ═════════════════════════════════════════════════════════════════════════════
section("10. Real SAM boxes (optional)")
# ═════════════════════════════════════════════════════════════════════════════
if ml_py and sam_model:
    from annotator.ml.client import MLBackend
    be = MLBackend(python=ml_py)
    out = {}
    be.request("sam.boxes", {"model": sam_model, "image": str(bus),
                             "boxes": [[50, 230, 800, 750], [220, 400, 350, 900], [0, 0, 2, 2]]},
               on_done=lambda r: out.setdefault("r", r))
    wait(lambda: "r" in out, 180)
    r = out.get("r")
    areas = []
    if r is not None and r.ok:
        for res in r.result["results"]:
            b = res["box"]
            areas.append(0 if b is None else (b[2] - b[0]) * (b[3] - b[1]))
    check("real SAM boxes: one result per box, in order (bus > person)",
          r is not None and r.ok and len(areas) == 3 and areas[0] > areas[1] > 0)
    if r is not None and r.ok:
        print(f"      3 boxes in {r.result['ms']} ms (+{r.result['embed_ms']} ms encode)")
    be.stop()
else:
    print("  (skipped: set ML_TEST_PYTHON and ML_TEST_SAM_MODEL)")


win._ml.shutdown()
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
