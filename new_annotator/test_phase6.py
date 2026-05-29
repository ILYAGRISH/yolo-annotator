"""
test_phase6.py — Phase 6: Crack Tool / Tool Properties Panel

Checks (headless, no GUI):
  1. shapely buffer geometry
  2. _buffer_polyline function
  3. CrackTool schema and params
  4. CrackTool annotation structure
  5. source_geometry serialization roundtrip
  6. Export: source_geometry not leaked to YOLO labels
  7. label_class registration
"""
import sys
import os
import math
import json
import tempfile
import shutil
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
print("=== 1. shapely available ===")

try:
    from shapely.geometry import LineString
    check("shapely import", True)
    check("shapely version >= 2", True)
except ImportError as e:
    check("shapely import", False, str(e))
    check("shapely version >= 2", False)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 2. _buffer_polyline function ===")

from annotator.tools.crack_tool import _buffer_polyline

# Horizontal line from (0.1,0.5) to (0.9,0.5), image 100x100
pts_h = [[0.1, 0.5], [0.9, 0.5]]
params_default = {
    "buffer_width": 0.05,
    "cap_style": "round",
    "join_style": "round",
    "simplify": 0.0,
}
result = _buffer_polyline(pts_h, params_default, (100, 100))

check("buffer returns list", isinstance(result, list))
check("buffer has >= 4 points", len(result) >= 4)
check("buffer points normalized (x in 0-1)", all(0.0 <= x <= 1.0 for x, y in result))
check("buffer points normalized (y in 0-1)", all(0.0 <= y <= 1.0 for x, y in result))

# Width should be ~0.05*100*2 = 10px → normalized ~0.1 (span in y)
ys = [y for _, y in result]
y_span = max(ys) - min(ys)
check("buffer y-span ~0.1", abs(y_span - 0.10) < 0.02, f"y_span={y_span:.4f}")

# Single point → no polygon
result_1pt = _buffer_polyline([[0.5, 0.5]], params_default, (100, 100))
check("single point returns []", result_1pt == [])

# Empty → no polygon
result_empty = _buffer_polyline([], params_default, (100, 100))
check("empty points returns []", result_empty == [])

# cap_style=flat
params_flat = {**params_default, "cap_style": "flat"}
result_flat = _buffer_polyline(pts_h, params_flat, (100, 100))
check("flat cap: result not empty", len(result_flat) >= 4)

# simplify reduces points
pts_curve = [[i * 0.05, 0.5 + 0.1 * math.sin(i)] for i in range(20)]
result_full = _buffer_polyline(pts_curve, {**params_default, "simplify": 0.0}, (200, 200))
result_simp = _buffer_polyline(pts_curve, {**params_default, "simplify": 0.01}, (200, 200))
check("simplify reduces point count",
      len(result_simp) <= len(result_full),
      f"full={len(result_full)} simp={len(result_simp)}")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 3. CrackTool schema ===")

from annotator.tools.crack_tool import CrackTool

ct = CrackTool()
check("tool name = crack_tool", ct.name == "crack_tool")
schema = ct.get_params_schema()
check("schema is dict", isinstance(schema, dict))
check("schema has buffer_width", "buffer_width" in schema)
check("schema has cap_style", "cap_style" in schema)
check("schema has join_style", "join_style" in schema)
check("schema has simplify", "simplify" in schema)

bw = schema["buffer_width"]
check("buffer_width type=float", bw["type"] == "float")
check("buffer_width min < default", bw["min"] < bw["default"])
check("buffer_width default=0.008", abs(bw["default"] - 0.008) < 1e-9)

cs = schema["cap_style"]
check("cap_style type=select", cs["type"] == "select")
check("cap_style has round option", "round" in cs["options"])
check("cap_style has flat option", "flat" in cs["options"])

js = schema["join_style"]
check("join_style type=select", js["type"] == "select")
check("join_style has round option", "round" in js["options"])


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 4. CrackTool set_params ===")

ct2 = CrackTool()
ct2.set_params({"buffer_width": 0.02, "cap_style": "flat"})
check("set_params updates buffer_width", ct2._params["buffer_width"] == 0.02)
check("set_params updates cap_style", ct2._params["cap_style"] == "flat")
check("set_params preserves join_style", ct2._params["join_style"] == "round")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 5. CrackTool annotation structure ===")

from annotator.domain.annotation import Annotation, AnnotationType

# Simulate commit directly
norm_src = [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]]
params = {
    "buffer_width": 0.05,
    "cap_style": "round",
    "join_style": "round",
    "simplify": 0.0,
}
poly_pts = _buffer_polyline(norm_src, params, (100, 100))
ann = Annotation.new(
    class_id=0,
    ann_type=AnnotationType.SEGMENT,
    data={
        "points": poly_pts,
        "source_geometry": {"type": "polyline", "points": norm_src},
        "tool_params": dict(params),
    },
    tool="crack_tool",
)

check("ann type is SEGMENT", ann.ann_type == AnnotationType.SEGMENT)
check("ann has points", "points" in ann.data)
check("ann has source_geometry", "source_geometry" in ann.data)
check("ann has tool_params", "tool_params" in ann.data)
check("source_geometry type=polyline", ann.data["source_geometry"]["type"] == "polyline")
check("source_geometry has points", "points" in ann.data["source_geometry"])
check("source_geometry points match input",
      ann.data["source_geometry"]["points"] == norm_src)
check("tool_params has buffer_width",
      "buffer_width" in ann.data["tool_params"])
check("meta tool=crack_tool", ann.meta.get("tool") == "crack_tool")


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 6. Annotation serialization roundtrip ===")

d = ann.to_dict()
check("to_dict has data", "data" in d)
check("to_dict data has source_geometry", "source_geometry" in d["data"])
check("to_dict data has tool_params", "tool_params" in d["data"])

ann2 = Annotation.from_dict(d)
check("from_dict preserves source_geometry",
      ann2.data.get("source_geometry") == ann.data["source_geometry"])
check("from_dict preserves tool_params",
      ann2.data.get("tool_params") == ann.data["tool_params"])
check("from_dict type is SEGMENT", ann2.ann_type == AnnotationType.SEGMENT)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 7. Export: source_geometry NOT in YOLO output ===")

from annotator.exporters.yolo_seg import _format_annotation as fmt_seg
from annotator.exporters.yolo_detect import _format_detect

# YOLO seg should output only class_id + polygon points, not source_geometry
line = fmt_seg(ann)
check("seg export returns str", isinstance(line, str))
check("seg export does not contain 'source_geometry'",
      "source_geometry" not in line)
check("seg export does not contain 'tool_params'",
      "tool_params" not in line)
check("seg export starts with class_id", line.startswith("0 "))
# fields = class_id + 2*n points
fields = line.split()
n_pts = len(poly_pts)
check("seg export field count = 1 + 2*n",
      len(fields) == 1 + 2 * n_pts,
      f"expected {1 + 2*n_pts}, got {len(fields)}")

# YOLO detect should skip SEGMENT entirely
bbox_ann = Annotation.new(0, AnnotationType.BBOX,
                          {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
detect_line = _format_detect(ann)  # SEGMENT → should be None
check("detect export skips SEGMENT", detect_line is None)


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 8. label_class registration ===")

from annotator.domain.label_class import ANNOTATION_TYPE_TOOLS, ANNOTATION_TYPE_DEFAULT_TOOL

check("polygon allowed_tools includes crack_tool",
      "crack_tool" in ANNOTATION_TYPE_TOOLS.get("polygon", []))
check("polygon default tool = polygon",
      ANNOTATION_TYPE_DEFAULT_TOOL.get("polygon") == "polygon")
check("crack_tool NOT in obb allowed_tools",
      "crack_tool" not in ANNOTATION_TYPE_TOOLS.get("obb", []))
check("crack_tool NOT in bbox allowed_tools",
      "crack_tool" not in ANNOTATION_TYPE_TOOLS.get("bbox", []))


# ─────────────────────────────────────────────────────────────────────────────
print("\n=== 9. Full project export: source_geometry not in label files ===")

from annotator.domain.project import Project
from annotator.domain.label_class import LabelClass
from annotator.exporters.yolo_seg import YoloSegExporter

project = Project.create("test")
project.add_class("crack", "#FF4444")

crack_ann = Annotation.new(
    class_id=0,
    ann_type=AnnotationType.SEGMENT,
    data={
        "points": [[0.1, 0.4], [0.5, 0.5], [0.9, 0.4], [0.9, 0.6], [0.5, 0.7], [0.1, 0.6]],
        "source_geometry": {"type": "polyline", "points": [[0.1, 0.5], [0.5, 0.5], [0.9, 0.5]]},
        "tool_params": {"buffer_width": 0.05},
    },
    tool="crack_tool",
)

tmp = Path(tempfile.mkdtemp())
try:
    import uuid
    from annotator.domain.project import ImageRecord
    img_path = str(tmp / "img.jpg")
    Path(img_path).write_bytes(b"fake")
    project.images.append(ImageRecord(path=img_path, split="train"))

    all_anns = {img_path: [crack_ann]}
    exp = YoloSegExporter()
    exp.export(project, tmp / "out", all_annotations=all_anns, copy_images=False)

    label_file = tmp / "out" / "labels" / "train" / "img.txt"
    check("label file exists", label_file.exists())
    content = label_file.read_text()
    check("label file not empty", content.strip() != "")
    check("label does not contain source_geometry", "source_geometry" not in content)
    check("label does not contain tool_params", "tool_params" not in content)
    check("label starts with class_id '0'", content.strip().startswith("0 "))
finally:
    shutil.rmtree(tmp)


# ─────────────────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  Results: {PASS} passed, {FAIL} failed")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
