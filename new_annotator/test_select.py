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

# ═════════════════════════════════════════════════════════════════════════════
# §4  Moving a whole annotation by its body
# ═════════════════════════════════════════════════════════════════════════════
section("4. Move by dragging the body")
from annotator.domain.geometry import MOVABLE, clamp_shift, move_data
scene._selected_item = None
scene.deselect_all()

mbox = Annotation.new(box_cls.id, AnnotationType.BBOX,
                      {"x": 0.05, "y": 0.70, "w": 0.20, "h": 0.20, **META})
ctrl.add_annotation(mbox)
n0 = ctrl.undo_stack.count()
drag((30, 80), (60, 75))                    # inside the box, away from corners
d = ctrl.get_annotation(mbox.id).data
check("box moved by the drag (30 px right, 5 px up)",
      abs(d["x"] - 0.20) < 1e-6 and abs(d["y"] - 0.65) < 1e-6
      and (d["w"], d["h"]) == (0.20, 0.20))
check("move keeps attributes and subclass", {k: d[k] for k in META} == META)
check("move is one undo step", ctrl.undo_stack.count() == n0 + 1)
ctrl.undo_stack.undo()
check("undo puts it back", ctrl.get_annotation(mbox.id).data["x"] == 0.05)
drag((30, 80), (32, 81))                    # a click with a tiny jitter
check("a jitter below the threshold does not move it",
      ctrl.get_annotation(mbox.id).data["x"] == 0.05 and ctrl.undo_stack.count() == n0 + 1)
drag((30, 80), (900, 80))
check("moving stops at the image edge", abs(ctrl.get_annotation(mbox.id).data["x"] - 0.80) < 1e-6)
ctrl.undo_stack.undo()
item = scene._ann_items[mbox.id]
tool.on_press(QPointF(30, 80), NOMOD, LB)
tool.on_move(QPointF(50, 80), NOMOD)
check("preview: the item follows the mouse", item.pos().x() == 20)
tool.on_release(QPointF(50, 80), NOMOD, LB)
ctrl.undo_stack.undo()

mpoly = Annotation.new(poly_cls.id, AnnotationType.SEGMENT,
                       {"points": [[0.30, 0.10], [0.45, 0.10], [0.40, 0.40]]})
ctrl.add_annotation(mpoly)
drag((78, 20), (88, 40))
pts = ctrl.get_annotation(mpoly.id).data["points"]
check("polygon moves as a whole",
      all(abs(a - b) < 1e-6 for p, q in zip(pts, [[0.35, 0.30], [0.50, 0.30], [0.45, 0.60]])
          for a, b in zip(p, q)))

track = Annotation.new(box_cls.id, AnnotationType.BBOX, {"x": 0.6, "y": 0.6, "w": 0.1, "h": 0.1})
track.meta.update(track_id=1, keyframe=False, source="interpolated")
ctrl.add_annotation(track)
drag((130, 65), (140, 65))
check("moving an interpolated track frame makes it a keyframe",
      ctrl.get_annotation(track.id).meta["keyframe"] is True)

B, O, K = AnnotationType.BBOX, AnnotationType.OBB, AnnotationType.POSE
check("masks, semantic layers and image labels are not movable",
      not {AnnotationType.MASK, AnnotationType.SEMANTIC, AnnotationType.CLASSIFY} & MOVABLE)
check("OBB moves by its centre",
      move_data(O, {"cx": .5, "cy": .5, "w": .2, "h": .1, "angle_deg": 30}, .1, 0)["cx"] == .6)
check("pose: hidden keypoints stay put",
      move_data(K, {"keypoints": [[.1, .1, 2], [.0, .0, 0]]}, .1, .1)["keypoints"]
      == [[.2, .2, 2], [.0, .0, 0]])
crack = move_data(AnnotationType.SEGMENT, {"points": [[.1, .1], [.2, .1], [.2, .2]],
                  "source_geometry": {"type": "polyline", "points": [[.1, .1], [.2, .2]]}}, .1, 0)
check("a crack's source polyline moves along", crack["source_geometry"]["points"][0] == [.2, .1])
_cx, _cy = clamp_shift(AnnotationType.POINT, {"x": .9, "y": .5}, .5, 0)
check("clamp keeps a point inside", abs(_cx - 0.1) < 1e-9 and _cy == 0)

shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
