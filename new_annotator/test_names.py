"""
Same file name in different folders — image keys, storage, old projects, exports
Run: .venv/Scripts/python test_names.py
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# ── headless Qt ───────────────────────────────────────────────────────────────
_TMP = Path(tempfile.mkdtemp())
os.environ["ANNOTATOR_SETTINGS"] = str(_TMP / "settings.ini")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))

from PyQt6.QtWidgets import QApplication
_app = QApplication.instance() or QApplication(sys.argv)

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
# §1  unique_stem / image keys
# ═════════════════════════════════════════════════════════════════════════════
section("1. Image keys")

from annotator.domain.project import ImageRecord, Project, unique_stem

taken: set[str] = set()
check("free name stays", unique_stem("/d/road_a/frame.jpg", taken) == "frame")
check("same name -> <folder>_<name>", unique_stem("/d/road_b/frame.jpg", taken) == "road_b_frame")
check("same folder name again -> _2", unique_stem("/x/road_b/frame.png", taken) == "road_b_frame_2")
check("case-insensitive (Windows file names)", unique_stem("/d/c/FRAME.jpg", taken) == "c_FRAME")
check("odd folder characters replaced",
      unique_stem("/d/my photos (1)/frame.jpg", taken) == "my_photos_1_frame")
check("cyrillic folder kept", unique_stem("/d/дорога/frame.jpg", taken) == "дорога_frame")

p = Project.create("k")
a = p.add_image("/d/road_a/frame.jpg")
b = p.add_image("/d/road_b/frame.jpg")
c = p.add_image("/d/road_b/other.jpg")
check("add_image gives keys", (a.key, b.key, c.key) == ("frame", "road_b_frame", "other"))
check("adding the same path again returns the record", p.add_image("/d/road_b/frame.jpg") is b)
check("image_key by path", p.image_key("/d/road_b/frame.jpg") == "road_b_frame")
check("image_key outside the project = stem", p.image_key("/z/q.png") == "q")
check("key saved only when it differs from the name",
      "key" not in a.to_dict() and b.to_dict()["key"] == "road_b_frame")
check("round-trip", ImageRecord.from_dict(b.to_dict()).key == "road_b_frame"
      and ImageRecord.from_dict(a.to_dict()).ann_key == "frame")

old = Project.create("old")
old.images = [ImageRecord(path="/d/road_a/frame.jpg"), ImageRecord(path="/d/road_b/frame.jpg"),
              ImageRecord(path="/d/road_c/Frame.jpg"), ImageRecord(path="/d/x/solo.jpg")]
renamed = old.ensure_image_keys()
check("old image list: first keeps the name, the rest renamed",
      [r.key for r in old.images] == ["frame", "road_b_frame", "road_c_Frame", "solo"])
check("ensure_image_keys reports the renamed ones",
      renamed == ["/d/road_b/frame.jpg", "/d/road_c/Frame.jpg"])
check("second call changes nothing", old.ensure_image_keys() == [])


# ═════════════════════════════════════════════════════════════════════════════
# §2  Storage: same-named images keep their own annotations
# ═════════════════════════════════════════════════════════════════════════════
section("2. Storage")

from annotator.controller.project_controller import ProjectController
from annotator.domain.annotation import Annotation, AnnotationType
from annotator.storage.project_store import ProjectStore

src = _TMP / "src"
for d, color in (("road_a", (200, 0, 0)), ("road_b", (0, 200, 0))):
    (src / d).mkdir(parents=True)
    Image.new("RGB", (100, 80), color).save(src / d / "frame.jpg")
A, B = str(src / "road_a" / "frame.jpg"), str(src / "road_b" / "frame.jpg")

def bbox(x):
    return Annotation.new(0, AnnotationType.BBOX, {"x": x, "y": 0.1, "w": 0.2, "h": 0.2})

ctrl = ProjectController()
proj = ctrl.create_project("dup", _TMP / "proj")
ctrl.add_images_from_paths([str(src / "road_a"), str(src / "road_b")])
check("both images in the project", len(proj.images) == 2)
ctrl.set_image(A)
ctrl.add_annotation(bbox(0.1))
ctrl.set_image(B)
check("second image does not show the first one's box", ctrl.current_annotations == [])
ctrl.add_annotation(bbox(0.5))
ctrl.add_annotation(bbox(0.7))
ctrl.set_image(A)
check("first image keeps exactly its own box", len(ctrl.current_annotations) == 1
      and ctrl.current_annotations[0].data["x"] == 0.1)
ctrl.save_project()
files = sorted(f.name for f in (proj.project_path / "annotations").glob("*.json"))
check("two annotation files", files == ["frame.json", "road_b_frame.json"])
allann = ProjectStore.load_all_annotations(proj)
check("load_all_annotations maps each file to its image",
      len(allann[A]) == 1 and len(allann[B]) == 2)
imgs = json.loads((proj.project_path / "images.json").read_text(encoding="utf-8"))
check("images.json: key only on the renamed image",
      "key" not in imgs[0] and imgs[1]["key"] == "road_b_frame")

ctrl2 = ProjectController()
ctrl2.open_project(proj.project_path)
check("reopened project: keys kept, nothing reported",
      ctrl2.project.image_key(B) == "road_b_frame" and ctrl2.project.dup_renamed == [])
ctrl2.set_image(B)
check("reopened: second image has its 2 boxes", len(ctrl2.current_annotations) == 2)


# ═════════════════════════════════════════════════════════════════════════════
# §3  Old project (before keys): one shared file
# ═════════════════════════════════════════════════════════════════════════════
section("3. Old project")

oldp = _TMP / "old.annproj"
shutil.copytree(proj.project_path, oldp)
ann = oldp / "annotations"
(ann / "road_b_frame.json").unlink()
shared = json.loads((ann / "frame.json").read_text(encoding="utf-8"))
shared.append(bbox(0.6).to_dict())                      # drawn while B was open
(ann / "frame.json").write_text(json.dumps(shared), encoding="utf-8")
for r in imgs:
    r.pop("key", None)
(oldp / "images.json").write_text(json.dumps(imgs), encoding="utf-8")

ctrl3 = ProjectController()
op = ctrl3.open_project(oldp)
check("open reports the image that shared a file", op.dup_renamed == [B])
check("it gets a copy of the shared file", (ann / "road_b_frame.json").exists())
ctrl3.set_image(B)
check("nothing drawn on it is lost (2 boxes from the shared file)", len(ctrl3.current_annotations) == 2)
ctrl3.add_annotation(bbox(0.3))
ctrl3.set_image(A)
check("editing it no longer changes the first image", len(ctrl3.current_annotations) == 2)
check("the new key is saved at once",
      json.loads((oldp / "images.json").read_text(encoding="utf-8"))[1].get("key") == "road_b_frame")
check("reopening does not report again", ProjectController().open_project(oldp).dup_renamed == [])

# existing <key>.json is never overwritten by the copy
oldq = _TMP / "old2.annproj"
shutil.copytree(oldp, oldq)
imgs_q = json.loads((oldq / "images.json").read_text(encoding="utf-8"))
for r in imgs_q:
    r.pop("key", None)
(oldq / "images.json").write_text(json.dumps(imgs_q), encoding="utf-8")
before = (oldq / "annotations" / "road_b_frame.json").read_text(encoding="utf-8")
ProjectController().open_project(oldq)
check("an existing file of the new name is kept",
      (oldq / "annotations" / "road_b_frame.json").read_text(encoding="utf-8") == before)


# ═════════════════════════════════════════════════════════════════════════════
# §4  Exports: no file overwrites another
# ═════════════════════════════════════════════════════════════════════════════
section("4. Exports")

proj.classes[0].annotation_type = "bbox"
cls_c = proj.add_class("scene"); cls_c.annotation_type = "classification"
ctrl.set_image(A)
ctrl.add_annotation(Annotation.new(cls_c.id, AnnotationType.CLASSIFY, {}))
ctrl.set_image(B)
ctrl.add_annotation(Annotation.new(cls_c.id, AnnotationType.CLASSIFY, {}))
ctrl.save_project()

def export(fmt):
    out = _TMP / f"out_{fmt}"
    ctrl.export_dataset(out, fmt, copy_images=True)
    return out

def same_pixels(path, original):
    return Image.open(path).convert("RGB").getpixel((5, 5)) == Image.open(original).getpixel((5, 5))

out = export("yolo_detect")
check("YOLO: two images", sorted(f.name for f in (out / "images" / "train").iterdir())
      == ["frame.jpg", "road_b_frame.jpg"])
check("YOLO: renamed copy is the second image",
      same_pixels(out / "images" / "train" / "road_b_frame.jpg", B)
      and same_pixels(out / "images" / "train" / "frame.jpg", A))
lab = out / "labels" / "train"
check("YOLO: label files match the image names (1 and 2 boxes)",
      len((lab / "frame.txt").read_text().splitlines()) == 1
      and len((lab / "road_b_frame.txt").read_text().splitlines()) == 2)

for fmt in ("coco", "coco_keypoints", "coco_panoptic"):
    out = export(fmt)
    js = (out / "annotations" / ("panoptic_train.json" if fmt == "coco_panoptic" else "instances_train.json"))
    if not js.exists():
        js = next((out / "annotations").glob("*train*.json"))
    data = json.loads(js.read_text(encoding="utf-8"))
    names = [im["file_name"] for im in data["images"]]
    check(f"{fmt}: unique file names in JSON", sorted(names) == ["frame.jpg", "road_b_frame.jpg"])
    check(f"{fmt}: both images copied",
          all((out / "images" / "train" / n).exists() for n in names))
    if fmt == "coco":
        per_img = {im["file_name"]: sum(1 for a in data["annotations"] if a["image_id"] == im["id"])
                   for im in data["images"]}
        check("coco: annotations stay with their image", per_img == {"frame.jpg": 1, "road_b_frame.jpg": 2})
    if fmt == "coco_panoptic":
        pngs = sorted(a["file_name"] for a in data["annotations"])
        check("coco_panoptic: one PNG per image", pngs == ["frame.png", "road_b_frame.png"]
              and all((out / "annotations" / "panoptic_train" / n).exists() for n in pngs))

out = export("labelme")
lm = {f.name: json.loads(f.read_text(encoding="utf-8")) for f in (out / "train").glob("*.json")}
check("LabelMe: two JSON files", sorted(lm) == ["frame.json", "road_b_frame.json"])
check("LabelMe: imagePath points to its own copy",
      lm["road_b_frame.json"]["imagePath"] == "road_b_frame.jpg"
      and len(lm["road_b_frame.json"]["shapes"]) == 2 and (out / "train" / "road_b_frame.jpg").exists())

out = export("pascal_voc")
xmls = sorted(f.name for f in (out / "Annotations").glob("*.xml"))
check("VOC: two XML files", xmls == ["frame.xml", "road_b_frame.xml"])
check("VOC: <filename> and train.txt use the new name",
      "<filename>road_b_frame.jpg</filename>" in (out / "Annotations" / "road_b_frame.xml").read_text(encoding="utf-8")
      and (out / "ImageSets" / "Main" / "train.txt").read_text().split() == ["frame", "road_b_frame"])

out = export("semantic_masks")
check("Semantic Masks: two masks, two images",
      sorted(f.name for f in (out / "masks" / "train").iterdir()) == ["frame.png", "road_b_frame.png"]
      and sorted(f.name for f in (out / "images" / "train").iterdir()) == ["frame.jpg", "road_b_frame.jpg"])

out = export("yolo_classify")
check("YOLO Classify: both images in the class folder",
      sorted(f.name for f in (out / "train" / "scene").iterdir()) == ["frame.jpg", "road_b_frame.jpg"])

# a project without duplicates exports the original names
uniq = _TMP / "uniq"
uniq.mkdir()
Image.new("RGB", (40, 30)).save(uniq / "cat.jpg")
cu = ProjectController()
cu.create_project("u", _TMP / "uproj")
cu.add_images_from_paths([str(uniq)])
cu.export_dataset(_TMP / "out_u", "yolo_detect", copy_images=True)
check("no duplicates: names unchanged",
      [f.name for f in (_TMP / "out_u" / "images" / "train").iterdir()] == ["cat.jpg"]
      and (_TMP / "out_u" / "labels" / "train" / "cat.txt").exists())


# ═════════════════════════════════════════════════════════════════════════════
# §5  Multi-user filter and the image list
# ═════════════════════════════════════════════════════════════════════════════
section("5. Image list / assignments")

from annotator.ui.panels.images_panel import ImagesPanel

panel = ImagesPanel()
panel.load_project(proj)
texts = [panel._list.item(i).text() for i in range(panel._list.count())]
check("renamed duplicate shows its folder", texts[0].startswith("frame.jpg")
      and texts[1].startswith("road_b/frame.jpg"))
check("both marked as annotated", all("✓" in t for t in texts))
panel.set_user_filter({"road_b_frame"})
check("assignment by key shows only that image",
      [r.path for r in panel._displayed] == [B])
panel.set_assignments({"users": {"anna": ["frame"], "boris": ["road_b_frame"]}})
panel.set_user_filter(None)
texts = [panel._list.item(i).text() for i in range(panel._list.count())]
check("leader view: each image has its own assignee", "anna" in texts[0] and "boris" in texts[1])

from annotator.ui.dialogs.assign_images_dialog import AssignImagesDialog
dlg = AssignImagesDialog(proj.images, {"version": 1, "users": {}}, leader_name="lead")
check("assign dialog: two separate unassigned images",
      dlg._unassigned_stems() == ["frame", "road_b_frame"]
      and dlg._stem_to_name()["road_b_frame"] == "road_b/frame.jpg")
dlg.deleteLater()


# ═════════════════════════════════════════════════════════════════════════════
# §6  YOLO import does not mix up same-named images
# ═════════════════════════════════════════════════════════════════════════════
section("6. YOLO import")

from annotator.importers.yolo_importer import YoloImporter
find = YoloImporter._find_image
check("same file -> that image", find(proj, Path(B)).path == B)
check("same name, two project images -> no guess", find(proj, _TMP / "ds" / "frame.jpg") is None)
check("unique name elsewhere -> that image (labels re-import)",
      find(cu.project, _TMP / "ds" / "cat.jpg").path == str(uniq / "cat.jpg"))
check("unknown name -> none", find(proj, _TMP / "ds" / "zzz.jpg") is None)


shutil.rmtree(_TMP, ignore_errors=True)

# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
