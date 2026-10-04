"""
Select tool editing tests — dragging handles of every editable type
Run: .venv/Scripts/python test_select.py
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
os.environ["ANNOTATOR_SETTINGS"] = str(Path(tempfile.mkdtemp()) / "settings.ini")

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from PIL import Image
from PyQt6.QtCore import QPointF, Qt

# ── helpers ───────────────────────────────────────────────────────────────────
_pass = _fail = 0

def check(name: str, ok: bool):
    global _pass, _fail
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {name}")
    if ok:
        _pass += 1
    else:
        _fail += 1

def section(title: str):
    print(f"\n--- {title} ---")

LB = Qt.MouseButton.LeftButton
NOMOD = Qt.KeyboardModifier.NoModifier

from annotator.controller.project_controller import ProjectController
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import SkeletonKeypoint
from annotator.tools.select_tool import SelectTool
from annotator.ui.canvas.scene import AnnotationScene

tmp = Path(tempfile.mkdtemp())
img = tmp / "img.png"
Image.new("RGB", (200, 100), (60, 60, 60)).save(img)          # W=200, H=100

ctrl = ProjectController()
proj = ctrl.create_project("sel", tmp / "sel.annproj")
person = proj.classes[0]; person.name = "person"; person.annotation_type = "keypoints"
person.skeleton = [SkeletonKeypoint("head", [1]), SkeletonKeypoint("neck", [0, 2]),
                   SkeletonKeypoint("pelvis", [1])]
box_cls = proj.add_class("car"); box_cls.annotation_type = "bbox"
poly_cls = proj.add_class("building"); poly_cls.annotation_type = "polygon"
ctrl.add_images_from_paths([str(img)])
ctrl.set_image(str(img))

scene = AnnotationScene()
scene.load_image(str(img))
ctrl.annotations_changed.connect(lambda anns: scene.rebuild_annotations(anns, ctrl.project))
tool = SelectTool()
scene.set_tool(tool, ctrl)

META = {"attributes": {"state": "walking"}, "subclass": "adult"}

def drag(a, b):
    """Select-tool press at a, move, release at b (scene pixels)."""
    tool.on_press(QPointF(*a), NOMOD, LB)
    tool.on_move(QPointF(*b), NOMOD)
    tool.on_release(QPointF(*b), NOMOD, LB)

def select_at(p):
    tool.on_press(QPointF(*p), NOMOD, LB)
    tool.on_release(QPointF(*p), NOMOD, LB)


# ═════════════════════════════════════════════════════════════════════════════
# §1  Pose keypoints (regression: AttributeError: no attribute 'handle_at')
# ═════════════════════════════════════════════════════════════════════════════
section("1. Pose keypoints")

# head (40,20)  neck (40,26) — only 6 px apart   pelvis (40,60) hidden-but-labeled v=1
pose = Annotation.new(person.id, AnnotationType.POSE, {
    "keypoints": [[0.20, 0.20, 2], [0.20, 0.26, 2], [0.20, 0.60, 1]], **META})
ctrl.add_annotation(pose)

check("click where keypoint circles overlap selects the pose (WindingFill)",
      scene.annotation_item_at(QPointF(40, 26)) is scene._ann_items[pose.id])

try:
    select_at((40, 60))                    # select via the lone pelvis point
    check("pose selected by clicking a keypoint", scene.get_selected_item() is not None)
    select_at((40, 26))                    # click a keypoint of the SELECTED pose
    crashed = False
except AttributeError:
    crashed = True
check("clicking a keypoint of a selected pose does not crash", not crashed)

select_at((40, 26))
drag((40, 25), (70, 30))                   # nearer to neck (40,26) than head (40,20)
kps = ctrl.get_annotation(pose.id).data["keypoints"]
check("drag moves the NEAREST keypoint (neck, not head)",
      abs(kps[1][0] - 0.35) < 1e-6 and abs(kps[1][1] - 0.30) < 1e-6 and kps[0][:2] == [0.20, 0.20])
check("visibility flag kept", kps[1][2] == 2 and kps[2][2] == 1)
check("attributes and subclass kept", {k: ctrl.get_annotation(pose.id).data[k] for k in META} == META)
ctrl.undo_stack.undo()
check("undo restores the keypoint", ctrl.get_annotation(pose.id).data["keypoints"][1][:2] == [0.20, 0.26])
select_at((40, 26))
drag((150, 90), (160, 95))                 # far from any keypoint -> no change
check("drag away from keypoints changes nothing",
      ctrl.get_annotation(pose.id).data["keypoints"][1][:2] == [0.20, 0.26])


# ═════════════════════════════════════════════════════════════════════════════
# §2  Metadata survives vertex / handle drags (regression: attributes wiped)
# ═════════════════════════════════════════════════════════════════════════════
section("2. Attributes survive edits")

poly = Annotation.new(poly_cls.id, AnnotationType.SEGMENT, {
    "points": [[0.6, 0.1], [0.9, 0.1], [0.75, 0.5]], **META})
ctrl.add_annotation(poly)
select_at((150, 25))
drag((120, 10), (125, 15))
d = ctrl.get_annotation(poly.id).data
check("polygon vertex moved", abs(d["points"][0][0] - 0.625) < 1e-6)
check("polygon keeps attributes and subclass", {k: d[k] for k in META} == META)

box = Annotation.new(box_cls.id, AnnotationType.BBOX, {
    "x": 0.05, "y": 0.70, "w": 0.20, "h": 0.20, **META})
ctrl.add_annotation(box)
select_at((30, 80))
before = dict(ctrl.get_annotation(box.id).data)
drag((10, 70), (5, 65))                    # top-left corner handle
d = ctrl.get_annotation(box.id).data
check("bbox resized", (d["x"], d["y"]) != (before["x"], before["y"]))
check("bbox keeps attributes and subclass", {k: d[k] for k in META} == META)


# ═════════════════════════════════════════════════════════════════════════════
# §3  Items without handles never crash Select
# ═════════════════════════════════════════════════════════════════════════════
section("3. Items without handle_at")

class _NoHandles:                          # e.g. a plugin item
    annotation_id = "x"

scene._selected_item = _NoHandles()
try:
    tool.on_press(QPointF(1, 1), NOMOD, LB)
    tool.on_release(QPointF(1, 1), NOMOD, LB)
    ok = True
except AttributeError:
    ok = False
check("selected item without handle_at: no crash", ok)

shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
