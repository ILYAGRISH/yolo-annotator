"""CocoExporter — COCO instance JSON format.

Output layout:
  <output_dir>/
    annotations/
      instances_<split>.json   (one per split)
    images/
      <split>/                 (if copy_images=True)

Supported annotation types:
  SEGMENT / POLYLINE  → segmentation (flat polygon in pixels)
  BBOX                → bbox [x, y, w, h]
  OBB                 → 4 rotated corners as segmentation polygon

Attributes are exported as an extra "attributes" field on each annotation.
source_geometry and tool_params are never written to output.
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


def _ann_to_coco(ann: Annotation, img_id: int, ann_id: int,
                 w: int, h: int, project: Project) -> dict | None:
    """Convert one Annotation to a COCO annotation dict, or None to skip."""
    t = ann.ann_type
    base: dict = {
        "id": ann_id,
        "image_id": img_id,
        "category_id": ann.class_id,
        "iscrowd": 0,
    }

    if t in (AnnotationType.SEGMENT, AnnotationType.POLYLINE):
        pts = ann.data.get("points", [])
        if not pts:
            return None
        flat = [v for x, y in pts
                for v in (round(x * w, 2), round(y * h, 2))]
        base["segmentation"] = [flat]
        xs = [p[0] * w for p in pts]
        ys = [p[1] * h for p in pts]
        bx, by = min(xs), min(ys)
        bw, bh = max(xs) - bx, max(ys) - by
        base["bbox"] = [round(bx, 2), round(by, 2),
                        round(bw, 2), round(bh, 2)]
        base["area"] = round(bw * bh, 2)

    elif t == AnnotationType.BBOX:
        d = ann.data
        bx, by = d["x"] * w, d["y"] * h
        bw, bh = d["w"] * w, d["h"] * h
        base["segmentation"] = []
        base["bbox"] = [round(bx, 2), round(by, 2),
                        round(bw, 2), round(bh, 2)]
        base["area"] = round(bw * bh, 2)

    elif t == AnnotationType.OBB:
        d = ann.data
        cx, cy = d["cx"] * w, d["cy"] * h
        hw, hh = d["w"] * w / 2, d["h"] * h / 2
        rad = math.radians(d.get("angle", 0.0))
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        rotated = [
            (cx + dx * cos_a - dy * sin_a,
             cy + dx * sin_a + dy * cos_a)
            for dx, dy in corners
        ]
        flat = [v for rx, ry in rotated
                for v in (round(rx, 2), round(ry, 2))]
        base["segmentation"] = [flat]
        xs = [p[0] for p in rotated]
        ys = [p[1] for p in rotated]
        bx, by = min(xs), min(ys)
        bw, bh = max(xs) - bx, max(ys) - by
        base["bbox"] = [round(bx, 2), round(by, 2),
                        round(bw, 2), round(bh, 2)]
        base["area"] = round(bw * bh, 2)

    else:
        return None

    # Attributes — included in COCO (unlike YOLO)
    cls = project.get_class(ann.class_id)
    if cls and cls.attributes:
        attr_vals = ann.data.get("attributes", {})
        if attr_vals:
            base["attributes"] = attr_vals

    return base


class CocoExporter(BaseExporter):

    @property
    def name(self) -> str:
        return "COCO Instances"

    @property
    def file_extension(self) -> str:
        return ".json"

    def export(self, project: Project, output_dir: Path, **kwargs) -> None:
        all_annotations: dict = kwargs.get("all_annotations", {})
        copy_images: bool = kwargs.get("copy_images", True)

        output_dir = Path(output_dir)
        ann_dir = output_dir / "annotations"
        ann_dir.mkdir(parents=True, exist_ok=True)

        categories = [
            {"id": cls.id, "name": cls.name, "supercategory": ""}
            for cls in sorted(project.classes, key=lambda c: c.id)
        ]

        # Group images by split
        splits: dict[str, list] = {}
        for img_rec in project.images:
            splits.setdefault(img_rec.split or "train", []).append(img_rec)

        for split, img_records in splits.items():
            coco_images: list[dict] = []
            coco_anns: list[dict] = []
            ann_id = 0

            for img_id, img_rec in enumerate(img_records):
                img_path = Path(img_rec.path)
                iw, ih = _image_size(img_rec, img_path)
                coco_images.append({
                    "id": img_id,
                    "file_name": img_path.name,
                    "width": iw,
                    "height": ih,
                })

                for ann in all_annotations.get(img_rec.path, []):
                    coco_ann = _ann_to_coco(ann, img_id, ann_id,
                                            iw, ih, project)
                    if coco_ann is not None:
                        coco_anns.append(coco_ann)
                        ann_id += 1

                if copy_images and img_path.exists():
                    img_out = output_dir / "images" / split
                    img_out.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(img_path, img_out / img_path.name)

            coco_data = {
                "info": {"description": project.name, "version": "1.0"},
                "licenses": [],
                "categories": categories,
                "images": coco_images,
                "annotations": coco_anns,
            }
            (ann_dir / f"instances_{split}.json").write_text(
                json.dumps(coco_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
