"""
Boxes -> outlines with SAM (7-D): every box of a source class (bbox or OBB)
on the chosen images becomes a polygon / mask / tight rotated box of a
target class, one sam.boxes request per image.

New annotations are model annotations (🤖, confidence = SAM's mask score) and
remember their box in meta["from_box"], so a second run into the same class
skips boxes already outlined. The boxes themselves are kept, or removed if asked.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.label_class import LabelClass
from annotator.exporters.base import image_size
from annotator.ml.client import MLBackend, Reply
from annotator.ml.convert import ConvertOptions, ConvertReport, convert, min_area_rect
from annotator.ml.prelabel import _FATAL
from ml_backend import protocol

SOURCE_TYPES = ("bbox", "obb")                  # classes whose boxes can be outlined
TARGET_TYPES = ("polygon", "mask", "obb")       # classes an outline can go into
FROM_BOX = "from_box"                           # meta key: id of the box it came from


@dataclass
class BoxSummary:
    total: int = 0                # images in scope
    images: int = 0               # images that had boxes to outline
    outlined: int = 0             # boxes that became an annotation
    empty: int = 0                # boxes where SAM found nothing
    removed: int = 0              # source boxes deleted
    failed: int = 0
    errors: list = field(default_factory=list)
    cancelled: bool = False
    fatal: str = ""
    seconds: float = 0.0
    changed_images: set = field(default_factory=set)


def boxes_to_outline(annotations: list[Annotation], source_id: int,
                     target_id: int) -> list[Annotation]:
    """Boxes of the source class not yet outlined into the target class."""
    done = {a.meta.get(FROM_BOX) for a in annotations if a.class_id == target_id}
    return [a for a in annotations
            if a.class_id == source_id and a.ann_type in (AnnotationType.BBOX, AnnotationType.OBB)
            and a.id not in done]


def pixel_box(ann: Annotation, w: int, h: int) -> list[float]:
    """[x1, y1, x2, y2] in pixels; an OBB gives the box around its rotated
    corners (rotated in pixels, like the canvas)."""
    d = ann.data
    if ann.ann_type == AnnotationType.BBOX:
        return [d["x"] * w, d["y"] * h, (d["x"] + d["w"]) * w, (d["y"] + d["h"]) * h]
    cx, cy, hw, hh = d["cx"] * w, d["cy"] * h, d["w"] * w / 2, d["h"] * h / 2
    a = math.radians(d.get("angle_deg", 0.0))
    c, s = math.cos(a), math.sin(a)
    xs, ys = [], []
    for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
        xs.append(cx + c * dx - s * dy)
        ys.append(cy + s * dx + c * dy)
    return [max(0.0, min(xs)), max(0.0, min(ys)), min(float(w), max(xs)), min(float(h), max(ys))]


class SamBoxRunner(QObject):
    progress = pyqtSignal(int, int, str)       # done, total, current image name
    finished = pyqtSignal(object)              # BoxSummary

    def __init__(self, backend: MLBackend, ctrl, parent=None):
        super().__init__(parent)
        self._backend = backend
        self._ctrl = ctrl
        self._images: list[str] = []
        self._idx = 0
        self._rid: int | None = None
        self._cancel = False
        self._running = False
        self._t0 = 0.0
        self.summary = BoxSummary()

    @property
    def running(self) -> bool:
        return self._running

    def start(self, images: list[str], source: LabelClass, target: LabelClass, sam_model: str,
              delete_source: bool = False, simplify_px: float = 2.0) -> None:
        if self._running:
            return
        self._images = list(images)
        self._source, self._target = source, target
        self._model = sam_model
        self._delete = delete_source
        self._simplify = simplify_px
        self._idx = 0
        self._cancel = False
        self._running = True
        self._t0 = time.monotonic()
        self.summary = BoxSummary(total=len(self._images))
        if not (sam_model and Path(sam_model).is_file()):
            self.summary.fatal = "No SAM model is chosen (ML Settings)."
            QTimer.singleShot(0, self._finish)
            return
        QTimer.singleShot(0, self._next)

    def cancel(self) -> None:
        if not self._running:
            return
        self._cancel = True
        if self._rid is not None:
            self._backend.cancel(self._rid)

    # ── loop ──────────────────────────────────────────────────────────────────

    def _next(self) -> None:
        project = self._ctrl.project
        records = {r.path: r for r in project.images} if project else {}
        while not self._cancel and self._idx < len(self._images):
            path = self._images[self._idx]
            boxes = boxes_to_outline(self._ctrl.annotations_for(path), self._source.id,
                                     self._target.id)
            w, h = image_size(records.get(path))
            if not boxes or w <= 0 or h <= 0:
                self._advance(path)
                continue
            self._rid = self._backend.request(
                "sam.boxes", {"model": self._model, "image": path,
                              "boxes": [pixel_box(b, w, h) for b in boxes]},
                on_done=lambda r, p=path, b=boxes: self._on_reply(p, b, r))
            return
        self._finish()

    def _advance(self, path: str) -> None:
        self._idx += 1
        self.progress.emit(self._idx, len(self._images), Path(path).name)

    def _on_reply(self, path: str, boxes: list[Annotation], r: Reply) -> None:
        self._rid = None
        if not self._running:
            return
        if not r.ok:
            if r.error_type in _FATAL:
                if r.error_type == protocol.CANCELLED:
                    self._cancel = True
                else:
                    self.summary.fatal = r.message
                self._finish()
                return
            self.summary.failed += 1
            if len(self.summary.errors) < 5:
                self.summary.errors.append(f"{Path(path).name}: {r.message}")
        else:
            self._apply(path, boxes, r.result)
        self._advance(path)
        QTimer.singleShot(0, self._next)       # never recurse: thousands of images

    def _apply(self, path: str, boxes: list[Annotation], result: dict) -> None:
        project = self._ctrl.project
        opts = ConvertOptions(model_name=Path(self._model).name, simplify_px=self._simplify,
                              project_path=project.project_path if project else None,
                              image_stem=Path(path).stem, tool="sam")
        add, done = [], []
        for box, out in zip(boxes, result["results"]):
            if not out["polygons"]:
                self.summary.empty += 1
                continue
            det = {"cls": 0, "conf": out["score"], "box": out["box"], "polygons": out["polygons"]}
            if self._target.annotation_type == "obb":
                det["obb"] = min_area_rect(out["polygons"][0])
            anns = convert({"width": result["width"], "height": result["height"],
                            "task": "segment", "detections": [det]},
                           {0: self._target}, opts, report=ConvertReport())
            for ann in anns:
                ann.meta[FROM_BOX] = box.id
            if anns:
                add.extend(anns)
                done.append(box.id)
            else:
                self.summary.empty += 1
        remove = done if self._delete else []
        if add or remove:
            self._ctrl.apply_annotation_changes(path, add, remove, text="SAM: boxes → outlines")
            self.summary.changed_images.add(path)
        self.summary.images += 1
        self.summary.outlined += len(add)
        self.summary.removed += len(remove)

    def _finish(self) -> None:
        if not self._running:
            return
        self._running = False
        self.summary.cancelled = self._cancel
        self.summary.seconds = round(time.monotonic() - self._t0, 1)
        others = self.summary.changed_images - {self._ctrl.current_image}
        if others and self._ctrl.project is not None:
            self._ctrl.project_changed.emit(self._ctrl.project)    # refresh the ✓ marks
        self.finished.emit(self.summary)
