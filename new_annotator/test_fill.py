"""
Fill tool tests — fill_enclosed, FillTool on mask and semantic classes
Run: .venv/Scripts/python test_fill.py
"""
import os
import sys
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
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsLineItem, QGraphicsPathItem

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
# §1  fill_enclosed
# ═════════════════════════════════════════════════════════════════════════════
section("1. fill_enclosed")

import cv2
from annotator.tools.fill_tool import fill_enclosed

ring = np.zeros((50, 60), dtype=np.uint8)
cv2.rectangle(ring, (10, 10), (40, 30), 255, 1)
f = fill_enclosed(ring)
check("closed 1-px rectangle -> inside filled", f[20, 25] and f[11, 11])
check("line itself kept", f[10, 10] and f[30, 40])
check("outside untouched", not f[5, 5] and not f[20, 50])

open_ring = ring.copy()
open_ring[20, 10] = 0                            # gap in the left side
check("open contour -> nothing inside", not fill_enclosed(open_ring)[20, 25])

diag = np.zeros((20, 20), dtype=np.uint8)
cv2.circle(diag, (10, 10), 6, 255, 1, lineType=cv2.LINE_8)
check("8-connected diagonal line holds the fill", fill_enclosed(diag)[10, 10])

corner = np.zeros((40, 40), dtype=np.uint8)
corner[0:20, 19] = 255                           # wall + image border close a corner
corner[19, 0:20] = 255
fc = fill_enclosed(corner)
check("image border does not count as closed", not fc[5, 5])

two = np.zeros((40, 80), dtype=np.uint8)
cv2.rectangle(two, (5, 5), (30, 30), 255, 1)
cv2.rectangle(two, (45, 5), (70, 30), 255, 1)
ft = fill_enclosed(two)
check("two loops -> both filled", ft[15, 15] and ft[15, 55] and not ft[15, 38])


# ═════════════════════════════════════════════════════════════════════════════
# §2  Domain registration
# ═════════════════════════════════════════════════════════════════════════════
section("2. Registration")

from annotator.domain.label_class import ANNOTATION_TYPE_TOOLS, ANNOTATION_TYPE_DEFAULT_TOOL
from annotator.domain.project import DEFAULT_HOTKEYS

check("mask classes: brush + fill", ANNOTATION_TYPE_TOOLS["mask"] == ["brush", "fill"])
check("semantic classes: semantic_brush + fill",
      ANNOTATION_TYPE_TOOLS["semantic"] == ["semantic_brush", "fill"])
check("defaults unchanged",
      ANNOTATION_TYPE_DEFAULT_TOOL["mask"] == "brush"
      and ANNOTATION_TYPE_DEFAULT_TOOL["semantic"] == "semantic_brush")
check("fill not offered for polygon / bbox",
      "fill" not in ANNOTATION_TYPE_TOOLS["polygon"] and "fill" not in ANNOTATION_TYPE_TOOLS["bbox"])
check("hotkey G", DEFAULT_HOTKEYS.get("tool_fill") == "G")
check("G not taken by another action",
      [k for k, v in DEFAULT_HOTKEYS.items() if v == "G"] == ["tool_fill"])


# ═════════════════════════════════════════════════════════════════════════════
# §3  FillTool on a mask class
# ═════════════════════════════════════════════════════════════════════════════
section("3. Mask class")

from annotator.controller.project_controller import ProjectController
from annotator.ui.canvas.scene import AnnotationScene
from annotator.domain.annotation import AnnotationType
from annotator.storage.mask_storage import MaskStorage
from annotator.tools.fill_tool import FillTool, _MaskFill, _SemanticFill
from annotator.tools.select_tool import SelectTool

tmp = Path(tempfile.mkdtemp())
img_path = tmp / "street.png"
Image.new("RGB", (200, 100), (90, 90, 90)).save(img_path)

ctrl = ProjectController()
proj = ctrl.create_project("fill", tmp / "proj")
proj.classes[0].name = "car"
proj.classes[0].annotation_type = "mask"
road_cls = proj.add_class("road");  road_cls.annotation_type = "semantic"
sky_cls = proj.add_class("sky");    sky_cls.annotation_type = "semantic"
ctrl.add_images_from_paths([str(img_path)])
ctrl.set_image(str(img_path))

scene = AnnotationScene()
scene.load_image(str(img_path))
ctrl.annotations_changed.connect(lambda anns: scene.rebuild_annotations(anns, ctrl.project))

def activate(tool, class_id):
    """Same order as MainWindow._activate_tool: set_tool, then set_class."""
    scene.set_tool(tool, ctrl)
    tool.set_class(class_id)

def contour(tool, pts, release=True):
    tool.on_press(QPointF(*pts[0]), NOMOD, LB)
    for p in pts[1:]:
        tool.on_move(QPointF(*p), NOMOD)
    if release:
        tool.on_release(QPointF(*pts[-1]), NOMOD, LB)

def masks():
    return [a for a in ctrl.current_annotations if a.ann_type == AnnotationType.MASK]

def sem_anns():
    return [a for a in ctrl.current_annotations if a.ann_type == AnnotationType.SEMANTIC]

def bitmap(ann):
    return MaskStorage(ctrl.project.project_path).load_mask(ann.data["mask_png_path"])

def previews():
    return [i for i in scene.items() if isinstance(i, (QGraphicsPathItem, QGraphicsLineItem))
            and i.zValue() >= 5]

fill = FillTool()
fill.set_params({"brush_size": 2, "mode": "draw"})
activate(fill, 0)
check("mask class -> mask fill", isinstance(fill._active, _MaskFill))
check("annotation name is 'fill'", fill._active.name == "fill")

SQUARE = [(20, 20), (60, 20), (60, 60), (20, 60), (20, 22)]
contour(fill, SQUARE[:3], release=False)
check("preview + closing guide while drawing", len(previews()) == 2)
check("nothing saved while drawing", masks() == [])
n_undo = ctrl.undo_stack.count()
fill.on_release(QPointF(60, 60), NOMOD, LB)
check("preview removed after release", previews() == [])
check("release saves a MASK at once (no Enter)", len(masks()) == 1)
check("one undo step", ctrl.undo_stack.count() == n_undo + 1)
tri = masks()[0]
bm = bitmap(tri)
check("open contour closed by a straight line and filled",
      bm[40, 50] == 255 and bm[25, 58] == 255)
check("triangle edge respected (outside the diagonal)", bm[55, 25] == 0)
check("meta.tool == fill", tri.meta.get("tool") == "fill")
check("polygon and bbox stored", bool(tri.data.get("polygon")) and bool(tri.data.get("bbox")))

contour(fill, [(120, 20), (180, 20), (180, 80), (120, 80)])
check("no selection -> next contour is a new mask", len(masks()) == 2)

ctrl.undo_stack.undo()
check("undo removes the last contour", len(masks()) == 1)
ctrl.undo_stack.redo()
check("redo restores it", len(masks()) == 2)

n_undo = ctrl.undo_stack.count()
fill.on_press(QPointF(150, 50), NOMOD, LB)
fill.on_release(QPointF(150, 50), NOMOD, LB)
fill.on_double_click(QPointF(150, 50), NOMOD, LB)
check("bare click / double click saves nothing",
      len(masks()) == 2 and ctrl.undo_stack.count() == n_undo and previews() == [])

# selected mask: contours are added to it
box = next(a for a in masks() if bitmap(a)[50, 150] == 255)
old_png = box.data["mask_png_path"]
scene.select_item(scene._ann_items[box.id])
contour(fill, [(170, 70), (195, 70), (195, 95), (170, 95)])
box2 = next(a for a in masks() if a.id == box.id)
bb = bitmap(box2)
check("selected mask grows (same annotation)", len(masks()) == 2
      and bb[85, 185] == 255 and bb[50, 150] == 255)
check("edit writes a new PNG revision", box2.data["mask_png_path"] != old_png)
check("selection kept after the edit",
      getattr(scene.get_selected_item(), "annotation_id", None) == box.id)
ctrl.undo_stack.undo()
check("undo restores the previous pixels", bitmap(next(a for a in masks() if a.id == box.id))[85, 185] == 0)
ctrl.undo_stack.redo()

# erase: selected mask only / every mask of the class
fill.set_params({"mode": "erase"})
contour(fill, [(140, 40), (160, 40), (160, 60), (140, 60)])
check("erase cuts a hole in the selected mask",
      bitmap(next(a for a in masks() if a.id == box.id))[50, 150] == 0)
from annotator.ui.canvas.items.mask_item import MaskAnnotationItem
item = scene._ann_items[box.id]
check("canvas draws the mask from its PNG", isinstance(item, MaskAnnotationItem)
      and item._pixmap is not None)
check("hole is see-through: no hit inside it", not item.contains(QPointF(150, 50)))
check("...but the mask around it is hit", item.contains(QPointF(125, 25)))
check("outline includes the hole edge", item._outline.elementCount() > 0
      and not item.shape().contains(QPointF(150, 50)) and item.shape().contains(QPointF(125, 25)))
from PyQt6.QtGui import QImage, QPainter
shot = QImage(200, 100, QImage.Format.Format_ARGB32)
shot.fill(0)
qp = QPainter(shot)
scene.render(qp, QRectF(0, 0, 200, 100), QRectF(0, 0, 200, 100))
qp.end()
bg, ring_px = QColor(shot.pixel(150, 50)), QColor(shot.pixel(125, 25))
check("rendered: hole shows the image, the mask is tinted",
      abs(bg.red() - 90) <= 2 and abs(bg.green() - 90) <= 2 and ring_px != bg)

scene.deselect_all()
contour(fill, [(0, 0), (199, 0), (199, 35), (0, 35)])
check("erase without selection cuts every mask of the class",
      all(not bitmap(a)[30, 40].any() and not bitmap(a)[30, 150].any() for a in masks()))
n_undo = ctrl.undo_stack.count()
contour(fill, [(0, 0), (199, 0), (199, 99), (0, 99)])
check("erasing a whole mask deletes it, one undo step",
      masks() == [] and ctrl.undo_stack.count() == n_undo + 1)
ctrl.undo_stack.undo()
check("undo brings both masks back", len(masks()) == 2)
fill.set_params({"mode": "draw"})

contour(fill, [(100, 90), (110, 90), (110, 95)], release=False)
fill.on_key_press(Qt.Key.Key_Escape, NOMOD)
check("Esc while drawing drops the contour", previews() == [])
fill.on_release(QPointF(110, 95), NOMOD, LB)
check("release after Esc saves nothing", len(masks()) == 2)

contour(fill, [(100, 90), (110, 90), (110, 95)], release=False)
fill.leave_image()
check("leaving the image drops an unfinished contour", previews() == [])
fill.on_release(QPointF(110, 95), NOMOD, LB)
scene.set_tool(SelectTool(), ctrl)
check("tool switch leaves no preview", previews() == [] and len(masks()) == 2)

fill2 = FillTool()
scene.set_tool(fill2, ctrl)
check("activate alone picks no fill yet", fill2._active is None)
scene.set_tool(SelectTool(), ctrl)


# ═════════════════════════════════════════════════════════════════════════════
# §3b  Brush never drops unsaved work
# ═════════════════════════════════════════════════════════════════════════════
section("3b. Brush: unsaved strokes")

from annotator.tools.brush_tool import BrushTool

img2 = tmp / "other.png"
Image.new("RGB", (120, 60), (90, 90, 90)).save(img2)
ctrl.add_images_from_paths([str(img2)])
messages = []
ctrl.status_message.connect(messages.append)

br = BrushTool()
br.set_params({"brush_size": 3, "mode": "draw"})
activate(br, 0)
n = len(masks())
contour(br, [(100, 10), (110, 10)])
check("unsaved hint in the status line", any("Enter" in m for m in messages))
scene.set_tool(SelectTool(), ctrl)
check("tool switch saves the strokes", len(masks()) == n + 1)

activate(br, 0)
contour(br, [(100, 30), (110, 30)])
br.set_class(road_cls.id)
check("class switch saves them with the old class",
      len(masks()) == n + 2 and masks()[-1].class_id == 0)
br.set_class(0)

contour(br, [(100, 50), (110, 50)])
first = str(img_path)


def go(path):
    """Image switch as MainWindow does it: tools hear image_about_to_change."""
    ctrl.set_image(path)
    scene.load_image(path)
    scene.rebuild_annotations(ctrl.current_annotations, ctrl.project)


ctrl.image_about_to_change.connect(lambda _p: scene.active_tool.leave_image())
go(str(img2))
check("image switch saved the strokes into the image they were painted on",
      ctrl.current_annotations == [])
contour(br, [(10, 10), (40, 10)])
check("canvas re-created for the new image size", br._mask_bitmap.shape == (60, 120))
br.on_key_press(Qt.Key.Key_Escape, NOMOD)
go(first)
check("...and they are there", len(masks()) == n + 3)

# a mask loaded for editing goes back to its own image untouched
target = masks()[0]
scene.set_tool(SelectTool(), ctrl)
scene.select_item(scene._ann_items[target.id])
activate(br, 0)
check("selected mask loaded for editing", target.id not in [a.id for a in masks()])
go(str(img2))
check("other image gets nothing", ctrl.current_annotations == [])
go(first)
back = [a for a in masks() if a.id == target.id]
check("loaded-but-untouched mask is back on its image, same id and file",
      len(back) == 1 and back[0].data["mask_png_path"] == target.data["mask_png_path"])
scene.set_tool(SelectTool(), ctrl)
ctrl.status_message.disconnect()


# ═════════════════════════════════════════════════════════════════════════════
# §4  FillTool on a semantic class
# ═════════════════════════════════════════════════════════════════════════════
section("4. Semantic class")

fill = FillTool()
fill.set_params({"brush_size": 2, "mode": "draw", "overlap": "overwrite"})
activate(fill, road_cls.id)
check("semantic class -> semantic fill", isinstance(fill._active, _SemanticFill))

n_undo = ctrl.undo_stack.count()
contour(fill, [(10, 10), (100, 10), (100, 90), (10, 90)])
check("contour commits a SEMANTIC layer at once", len(sem_anns()) == 1)
check("one undo step", ctrl.undo_stack.count() == n_undo + 1)
rb = bitmap(sem_anns()[0])
check("layer covers the enclosed area", rb[50, 50] == 255 and rb[50, 120] == 0)

fill.set_class(sky_cls.id)
check("same fill reused for another semantic class", isinstance(fill._active, _SemanticFill))
contour(fill, [(60, 30), (150, 30), (150, 70), (60, 70)])
layers = {a.class_id: bitmap(a) for a in sem_anns()}
check("overwrite takes pixels from road",
      layers[sky_cls.id][50, 80] == 255 and layers[road_cls.id][50, 80] == 0)
check("layers never overlap", not ((layers[road_cls.id] > 0) & (layers[sky_cls.id] > 0)).any())

fill.set_params({"mode": "erase"})
contour(fill, [(120, 35), (145, 35), (145, 65), (120, 65)])
layers = {a.class_id: bitmap(a) for a in sem_anns()}
check("erase clears the enclosed area", layers[sky_cls.id][50, 130] == 0
      and layers[sky_cls.id][50, 80] == 255)
fill.set_params({"mode": "draw"})

n_undo = ctrl.undo_stack.count()
contour(fill, [(160, 10), (190, 10), (190, 40)], release=False)
fill.on_key_press(Qt.Key.Key_Escape, NOMOD)
fill.on_release(QPointF(190, 40), NOMOD, LB)
check("Esc cancels the contour", ctrl.undo_stack.count() == n_undo and previews() == [])

# switching class type swaps the fill
fill.set_class(0)
check("mask class again -> mask fill", isinstance(fill._active, _MaskFill))
fill.set_class(road_cls.id)
check("and back to semantic", isinstance(fill._active, _SemanticFill))
scene.set_tool(SelectTool(), ctrl)
check("deactivate drops the active fill", fill._active is None and previews() == [])

shutil.rmtree(tmp, ignore_errors=True)


# ═════════════════════════════════════════════════════════════════════════════
print(f"\n{'=' * 60}\n  {_pass} passed, {_fail} failed\n{'=' * 60}")
sys.exit(1 if _fail else 0)
