"""
Phase 7A tests — POSE instrument + YOLO Pose export
Run: .venv/Scripts/python test_phase7a.py
"""
import os
import sys
import json
import math
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from PyQt6.QtCore import QPointF

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


# ═════════════════════════════════════════════════════════════════════════════
# §1  SkeletonKeypoint serialization
# ═════════════════════════════════════════════════════════════════════════════
section("1. SkeletonKeypoint serialization")

from annotator.domain.label_class import SkeletonKeypoint

kp = SkeletonKeypoint(name="nose", edges=[1, 2])
d = kp.to_dict()
check("to_dict keys", set(d.keys()) == {"name", "edges"})
check("to_dict name", d["name"] == "nose")
check("to_dict edges", d["edges"] == [1, 2])

kp2 = SkeletonKeypoint.from_dict({"name": "left_eye", "edges": [0, 3]})
check("from_dict name", kp2.name == "left_eye")
check("from_dict edges", kp2.edges == [0, 3])

kp3 = SkeletonKeypoint.from_dict({"name": "no_edges"})
check("from_dict no edges", kp3.edges == [])

kp4 = SkeletonKeypoint.from_dict(kp.to_dict())
check("round-trip", kp4.name == "nose" and kp4.edges == [1, 2])

# ═════════════════════════════════════════════════════════════════════════════
# §2  LabelClass skeleton field
# ═════════════════════════════════════════════════════════════════════════════
section("2. LabelClass skeleton field")

from annotator.domain.label_class import LabelClass

skel = [
    SkeletonKeypoint("nose",      edges=[1, 2]),
    SkeletonKeypoint("left_eye",  edges=[0]),
    SkeletonKeypoint("right_eye", edges=[0]),
]
cls = LabelClass(id=0, name="person", color="#FF0000",
                 annotation_type="keypoints", skeleton=skel)

d = cls.to_dict()
check("skeleton in to_dict", "skeleton" in d)
check("skeleton length", len(d["skeleton"]) == 3)
check("skeleton[0] name", d["skeleton"][0]["name"] == "nose")
check("skeleton[0] edges", d["skeleton"][0]["edges"] == [1, 2])

cls2 = LabelClass.from_dict(d)
check("from_dict skeleton length", len(cls2.skeleton) == 3)
check("from_dict skeleton names",
      [kp.name for kp in cls2.skeleton] == ["nose", "left_eye", "right_eye"])
check("from_dict skeleton edges[0]", cls2.skeleton[0].edges == [1, 2])

# No skeleton on non-keypoints class
cls3 = LabelClass(id=1, name="car", color="#00FF00", annotation_type="bbox")
d3 = cls3.to_dict()
check("no skeleton -> empty list", d3["skeleton"] == [])
cls4 = LabelClass.from_dict(d3)
check("from_dict no skeleton -> []", cls4.skeleton == [])

# ═════════════════════════════════════════════════════════════════════════════
# §3  ANNOTATION_TYPE_DEFAULT_TOOL updated
# ═════════════════════════════════════════════════════════════════════════════
section("3. ANNOTATION_TYPE_DEFAULT_TOOL for keypoints")

from annotator.domain.label_class import ANNOTATION_TYPE_DEFAULT_TOOL, ANNOTATION_TYPE_TOOLS
check("default tool for keypoints = pose",
      ANNOTATION_TYPE_DEFAULT_TOOL["keypoints"] == "pose")
check("compatible tools for keypoints includes pose",
      "pose" in ANNOTATION_TYPE_TOOLS["keypoints"])

# ═════════════════════════════════════════════════════════════════════════════
# §4  PoseTool — basic mechanics (headless mock)
# ═════════════════════════════════════════════════════════════════════════════
section("4. PoseTool basic mechanics")

from annotator.tools.pose_tool import PoseTool
from annotator.domain.annotation import AnnotationType


class _MockItem:
    def __init__(self): pass
    def scene(self): return True
    def setZValue(self, v): pass
    def setBrush(self, b): pass
    def setPos(self, x, y): pass


class _MockScene:
    def __init__(self, w=800, h=600):
        self.image_size = (w, h)
        self.removed = []
    def addLine(self, *a, **kw): return _MockItem()
    def addEllipse(self, *a, **kw): return _MockItem()
    def addSimpleText(self, *a): return _MockItem()
    def removeItem(self, item): self.removed.append(item)


class _MockCtrl:
    def __init__(self):
        self.added = []
        self.project = None
    def add_annotation(self, ann):
        self.added.append(ann)


scene = _MockScene()
ctrl = _MockCtrl()
tool = PoseTool()
tool.activate(scene, ctrl)

# Place 3 keypoints via LMB
from PyQt6.QtCore import Qt
tool.on_press(QPointF(100, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool.on_press(QPointF(200, 150), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool.on_press(QPointF(300, 200), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
check("3 points placed", len(tool._points) == 3)

# RMB undo last
tool.on_press(QPointF(0, 0), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.RightButton)
check("RMB removes last", len(tool._points) == 2)

# Enter commits
tool.on_key_press(Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
check("Enter commits", len(ctrl.added) == 1)
check("Ann type is POSE", ctrl.added[0].ann_type == AnnotationType.POSE)
check("Points cleared after commit", len(tool._points) == 0)

kps = ctrl.added[0].data["keypoints"]
check("2 keypoints in data", len(kps) == 2)
check("keypoint v=2 (visible)", all(k[2] == 2 for k in kps))
check("keypoints normalized",
      all(0 <= k[0] <= 1 and 0 <= k[1] <= 1 for k in kps))

# ═════════════════════════════════════════════════════════════════════════════
# §5  PoseTool — Esc cancel
# ═════════════════════════════════════════════════════════════════════════════
section("5. PoseTool — cancel")

tool2 = PoseTool()
tool2.activate(_MockScene(), _MockCtrl())
tool2.on_press(QPointF(50, 50), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
check("point added", len(tool2._points) == 1)
tool2.on_key_press(Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
check("Esc clears points", len(tool2._points) == 0)

# Empty commit does nothing
ctrl3 = _MockCtrl()
tool3 = PoseTool()
tool3.activate(_MockScene(), ctrl3)
tool3.on_key_press(Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
check("empty commit adds nothing", len(ctrl3.added) == 0)

# ═════════════════════════════════════════════════════════════════════════════
# §6  PoseTool — skeleton-guided mode (auto-commit + padding)
# ═════════════════════════════════════════════════════════════════════════════
section("6. PoseTool — skeleton-guided mode")

class _MockProject:
    def get_class(self, class_id):
        from annotator.domain.label_class import LabelClass, SkeletonKeypoint
        return LabelClass(
            id=0, name="person", color="#FF0000",
            annotation_type="keypoints",
            skeleton=[
                SkeletonKeypoint("nose",  edges=[1]),
                SkeletonKeypoint("l_eye", edges=[0]),
                SkeletonKeypoint("r_eye", edges=[0]),
            ])

ctrl4 = _MockCtrl()
ctrl4.project = _MockProject()
tool4 = PoseTool()
tool4.activate(_MockScene(), ctrl4)
tool4.set_class(0)

check("skeleton loaded", tool4._skeleton_names == ["nose", "l_eye", "r_eye"])
check("edges loaded", (0, 1) in tool4._skeleton_edges)

# Place 3 points - should auto-commit
tool4.on_press(QPointF(100, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool4.on_press(QPointF(200, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool4.on_press(QPointF(300, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
check("auto-committed on 3rd point", len(ctrl4.added) == 1)
check("exactly 3 keypoints", len(ctrl4.added[0].data["keypoints"]) == 3)
check("all visible", all(k[2] == 2 for k in ctrl4.added[0].data["keypoints"]))

# Place only 1 point, then Enter - skeleton pads to 3
ctrl5 = _MockCtrl()
ctrl5.project = _MockProject()
tool5 = PoseTool()
tool5.activate(_MockScene(), ctrl5)
tool5.set_class(0)
tool5.on_press(QPointF(100, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool5.on_key_press(Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
check("partial: 1 point committed", len(ctrl5.added) == 1)
kps5 = ctrl5.added[0].data["keypoints"]
check("partial: padded to 3", len(kps5) == 3)
check("partial: first visible", kps5[0][2] == 2)
check("partial: rest invisible", kps5[1][2] == 0 and kps5[2][2] == 0)

# ═════════════════════════════════════════════════════════════════════════════
# §7  YoloPoseExporter — line format
# ═════════════════════════════════════════════════════════════════════════════
section("7. YoloPoseExporter — line format")

from annotator.exporters.yolo_pose import _make_format_fn, _kpt_count_for_project
from annotator.domain.annotation import Annotation, AnnotationType

class _FakeProject:
    classes = []
    def get_class(self, cid):
        return None

fake_proj = _FakeProject()
fmt_fn = _make_format_fn(fake_proj)

# Basic POSE annotation — no skeleton, 2 keypoints
ann = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.2, 0.3, 2], [0.4, 0.5, 2]]
})
line = fmt_fn(ann)
check("line is not None", line is not None)
parts = line.split()
check("class_id is 0", parts[0] == "0")
check("7 fields for 2 kp (1 id + 4 bbox + 2*3 kp)", len(parts) == 1 + 4 + 2*3)

# Verify bbox math: visible=[0.2,0.3],[0.4,0.5], margin=0.05
# xmin=0.15 xmax=0.45 ymin=0.25 ymax=0.55 -> cx=0.3 cy=0.4 w=0.3 h=0.3
cx = float(parts[1])
cy = float(parts[2])
w  = float(parts[3])
h  = float(parts[4])
check("cx computed", abs(cx - 0.3) < 1e-4)
check("cy computed", abs(cy - 0.4) < 1e-4)
check("w computed",  abs(w  - 0.3) < 1e-4)
check("h computed",  abs(h  - 0.3) < 1e-4)

# Verify keypoint fields
check("kp1 x", abs(float(parts[5]) - 0.2) < 1e-5)
check("kp1 y", abs(float(parts[6]) - 0.3) < 1e-5)
check("kp1 v=2", parts[7] == "2")

# All invisible - skip
ann_invis = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.0, 0.0, 0], [0.0, 0.0, 0]]
})
check("all invisible -> None", fmt_fn(ann_invis) is None)

# Non-POSE - skip
from annotator.domain.annotation import Annotation, AnnotationType
ann_seg = Annotation.new(0, AnnotationType.SEGMENT, {"points": [[0.1, 0.1], [0.5, 0.5], [0.9, 0.1]]})
check("non-POSE -> None", fmt_fn(ann_seg) is None)

# ═════════════════════════════════════════════════════════════════════════════
# §8  YoloPoseExporter — skeleton padding
# ═════════════════════════════════════════════════════════════════════════════
section("8. YoloPoseExporter — skeleton padding")

class _ProjectWithSkel:
    classes = [LabelClass(id=0, name="person", color="#FF0000",
                          annotation_type="keypoints",
                          skeleton=[
                              SkeletonKeypoint("nose"),
                              SkeletonKeypoint("l_eye"),
                              SkeletonKeypoint("r_eye"),
                          ])]
    def get_class(self, cid):
        return self.classes[0] if cid == 0 else None

proj_skel = _ProjectWithSkel()
fmt_skel = _make_format_fn(proj_skel)

# 2 keypoints placed, skeleton wants 3 - pad with invisible
ann_2kp = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.2, 0.3, 2], [0.4, 0.5, 2]]
})
line2 = fmt_skel(ann_2kp)
check("padded line not None", line2 is not None)
parts2 = line2.split()
check("padded: 1+4+3*3 fields", len(parts2) == 1 + 4 + 3*3)
check("padded kp3 v=0", parts2[-1] == "0")  # last visibility = 0

# 4 keypoints placed, skeleton wants 3 - trim
ann_4kp = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.1,0.1,2],[0.2,0.2,2],[0.3,0.3,2],[0.9,0.9,2]]
})
line3 = fmt_skel(ann_4kp)
check("trimmed line not None", line3 is not None)
parts3 = line3.split()
check("trimmed: 1+4+3*3 fields", len(parts3) == 1 + 4 + 3*3)

# kpt_count_for_project
check("kpt_count with skeleton=3", _kpt_count_for_project(proj_skel) == 3)
check("kpt_count no skeleton=0", _kpt_count_for_project(fake_proj) == 0)

# ═════════════════════════════════════════════════════════════════════════════
# §9  YoloPoseExporter — full dataset write
# ═════════════════════════════════════════════════════════════════════════════
section("9. YoloPoseExporter — full dataset write")

from annotator.domain.project import Project, ImageRecord
from annotator.exporters.yolo_pose import YoloPoseExporter

tmpdir = Path(tempfile.mkdtemp())
try:
    proj9 = Project(id="test-id", name="test",
                    created_at="2024-01-01", modified_at="2024-01-01",
                    classes=[
                        LabelClass(id=0, name="person", color="#FF0000",
                                   annotation_type="keypoints",
                                   skeleton=[
                                       SkeletonKeypoint("nose",  edges=[1]),
                                       SkeletonKeypoint("l_eye", edges=[0]),
                                   ])
                    ], images=[
                        ImageRecord(path="img1.jpg", width=640, height=480, split="train"),
                    ])

    ann9 = Annotation.new(0, AnnotationType.POSE, {
        "keypoints": [[0.3, 0.4, 2], [0.5, 0.6, 2]]
    })
    all_anns = {"img1.jpg": [ann9]}

    exp = YoloPoseExporter()
    exp.export(proj9, tmpdir, all_annotations=all_anns, copy_images=False)

    label_file = tmpdir / "labels" / "train" / "img1.txt"
    check("label file created", label_file.exists())

    content = label_file.read_text().strip()
    check("label file not empty", bool(content))
    parts9 = content.split()
    check("class_id=0", parts9[0] == "0")
    check("fields: 1+4+2*3", len(parts9) == 1 + 4 + 2*3)

    yaml_path = tmpdir / "data.yaml"
    check("data.yaml created", yaml_path.exists())
    yaml_text = yaml_path.read_text()
    check("kpt_shape in yaml", "kpt_shape: [2, 3]" in yaml_text)
    check("nc in yaml", "nc: 1" in yaml_text)

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

# ═════════════════════════════════════════════════════════════════════════════
# §10  PoseAnnotationItem — update_from_data / to_data
# ═════════════════════════════════════════════════════════════════════════════
section("10. PoseAnnotationItem — data round-trip")

from annotator.ui.canvas.items.pose_item import PoseAnnotationItem

kps_scene = [(100.0, 150.0, 2), (200.0, 250.0, 2), (300.0, 350.0, 0)]
edges = [(0, 1)]
item = PoseAnnotationItem("ann1", kps_scene, edges, "#FF0000", "person")

check("item created", item is not None)
check("annotation_id", item.annotation_id == "ann1")
check("keypoints stored", len(item._keypoints) == 3)
check("invisible kp", item._keypoints[2][2] == 0)

# to_data
data = item.to_data((640, 480))
check("to_data has keypoints key", "keypoints" in data)
kps_out = data["keypoints"]
check("to_data 3 keypoints", len(kps_out) == 3)
check("to_data normalized x", abs(kps_out[0][0] - 100.0/640) < 1e-6)
check("to_data normalized y", abs(kps_out[0][1] - 150.0/480) < 1e-6)
check("to_data v preserved", kps_out[0][2] == 2)
check("to_data invisible preserved", kps_out[2][2] == 0)

# update_from_data
item2 = PoseAnnotationItem("ann2", [], [], "#00FF00", "test")
item2.update_from_data({"keypoints": [[0.5, 0.5, 2], [0.25, 0.75, 1]]}, (800, 600))
check("update_from_data 2 kp", len(item2._keypoints) == 2)
check("update_from_data pixel x", abs(item2._keypoints[0][0] - 400.0) < 1e-4)
check("update_from_data pixel y", abs(item2._keypoints[0][1] - 300.0) < 1e-4)
check("update_from_data v=1", item2._keypoints[1][2] == 1)

# boundingRect with visible points
br = item.boundingRect()
check("boundingRect not empty", br.width() > 0 and br.height() > 0)

# boundingRect with no visible points
item_invis = PoseAnnotationItem("x", [(0,0,0), (1,1,0)], [], "#000", "")
br2 = item_invis.boundingRect()
check("boundingRect all-invisible = (0,0,1,1)", br2.width() == 1 and br2.height() == 1)

# ═════════════════════════════════════════════════════════════════════════════
# §11  scene._make_item for POSE
# ═════════════════════════════════════════════════════════════════════════════
section("11. scene._make_item for POSE")

from annotator.ui.canvas.scene import AnnotationScene
from annotator.ui.canvas.items.pose_item import PoseAnnotationItem

scene11 = AnnotationScene()
scene11._image_size = (640, 480)

class _Proj11:
    def get_class(self, cid):
        return LabelClass(
            id=0, name="person", color="#FF4444",
            annotation_type="keypoints",
            skeleton=[
                SkeletonKeypoint("nose",  edges=[1]),
                SkeletonKeypoint("l_eye", edges=[0]),
            ])

ann11 = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.3, 0.4, 2], [0.5, 0.6, 2]]
})
item11 = scene11._make_item(ann11, _Proj11())
check("POSE item created", item11 is not None)
check("POSE item type", isinstance(item11, PoseAnnotationItem))
check("POSE item kp count", len(item11._keypoints) == 2)
check("POSE item color", item11.class_color == "#FF4444")
check("POSE item edges loaded", (0, 1) in item11._edges)

# POSE with no project - no edges, gray color
item11b = scene11._make_item(ann11, None)
check("POSE item no project", item11b is not None)
check("POSE item no project edges empty", item11b._edges == [])

# ═════════════════════════════════════════════════════════════════════════════
# §12  schema editor helpers (_parse_edges, _collect_edges)
# ═════════════════════════════════════════════════════════════════════════════
section("12. Schema editor skeleton helpers")

from annotator.ui.dialogs.class_schema_editor import ClassSchemaEditorDialog

# _parse_edges
pairs = ClassSchemaEditorDialog._parse_edges("0-1, 1-2, 0-2", 3)
check("parse 3 edges", len(pairs) == 3)
check("parse edge (0,1)", (0, 1) in pairs)
check("parse edge (1,2)", (1, 2) in pairs)
check("parse edge (0,2)", (0, 2) in pairs)

# Out-of-range ignored
pairs2 = ClassSchemaEditorDialog._parse_edges("0-5, 1-2", 3)
check("parse out-of-range ignored", len(pairs2) == 1)

# Duplicates deduplicated
pairs3 = ClassSchemaEditorDialog._parse_edges("0-1, 1-0, 0-1", 3)
check("parse dedup", len(pairs3) == 1)

# Self-loop ignored
pairs4 = ClassSchemaEditorDialog._parse_edges("0-0, 1-2", 3)
check("parse self-loop ignored", len(pairs4) == 1)

# _collect_edges
skel_ce = [
    SkeletonKeypoint("a", edges=[1, 2]),
    SkeletonKeypoint("b", edges=[0]),
    SkeletonKeypoint("c", edges=[0]),
]
collected = ClassSchemaEditorDialog._collect_edges(skel_ce)
check("collect 2 edges (dedup)", len(collected) == 2)
check("collect (0,1)", (0, 1) in collected)
check("collect (0,2)", (0, 2) in collected)

# ═════════════════════════════════════════════════════════════════════════════
# §13  LabelClass skeleton round-trip via ClassSchema
# ═════════════════════════════════════════════════════════════════════════════
section("13. LabelClass skeleton persisted via to_dict/from_dict")

skel_full = [
    SkeletonKeypoint("nose",  edges=[1, 2]),
    SkeletonKeypoint("l_eye", edges=[0]),
    SkeletonKeypoint("r_eye", edges=[0]),
]
cls13 = LabelClass(id=0, name="person", color="#FF0000",
                   annotation_type="keypoints", skeleton=skel_full)
d13 = cls13.to_dict()
cls13b = LabelClass.from_dict(d13)

check("round-trip skeleton length", len(cls13b.skeleton) == 3)
check("round-trip name[0]", cls13b.skeleton[0].name == "nose")
check("round-trip edges[0]", sorted(cls13b.skeleton[0].edges) == [1, 2])
check("round-trip name[1]", cls13b.skeleton[1].name == "l_eye")
check("round-trip edges[1]", cls13b.skeleton[1].edges == [0])

# ═════════════════════════════════════════════════════════════════════════════
# §14  PoseTool — deactivate clears preview
# ═════════════════════════════════════════════════════════════════════════════
section("14. PoseTool — deactivate clears state")

tool_d = PoseTool()
scene_d = _MockScene()
ctrl_d = _MockCtrl()
tool_d.activate(scene_d, ctrl_d)
tool_d.on_press(QPointF(100, 100), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
tool_d.on_press(QPointF(200, 200), Qt.KeyboardModifier.NoModifier, Qt.MouseButton.LeftButton)
check("points before deactivate", len(tool_d._points) == 2)
tool_d.deactivate()
check("points cleared on deactivate", len(tool_d._points) == 0)
check("scene cleared on deactivate", tool_d._scene is None)

# ═════════════════════════════════════════════════════════════════════════════
# §15  Bbox margin clamping in exporter
# ═════════════════════════════════════════════════════════════════════════════
section("15. Exporter bbox clamping to [0,1]")

# Keypoint near edge — margin should be clamped
ann_edge = Annotation.new(0, AnnotationType.POSE, {
    "keypoints": [[0.02, 0.02, 2]]  # near top-left; margin 0.05 -> xmin<0
})
line_edge = fmt_fn(ann_edge)
check("edge kp line not None", line_edge is not None)
vals = [float(v) for v in line_edge.split()[1:5]]  # cx cy w h
check("bbox cx >= 0", vals[0] >= 0)
check("bbox cy >= 0", vals[1] >= 0)
check("bbox cx+w/2 <= 1", vals[0] + vals[2]/2 <= 1.0 + 1e-9)

# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════
total = _pass + _fail
print(f"\n{'='*50}")
print(f"Results: {_pass}/{total} passed" + ("" if _fail == 0 else f"  ({_fail} FAILED)"))
if _fail:
    sys.exit(1)
