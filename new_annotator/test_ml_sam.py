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

win._ml.shutdown()
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
