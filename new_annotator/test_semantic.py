"""
Semantic mode tests — SEMANTIC layers, SemanticBrushTool, exporters
Run: .venv/Scripts/python test_semantic.py
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import numpy as np
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


# ═════════════════════════════════════════════════════════════════════════════
# §1  compose_stroke — layer merge rules
# ═════════════════════════════════════════════════════════════════════════════
section("1. compose_stroke")

from annotator.tools.semantic_tool import compose_stroke

H, W = 20, 30
def box(x0, y0, x1, y1):
    m = np.zeros((H, W), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m
def layer(m):
    return (m * 255).astype(np.uint8)

road = layer(box(0, 0, 15, 20))
changed = compose_stroke({}, box(5, 5, 10, 10), class_id=1)
check("new class layer created", set(changed) == {1} and changed[1][7, 7] == 255)

changed = compose_stroke({0: road}, box(10, 5, 20, 10), class_id=1)
check("overwrite: both layers change", set(changed) == {0, 1})
check("overwrite: pixel moved to new class",
      changed[1][7, 12] == 255 and changed[0][7, 12] == 0)
check("overwrite: rest of old layer intact", changed[0][0, 0] == 255)

changed = compose_stroke({0: road}, box(10, 5, 20, 10), class_id=1, overlap="keep")
check("keep: other layer untouched", set(changed) == {1})
check("keep: paints only unlabeled pixels",
      changed[1][7, 12] == 0 and changed[1][7, 17] == 255)

changed = compose_stroke({0: road}, box(0, 0, 5, 5), class_id=1, overlap="keep")
check("keep: fully occupied stroke -> no change", changed == {})

changed = compose_stroke({0: road}, box(0, 0, 5, 5), class_id=0)
check("same class repaint over own pixels -> no change", changed == {})

sky = layer(box(20, 0, 30, 20))
changed = compose_stroke({0: road, 2: sky}, box(10, 0, 25, 20), class_id=0, mode="erase")
check("erase: unlabels every class", set(changed) == {0, 2})
check("erase: pixels cleared",
      changed[0][5, 12] == 0 and changed[2][5, 22] == 0 and changed[2][5, 27] == 255)

changed = compose_stroke({0: road}, box(0, 0, 15, 20), class_id=0, mode="erase")
check("erase whole layer -> returned empty", not changed[0].any())


# ═════════════════════════════════════════════════════════════════════════════
# §2  MaskStorage helpers
# ═════════════════════════════════════════════════════════════════════════════
section("2. MaskStorage")

from annotator.storage.mask_storage import MaskStorage

tmp_store = Path(tempfile.mkdtemp())
st = MaskStorage(tmp_store)

two = np.zeros((100, 200), dtype=np.uint8)
two[10:40, 10:40] = 255       # 900 px
two[50:90, 100:190] = 255     # 3600 px (largest)
two[0, 199] = 255             # 1 px speck -> dropped
polys = st.mask_to_polygons(two, 200, 100)
check("mask_to_polygons: every region", len(polys) == 2)
check("mask_to_polygons: largest first", min(p[0] for p in polys[0]) > 0.45)
check("mask_to_polygon (legacy) keeps largest only",
      len(st.mask_to_polygon(two, 200, 100)) >= 3)

d = st.semantic_data("img", 3, two, 200, 100)
check("semantic_data keys", set(d) == {"mask_png_path", "polygons", "bbox", "area"})
check("semantic_data path pattern", d["mask_png_path"].startswith("masks/img_sem3_"))
check("semantic_data area", abs(d["area"] - (900 + 3600 + 1) / 20000) < 1e-9)
d2 = st.semantic_data("img", 3, two, 200, 100)
check("every save gets a fresh file", d2["mask_png_path"] != d["mask_png_path"])

cached = st.load_mask_cached(d["mask_png_path"])
check("cached load equals bitmap", np.array_equal(cached, two))
check("cached array is read-only", not cached.flags.writeable)
check("cache returns same object", st.load_mask_cached(d["mask_png_path"]) is cached)
check("missing file -> None", st.load_mask_cached("masks/nope.png") is None)
shutil.rmtree(tmp_store, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# §3  Domain
# ═════════════════════════════════════════════════════════════════════════════
section("3. Domain")

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import (ANNOTATION_TYPES, ANNOTATION_TYPE_TOOLS,
                                          ANNOTATION_TYPE_DEFAULT_TOOL)
from annotator.domain.project import DEFAULT_HOTKEYS

a = Annotation.new(2, AnnotationType.SEMANTIC, {"mask_png_path": "masks/x.png",
                                               "polygons": [], "bbox": [], "area": 0.0})
check("SEMANTIC round-trip",
      Annotation.from_dict(json.loads(json.dumps(a.to_dict()))).ann_type
      == AnnotationType.SEMANTIC)
check("'semantic' class type registered", "semantic" in ANNOTATION_TYPES)
check("semantic -> semantic_brush tool",
      ANNOTATION_TYPE_TOOLS["semantic"] == ["semantic_brush"]
      and ANNOTATION_TYPE_DEFAULT_TOOL["semantic"] == "semantic_brush")
check("hotkey S", DEFAULT_HOTKEYS.get("tool_semantic") == "S")


# ═════════════════════════════════════════════════════════════════════════════
# §4  SemanticBrushTool end-to-end (controller + scene)
# ═════════════════════════════════════════════════════════════════════════════
section("4. SemanticBrushTool")

from annotator.controller.project_controller import ProjectController
from annotator.ui.canvas.scene import AnnotationScene
from annotator.tools.semantic_tool import SemanticBrushTool

tmp = Path(tempfile.mkdtemp())
img_path = tmp / "street.png"
Image.new("RGB", (200, 100), (90, 90, 90)).save(img_path)

ctrl = ProjectController()
proj = ctrl.create_project("sem", tmp / "proj")
proj.classes[0].name = "road"
proj.classes[0].annotation_type = "semantic"
sky_cls = proj.add_class("sky");   sky_cls.annotation_type = "semantic"
car_cls = proj.add_class("car");   car_cls.annotation_type = "mask"
ctrl.add_images_from_paths([str(img_path)])
ctrl.set_image(str(img_path))

scene = AnnotationScene()
scene.load_image(str(img_path))
ctrl.annotations_changed.connect(lambda anns: scene.rebuild_annotations(anns, ctrl.project))

tool = SemanticBrushTool()
scene.set_tool(tool, ctrl)
tool.set_params({"brush_size": 10, "mode": "draw", "overlap": "overwrite"})

def stroke(pts):
    tool.on_press(QPointF(*pts[0]), NOMOD, LB)
    for p in pts[1:]:
        tool.on_move(QPointF(*p), NOMOD)
    tool.on_release(QPointF(*pts[-1]), NOMOD, LB)

def sem_anns():
    return [a for a in ctrl.current_annotations if a.ann_type == AnnotationType.SEMANTIC]

def bitmap(ann):
    return MaskStorage(ctrl.project.project_path).load_mask(ann.data["mask_png_path"])

tool.set_class(0)
stroke([(20, 50), (80, 50)])
check("stroke -> one SEMANTIC annotation", len(sem_anns()) == 1)
stroke([(20, 20), (20, 80)])
check("second stroke merges into same layer", len(sem_anns()) == 1)
road_ann = sem_anns()[0]
bm = bitmap(road_ann)
check("layer covers both strokes", bm[50, 60] == 255 and bm[25, 20] == 255)
check("polygons stored", len(road_ann.data["polygons"]) >= 1)
check("preview removed after stroke", tool._preview is None)

stroke([(150, 20), (190, 20)])
check("disconnected stroke -> still one layer", len(sem_anns()) == 1)
check("...with two regions", len(sem_anns()[0].data["polygons"]) == 2)

tool.set_class(sky_cls.id)
stroke([(60, 50), (100, 50)])            # overlaps road at x≈60..90
anns = {a.class_id: a for a in sem_anns()}
check("second class -> second layer", set(anns) == {0, sky_cls.id})
road_bm, sky_bm = bitmap(anns[0]), bitmap(anns[sky_cls.id])
check("overwrite moved overlap to sky", sky_bm[50, 70] == 255 and road_bm[50, 70] == 0)
check("layers never overlap", not ((road_bm > 0) & (sky_bm > 0)).any())

ctrl.undo_stack.undo()
anns = {a.class_id: a for a in sem_anns()}
check("undo removes whole stroke in one step", set(anns) == {0})
check("undo restores road pixels", bitmap(anns[0])[50, 70] == 255)
ctrl.undo_stack.redo()
check("redo re-applies", len(sem_anns()) == 2)

tool.set_params({"overlap": "keep"})
stroke([(20, 50), (40, 50)])             # fully inside road
check("keep mode over foreign pixels -> no-op",
      len(sem_anns()) == 2 and ctrl.undo_stack.count() == 4)
tool.set_params({"overlap": "overwrite"})

tool.set_params({"mode": "erase"})
stroke([(150, 20), (190, 20)])
road = next(a for a in sem_anns() if a.class_id == 0)
check("erase removes a region", len(road.data["polygons"]) == 1)
tool.set_params({"mode": "draw"})

n_before = len(ctrl.current_annotations)
tool.set_class(car_cls.id)
stroke([(10, 10), (20, 10)])
check("non-semantic class -> tool does nothing", len(ctrl.current_annotations) == n_before)

tool.set_class(0)
tool.on_press(QPointF(10, 90), NOMOD, LB)
tool.on_move(QPointF(40, 90), NOMOD)
tool.on_key_press(Qt.Key.Key_Escape, NOMOD)
tool.on_release(QPointF(40, 90), NOMOD, LB)
check("Esc cancels stroke", len(ctrl.current_annotations) == n_before)


# ═════════════════════════════════════════════════════════════════════════════
# §5  Scene item
# ═════════════════════════════════════════════════════════════════════════════
section("5. SemanticAnnotationItem")

from annotator.ui.canvas.items.semantic_item import SemanticAnnotationItem

# an instance MASK of "car" on top of the sky layer
car_bm = np.zeros((100, 200), dtype=np.uint8)
car_bm[45:55, 70:80] = 255
st = MaskStorage(ctrl.project.project_path)
car = Annotation.new(car_cls.id, AnnotationType.MASK, {
    "mask_png_path": st.save_mask("carid", "street", car_bm),
    "polygon": st.mask_to_polygon(car_bm, 200, 100),
    "bbox": st.mask_to_bbox(car_bm, 200, 100)})
ctrl.add_annotation(car)

sem_items = [i for i in scene._ann_items.values() if isinstance(i, SemanticAnnotationItem)]
check("scene builds semantic items", len(sem_items) == 2)
check("semantic items under instances",
      all(i.zValue() < scene._ann_items[car.id].zValue() for i in sem_items))
hit = scene.annotation_item_at(QPointF(75, 50))
check("click on car picks the instance", hit is not None and hit.annotation_id == car.id)
hit = scene.annotation_item_at(QPointF(95, 50))
check("click on sky picks sky layer",
      hit is not None and ctrl.get_annotation(hit.annotation_id).class_id == sky_cls.id)
hit = scene.annotation_item_at(QPointF(195, 95))
check("click on unlabeled pixel picks nothing", hit is None)


# ═════════════════════════════════════════════════════════════════════════════
# §6  Exporters
# ═════════════════════════════════════════════════════════════════════════════
section("6. Exporters")

ctrl.save_project()
ctrl._flush_current_image()
out = tmp / "out"

ctrl.export_dataset(out / "masks_idx", "semantic_masks", mask_mode="index")
m = np.array(Image.open(out / "masks_idx" / "masks" / "train" / "street.png"))
idx = {c.id: i + 1 for i, c in enumerate(ctrl.project.classes)}
check("masks: road pixel", m[25, 20] == idx[0])
check("masks: sky pixel", m[50, 95] == idx[sky_cls.id])
check("masks: car (thing) drawn over sky (stuff)", m[50, 75] == idx[car_cls.id])
check("masks: unlabeled = 0", m[95, 195] == 0)

# MASK with two disconnected blobs is exported pixel-exact from its PNG
blob2 = np.zeros((100, 200), dtype=np.uint8)
blob2[5:15, 5:15] = 255
blob2[80:95, 180:195] = 255
ann2 = Annotation.new(car_cls.id, AnnotationType.MASK, {
    "mask_png_path": st.save_mask("blobid", "street", blob2),
    "polygon": st.mask_to_polygon(blob2, 200, 100),
    "bbox": st.mask_to_bbox(blob2, 200, 100)})
ctrl.add_annotation(ann2)
ctrl._flush_current_image()
ctrl.export_dataset(out / "masks_bin", "semantic_masks", mask_mode="binary")
m = np.array(Image.open(out / "masks_bin" / "masks" / "train" / "street.png"))
check("masks: both blobs of a MASK exported", m[10, 10] == 255 and m[88, 188] == 255)

ctrl.export_dataset(out / "yseg", "yolo_seg")
lines = (out / "yseg" / "labels" / "train" / "street.txt").read_text().splitlines()
sem_lines = [ln for ln in lines if ln.split()[0] in ("0", str(sky_cls.id))]
check("yolo_seg: one line per semantic region",
      len(sem_lines) == sum(len(a.data["polygons"]) for a in sem_anns()))

ctrl.export_dataset(out / "coco", "coco")
coco_json = next((out / "coco").rglob("*.json"))
coco = json.loads(coco_json.read_text(encoding="utf-8"))
sky_c = [a for a in coco["annotations"] if a["category_id"] == sky_cls.id]
check("coco: semantic layer exported", len(sky_c) == 1 and len(sky_c[0]["segmentation"]) >= 1)
check("coco: area in pixels", sky_c[0]["area"] > 100)

ctrl.export_dataset(out / "lm", "labelme")
lm = json.loads(next((out / "lm").rglob("*.json")).read_text(encoding="utf-8"))
check("labelme: road/sky polygons present",
      {"road", "sky"} <= {s["label"] for s in lm["shapes"]})

ctrl.export_dataset(out / "det", "yolo_detect", geometry_policy="convert")
det = (out / "det" / "labels" / "train" / "street.txt").read_text().splitlines()
check("yolo_detect convert: MASK bbox list no longer crashes",
      sum(1 for ln in det if ln.split()[0] == str(car_cls.id)) == 2)
check("yolo_detect: semantic layers skipped",
      not any(ln.split()[0] in ("0", str(sky_cls.id)) for ln in det))

scene.set_tool(__import__("annotator.tools.select_tool", fromlist=["SelectTool"]).SelectTool(), ctrl)
shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
