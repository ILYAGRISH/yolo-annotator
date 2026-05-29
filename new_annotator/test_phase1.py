"""
Phase 1 integration test — runs headless (offscreen) to verify:
  - ProjectController + undo/redo
  - Add/delete annotations via commands
  - Persistence: save → load round-trip
  - Scene rebuild from Annotation objects
  - All three annotation types (SEGMENT, POLYLINE, BBOX)

Run from new_annotator/:
  .venv/Scripts/python test_phase1.py
"""
import os
import sys
import tempfile
from pathlib import Path

# Must set offscreen platform BEFORE creating QApplication
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

# ── imports from annotator package ──────────────────────────────────────────
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.controller.project_controller import ProjectController
from annotator.storage.project_store import ProjectStore
from annotator.domain.label_class import LabelClass
from annotator.ui.canvas.scene import AnnotationScene

# ── helpers ───────────────────────────────────────────────────────────────

PASSED = 0
FAILED = 0

def check(label: str, condition: bool):
    global PASSED, FAILED
    if condition:
        print(f"  PASS  {label}")
        PASSED += 1
    else:
        print(f"  FAIL  {label}")
        FAILED += 1

# ── 1. Controller + undo/redo ────────────────────────────────────────────

print("\n=== 1. ProjectController + undo/redo ===")

with tempfile.TemporaryDirectory() as tmp:
    proj_dir = Path(tmp) / "test.annproj"
    ctrl = ProjectController()
    proj = ctrl.create_project("TestProj", proj_dir)
    check("project created", proj is not None)
    check("project name", ctrl.project.name == "TestProj")

    # Set a fake current image (no actual file needed for undo/add tests)
    ctrl._current_image = "fake_image.jpg"

    seg_ann = Annotation.new(0, AnnotationType.SEGMENT,
                             {"points": [[0.1,0.1],[0.5,0.1],[0.5,0.5],[0.1,0.5]]})
    bbox_ann = Annotation.new(1, AnnotationType.BBOX,
                              {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3})
    poly_ann = Annotation.new(0, AnnotationType.POLYLINE,
                              {"points": [[0.0,0.5],[0.5,0.5],[1.0,0.5]]})

    ctrl.add_annotation(seg_ann)
    ctrl.add_annotation(bbox_ann)
    ctrl.add_annotation(poly_ann)
    check("3 annotations added", len(ctrl.current_annotations) == 3)

    # Undo one
    ctrl.undo_stack.undo()
    check("undo removes polyline", len(ctrl.current_annotations) == 2)

    # Redo
    ctrl.undo_stack.redo()
    check("redo restores polyline", len(ctrl.current_annotations) == 3)

    # Delete via controller
    ctrl.delete_annotation(seg_ann.id)
    check("delete removes segment", len(ctrl.current_annotations) == 2)
    check("segment gone", all(a.id != seg_ann.id for a in ctrl.current_annotations))

    # Undo delete
    ctrl.undo_stack.undo()
    check("undo restores segment", len(ctrl.current_annotations) == 3)

    # Update annotation data
    original_bbox = {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}
    new_bbox = {"x": 0.1, "y": 0.1, "w": 0.4, "h": 0.4}
    ctrl.update_annotation_data(bbox_ann.id, new_bbox, "Move bbox")
    fetched = ctrl.get_annotation(bbox_ann.id)
    check("bbox data updated", fetched.data == new_bbox)

    ctrl.undo_stack.undo()
    fetched_after_undo = ctrl.get_annotation(bbox_ann.id)
    check("undo reverts bbox data", fetched_after_undo.data == original_bbox)

# ── 2. Persistence round-trip ────────────────────────────────────────────

print("\n=== 2. Persistence (save / load) ===")

with tempfile.TemporaryDirectory() as tmp:
    proj_dir = Path(tmp) / "persist.annproj"
    ctrl = ProjectController()
    proj = ctrl.create_project("SaveTest", proj_dir)

    # Add classes
    proj.add_class("cat")

    # Fake image path
    img_path = str(Path(tmp) / "img001.jpg")
    ctrl._current_image = img_path

    seg = Annotation.new(0, AnnotationType.SEGMENT,
                         {"points": [[0.0,0.0],[1.0,0.0],[1.0,1.0],[0.0,1.0]]})
    bbox = Annotation.new(0, AnnotationType.BBOX,
                          {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8})
    ctrl.add_annotation(seg)
    ctrl.add_annotation(bbox)
    check("2 annotations in memory", len(ctrl.current_annotations) == 2)

    # Force flush + save
    ctrl._flush_current_image()
    ProjectStore.save(proj, proj_dir)

    # Load from disk
    loaded_anns = ProjectStore.load_annotations(proj, img_path)
    check("loaded 2 annotations", len(loaded_anns) == 2)

    ids_saved = {a.id for a in ctrl.current_annotations}
    ids_loaded = {a.id for a in loaded_anns}
    check("annotation IDs match", ids_saved == ids_loaded)

    types_loaded = {a.ann_type for a in loaded_anns}
    check("both types present", AnnotationType.SEGMENT in types_loaded
          and AnnotationType.BBOX in types_loaded)

    # Full project reload
    ctrl2 = ProjectController()
    proj2 = ctrl2.open_project(proj_dir)
    check("project reloaded", proj2.name == "SaveTest")

# ── 3. Scene rebuild ──────────────────────────────────────────────────────

print("\n=== 3. AnnotationScene rebuild ===")

scene = AnnotationScene()
proj = Project.create("SceneTest")
proj.add_class("dog")
proj.add_class("cat")

# Provide a real image for scene load test
example_img = Path("d:/Label_segment/Example/10.jpg")
if example_img.exists():
    ok = scene.load_image(str(example_img))
    check(f"image loaded ({scene.image_size})", ok)
else:
    # Fallback: use a minimal 1x1 scene size
    scene._image_size = (416, 416)
    print("  SKIP  image load (Example/10.jpg not found)")

w, h = scene.image_size
anns = [
    Annotation.new(0, AnnotationType.SEGMENT,
                   {"points": [[0.1,0.1],[0.5,0.1],[0.5,0.5]]}),
    Annotation.new(1, AnnotationType.BBOX,
                   {"x": 0.2, "y": 0.2, "w": 0.3, "h": 0.3}),
    Annotation.new(0, AnnotationType.POLYLINE,
                   {"points": [[0.0,0.5],[0.5,0.5],[1.0,0.5]]}),
]
scene.rebuild_annotations(anns, proj)
check("3 items in scene", len(scene._ann_items) == 3)

# Check item ids match annotation ids
for ann in anns:
    check(f"item for {ann.ann_type.value} present", ann.id in scene._ann_items)

# Selection
first_id = anns[0].id
scene.select_by_id(first_id)
check("select_by_id works", scene.get_selected_item() is not None)
check("correct item selected",
      scene.get_selected_item().annotation_id == first_id)

scene.deselect_all()
check("deselect_all works", scene.get_selected_item() is None)

# Selection persists across rebuild
scene.select_by_id(first_id)
scene.rebuild_annotations(anns, proj)
check("selection restored after rebuild",
      scene.get_selected_item() is not None and
      scene.get_selected_item().annotation_id == first_id)

# ── 4. YOLO auto-export ───────────────────────────────────────────────────

print("\n=== 4. YOLO auto-export ===")

from annotator.exporters.yolo_seg import YoloSegExporter

with tempfile.TemporaryDirectory() as tmp:
    # Flat folder: images directly in tmp/
    img_path = str(Path(tmp) / "img001.jpg")
    export_anns = [
        Annotation.new(0, AnnotationType.SEGMENT,
                       {"points": [[0.1,0.1],[0.9,0.1],[0.9,0.9],[0.1,0.9]]}),
        Annotation.new(1, AnnotationType.BBOX,
                       {"x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4}),
        Annotation.new(0, AnnotationType.POLYLINE,
                       {"points": [[0.0,0.5],[0.5,0.7],[1.0,0.5]]}),
    ]
    proj_export = Project.create("ExportTest")
    out = YoloSegExporter.export_image(img_path, export_anns, proj_export)
    check("labels/ dir created", out.parent.name == "labels")
    check("label file created", out.exists())

    lines = out.read_text(encoding="utf-8").splitlines()
    check("3 lines written", len(lines) == 3)

    # SEGMENT line
    seg_line = lines[0].split()
    check("segment: class_id=0", seg_line[0] == "0")
    check("segment: 4 points = 8 coords", len(seg_line) == 1 + 8)

    # BBOX → 4-corner polygon
    bbox_line = lines[1].split()
    check("bbox: class_id=1", bbox_line[0] == "1")
    check("bbox: 4 corners = 8 coords", len(bbox_line) == 1 + 8)

    # POLYLINE
    poly_line = lines[2].split()
    check("polyline: class_id=0", poly_line[0] == "0")
    check("polyline: 3 points = 6 coords", len(poly_line) == 1 + 6)

    # Empty annotations — file written but empty
    out2 = YoloSegExporter.export_image(img_path, [], proj_export)
    check("empty annotations: file exists", out2.exists())
    check("empty annotations: file is empty", out2.read_text() == "")

    # Standard YOLO structure: images/ folder
    images_dir = Path(tmp) / "dataset" / "images"
    images_dir.mkdir(parents=True)
    img_yolo = str(images_dir / "frame01.jpg")
    out3 = YoloSegExporter.export_image(img_yolo, export_anns[:1], proj_export)
    check("standard yolo: labels/ next to images/",
          out3.parent == images_dir.parent / "labels")

# ── summary ───────────────────────────────────────────────────────────────

print(f"\n{'='*40}")
print(f"  Results: {PASSED} passed, {FAILED} failed")
print(f"{'='*40}\n")

if FAILED > 0:
    sys.exit(1)
