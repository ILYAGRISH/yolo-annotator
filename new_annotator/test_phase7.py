"""
test_phase7.py — Phase 7C: COCO Export / CrackTool edit / Plugin Loader

Checks (headless, no GUI):
  1. CocoExporter — output structure
  2. CocoExporter — SEGMENT annotation
  3. CocoExporter — BBOX annotation
  4. CocoExporter — OBB annotation
  5. CocoExporter — crack annotation (source_geometry NOT in output)
  6. CocoExporter — attributes included
  7. CocoExporter — multiple splits
  8. CrackTool — start_edit loads points and params
  9. CrackTool — commit in edit mode updates existing annotation
  10. Plugin loader — discovers BaseTool subclasses from .py file
"""
import sys
import os
import json
import math
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PASS = 0
FAIL = 0


def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}" + (f"  ({detail})" if detail else ""))
        FAIL += 1


# ─────────────────────────────────────────────────────────────────────────────
print("=== 1. CocoExporter — output structure ===")

from annotator.exporters.coco import CocoExporter
from annotator.domain.project import Project, ImageRecord
from annotator.domain.annotation import Annotation, AnnotationType

exp = CocoExporter()
check("exporter name", exp.name == "COCO Instances")
check("file extension", exp.file_extension == ".json")

project = Project.create("test_coco")
project.classes.clear()
project.add_class("crack", "#FF4444")   # id=0
project.add_class("car",   "#4488FF")   # id=1

tmp = Path(tempfile.mkdtemp())
try:
    # Create a minimal image record with known dimensions
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    rec = ImageRecord(path=img_path, width=200, height=100, split="train")
    project.images.append(rec)

    seg_ann = Annotation.new(0, AnnotationType.SEGMENT,
                             {"points": [[0.1, 0.2], [0.5, 0.2],
                                         [0.5, 0.8], [0.1, 0.8]]})
    all_anns = {img_path: [seg_ann]}

    out = tmp / "coco_out"
    exp.export(project, out, all_annotations=all_anns, copy_images=False)

    ann_dir = out / "annotations"
    check("annotations/ dir created", ann_dir.is_dir())

    inst_file = ann_dir / "instances_train.json"
    check("instances_train.json created", inst_file.exists())

    data = json.loads(inst_file.read_text())
    check("has 'info' key", "info" in data)
    check("has 'categories' key", "categories" in data)
    check("has 'images' key", "images" in data)
    check("has 'annotations' key", "annotations" in data)

    check("categories count = 2", len(data["categories"]) == 2)
    check("first category id = 0", data["categories"][0]["id"] == 0)
    check("first category name = crack", data["categories"][0]["name"] == "crack")
    check("images count = 1", len(data["images"]) == 1)
    check("image width = 200", data["images"][0]["width"] == 200)
    check("image height = 100", data["images"][0]["height"] == 100)
    check("image file_name", data["images"][0]["file_name"] == "img.png")

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 2. CocoExporter — SEGMENT annotation ===")

tmp = Path(tempfile.mkdtemp())
try:
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    project2 = Project.create("test2")
    project2.classes.clear()
    project2.add_class("obj", "#FF0000")

    rec = ImageRecord(path=img_path, width=100, height=100, split="train")
    project2.images.append(rec)

    # Square 0.1–0.9 in both axes → 10–90 px
    ann = Annotation.new(0, AnnotationType.SEGMENT,
                         {"points": [[0.1, 0.1], [0.9, 0.1],
                                     [0.9, 0.9], [0.1, 0.9]]})
    all_anns = {img_path: [ann]}
    out = tmp / "out"
    exp.export(project2, out, all_annotations=all_anns, copy_images=False)

    data = json.loads((out / "annotations" / "instances_train.json").read_text())
    cann = data["annotations"][0]

    check("SEGMENT: has segmentation", "segmentation" in cann)
    check("SEGMENT: segmentation is list of lists",
          isinstance(cann["segmentation"], list) and
          isinstance(cann["segmentation"][0], list))
    flat = cann["segmentation"][0]
    check("SEGMENT: flat len = 2*n_pts", len(flat) == 8)
    check("SEGMENT: first x = 10.0", abs(flat[0] - 10.0) < 0.01)
    check("SEGMENT: first y = 10.0", abs(flat[1] - 10.0) < 0.01)
    check("SEGMENT: has bbox", "bbox" in cann)
    bx, by, bw, bh = cann["bbox"]
    check("SEGMENT: bbox x ~ 10", abs(bx - 10.0) < 0.01)
    check("SEGMENT: bbox w ~ 80", abs(bw - 80.0) < 0.01)
    check("SEGMENT: has area", "area" in cann)
    check("SEGMENT: area ~ 6400", abs(cann["area"] - 6400.0) < 1.0)
    check("SEGMENT: category_id = 0", cann["category_id"] == 0)
    check("SEGMENT: iscrowd = 0", cann["iscrowd"] == 0)

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 3. CocoExporter — BBOX annotation ===")

tmp = Path(tempfile.mkdtemp())
try:
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    project3 = Project.create("test3")
    project3.classes.clear()
    project3.add_class("car", "#0000FF")

    rec = ImageRecord(path=img_path, width=200, height=100, split="train")
    project3.images.append(rec)

    ann = Annotation.new(0, AnnotationType.BBOX,
                         {"x": 0.1, "y": 0.2, "w": 0.4, "h": 0.5})
    all_anns = {img_path: [ann]}
    out = tmp / "out"
    exp.export(project3, out, all_annotations=all_anns, copy_images=False)

    data = json.loads((out / "annotations" / "instances_train.json").read_text())
    cann = data["annotations"][0]

    check("BBOX: has bbox", "bbox" in cann)
    bx, by, bw, bh = cann["bbox"]
    # x=0.1*200=20, y=0.2*100=20, w=0.4*200=80, h=0.5*100=50
    check("BBOX: x ~ 20", abs(bx - 20.0) < 0.01)
    check("BBOX: y ~ 20", abs(by - 20.0) < 0.01)
    check("BBOX: w ~ 80", abs(bw - 80.0) < 0.01)
    check("BBOX: h ~ 50", abs(bh - 50.0) < 0.01)
    check("BBOX: segmentation empty", cann["segmentation"] == [])
    check("BBOX: area ~ 4000", abs(cann["area"] - 4000.0) < 1.0)

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 4. CocoExporter — OBB annotation ===")

tmp = Path(tempfile.mkdtemp())
try:
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    project4 = Project.create("test4")
    project4.classes.clear()
    project4.add_class("obb_obj", "#FFFF00")

    rec = ImageRecord(path=img_path, width=100, height=100, split="train")
    project4.images.append(rec)

    # Axis-aligned OBB (angle=0) → same as bbox
    ann = Annotation.new(0, AnnotationType.OBB,
                         {"cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.2, "angle": 0.0})
    all_anns = {img_path: [ann]}
    out = tmp / "out"
    exp.export(project4, out, all_annotations=all_anns, copy_images=False)

    data = json.loads((out / "annotations" / "instances_train.json").read_text())
    cann = data["annotations"][0]

    check("OBB: has segmentation", "segmentation" in cann)
    flat = cann["segmentation"][0]
    check("OBB: segmentation has 8 values (4 corners)", len(flat) == 8)
    check("OBB: has bbox", "bbox" in cann)
    check("OBB: has area", "area" in cann)

    # Axis-aligned: bbox should be w=40, h=20 (px)
    _, _, bw, bh = cann["bbox"]
    check("OBB angle=0: bbox w ~ 40", abs(bw - 40.0) < 0.5)
    check("OBB angle=0: bbox h ~ 20", abs(bh - 20.0) < 0.5)

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 5. CocoExporter — crack annotation (source_geometry not in output) ===")

from annotator.tools.crack_tool import _buffer_polyline

tmp = Path(tempfile.mkdtemp())
try:
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    project5 = Project.create("test5")
    project5.classes.clear()
    project5.add_class("crack", "#FF4444")

    rec = ImageRecord(path=img_path, width=100, height=100, split="train")
    project5.images.append(rec)

    norm_src = [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]]
    params = {"buffer_width": 0.05, "cap_style": "round",
              "join_style": "round", "simplify": 0.0}
    poly_pts = _buffer_polyline(norm_src, params, (100, 100))

    crack_ann = Annotation.new(
        0, AnnotationType.SEGMENT,
        {
            "points": poly_pts,
            "source_geometry": {"type": "polyline", "points": norm_src},
            "tool_params": dict(params),
        },
        tool="crack_tool",
    )
    all_anns = {img_path: [crack_ann]}
    out = tmp / "out"
    exp.export(project5, out, all_annotations=all_anns, copy_images=False)

    raw = (out / "annotations" / "instances_train.json").read_text()
    data = json.loads(raw)

    check("crack: annotation exported", len(data["annotations"]) == 1)
    check("crack: source_geometry NOT in raw output",
          "source_geometry" not in raw)
    check("crack: tool_params NOT in raw output",
          "tool_params" not in raw)
    cann = data["annotations"][0]
    check("crack: has segmentation", "segmentation" in cann)
    check("crack: category_id = 0", cann["category_id"] == 0)

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 6. CocoExporter — attributes included ===")

from annotator.domain.label_class import ClassAttribute

tmp = Path(tempfile.mkdtemp())
try:
    img_path = str(tmp / "img.png")
    Path(img_path).write_bytes(b"fake")
    project6 = Project.create("test6")
    project6.classes.clear()
    cls = project6.add_class("damage", "#FF0000")
    cls.attributes = [
        ClassAttribute(id="sev", name="severity", attr_type="select",
                       options=["low", "high"])
    ]

    rec = ImageRecord(path=img_path, width=100, height=100, split="train")
    project6.images.append(rec)

    ann_with_attr = Annotation.new(
        0, AnnotationType.SEGMENT,
        {"points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]],
         "attributes": {"severity": "high"}},
    )
    ann_no_attr = Annotation.new(
        0, AnnotationType.SEGMENT,
        {"points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]},
    )
    all_anns = {img_path: [ann_with_attr, ann_no_attr]}
    out = tmp / "out"
    exp.export(project6, out, all_annotations=all_anns, copy_images=False)

    data = json.loads((out / "annotations" / "instances_train.json").read_text())
    anns = data["annotations"]

    check("attributes: 2 annotations exported", len(anns) == 2)
    # First annotation has attributes
    check("attributes: first ann has 'attributes' field", "attributes" in anns[0])
    check("attributes: severity = high",
          anns[0].get("attributes", {}).get("severity") == "high")
    # Second annotation has no attributes → no 'attributes' key
    check("attributes: second ann has no 'attributes' field",
          "attributes" not in anns[1])

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 7. CocoExporter — multiple splits ===")

tmp = Path(tempfile.mkdtemp())
try:
    project7 = Project.create("test7")
    project7.classes.clear()
    project7.add_class("obj", "#FF0000")

    all_anns = {}
    for split, fname in [("train", "t.png"), ("val", "v.png")]:
        p = str(tmp / fname)
        Path(p).write_bytes(b"fake")
        rec = ImageRecord(path=p, width=50, height=50, split=split)
        project7.images.append(rec)
        ann = Annotation.new(0, AnnotationType.BBOX,
                             {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
        all_anns[p] = [ann]

    out = tmp / "out"
    exp.export(project7, out, all_annotations=all_anns, copy_images=False)

    ann_dir = out / "annotations"
    check("split: instances_train.json exists",
          (ann_dir / "instances_train.json").exists())
    check("split: instances_val.json exists",
          (ann_dir / "instances_val.json").exists())
    train_data = json.loads((ann_dir / "instances_train.json").read_text())
    val_data   = json.loads((ann_dir / "instances_val.json").read_text())
    check("split: train has 1 image", len(train_data["images"]) == 1)
    check("split: val has 1 image",   len(val_data["images"]) == 1)
    check("split: train has 1 ann",   len(train_data["annotations"]) == 1)
    check("split: val has 1 ann",     len(val_data["annotations"]) == 1)

finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 8. CrackTool — start_edit loads source geometry ===")

from annotator.tools.crack_tool import CrackTool
from PyQt6.QtCore import QPointF


class _MockItem:
    def scene(self): return True
    def setZValue(self, v): pass


class _MockScene:
    image_size = (200, 100)

    def addLine(self, *a): return _MockItem()
    def addEllipse(self, *a): return _MockItem()
    def addPolygon(self, *a): return _MockItem()
    def removeItem(self, item): pass


norm_src = [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]]
params_orig = {"buffer_width": 0.05, "cap_style": "flat",
               "join_style": "round", "simplify": 0.0}
poly_pts2 = _buffer_polyline(norm_src, params_orig, (200, 100))

edit_ann = Annotation.new(
    0, AnnotationType.SEGMENT,
    {
        "points": poly_pts2,
        "source_geometry": {"type": "polyline", "points": norm_src},
        "tool_params": dict(params_orig),
    },
    tool="crack_tool",
)

ct = CrackTool()
ct._scene = _MockScene()
ct._ctrl = None

check("is_editing = False before start_edit", not ct.is_editing)
ct.start_edit(edit_ann)
check("is_editing = True after start_edit", ct.is_editing)
check("points count matches source_geometry",
      len(ct._points) == len(norm_src))
check("points are QPointF", all(isinstance(p, QPointF) for p in ct._points))
# First point: norm (0.1, 0.5) → pixel (0.1*200=20, 0.5*100=50)
check("first point x ~ 20", abs(ct._points[0].x() - 20.0) < 0.01)
check("first point y ~ 50", abs(ct._points[0].y() - 50.0) < 0.01)
check("buffer_width loaded from tool_params",
      abs(ct._params["buffer_width"] - 0.05) < 1e-9)
check("cap_style loaded from tool_params",
      ct._params["cap_style"] == "flat")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 9. CrackTool — commit in edit mode updates annotation ===")


class _MockCtrl:
    def __init__(self):
        self.updated: tuple | None = None
        self.added = None

    def update_annotation_data(self, ann_id, new_data, text=""):
        self.updated = (ann_id, new_data)

    def add_annotation(self, ann):
        self.added = ann


mock_ctrl = _MockCtrl()
ct2 = CrackTool()
ct2._scene = _MockScene()
ct2._ctrl = mock_ctrl
ct2.start_edit(edit_ann)

# Simulate commit
ct2._commit()

check("update_annotation_data was called", mock_ctrl.updated is not None)
check("correct ann_id updated", mock_ctrl.updated[0] == edit_ann.id)
new_data = mock_ctrl.updated[1]
check("new_data has points", "points" in new_data)
check("new_data has source_geometry", "source_geometry" in new_data)
check("new_data has tool_params", "tool_params" in new_data)
check("add_annotation NOT called (edit mode)", mock_ctrl.added is None)
check("is_editing = False after commit", not ct2.is_editing)

# Normal (create) mode: add_annotation IS called
ct3 = CrackTool()
ct3._scene = _MockScene()
ct3._ctrl = _MockCtrl()
# Push enough points for a valid buffer
from PyQt6.QtCore import QPointF
for nx, ny in norm_src:
    ct3._points.append(QPointF(nx * 200, ny * 100))
ct3._commit()
check("create mode: add_annotation called", ct3._ctrl.added is not None)
check("create mode: update NOT called", ct3._ctrl.updated is None)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 10. Plugin loader ===")

from annotator.plugins.loader import load_plugins
from annotator.tools.base import BaseTool

# Empty / nonexistent dir
check("nonexistent dir returns []",
      load_plugins(Path("__nonexistent_dir__")) == [])

# Valid plugin file
tmp_plugins = Path(tempfile.mkdtemp())
try:
    plugin_code = """\
from annotator.tools.base import BaseTool

class DummyTool(BaseTool):
    @property
    def name(self): return "dummy_tool"
    def on_press(self, pos, mods, btn): pass
    def on_move(self, pos, mods): pass
    def on_release(self, pos, mods, btn): pass
"""
    (tmp_plugins / "dummy.py").write_text(plugin_code, encoding="utf-8")
    tools = load_plugins(tmp_plugins)
    check("plugin loaded: 1 tool found", len(tools) == 1)
    check("plugin tool name = dummy_tool", tools[0].name == "dummy_tool")
    check("plugin is BaseTool instance", isinstance(tools[0], BaseTool))

    # File starting with _ is skipped
    (tmp_plugins / "_private.py").write_text(plugin_code.replace("dummy_tool", "private_tool"),
                                             encoding="utf-8")
    tools2 = load_plugins(tmp_plugins)
    check("_ prefix file skipped (still 1 tool)", len(tools2) == 1)

    # File with bad import should not crash loader
    (tmp_plugins / "broken.py").write_text(
        "import totally_nonexistent_package_xyz\n", encoding="utf-8")
    tools3 = load_plugins(tmp_plugins)
    check("broken plugin doesn't crash loader", True)
    check("broken plugin: only 1 valid tool returned", len(tools3) == 1)

finally:
    shutil.rmtree(tmp_plugins)


# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  Results: {PASS} passed, {FAIL} failed")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
