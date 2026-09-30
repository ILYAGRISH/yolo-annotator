"""Pascal VOC XML exporter.

Output layout:
  <output_dir>/
    Annotations/<stem>.xml       — one XML per image
    JPEGImages/<stem>.<ext>      — copied images (if copy_images=True)
    ImageSets/Main/
      train.txt / val.txt / test.txt  — stem lists per split

Supported annotation types:
  BBOX                → <bndbox> in pixels
  SEGMENT / POLYLINE  → bounding box of polygon extents
  OBB                 → bounding box of rotated corners
  MASK                → bounding box from stored [cx,cy,w,h] field
  POSE / POINT / CLASSIFY → skipped
"""
from __future__ import annotations

import math
import shutil
import xml.etree.ElementTree as ET
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


def _bbox_pixels(ann: Annotation, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Return (xmin, ymin, xmax, ymax) in pixels, or None to skip."""
    t = ann.ann_type

    if t == AnnotationType.BBOX:
        d = ann.data
        xmin = d["x"] * w
        ymin = d["y"] * h
        xmax = (d["x"] + d["w"]) * w
        ymax = (d["y"] + d["h"]) * h
        return int(xmin), int(ymin), int(xmax), int(ymax)

    if t in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        pts = ann.data.get("points", [])
        if len(pts) < 2:
            return None
        xs = [p[0] * w for p in pts]
        ys = [p[1] * h for p in pts]
        return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))

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
        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]
        return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))

    if t == AnnotationType.MASK:
        b = ann.data.get("bbox")  # [cx, cy, w, h] normalized
        if b and len(b) == 4:
            cx, cy, bw, bh = b
            xmin = (cx - bw / 2) * w
            ymin = (cy - bh / 2) * h
            xmax = (cx + bw / 2) * w
            ymax = (cy + bh / 2) * h
            return int(xmin), int(ymin), int(xmax), int(ymax)

    return None


def _make_xml(img_path: Path, w: int, h: int,
              anns: list[Annotation], project: Project) -> str:
    root = ET.Element("annotation")
    ET.SubElement(root, "folder").text = "JPEGImages"
    ET.SubElement(root, "filename").text = img_path.name
    ET.SubElement(root, "path").text = str(img_path)
    src = ET.SubElement(root, "source")
    ET.SubElement(src, "database").text = "Unknown"
    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(w)
    ET.SubElement(size, "height").text = str(h)
    ET.SubElement(size, "depth").text = "3"
    ET.SubElement(root, "segmented").text = "0"

    for ann in anns:
        bbox = _bbox_pixels(ann, w, h)
        if bbox is None:
            continue
        xmin, ymin, xmax, ymax = bbox
        if xmin >= xmax or ymin >= ymax:
            continue
        cls = project.get_class(ann.class_id)
        name = cls.name if cls else str(ann.class_id)

        obj = ET.SubElement(root, "object")
        ET.SubElement(obj, "name").text = name
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = str(xmin)
        ET.SubElement(bndbox, "ymin").text = str(ymin)
        ET.SubElement(bndbox, "xmax").text = str(xmax)
        ET.SubElement(bndbox, "ymax").text = str(ymax)

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(
        root, encoding="unicode")


class PascalVocExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "Pascal VOC"

    @property
    def file_extension(self) -> str:
        return ".xml"

    def export(self, project: Project, output_dir: Path, **kwargs) -> None:
        all_annotations: dict = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        output_dir = Path(output_dir)
        ann_dir = output_dir / "Annotations"
        ann_dir.mkdir(parents=True, exist_ok=True)
        img_dir = output_dir / "JPEGImages"
        if copy_images:
            img_dir.mkdir(parents=True, exist_ok=True)
        sets_dir = output_dir / "ImageSets" / "Main"
        sets_dir.mkdir(parents=True, exist_ok=True)

        split_stems: dict[str, list[str]] = {}

        for img_rec in project.images:
            img_path = Path(img_rec.path)
            iw, ih = _image_size(img_rec, img_path)
            anns = all_annotations.get(img_rec.path, [])

            xml_content = _make_xml(img_path, iw, ih, anns, project)
            (ann_dir / (img_path.stem + ".xml")).write_text(
                xml_content, encoding="utf-8")

            if copy_images and img_path.exists():
                shutil.copy2(img_path, img_dir / img_path.name)

            split = img_rec.split or "train"
            split_stems.setdefault(split, []).append(img_path.stem)

        for split, stems in split_stems.items():
            (sets_dir / f"{split}.txt").write_text(
                "\n".join(stems), encoding="utf-8")
