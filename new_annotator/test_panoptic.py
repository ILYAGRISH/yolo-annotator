"""
Panoptic phase tests — thing/stuff roles, COCO RLE, COCO Panoptic, mask cleanup
Run: .venv/Scripts/python test_panoptic.py
"""
import os
import sys
import json
import time
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
# keep app settings (language, recent projects) away from the real user ones
os.environ["ANNOTATOR_SETTINGS"] = str(Path(tempfile.mkdtemp()) / "settings.ini")

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

import numpy as np
from PIL import Image

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
# §1  Panoptic role
# ═════════════════════════════════════════════════════════════════════════════
section("1. Panoptic role")

from annotator.domain.label_class import LabelClass

check("auto: semantic -> stuff", LabelClass(0, "a", "#fff", "semantic").is_stuff)
check("auto: mask -> thing", not LabelClass(0, "a", "#fff", "mask").is_stuff)
check("override: polygon as stuff",
      LabelClass(0, "a", "#fff", "polygon", panoptic_role="stuff").is_stuff)
check("override: semantic as thing",
      not LabelClass(0, "a", "#fff", "semantic", panoptic_role="thing").is_stuff)
lc = LabelClass.from_dict(LabelClass(0, "a", "#fff", "bbox", panoptic_role="stuff").to_dict())
check("role survives round-trip", lc.panoptic_role == "stuff")
check("old schema without role -> auto",
      LabelClass.from_dict({"id": 1, "name": "x"}).panoptic_role == "auto")


# ═════════════════════════════════════════════════════════════════════════════
# §2  RLE codec
# ═════════════════════════════════════════════════════════════════════════════
section("2. RLE codec")

from annotator.exporters.raster import (rle_encode, rle_decode, _counts_to_string,
                                        _string_to_counts, _run_lengths)

check("counts [3,4,2,1] -> '342M' (pycocotools vector)",
      _counts_to_string([3, 4, 2, 1]) == "342M")
check("string -> counts", _string_to_counts("342M") == [3, 4, 2, 1])
m = np.array([[1, 0], [0, 0]], dtype=bool)
check("runs start with object -> leading 0", _run_lengths(m) == [0, 1, 3])
m = np.array([[0, 1], [0, 1]], dtype=bool)
check("column-major order", _run_lengths(m) == [2, 2])
rng = np.random.default_rng(7)
ok = True
for _ in range(100):
    h, w = rng.integers(1, 60, 2)
    mk = rng.random((h, w)) < rng.random()
    ok &= np.array_equal(rle_decode(rle_encode(mk)), mk)
check("round-trip on 100 random masks", ok)
big = np.zeros((300, 400), dtype=bool); big[10:290, 5:395] = True
check("large runs (multi-chunk values)", np.array_equal(rle_decode(rle_encode(big)), big))
check("empty mask", not rle_decode(rle_encode(np.zeros((5, 7), bool))).any())


# ═════════════════════════════════════════════════════════════════════════════
# Test project: street scene 200x100
# ═════════════════════════════════════════════════════════════════════════════
from annotator.controller.project_controller import ProjectController
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.storage.mask_storage import MaskStorage

tmp = Path(tempfile.mkdtemp())
img_path = tmp / "street.png"
Image.new("RGB", (200, 100), (90, 90, 90)).save(img_path)

ctrl = ProjectController()
proj = ctrl.create_project("pan", tmp / "proj")
road = proj.classes[0]; road.name = "road"; road.annotation_type = "semantic"; road.color = "#804080"
sky = proj.add_class("sky", "#4682B4");        sky.annotation_type = "semantic"
car = proj.add_class("car", "#00008E");        car.annotation_type = "mask"
person = proj.add_class("person", "#DC143C");  person.annotation_type = "polygon"
veg = proj.add_class("vegetation", "#6B8E23"); veg.annotation_type = "polygon"
veg.panoptic_role = "stuff"
kp = proj.add_class("face", "#FFFFFF");        kp.annotation_type = "keypoints"
box = proj.add_class("sign", "#FFD700");       box.annotation_type = "obb"
ctrl.add_images_from_paths([str(img_path)])
ctrl.set_image(str(img_path))
st = MaskStorage(proj.project_path)
W, H = 200, 100

def semantic(cls, bm):
    return Annotation.new(cls.id, AnnotationType.SEMANTIC,
                          st.semantic_data("street", cls.id, bm, W, H))

def mask_ann(cls, bm, name):
    return Annotation.new(cls.id, AnnotationType.MASK, {
        "mask_png_path": st.save_mask(name, "street", bm),
        "polygon": st.mask_to_polygon(bm, W, H),
        "bbox": st.mask_to_bbox(bm, W, H)})

road_bm = np.zeros((H, W), np.uint8); road_bm[50:, :] = 255
sky_bm = np.zeros((H, W), np.uint8);  sky_bm[:50, :] = 255
sky_bm[10:20, 150:170] = 0            # a hole (e.g. a bird)
car1_bm = np.zeros((H, W), np.uint8); car1_bm[60:80, 20:60] = 255
car2_bm = np.zeros((H, W), np.uint8); car2_bm[65:85, 50:90] = 255   # overlaps car1
car2_bm[5:10, 5:10] = 255                                            # 2nd blob
hidden_bm = np.zeros((H, W), np.uint8); hidden_bm[62:66, 25:30] = 255  # under car1

anns = [
    semantic(road, road_bm),
    semantic(sky, sky_bm),
    mask_ann(car, hidden_bm, "hid"),
    mask_ann(car, car1_bm, "c1"),
    mask_ann(car, car2_bm, "c2"),
    Annotation.new(person.id, AnnotationType.SEGMENT,
                   {"points": [[0.60, 0.40], [0.65, 0.40], [0.65, 0.90], [0.60, 0.90]]}),
    Annotation.new(veg.id, AnnotationType.SEGMENT,
                   {"points": [[0.80, 0.05], [0.95, 0.05], [0.95, 0.30], [0.80, 0.30]]}),
    Annotation.new(veg.id, AnnotationType.SEGMENT,
                   {"points": [[0.02, 0.30], [0.10, 0.30], [0.10, 0.45], [0.02, 0.45]]}),
    Annotation.new(kp.id, AnnotationType.POSE, {"keypoints": [[0.5, 0.5, 2]]}),
    Annotation.new(box.id, AnnotationType.OBB,
                   {"cx": 0.4, "cy": 0.25, "w": 0.1, "h": 0.2, "angle_deg": 45.0}),
]
car1_id = anns[3].id
for a in anns:
    ctrl.add_annotation(a)
ctrl.save_project()
out = tmp / "out"


# ═════════════════════════════════════════════════════════════════════════════
# §3  COCO Instances: polygon / RLE
# ═════════════════════════════════════════════════════════════════════════════
section("3. COCO Instances polygon / RLE")

def coco(fmt):
    ctrl.export_dataset(out / f"coco_{fmt}", "coco", seg_format=fmt)
    return json.loads((out / f"coco_{fmt}" / "annotations" / "instances_train.json")
                      .read_text(encoding="utf-8"))

cp = coco("polygon")
cars = [a for a in cp["annotations"] if a["category_id"] == car.id]
check("MASK is exported to COCO (was skipped before)", len(cars) == 3)
car2 = max(cars, key=lambda a: len(a["segmentation"]))
check("polygon mode: every blob of a MASK", len(car2["segmentation"]) == 2)
check("polygon mode: area = pixel count", car2["area"] == float((car2_bm > 0).sum()))
sky_p = next(a for a in cp["annotations"] if a["category_id"] == sky.id)
check("polygon mode: sky segmentation is a list", isinstance(sky_p["segmentation"], list))

cr = coco("rle")
sky_r = next(a for a in cr["annotations"] if a["category_id"] == sky.id)
seg = sky_r["segmentation"]
check("rle mode: segmentation is RLE dict",
      isinstance(seg, dict) and seg["size"] == [H, W] and isinstance(seg["counts"], str))
check("rle mode: decodes to the exact PNG (hole kept)",
      np.array_equal(rle_decode(seg), sky_bm > 0))
check("rle mode: bbox [x,y,w,h]", sky_r["bbox"] == [0.0, 0.0, 200.0, 50.0])
check("rle mode: area", sky_r["area"] == float((sky_bm > 0).sum()))
pers = next(a for a in cr["annotations"] if a["category_id"] == person.id)
check("rle mode: polygons stay polygons", isinstance(pers["segmentation"], list))
obb = next(a for a in cr["annotations"] if a["category_id"] == box.id)
check("OBB rotation now applied (angle_deg)", abs(obb["bbox"][2] - obb["bbox"][3]) < 1.0)


# ═════════════════════════════════════════════════════════════════════════════
# §4  COCO Panoptic
# ═════════════════════════════════════════════════════════════════════════════
section("4. COCO Panoptic")

from annotator.exporters.coco_panoptic import rgb_to_id

ctrl.export_dataset(out / "pan", "coco_panoptic")
pj = json.loads((out / "pan" / "annotations" / "panoptic_train.json").read_text(encoding="utf-8"))
png = np.array(Image.open(out / "pan" / "annotations" / "panoptic_train" / "street.png"))
png = png.astype(np.int64)
ids = png[..., 0] + 256 * png[..., 1] + 65536 * png[..., 2]

cats = {c["id"]: c for c in pj["categories"]}
check("categories: keypoints class excluded", kp.id not in cats)
check("isthing flags",
      cats[road.id]["isthing"] == 0 and cats[sky.id]["isthing"] == 0
      and cats[veg.id]["isthing"] == 0 and cats[car.id]["isthing"] == 1
      and cats[person.id]["isthing"] == 1)
check("images copied", (out / "pan" / "images" / "train" / "street.png").exists())

entry = pj["annotations"][0]
segs = entry["segments_info"]
check("annotation file_name", entry["file_name"] == "street.png")
by_cat = {}
for s in segs:
    by_cat.setdefault(s["category_id"], []).append(s)
check("stuff: one segment per class (vegetation has 2 polygons)", len(by_cat[veg.id]) == 1)
check("things: fully hidden instance dropped", len(by_cat[car.id]) == 2)
check("things: person segment", len(by_cat[person.id]) == 1)
check("OBB class exported as thing", len(by_cat[box.id]) == 1)

seg_ids = {s["id"] for s in segs}
png_ids = set(np.unique(ids).tolist()) - {0}
check("PNG ids == segments_info ids", seg_ids == png_ids)
check("ids unique", len(seg_ids) == len(segs))
check("areas match PNG", all(int((ids == s["id"]).sum()) == s["area"] for s in segs))
check("stuff id = class color", by_cat[road.id][0]["id"] == rgb_to_id(0x80, 0x40, 0x80))

sid = lambda y, x: int(ids[y, x])
cat_of = {s["id"]: s["category_id"] for s in segs}
check("thing over stuff (car over road)", cat_of[sid(70, 30)] == car.id)
check("later thing wins overlap (car2 over car1)",
      sid(70, 55) != sid(70, 30) and cat_of[sid(70, 55)] == car.id)
check("second blob of car2 in the same segment", sid(7, 7) == sid(70, 55))
check("sky hole is void", sid(15, 152) == 0)
check("stuff pixel", cat_of[sid(30, 100)] == sky.id)
car1_seg = next(s for s in by_cat[car.id] if s["id"] == sid(70, 30))
check("bbox of visible part",
      car1_seg["bbox"] == [20.0, 60.0, 40.0, 20.0])


# ═════════════════════════════════════════════════════════════════════════════
# §5  Mask garbage collection
# ═════════════════════════════════════════════════════════════════════════════
section("5. Mask cleanup")

from annotator.storage.project_store import ProjectStore

ctrl._flush_current_image()
masks = proj.project_path / "masks"
referenced = {Path(a.data["mask_png_path"]).name for a in anns if "mask_png_path" in a.data}
old = time.time() - 48 * 3600
Image.fromarray(np.zeros((4, 4), np.uint8)).save(masks / "stale.png")
os.utime(masks / "stale.png", (old, old))
Image.fromarray(np.zeros((4, 4), np.uint8)).save(masks / "fresh.png")
for name in referenced:
    os.utime(masks / name, (old, old))

moved = ProjectStore.collect_mask_garbage(proj.project_path)
check("old unreferenced moved to _orphaned", moved == 1 and (masks / "_orphaned" / "stale.png").exists())
check("fresh unreferenced kept (multi-user grace)", (masks / "fresh.png").exists())
check("referenced masks kept", all((masks / n).exists() for n in referenced))

one = sorted(referenced)[0]
shutil.move(str(masks / one), str(masks / "_orphaned" / one))
ProjectStore.collect_mask_garbage(proj.project_path)
check("second run deletes orphan", not (masks / "_orphaned" / "stale.png").exists())
check("referenced file in _orphaned restored", (masks / one).exists())

bad = proj.project_path / "annotations" / "zzz_broken.json"
bad.write_text("{not json", encoding="utf-8")
Image.fromarray(np.zeros((4, 4), np.uint8)).save(masks / "stale2.png")
os.utime(masks / "stale2.png", (old, old))
check("unreadable annotation file aborts cleanup",
      ProjectStore.collect_mask_garbage(proj.project_path) == -1
      and (masks / "stale2.png").exists())
bad.unlink()


# ═════════════════════════════════════════════════════════════════════════════
# §6  Export dialog
# ═════════════════════════════════════════════════════════════════════════════
section("6. Export dialog")

from annotator.ui.dialogs.export_dialog import ExportDatasetDialog, _FORMATS

dlg = ExportDatasetDialog(ctrl.project, {})
keys = [k for _, k in _FORMATS]
dlg._fmt_combo.setCurrentIndex(keys.index("coco"))
check("COCO shows 'Masks as' option", not dlg._seg_fmt_combo.isHidden())
dlg._seg_fmt_combo.setCurrentIndex(1)
check("seg_format property", dlg.seg_format == "rle")
dlg._fmt_combo.setCurrentIndex(keys.index("coco_panoptic"))
check("panoptic format listed; option hidden",
      dlg.format_name == "coco_panoptic" and dlg._seg_fmt_combo.isHidden())

shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# §7  Schema edit keeps the Annotations panel (regression: panel emptied)
# ═════════════════════════════════════════════════════════════════════════════
section("7. Schema edit keeps annotations in the panel")

import copy
from annotator.ui.main_window import MainWindow

tmp2 = Path(tempfile.mkdtemp())
img2 = tmp2 / "scene.png"
Image.new("RGB", (120, 80), (40, 40, 40)).save(img2)
win = MainWindow()
c = win._ctrl
pr = c.create_project("schema", tmp2 / "proj")
bays = pr.classes[0]; bays.name = "bays"; bays.annotation_type = "polygon"
other = pr.add_class("other"); other.annotation_type = "polygon"
c.add_images_from_paths([str(img2)])
c.set_image(str(img2))
for cid in (bays.id, bays.id, other.id):
    c.add_annotation(Annotation.new(cid, AnnotationType.SEGMENT,
                     {"points": [[0.1, 0.1], [0.5, 0.1], [0.3, 0.6]]}))
win._classes_panel._list.setCurrentRow(0)
panel = win._annotations_panel

def editor_ok(mutate):
    """Same steps as MainWindow._open_schema_editor after the dialog is accepted."""
    classes = copy.deepcopy(c.project.classes)
    mutate(classes)
    c.project.classes = classes
    c.save_project()
    c.project_changed.emit(c.project)

check("before: panel lists 3 annotations", panel._list.count() == 3)
editor_ok(lambda cl: setattr(cl[0], "panoptic_role", "stuff"))
check("role auto -> stuff: panel still lists 3", panel._list.count() == 3)
check("role change persisted", c.project.get_class(bays.id).panoptic_role == "stuff")
editor_ok(lambda cl: setattr(cl[0], "color", "#00FF00"))
items = [i for i in win._scene._ann_items.values()]
check("color change: canvas rebuilt with new color",
      sum(1 for i in items if i.class_color == "#00FF00") == 2)
check("active class restored after edit",
      panel._active_class_id == win._classes_panel.current_class_id)

c.delete_class(other.id, reassign_to=None)
check("class deletion: remaining annotations still listed", panel._list.count() == 2)

c.create_project("fresh", tmp2 / "proj2")
check("opening another project still clears the panel", panel._list.count() == 0)
win.close()
shutil.rmtree(tmp2, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
# close every window: one left open is destroyed during interpreter shutdown,
# its app-wide key filter then crashes the process (random exit code 139)
from PyQt6.QtWidgets import QApplication as _QApp
for _w in _QApp.topLevelWidgets():
    _w.close()

print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
