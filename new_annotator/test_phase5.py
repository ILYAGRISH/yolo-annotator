"""
Phase 5 regression tests — OBB tool, YOLO exporters, split, data.yaml.
Run: .venv/Scripts/python test_phase5.py
"""
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import LabelClass
from annotator.domain.project import Project, ImageRecord
from annotator.exporters.yolo_detect import YoloDetectExporter, _format_detect
from annotator.exporters.yolo_obb import YoloObbExporter, _format_obb, _rotate_pt
from annotator.exporters.yolo_seg import _format_annotation as _format_seg
from annotator.exporters.base import write_yolo_dataset

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = FAIL = 0


def check(label: str, cond: bool):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


def _bbox_ann(class_id=0, x=0.1, y=0.2, w=0.3, h=0.4) -> Annotation:
    return Annotation.new(class_id, AnnotationType.BBOX,
                          {"x": x, "y": y, "w": w, "h": h})


def _obb_ann(class_id=0, cx=0.5, cy=0.5, w=0.3, h=0.2, angle=0.0) -> Annotation:
    return Annotation.new(class_id, AnnotationType.OBB,
                          {"cx": cx, "cy": cy, "w": w, "h": h, "angle_deg": angle})


def _poly_ann(class_id=0) -> Annotation:
    pts = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]
    return Annotation.new(class_id, AnnotationType.SEGMENT, {"points": pts})


def _project_with_images(n: int, split="train") -> Project:
    p = Project.create("test")
    p.images = [ImageRecord(path=f"/fake/img{i:03d}.jpg", split=split)
                for i in range(n)]
    p.classes = [LabelClass(id=0, name="car", color="#FF0000",
                             annotation_type="bbox")]
    return p


# ── 1. OBB annotation schema ──────────────────────────────────────────────────
print("\n=== 1. OBB annotation schema ===")
ann = _obb_ann(cx=0.5, cy=0.5, w=0.4, h=0.2, angle=30.0)
check("ann_type is OBB",           ann.ann_type == AnnotationType.OBB)
check("data has cx",               "cx" in ann.data)
check("data has angle_deg",        "angle_deg" in ann.data)
check("angle stored correctly",    ann.data["angle_deg"] == 30.0)
check("cx normalized",             0 <= ann.data["cx"] <= 1)
check("serialization roundtrip",
      Annotation.from_dict(ann.to_dict()).data == ann.data)

# ── 2. YOLO detect format ─────────────────────────────────────────────────────
print("\n=== 2. YOLO detect format ===")
b = _bbox_ann(class_id=2, x=0.1, y=0.2, w=0.3, h=0.4)
line = _format_detect(b)
parts = line.split()
check("detect: 5 fields",         len(parts) == 5)
check("detect: class_id=2",       parts[0] == "2")
check("detect: cx = x + w/2",     abs(float(parts[1]) - 0.25) < 1e-5)
check("detect: cy = y + h/2",     abs(float(parts[2]) - 0.40) < 1e-5)
check("detect: w correct",        abs(float(parts[3]) - 0.30) < 1e-5)
check("detect: h correct",        abs(float(parts[4]) - 0.40) < 1e-5)
check("detect: skips polygon",    _format_detect(_poly_ann()) is None)
check("detect: skips obb",        _format_detect(_obb_ann()) is None)

# ── 3. YOLO seg format ────────────────────────────────────────────────────────
print("\n=== 3. YOLO seg format ===")
p = _poly_ann(class_id=1)
seg_line = _format_seg(p)
seg_parts = seg_line.split()
check("seg: class_id=1",          seg_parts[0] == "1")
check("seg: 9 fields (1+4x2)",    len(seg_parts) == 9)
check("seg: skips obb",           _format_seg(_obb_ann()) is None)

# BBOX in seg format: 4-corner polygon (9 fields: class + 8 coords)
b2 = _bbox_ann(class_id=0)
seg_bbox = _format_seg(b2)
check("seg: bbox to 4-corner polygon", len(seg_bbox.split()) == 9)

# ── 4. YOLO OBB format ────────────────────────────────────────────────────────
print("\n=== 4. YOLO OBB format ===")
o = _obb_ann(class_id=3, cx=0.5, cy=0.5, w=0.4, h=0.2, angle=0.0)
obb_line = _format_obb(o)
obb_parts = obb_line.split()
check("obb: 9 fields (1+4x2)",    len(obb_parts) == 9)
check("obb: class_id=3",          obb_parts[0] == "3")
check("obb: skips bbox",          _format_obb(_bbox_ann()) is None)
check("obb: skips polygon",       _format_obb(_poly_ann()) is None)

# At angle=0: TL corner = (cx-w/2, cy-h/2)
x1, y1 = float(obb_parts[1]), float(obb_parts[2])
check("obb angle=0: TL.x = cx-w/2", abs(x1 - 0.3) < 1e-5)
check("obb angle=0: TL.y = cy-h/2", abs(y1 - 0.4) < 1e-5)

# At angle=90° CW: TL should rotate to bottom-left in screen
o90 = _obb_ann(cx=0.5, cy=0.5, w=0.4, h=0.2, angle=90.0)
l90 = _format_obb(o90)
p90 = [float(v) for v in l90.split()[1:]]
# TL_rotated: _rotate_pt(0.5-0.2, 0.5-0.1, 0.5, 0.5, 90) = _rotate_pt(0.3,0.4, ...)
rx, ry = _rotate_pt(0.3, 0.4, 0.5, 0.5, 90.0)
check("obb angle=90: TL rotated x", abs(p90[0] - rx) < 1e-5)
check("obb angle=90: TL rotated y", abs(p90[1] - ry) < 1e-5)

# ── 5. _rotate_pt geometry ────────────────────────────────────────────────────
print("\n=== 5. _rotate_pt geometry ===")
# 90° CW: (1,0) around origin → (0,1)  [screen: right→down]
rx0, ry0 = _rotate_pt(1.0, 0.0, 0.0, 0.0, 90.0)
check("rotate 90deg CW: x~0",      abs(rx0) < 1e-9)
check("rotate 90deg CW: y~1",      abs(ry0 - 1.0) < 1e-9)
# 180: (1,0) -> (-1,0)
rx1, ry1 = _rotate_pt(1.0, 0.0, 0.0, 0.0, 180.0)
check("rotate 180deg: x~-1",       abs(rx1 + 1.0) < 1e-9)
check("rotate 180deg: y~0",        abs(ry1) < 1e-9)

# ── 6. OBB canvas item geometry ───────────────────────────────────────────────
print("\n=== 6. OBB canvas item geometry ===")
from annotator.ui.canvas.items.obb_item import OBBAnnotationItem, _rotate

item = OBBAnnotationItem("id1", 100, 100, 80, 40, 0.0, "#FF0000", "car")
corners = item._corners()
check("4 corners at angle=0",     len(corners) == 4)
check("TL.x = cx-w/2",           abs(corners[0][0] - 60) < 1e-9)
check("TL.y = cy-h/2",           abs(corners[0][1] - 80) < 1e-9)
check("BR.x = cx+w/2",           abs(corners[2][0] - 140) < 1e-9)
check("BR.y = cy+h/2",           abs(corners[2][1] - 120) < 1e-9)

# Rotation handle: directly above at angle=0
from annotator.ui.canvas.items.obb_item import ROTATION_OFFSET
rx, ry = item._rot_handle_pos()
check("rot handle: x = cx",       abs(rx - 100) < 1e-9)
check("rot handle: y = cy-h/2-offset", abs(ry - (100 - 20 - ROTATION_OFFSET)) < 1e-9)

# ── 7. OBB item handle_at + move_handle ──────────────────────────────────────
print("\n=== 7. OBB item handle_at + move_handle ===")
from PyQt6.QtCore import QPointF

item2 = OBBAnnotationItem("id2", 200, 200, 100, 60, 0.0, "#0000FF", "obj")

# handle_at on rotation handle
rx2, ry2 = item2._rot_handle_pos()
h_idx = item2.handle_at(QPointF(rx2, ry2))
check("handle_at rot handle = 0",  h_idx == 0)

# handle_at on TL corner
c = item2._corners()
h_tl = item2.handle_at(QPointF(c[0][0], c[0][1]))
check("handle_at TL corner = 1",   h_tl == 1)

# move rotation handle → changes angle
from PyQt6.QtCore import QPointF
item3 = OBBAnnotationItem("id3", 100, 100, 80, 40, 0.0, "#FF0000")
# Move rotation handle to the right of center → angle=90°
item3.move_handle(0, QPointF(200, 100))  # directly to the right
check("rotation: angle~90deg",      abs(item3._angle - 90.0) < 1e-9)

# move TL corner → resizes OBB
item4 = OBBAnnotationItem("id4", 100, 100, 80, 40, 0.0, "#FF0000")
old_cx = item4._cx
# Drag TL closer to center (effectively shrink)
item4.move_handle(1, QPointF(80, 90))
check("resize: w shrunk",          item4._w < 80)
check("resize: h shrunk",          item4._h < 40)

# ── 8. OBB item to_data / update_from_data ───────────────────────────────────
print("\n=== 8. OBB item to_data / update_from_data ===")
item5 = OBBAnnotationItem("id5", 100, 200, 80, 40, 45.0, "#FF0000")
data = item5.to_data((1000, 500))
check("to_data cx normalized",     abs(data["cx"] - 0.1) < 1e-9)
check("to_data cy normalized",     abs(data["cy"] - 0.4) < 1e-9)
check("to_data w normalized",      abs(data["w"] - 0.08) < 1e-9)
check("to_data h normalized",      abs(data["h"] - 0.08) < 1e-9)
check("to_data angle preserved",   data["angle_deg"] == 45.0)

item6 = OBBAnnotationItem("id6", 0, 0, 1, 1, 0.0, "#FF0000")
item6.update_from_data({"cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.2, "angle_deg": 30.0},
                        (100, 100))
check("update_from_data cx",       abs(item6._cx - 50) < 1e-9)
check("update_from_data angle",    item6._angle == 30.0)

# ── 9. Full dataset export — YOLO detect ─────────────────────────────────────
print("\n=== 9. Full export: YOLO detect ===")
tmp = Path(tempfile.mkdtemp())
try:
    proj = _project_with_images(2)
    all_anns = {
        "/fake/img000.jpg": [_bbox_ann(class_id=0, x=0.1, y=0.1, w=0.3, h=0.3)],
        "/fake/img001.jpg": [_poly_ann()],  # polygon — should be skipped
    }
    YoloDetectExporter().export(proj, tmp / "detect",
                                all_annotations=all_anns, copy_images=False)
    lbl0 = (tmp / "detect/labels/train/img000.txt").read_text()
    lbl1 = (tmp / "detect/labels/train/img001.txt").read_text()
    check("detect: img000 has 1 line",    len(lbl0.strip().splitlines()) == 1)
    check("detect: img001 empty (poly)",  lbl1.strip() == "")
    check("detect: data.yaml exists",     (tmp / "detect/data.yaml").exists())
    yaml_text = (tmp / "detect/data.yaml").read_text()
    check("detect: yaml has nc",          "nc:" in yaml_text)
    check("detect: yaml has names",       "names:" in yaml_text)
    check("detect: yaml has train",       "train:" in yaml_text)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── 10. Full dataset export — YOLO OBB ───────────────────────────────────────
print("\n=== 10. Full export: YOLO obb ===")
tmp2 = Path(tempfile.mkdtemp())
try:
    proj2 = _project_with_images(1)
    all_anns2 = {"/fake/img000.jpg": [_obb_ann(class_id=0, angle=45.0)]}
    YoloObbExporter().export(proj2, tmp2 / "obb",
                             all_annotations=all_anns2, copy_images=False)
    lbl = (tmp2 / "obb/labels/train/img000.txt").read_text().strip()
    parts = lbl.split()
    check("obb export: 9 fields",         len(parts) == 9)
    check("obb export: class_id=0",       parts[0] == "0")
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

# ── 11. Full dataset export — YOLO seg ───────────────────────────────────────
print("\n=== 11. Full export: YOLO seg ===")
tmp3 = Path(tempfile.mkdtemp())
try:
    proj3 = _project_with_images(1)
    all_anns3 = {"/fake/img000.jpg": [_poly_ann(), _bbox_ann()]}
    from annotator.exporters.yolo_seg import YoloSegExporter
    YoloSegExporter().export(proj3, tmp3 / "seg",
                             all_annotations=all_anns3, copy_images=False)
    lbl = (tmp3 / "seg/labels/train/img000.txt").read_text().strip()
    lines = lbl.splitlines()
    check("seg export: 2 lines",          len(lines) == 2)
finally:
    shutil.rmtree(tmp3, ignore_errors=True)

# ── 12. Train/val/test split in export ───────────────────────────────────────
print("\n=== 12. Split export ===")
tmp4 = Path(tempfile.mkdtemp())
try:
    proj4 = Project.create("split_test")
    proj4.images = [
        ImageRecord(path="/fake/train.jpg", split="train"),
        ImageRecord(path="/fake/val.jpg",   split="val"),
        ImageRecord(path="/fake/test.jpg",  split="test"),
    ]
    proj4.classes = [LabelClass(id=0, name="car", color="#FF0000",
                                annotation_type="bbox")]
    all_anns4 = {
        "/fake/train.jpg": [_bbox_ann()],
        "/fake/val.jpg":   [_bbox_ann()],
        "/fake/test.jpg":  [_bbox_ann()],
    }
    write_yolo_dataset(proj4, all_anns4, tmp4 / "split",
                       _format_detect, copy_images=False)
    check("split: labels/train exists",   (tmp4 / "split/labels/train/train.txt").exists())
    check("split: labels/val exists",     (tmp4 / "split/labels/val/val.txt").exists())
    check("split: labels/test exists",    (tmp4 / "split/labels/test/test.txt").exists())
    yaml = (tmp4 / "split/data.yaml").read_text()
    check("split: yaml has val",          "val: images/val" in yaml)
    check("split: yaml has test",         "test: images/test" in yaml)
finally:
    shutil.rmtree(tmp4, ignore_errors=True)

# ── 13. data.yaml content ────────────────────────────────────────────────────
print("\n=== 13. data.yaml content ===")
tmp5 = Path(tempfile.mkdtemp())
try:
    proj5 = Project.create("yaml_test")
    proj5.images = [ImageRecord(path="/fake/img.jpg", split="train")]
    proj5.classes = [
        LabelClass(id=0, name="cat", color="#FF0000", annotation_type="bbox"),
        LabelClass(id=1, name="dog", color="#00FF00", annotation_type="bbox"),
    ]
    write_yolo_dataset(proj5, {"/fake/img.jpg": []}, tmp5,
                       _format_detect, copy_images=False)
    yaml = (tmp5 / "data.yaml").read_text()
    check("yaml: nc=2",            "nc: 2" in yaml)
    check("yaml: cat in names",    "cat" in yaml)
    check("yaml: dog in names",    "dog" in yaml)
    check("yaml: path line",       "path:" in yaml)
finally:
    shutil.rmtree(tmp5, ignore_errors=True)

# ── 14. Controller export_dataset ────────────────────────────────────────────
print("\n=== 14. Controller export_dataset ===")
from annotator.controller.project_controller import ProjectController

tmp6 = Path(tempfile.mkdtemp())
try:
    ctrl = ProjectController()
    ctrl.create_project("ctrl_export", tmp6 / "proj.annproj")
    ctrl._project.images = [ImageRecord(path=str(tmp6 / "img.jpg"), split="train")]
    ctrl._current_image = str(tmp6 / "img.jpg")
    ctrl._annotations = [_bbox_ann()]

    out = tmp6 / "export_out"
    ctrl.export_dataset(out, "yolo_detect", copy_images=False)
    check("ctrl: labels dir exists",   (out / "labels/train").exists())
    check("ctrl: data.yaml exists",    (out / "data.yaml").exists())

    # type counts
    counts = ctrl.get_annotation_type_counts()
    check("ctrl: counts has bbox",     "bbox" in counts)
    check("ctrl: bbox count = 1",      counts["bbox"] == 1)
finally:
    shutil.rmtree(tmp6, ignore_errors=True)

# ── 15. OBB tool creates correct annotation ───────────────────────────────────
print("\n=== 15. OBB tool creates correct annotation ===")
from annotator.tools.obb_tool import OBBTool
from annotator.domain.label_class import ANNOTATION_TYPE_DEFAULT_TOOL, ANNOTATION_TYPE_TOOLS

tool = OBBTool()
check("obb tool name",             tool.name == "obb")
check("ANNOTATION_TYPE_TOOLS obb has obb", "obb" in ANNOTATION_TYPE_TOOLS.get("obb", []))
check("ANNOTATION_TYPE_DEFAULT_TOOL obb = obb",
      ANNOTATION_TYPE_DEFAULT_TOOL.get("obb") == "obb")

# ── summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  Results: {PASS} passed, {FAIL} failed")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
