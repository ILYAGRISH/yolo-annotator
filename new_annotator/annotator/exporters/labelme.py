"""LabelMe JSON exporter (labelme v5 format).

Output layout:
  <output_dir>/
    train/
      image001.jpg   (if copy_images)
      image001.json
    val/
      ...

Supported annotation types:
  BBOX      → "rectangle"  [[xmin,ymin],[xmax,ymax]] in pixels
  SEGMENT   → "polygon"    [[x,y],...] in pixels
  POLYLINE  → "linestrip"  [[x,y],...] in pixels
  OBB       → "polygon"    4 rotated corners in pixels
  POINT     → "point"      [[x,y]] in pixels
  MASK      → "polygon"    stored polygon contour in pixels
  POSE      → one "point" per visible keypoint  (label = "class_kptname")
  CLASSIFY  → skipped (no geometry)
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

from annotator.domain.annotation import Annotation, AnnotationType
from annotator.domain.project import Project
from annotator.exporters.base import BaseExporter


def _image_size(img_rec, img_path: Path) -> tuple[int, int]:
    if img_rec.width > 0 and img_rec.height > 0:
        return img_rec.width, img_rec.height
    try:
        from PIL import Image as PILImage
        with PILImage.open(img_path) as im:
            return im.width, im.height
    except Exception:
        return 0, 0


def _ann_to_shapes(ann: Annotation, w: int, h: int, project: Project) -> list[dict]:
    """Convert one Annotation to a list of LabelMe shape dicts."""
    cls = project.get_class(ann.class_id)
    label = cls.name if cls else str(ann.class_id)
    t = ann.ann_type

    if t == AnnotationType.CLASSIFY:
        return []

    if t == AnnotationType.BBOX:
        d = ann.data
        xmin, ymin = d["x"] * w, d["y"] * h
        xmax, ymax = (d["x"] + d["w"]) * w, (d["y"] + d["h"]) * h
        return [_shape(label, "rectangle",
                       [[round(xmin, 2), round(ymin, 2)],
                        [round(xmax, 2), round(ymax, 2)]])]

    if t == AnnotationType.SEGMENT:
        pts = ann.data.get("points", [])
        if len(pts) < 3:
            return []
        return [_shape(label, "polygon",
                       [[round(x * w, 2), round(y * h, 2)] for x, y in pts])]

    if t == AnnotationType.POLYLINE:
        pts = ann.data.get("points", [])
        if len(pts) < 2:
            return []
        return [_shape(label, "linestrip",
                       [[round(x * w, 2), round(y * h, 2)] for x, y in pts])]

    if t == AnnotationType.OBB:
        d = ann.data
        cx, cy = d["cx"] * w, d["cy"] * h
        hw, hh = d["w"] * w / 2, d["h"] * h / 2
        rad = math.radians(d.get("angle_deg", 0.0))
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        rotated = [
            (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)
            for dx, dy in corners
        ]
        return [_shape(label, "polygon",
                       [[round(rx, 2), round(ry, 2)] for rx, ry in rotated])]

    if t == AnnotationType.POINT:
        d = ann.data
        return [_shape(label, "point",
                       [[round(d["x"] * w, 2), round(d["y"] * h, 2)]])]

    if t == AnnotationType.POSE:
        kpts = ann.data.get("keypoints", [])
        shapes = []
        for i, (kx, ky, vis) in enumerate(kpts):
            if vis <= 0:
                continue
            kname = (cls.skeleton[i].name
                     if cls and i < len(cls.skeleton) else str(i))
            shapes.append(_shape(f"{label}_{kname}", "point",
                                 [[round(kx * w, 2), round(ky * h, 2)]]))
        return shapes

    if t == AnnotationType.MASK:
        pts = ann.data.get("polygon", [])
        if len(pts) < 3:
            return []
        return [_shape(label, "polygon",
                       [[round(x * w, 2), round(y * h, 2)] for x, y in pts])]

    return []


def _shape(label: str, shape_type: str, points: list) -> dict:
    return {"label": label, "points": points,
            "group_id": None, "shape_type": shape_type, "flags": {}}


class LabelMeExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "LabelMe JSON"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, project: Project, output_dir: Path, **kwargs) -> None:
        all_annotations: dict = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        output_dir = Path(output_dir)

        for img_rec in project.images:
            img_path = Path(img_rec.path)
            iw, ih = _image_size(img_rec, img_path)
            split = img_rec.split or "train"
            out_split = output_dir / split
            out_split.mkdir(parents=True, exist_ok=True)

            anns = all_annotations.get(img_rec.path, [])
            shapes: list[dict] = []
            for ann in anns:
                shapes.extend(_ann_to_shapes(ann, iw, ih, project))

            lm = {
                "version": "5.0.1",
                "flags": {},
                "shapes": shapes,
                "imagePath": img_path.name,
                "imageData": None,
                "imageHeight": ih,
                "imageWidth": iw,
            }
            (out_split / (img_path.stem + ".json")).write_text(
                json.dumps(lm, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            if copy_images and img_path.exists():
                shutil.copy2(img_path, out_split / img_path.name)
