"""
Phase 4 regression tests - Validation, QC, dataset statistics.
Run: .venv/Scripts/python test_phase4.py
"""
import os
import sys
import json
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── bootstrap Qt (headless) ──────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import LabelClass
from annotator.domain.project import Project, ImageRecord
from annotator.validation.base import ValidationReport
from annotator.validation.rules.empty_image import EmptyImageRule
from annotator.validation.rules.small_polygon import SmallPolygonRule
from annotator.validation.rules.duplicate import DuplicateAnnotationRule
from annotator.validation.validator import Validator

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = 0
FAIL = 0

def check(label: str, cond: bool):
    global PASS, FAIL
    if cond:
        print(f"  PASS  {label}")
        PASS += 1
    else:
        print(f"  FAIL  {label}")
        FAIL += 1


def _project_with_images(n: int) -> Project:
    p = Project.create("test")
    p.images = [ImageRecord(path=f"/fake/img{i:03d}.jpg") for i in range(n)]
    return p


def _bbox_ann(class_id=0, x=0.1, y=0.1, w=0.3, h=0.3) -> Annotation:
    return Annotation.new(class_id, AnnotationType.BBOX,
                          {"x": x, "y": y, "w": w, "h": h})


def _poly_ann(class_id=0, pts=None) -> Annotation:
    if pts is None:
        pts = [[0.1,0.1],[0.5,0.1],[0.5,0.5],[0.1,0.5]]
    return Annotation.new(class_id, AnnotationType.SEGMENT, {"points": pts})


# ── 1. EmptyImageRule ─────────────────────────────────────────────────────────
print("\n=== 1. EmptyImageRule ===")
proj = _project_with_images(3)
all_anns = {
    "/fake/img000.jpg": [_bbox_ann()],
    "/fake/img001.jpg": [],
    "/fake/img002.jpg": [],
}
rule = EmptyImageRule()
issues = rule.check(proj, all_anns)
check("2 empty images detected", len(issues) == 2)
check("severity is warning", all(i.severity == "warning" for i in issues))
check("ann_id is empty string", all(i.ann_id == "" for i in issues))

# ── 2. SmallPolygonRule ───────────────────────────────────────────────────────
print("\n=== 2. SmallPolygonRule ===")
proj2 = _project_with_images(1)
# Tiny polygon (area ≈ 0.0002)
tiny_pts = [[0.01,0.01],[0.03,0.01],[0.03,0.02],[0.01,0.02]]
# Normal polygon (area ≈ 0.16)
big_pts  = [[0.1,0.1],[0.5,0.1],[0.5,0.5],[0.1,0.5]]
all_anns2 = {
    "/fake/img000.jpg": [
        _poly_ann(pts=tiny_pts),
        _poly_ann(pts=big_pts),
    ]
}
rule2 = SmallPolygonRule(min_area=0.001)
issues2 = rule2.check(proj2, all_anns2)
check("1 small polygon detected", len(issues2) == 1)
check("ann_id is set", issues2[0].ann_id != "")

# BBOX annotations not flagged
all_anns2b = {"/fake/img000.jpg": [_bbox_ann()]}
check("bbox not flagged by SmallPolygon", len(rule2.check(proj2, all_anns2b)) == 0)

# ── 3. DuplicateAnnotationRule ────────────────────────────────────────────────
print("\n=== 3. DuplicateAnnotationRule ===")
proj3 = _project_with_images(1)
# Two nearly identical bboxes (IoU ≈ 0.96)
ann_a = _bbox_ann(class_id=0, x=0.1, y=0.1, w=0.3, h=0.3)
ann_b = _bbox_ann(class_id=0, x=0.11, y=0.11, w=0.3, h=0.3)
ann_c = _bbox_ann(class_id=1, x=0.1, y=0.1, w=0.3, h=0.3)  # different class
rule3 = DuplicateAnnotationRule(iou_threshold=0.85)
all_anns3 = {"/fake/img000.jpg": [ann_a, ann_b, ann_c]}
issues3 = rule3.check(proj3, all_anns3)
check("1 duplicate detected (same class)", len(issues3) == 1)
check("different class not flagged", issues3[0].ann_id == ann_b.id)

# No duplicates on well-separated boxes
ann_d = _bbox_ann(class_id=0, x=0.7, y=0.7, w=0.1, h=0.1)
check("non-overlapping not flagged",
      len(rule3.check(proj3, {"/fake/img000.jpg": [ann_a, ann_d]})) == 0)

# ── 4. Validator + stats ──────────────────────────────────────────────────────
print("\n=== 4. Validator + stats ===")
proj4 = _project_with_images(4)
proj4.classes = [
    LabelClass(id=0, name="car",  color="#FF0000", annotation_type="bbox"),
    LabelClass(id=1, name="road", color="#00FF00", annotation_type="polygon"),
]
all_anns4 = {
    "/fake/img000.jpg": [_bbox_ann(class_id=0), _bbox_ann(class_id=0)],
    "/fake/img001.jpg": [_poly_ann(class_id=1)],
    "/fake/img002.jpg": [],
    "/fake/img003.jpg": [],
}
report = Validator().run(proj4, all_anns4)
s = report.stats
check("total_images = 4",          s["total_images"] == 4)
check("annotated_images = 2",      s["annotated_images"] == 2)
check("unannotated_images = 2",    s["unannotated_images"] == 2)
check("coverage_pct = 50.0",       s["coverage_pct"] == 50.0)
check("total_annotations = 3",     s["total_annotations"] == 3)
check("by_class car=2",            s["by_class"].get("car") == 2)
check("by_class road=1",           s["by_class"].get("road") == 1)
check("by_type bbox=2",            s["by_type"].get("bbox") == 2)
check("by_type segment=1",         s["by_type"].get("segment") == 1)
check("2 empty-image warnings",    report.warning_count >= 2)
check("error_count = 0",           report.error_count == 0)

# ── 5. Export JSON ────────────────────────────────────────────────────────────
print("\n=== 5. Export JSON / CSV ===")
tmp = Path(tempfile.mkdtemp())
try:
    json_path = tmp / "report.json"
    Validator.export_json(report, json_path, "test_project")
    with open(json_path) as f:
        data = json.load(f)
    check("json has project field",  data.get("project") == "test_project")
    check("json has stats",          "stats" in data)
    check("json has issues list",    isinstance(data.get("issues"), list))

    csv_path = tmp / "report.csv"
    Validator.export_csv(report, csv_path)
    lines = csv_path.read_text().splitlines()
    check("csv header correct",      lines[0].startswith("severity,rule,image"))
    check("csv has data rows",       len(lines) > 1)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ── 6. Controller integration ─────────────────────────────────────────────────
print("\n=== 6. Controller run_validation ===")
from annotator.controller.project_controller import ProjectController
from PyQt6.QtCore import QCoreApplication

tmp2 = Path(tempfile.mkdtemp())
try:
    ctrl = ProjectController()
    ctrl.create_project("ctrl_test", tmp2 / "ctrl_test.annproj")

    # Add a fake image path (file doesn't need to exist for validation)
    ctrl._project.images = [
        ImageRecord(path=str(tmp2 / "img1.jpg")),
        ImageRecord(path=str(tmp2 / "img2.jpg")),
    ]
    ctrl._current_image = str(tmp2 / "img1.jpg")
    ctrl._annotations = [_bbox_ann()]

    report2 = ctrl.run_validation()
    check("controller returns ValidationReport",
          isinstance(report2, ValidationReport))
    check("stats total_images=2",   report2.stats["total_images"] == 2)
    check("annotated=1 (in-memory)", report2.stats["annotated_images"] == 1)
    check("1 empty-image issue",
          sum(1 for i in report2.issues if i.rule_name == "EmptyImage") == 1)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

# ── summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  Results: {PASS} passed, {FAIL} failed")
print(f"{'='*40}")
sys.exit(0 if FAIL == 0 else 1)
